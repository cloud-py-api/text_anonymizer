# SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""ExApp server providing TaskProcessing tasks and a Files action for detecting and redacting PII."""

import asyncio
import logging
import os
import posixpath
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from anonymizer import detect_pii, redact_text
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from nc_py_api import AsyncNextcloudApp, NextcloudApp, NextcloudException
from nc_py_api.ex_app import (
    AppAPIAuthMiddleware,
    LogLvl,
    anc_app,
    run_app,
    set_handlers,
)
from nc_py_api.ex_app.providers.task_processing import (
    ShapeDescriptor,
    ShapeType,
    TaskProcessingProvider,
    TaskType,
)
from nc_py_api.files import ActionFileInfo, ActionFileInfoEx

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_handlers(app, enabled_handler, trigger_handler=trigger_handler)
    if NextcloudApp().enabled_state:
        APP_ENABLED.set()
    worker = asyncio.create_task(process_tasks())
    yield
    SHUTDOWN.set()
    TRIGGER.set()
    await worker


APP = FastAPI(lifespan=lifespan)
APP.add_middleware(AppAPIAuthMiddleware)  # set global AppAPI authentication middleware
APP.mount("/img", StaticFiles(directory=Path(__file__).parent.parent / "img"), name="img")

DETECT_PII_TASK_TYPE = TaskType(
    id="text_anonymizer:detect_pii",
    name="Detect sensitive text",
    description="Check whether a text contains personally identifiable information (PII).",
    input_shape=[ShapeDescriptor(name="input", description="Text to check", shape_type=ShapeType.TEXT)],
    output_shape=[
        ShapeDescriptor(
            name="output",
            description="List of PII found in the text, or empty if none was found",
            shape_type=ShapeType.TEXT,
        )
    ],
)
DETECT_PII_PROVIDER = TaskProcessingProvider(
    id=DETECT_PII_TASK_TYPE.id,
    name="TextAnonymizer PII Detector",
    task_type=DETECT_PII_TASK_TYPE.id,
)

REDACT_PII_TASK_TYPE = TaskType(
    id="text_anonymizer:redact_pii",
    name="Redact sensitive text",
    description="Replace all personally identifiable information (PII) in a text with placeholders.",
    input_shape=[ShapeDescriptor(name="input", description="Text to redact", shape_type=ShapeType.TEXT)],
    output_shape=[ShapeDescriptor(name="output", description="Redacted text", shape_type=ShapeType.TEXT)],
)
REDACT_PII_PROVIDER = TaskProcessingProvider(
    id=REDACT_PII_TASK_TYPE.id,
    name="TextAnonymizer PII Redactor",
    task_type=REDACT_PII_TASK_TYPE.id,
)

TASK_PROCESSING_PROVIDERS = [
    (DETECT_PII_PROVIDER, DETECT_PII_TASK_TYPE),
    (REDACT_PII_PROVIDER, REDACT_PII_TASK_TYPE),
]
TASK_HANDLERS = {
    DETECT_PII_TASK_TYPE.id: detect_pii,
    REDACT_PII_TASK_TYPE.id: redact_text,
}

# Set by `enabled_handler`, which runs in a worker thread.
APP_ENABLED = threading.Event()
# Set when Nextcloud announces a new task (Nextcloud 33+) and on shutdown.
TRIGGER = asyncio.Event()
SHUTDOWN = asyncio.Event()
POLL_INTERVAL = 5
# Once Nextcloud has sent a trigger, polling is only a fallback for missed triggers.
POLL_INTERVAL_WITH_TRIGGER = 5 * 60
POLL_INTERVAL_ON_ERROR = 10


async def trigger_handler(_provider_id: str) -> None:
    TRIGGER.set()


async def wait_for_trigger(timeout: float) -> bool:
    """Wait until a trigger arrives or ``timeout`` seconds pass, and return whether a trigger arrived."""
    try:
        await asyncio.wait_for(TRIGGER.wait(), timeout)
    except TimeoutError:
        return False
    return True


async def process_task(nc: AsyncNextcloudApp, task: dict[str, Any]) -> None:
    loop = asyncio.get_running_loop()

    def on_progress(percent: float) -> None:
        # Wait for each update, as Nextcloud marks a task as running again if its progress arrives after its result.
        asyncio.run_coroutine_threadsafe(nc.providers.task_processing.set_progress(task["id"], percent), loop).result()

    try:
        handler = TASK_HANDLERS[task["type"]]
        # Presidio is CPU-bound, so it runs in a worker thread to keep the event loop responsive.
        output = await asyncio.to_thread(handler, task["input"]["input"], on_progress=on_progress)
    except Exception as e:
        await nc.log(LogLvl.ERROR, f"Failed to process task {task['id']}: {e}")
        await nc.providers.task_processing.report_result(
            task["id"], error_message=str(e), user_facing_error_message="The text could not be processed."
        )
        return
    await nc.providers.task_processing.report_result(task["id"], {"output": output})


