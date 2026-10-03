#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release notes from CHANGELOG.md (stdlib only).

Збирає опис GitHub Release з усіх записів CHANGELOG.md між попереднім
релізним тегом (не включно) і поточною версією (включно): реліз зазвичай
охоплює кілька patch-версій (кожен коміт бампає версію), а теги ставляться
рідше. Користувачу лишається тільки поставити тег — текст пише пайплайн.

    python .github/scripts/release_notes.py --version 3.0.18 --since v3.0.16 \
        --repo click0/data-masking --output release-notes.md

Без --since — лише запис поточної версії. Якщо для --version у CHANGELOG
немає запису, скрипт завершується з кодом 1 (реліз не публікується з
порожнім описом).
"""
import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

MARKER = "<!-- release-notes: generated from CHANGELOG.md -->"

HEADING_RE = re.compile(r"^## \[(?P<ver>[^\]]+)\](?:\s*-\s*(?P<date>.+))?\s*$")


def version_key(ver: str) -> Optional[Tuple[int, ...]]:
    """'v3.0.18' / '3.0.18' → (3, 0, 18); нечислові ('Unreleased') → None."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)", ver.strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def parse_changelog(text: str) -> List[Tuple[str, str, str]]:
    """[(версія, дата, тіло)] у порядку файлу (новіші зверху)."""
    entries: List[Tuple[str, str, str]] = []
    current: Optional[Tuple[str, str]] = None
    body: List[str] = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if current:
                entries.append((current[0], current[1], "\n".join(body).strip()))
            current = (m.group("ver").strip(), (m.group("date") or "").strip())
            body = []
        elif current:
            body.append(line)
    if current:
        entries.append((current[0], current[1], "\n".join(body).strip()))
    return entries


def select(entries, version: str, since: Optional[str]):
    """Записи з since < версія ≤ version (since=None → лише version)."""
    top = version_key(version)
    low = version_key(since) if since else None
    if top is None:
        raise ValueError(f"not a version: {version!r}")
    chosen = []
    for ver, date, body in entries:
        key = version_key(ver)
        if key is None:
            continue
        if low is None:
            if key == top:
                chosen.append((ver, date, body))
        elif low < key <= top:
            chosen.append((ver, date, body))
    return chosen


def _demote(body: str) -> str:
    """Заголовки записів (### Fixed …) — на рівень нижче, під ### <версія>."""
    return re.sub(r"^(#{3,5}) ", r"#\1 ", body, flags=re.M)


def render(version: str, chosen, since: Optional[str], repo: Optional[str]) -> str:
    out: List[str] = []
    if len(chosen) > 1:
        oldest, newest = chosen[-1][0], chosen[0][0]
        out.append(f"This release includes versions **{oldest} – {newest}** "
                   f"(changes since {since}).")
        out.append("")
    for ver, date, body in chosen:
        if len(chosen) > 1:
            out.append(f"### {ver}" + (f" ({date})" if date else ""))
            out.append("")
            out.append(_demote(body))
        else:
            out.append(body)
        out.append("")
    out.append("---")
    out.append("")
    out.append("### Installation")
    out.append("")
    out.append(f"- **Windows, no Python:** `data-masking-{version}-windows-x64.zip` — "
               "unpack and run `data_masking.exe` / `unmask_data.exe`.")
    if repo:
        wheel = (f"https://github.com/{repo}/releases/download/v{version}/"
                 f"data_masking-{version}-py3-none-any.whl")
        out.append("- **pip:**")
        out.append("")
        out.append("  ```bash")
        out.append(f'  pip install "data-masking[full] @ {wheel}"')
        out.append("  ```")
        out.append("")
        out.append(f"Full guide: https://github.com/{repo}/blob/v{version}/docs/INSTALL.md")
        out.append("")
        out.append("### Verify the download")
        out.append("")
        out.append("`SHA256SUMS` covers every file; each file also carries a GitHub build-provenance "
                   "attestation (which commit and workflow built it):")
        out.append("")
        out.append("```bash")
        out.append("sha256sum -c SHA256SUMS --ignore-missing")
        out.append(f"gh attestation verify data-masking-{version}-windows-x64.zip --repo {repo}")
        out.append("```")
        if since:
            out.append("")
            out.append(f"**Full Changelog**: https://github.com/{repo}/compare/{since}...v{version}")
    out.append("")
    out.append(MARKER)
    return "\n".join(out).rstrip() + "\n"


def is_replaceable(body: str) -> bool:
    """Чи можна перезаписати наявний опис релізу.

    Так — якщо він порожній, згенерований GitHub у формі релізу («What's
    Changed» / лише «**Full Changelog**: …») або цим скриптом (MARKER).
    Текст, написаний вручну, не чіпаємо.
    """
    text = (body or "").strip()
    if not text or MARKER in text:
        return True
    return re.fullmatch(r"(## What's Changed\s.*?)?(\*\*Full Changelog\*\*: \S+)?\s*",
                        text, flags=re.S) is not None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--version", help="release version, e.g. 3.0.18")
    ap.add_argument("--since", help="previous release tag, e.g. v3.0.16 (exclusive)")
    ap.add_argument("--changelog", default="CHANGELOG.md")
    ap.add_argument("--repo", help="owner/name for links")
    ap.add_argument("--output", help="write here instead of stdout")
    ap.add_argument("--check-replaceable", metavar="BODY_FILE",
                    help="exit 0 if the release body in BODY_FILE may be replaced, 3 if hand-written")
    args = ap.parse_args(argv)

    if args.check_replaceable:
        body = Path(args.check_replaceable).read_text(encoding="utf-8")
        return 0 if is_replaceable(body) else 3

    if not args.version:
        ap.error("--version is required")
    text = Path(args.changelog).read_text(encoding="utf-8")
    version = args.version.lstrip("v")
    since = args.since or None
    since_key, version_key_ = (version_key(since) if since else None), version_key(version)
    if version_key_ is None:
        print(f"error: not a version: {args.version!r}", file=sys.stderr)
        return 2
    if since_key is not None and since_key >= version_key_:
        since = None  # перший реліз або тег поза послідовністю — лише поточна версія
    chosen = select(parse_changelog(text), version, since)
    if not any(version_key(v) == version_key(version) for v, _, _ in chosen):
        print(f"error: CHANGELOG has no entry '## [{version}]'", file=sys.stderr)
        return 1

    notes = render(version, chosen, since, args.repo)
    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")
    else:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
