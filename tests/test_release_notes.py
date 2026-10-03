#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.github/scripts/release_notes.py — опис GitHub Release з CHANGELOG.md (v3.0.19).

Реліз зазвичай охоплює кілька patch-версій (кожен коміт бампає версію),
тому опис — усі записи між попереднім релізним тегом і поточною версією.
Опис, написаний вручну у формі релізу, пайплайн не перезаписує.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_SCRIPT = ROOT / ".github" / "scripts" / "release_notes.py"
if not _SCRIPT.exists():
    # Розпакований sdist (CI-джоба package) не містить .github/ — і не має
    pytest.skip("release tooling is not part of the sdist", allow_module_level=True)
_spec = importlib.util.spec_from_file_location("release_notes", _SCRIPT)
assert _spec and _spec.loader
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

from datamasking._version import __version__  # noqa: E402

SAMPLE = """# Changelog

## [1.2.0] - 2026-10
### Fixed
- three

## [1.1.1] - 2026-09
### Changed
- two

## [1.1.0] - 2026-09
- one

## [Unreleased]
- ignored
"""


def _write(tmp_path, text=SAMPLE):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


class TestRealChangelog:
    def test_current_version_has_changelog_entry(self):
        # Gate на кожен push: інакше реліз зупиниться на етапі збірки
        entries = rn.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        assert any(v == __version__ for v, _, _ in entries), \
            f"CHANGELOG.md has no '## [{__version__}]' entry"

    def test_newest_entry_is_current_version(self):
        entries = rn.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        assert entries[0][0] == __version__


class TestSelection:
    def test_range_since_previous_tag(self, tmp_path, capsys):
        assert rn.main(["--version", "1.2.0", "--since", "v1.1.0", "--changelog", _write(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "### 1.2.0" in out and "### 1.1.1" in out
        assert "- one" not in out and "ignored" not in out
        assert "#### Fixed" in out  # заголовки записів — на рівень нижче
        assert out.index("### 1.2.0") < out.index("### 1.1.1")  # новіші зверху
        assert "versions **1.1.1 – 1.2.0**" in out

    def test_single_version_without_since(self, tmp_path, capsys):
        assert rn.main(["--version", "v1.1.1", "--changelog", _write(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert out.startswith("### Changed\n- two")
        assert "1.2.0" not in out

    def test_since_not_older_falls_back_to_single(self, tmp_path, capsys):
        assert rn.main(["--version", "1.1.1", "--since", "v1.2.0", "--changelog", _write(tmp_path)]) == 0
        assert "- two" in capsys.readouterr().out

    def test_missing_entry_fails(self, tmp_path, capsys):
        assert rn.main(["--version", "9.9.9", "--since", "v1.1.0", "--changelog", _write(tmp_path)]) == 1
        assert "no entry" in capsys.readouterr().err

    def test_links_and_marker(self, tmp_path, capsys):
        rn.main(["--version", "1.2.0", "--since", "v1.1.0", "--repo", "o/r", "--changelog", _write(tmp_path)])
        out = capsys.readouterr().out
        assert "releases/download/v1.2.0/data_masking-1.2.0-py3-none-any.whl" in out
        assert "data-masking-1.2.0-windows-x64.zip" in out
        assert "https://github.com/o/r/compare/v1.1.0...v1.2.0" in out
        assert "sha256sum -c SHA256SUMS" in out
        assert "gh attestation verify data-masking-1.2.0-windows-x64.zip --repo o/r" in out
        assert out.rstrip().endswith(rn.MARKER)

    def test_output_file(self, tmp_path):
        out = tmp_path / "notes.md"
        assert rn.main(["--version", "1.2.0", "--changelog", _write(tmp_path), "--output", str(out)]) == 0
        assert "- three" in out.read_text(encoding="utf-8")


class TestReplaceable:
    @pytest.mark.parametrize("body", [
        "",
        "   \n",
        "**Full Changelog**: https://github.com/o/r/compare/v1...v2",
        "## What's Changed\n* Fix by @u in https://github.com/o/r/pull/1\n\n\n"
        "**Full Changelog**: https://github.com/o/r/compare/v1...v2\n",
        "anything\n" + rn.MARKER,
    ])
    def test_generated_or_empty_is_replaced(self, body):
        assert rn.is_replaceable(body)

    @pytest.mark.parametrize("body", [
        "## Highlights\n- hand-written\n\n**Full Changelog**: https://github.com/o/r/compare/v1...v2",
        "Short note by the maintainer.",
    ])
    def test_hand_written_is_kept(self, body):
        assert not rn.is_replaceable(body)

    def test_cli_exit_codes(self, tmp_path):
        f = tmp_path / "body.md"
        f.write_text("", encoding="utf-8")
        assert rn.main(["--check-replaceable", str(f)]) == 0
        f.write_text("My own text", encoding="utf-8")
        assert rn.main(["--check-replaceable", str(f)]) == 3