async def process_tasks() -> None:
    """Fetch and process tasks for all providers one at a time until shutdown."""
    nc = AsyncNextcloudApp()
    provider_ids = [provider.id for provider, _ in TASK_PROCESSING_PROVIDERS]
    task_types = list(TASK_HANDLERS)
    poll_interval = POLL_INTERVAL
    while not SHUTDOWN.is_set():
        TRIGGER.clear()
        if not APP_ENABLED.is_set():
            await wait_for_trigger(POLL_INTERVAL)
            continue
        try:
            response = await nc.providers.task_processing.next_task(provider_ids, task_types)
            if response:
                await process_task(nc, response["task"])
            elif await wait_for_trigger(poll_interval):
                poll_interval = POLL_INTERVAL_WITH_TRIGGER
        except Exception:
            LOGGER.exception("Failed to fetch or process the next task")
            await wait_for_trigger(POLL_INTERVAL_ON_ERROR)


REDACT_FILE_ACTION_NAME = "redact_pii_file"
REDACT_FILE_ACTION_HANDLER = "/redact_file"
# AppAPI matches by substring, so "text/" matches all text/* types but not e.g. ODT documents.
REDACT_FILE_ACTION_MIME = "text/"
# AppAPI passes an unset default action to the Files app as `null`, which the Files app treats as a default action.
# Ordering after the built-in "Download" action (30) keeps any real default action, e.g. "View", ahead of this one.
REDACT_FILE_ACTION_ORDER = 31
REDACTED_SUFFIX_RE = re.compile(r" \(redacted(?: \d+)?\)$")


def path_exists(nc: NextcloudApp, user_path: str) -> bool:
    try:
        nc.files.by_path(user_path)
    except NextcloudException as e:
        # WebDAV lookups raise a plain NextcloudException for a missing path, not NextcloudExceptionNotFound.
        if e.status_code == 404:
            return False
        raise
    return True


def redacted_copy_path(nc: NextcloudApp, user_path: str) -> str:
    """Return a free path next to ``user_path`` for the redacted copy, e.g. ``notes (redacted).txt``.

    Redacting an existing copy such as ``notes (redacted).txt`` yields ``notes (redacted 2).txt``.
    """
    directory, name = posixpath.split(user_path)
    stem, ext = posixpath.splitext(name)
    stem = REDACTED_SUFFIX_RE.sub("", stem)
    candidate = posixpath.join(directory, f"{stem} (redacted){ext}")
    counter = 2
    while path_exists(nc, candidate):
        candidate = posixpath.join(directory, f"{stem} (redacted {counter}){ext}")
        counter += 1
    return candidate


def redact_file(nc: NextcloudApp, file_info: ActionFileInfo) -> None:
    """Write a redacted copy of the file next to the original and notify the user of the outcome."""
    try:
        node = nc.files.by_id(file_info.fileId)
        if node is None or node.is_dir:
            nc.notifications.create(f"Could not redact {file_info.name}", "The file could not be found.")
            return
        try:
            text = nc.files.download(node).decode("utf-8")
        except UnicodeDecodeError:
            nc.notifications.create(f"Could not redact {node.name}", "The file is not a UTF-8 encoded text file.")
            return
        copy_path = redacted_copy_path(nc, node.user_path)
        nc.files.upload(copy_path, redact_text(text))
        nc.notifications.create(f"Redacted copy of {node.name} saved as {posixpath.basename(copy_path)}")
    except Exception as e:
        nc.log(LogLvl.ERROR, f"Failed to redact file {file_info.fileId}: {e}")
        nc.notifications.create(f"Could not redact {file_info.name}", "An unexpected error occurred.")


def redact_files(user_id: str, files: list[ActionFileInfo]) -> None:
    nc = NextcloudApp()
    nc.set_user(user_id)
    for file_info in files:
        redact_file(nc, file_info)


@APP.post(REDACT_FILE_ACTION_HANDLER)
async def redact_file_action(
    files: ActionFileInfoEx,
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)],
    background_tasks: BackgroundTasks,
):
    # Files are accessed as the user who triggered the action, so Nextcloud enforces their permissions.
    background_tasks.add_task(redact_files, await nc.user, files.files)
    return JSONResponse(content={})


def enabled_handler(enabled: bool, nc: NextcloudApp) -> str:
    # This will be called each time application is `enabled` or `disabled`
    # NOTE: `user` is unavailable on this step, so all NC API calls that require it will fail as unauthorized.
    try:
        if enabled:
            for provider, task_type in TASK_PROCESSING_PROVIDERS:
                nc.providers.task_processing.register(provider, task_type)
            nc.ui.files_dropdown_menu.register_ex(
                REDACT_FILE_ACTION_NAME,
                "Redact text",
                REDACT_FILE_ACTION_HANDLER,
                mime=REDACT_FILE_ACTION_MIME,
                icon="img/icon.svg",
                order=REDACT_FILE_ACTION_ORDER,
            )
            APP_ENABLED.set()
        else:
            APP_ENABLED.clear()
            for provider, _ in TASK_PROCESSING_PROVIDERS:
                nc.providers.task_processing.unregister(provider.id)
            nc.ui.files_dropdown_menu.unregister(REDACT_FILE_ACTION_NAME)
    except Exception as e:
        nc.log(LogLvl.ERROR, f"Failed to {'register' if enabled else 'unregister'} app features: {e}")
        # A non-empty string is shown to the Nextcloud administrator as an error.
        return str(e)
    return ""


if __name__ == "__main__":
    # Wrapper around `uvicorn.run`.
    # You are free to call it directly, with just using the `APP_HOST` and `APP_PORT` variables from the environment.
    os.chdir(Path(__file__).parent)
    run_app("main:APP", log_level="trace")
