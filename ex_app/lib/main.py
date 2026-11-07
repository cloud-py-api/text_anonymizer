# SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Simplest example."""

import asyncio
import datetime
import os
import posixpath
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from anonymizer import redact_text
from fastapi import BackgroundTasks, Depends, FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from nc_py_api import AsyncNextcloudApp, NextcloudApp, NextcloudException
from nc_py_api.ex_app import (
    AppAPIAuthMiddleware,
    LogLvl,
    anc_app,
    nc_app,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_handlers(app, enabled_handler)
    yield


APP = FastAPI(lifespan=lifespan)
APP.add_middleware(AppAPIAuthMiddleware)  # set global AppAPI authentication middleware

# Build the WebSocket URL dynamically using the NextcloudApp configuration.
WS_URL = NextcloudApp().app_cfg.endpoint + "/exapps/app-skeleton-python/ws"

# HTML content served at the root URL.
# This page opens a WebSocket connection, displays incoming messages,
# and allows you to send messages back to the server.
HTML = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>FastAPI WebSocket Demo</title>
    </head>
    <body>
        <h1>FastAPI WebSocket Demo</h1>
        <p>Type a message and click "Send", or simply watch the server send cool updates!</p>
        <input type="text" id="messageText" placeholder="Enter message here...">
        <button onclick="sendMessage()">Send</button>
        <ul id="messages"></ul>
        <script>
            // Create a WebSocket connection using the dynamic URL.
            var ws = new WebSocket("{WS_URL}");

            // When a message is received from the server, add it to the list.
            ws.onmessage = function(event) {{
                var messages = document.getElementById('messages');
                var message = document.createElement('li');
                message.textContent = event.data;
                messages.appendChild(message);
            }};

            // Function to send a message to the server.
            function sendMessage() {{
                var input = document.getElementById("messageText");
                ws.send(input.value);
                input.value = '';
            }}
        </script>
    </body>
</html>
"""


@APP.get("/")
async def get():
    # WebSockets works only in Nextcloud 32 when `HaRP` is used instead of `DSP`
    return HTMLResponse(HTML)


@APP.get("/public")
async def public_get(request: Request):
    print(f"public_get: {request.headers}", flush=True)
    return "Public page!"


@APP.get("/user")
async def user_get(request: Request, status: int = 200):
    print(f"user_get: {request.headers}", flush=True)
    return JSONResponse(content="Page for the registered users only!", status_code=status)


@APP.get("/admin")
async def admin_get(request: Request):
    print(f"admin_get: {request.headers}", flush=True)
    return "Admin page!"


@APP.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    nc: Annotated[NextcloudApp, Depends(nc_app)],
):
    # WebSockets works only in Nextcloud 32 when `HaRP` is used instead of `DSP`
    print(nc.user)  # if you need user_id that initiated WebSocket connection
    print(f"websocket_endpoint: {websocket.headers}", flush=True)
    await websocket.accept()

    # This background task sends a periodic message (the current time) every 2 seconds.
    async def send_periodic_messages():
        while True:
            try:
                message = f"Server time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                await websocket.send_text(message)
                await asyncio.sleep(2)
            except Exception as exc:
                NextcloudApp().log(LogLvl.ERROR, str(exc))
                break

    # Start the periodic sender in the background.
    periodic_task = asyncio.create_task(send_periodic_messages())

    try:
        # Continuously listen for messages from the client.
        while True:
            data = await websocket.receive_text()
            # Echo the received message back to the client.
            await websocket.send_text(f"Echo: {data}")
    except Exception as e:
        NextcloudApp().log(LogLvl.ERROR, str(e))
    finally:
        # Cancel the periodic message task when the connection is closed.
        periodic_task.cancel()


DETECT_PII_TASK_TYPE = TaskType(
    id="core:text2text:detect_pii",
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
    id="text_anonymizer:detect_pii",
    name="TextAnonymizer PII Detector",
    task_type=DETECT_PII_TASK_TYPE.id,
)

REDACT_PII_TASK_TYPE = TaskType(
    id="core:text2text:redact_pii",
    name="Redact sensitive text",
    description="Replace all personally identifiable information (PII) in a text with placeholders.",
    input_shape=[ShapeDescriptor(name="input", description="Text to redact", shape_type=ShapeType.TEXT)],
    output_shape=[ShapeDescriptor(name="output", description="Redacted text", shape_type=ShapeType.TEXT)],
)
REDACT_PII_PROVIDER = TaskProcessingProvider(
    id="text_anonymizer:redact_pii",
    name="TextAnonymizer PII Redactor",
    task_type=REDACT_PII_TASK_TYPE.id,
)

TASK_PROCESSING_PROVIDERS = [
    (DETECT_PII_PROVIDER, DETECT_PII_TASK_TYPE),
    (REDACT_PII_PROVIDER, REDACT_PII_TASK_TYPE),
]

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
        else:
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
