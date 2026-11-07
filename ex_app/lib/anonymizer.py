# SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""PII detection and redaction using Presidio."""

import threading

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

_LOCK = threading.Lock()
_ENGINES: tuple[AnalyzerEngine, AnonymizerEngine] | None = None
_KEEP_OPERATORS = {"DEFAULT": OperatorConfig("keep")}


def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Create the Presidio engines on first use, as loading the spaCy model takes several seconds."""
    global _ENGINES
    with _LOCK:
        if _ENGINES is None:
            _ENGINES = (AnalyzerEngine(), AnonymizerEngine())
        return _ENGINES


def detect_pii(text: str, language: str = "en") -> str:
    """List each distinct PII entity in ``text`` as a ``TYPE: value`` line, in order of first appearance.

    Overlapping entities are resolved the same way as in :func:`redact_text`, so the list matches what would be
    redacted. Returns an empty string if no PII was found.
    """
    analyzer, anonymizer = _get_engines()
    results = analyzer.analyze(text=text, language=language)
    items = anonymizer.anonymize(text=text, analyzer_results=results, operators=_KEEP_OPERATORS).items
    entities = dict.fromkeys((item.entity_type, item.text) for item in sorted(items, key=lambda item: item.start))
    return "\n".join(f"{entity_type}: {value}" for entity_type, value in entities)


def redact_text(text: str, language: str = "en") -> str:
    """Replace every PII entity in ``text`` with a placeholder naming its type, e.g. ``<PERSON>``."""
    analyzer, anonymizer = _get_engines()
    results = analyzer.analyze(text=text, language=language)
    return anonymizer.anonymize(text=text, analyzer_results=results).text
