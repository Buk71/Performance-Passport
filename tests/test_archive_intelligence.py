from __future__ import annotations

import datetime as dt

import core.archive_intelligence as archive


def test_archive_constants_are_locked():
    assert archive.RECENT_DAYS == 90
    assert archive.CURRENT_DAYS == 365


def test_archive_summary_key_is_persistent_and_separate():
    assert archive.ARCHIVE_KEY == "archive.history_summary.v1"


def test_archive_summary_uses_race_source_version():
    source = __import__("pathlib").Path(archive.__file__).read_text(encoding="utf-8")
    assert "get_race_intelligence_version" in source
    assert 'horizon="archive"' in source


def test_archive_summary_does_not_replace_verified_pb_logic():
    source = __import__("pathlib").Path(archive.__file__).read_text(encoding="utf-8")
    assert "supporting archive" in source.lower()
    assert "not replacements for verified PB detection" in source
