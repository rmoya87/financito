#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "data:")

errors: list[str] = []

for md in sorted([ROOT / "README.md", *ROOT.joinpath("docs").rglob("*.md")]):
    text = md.read_text(encoding="utf-8")
    for raw in LINK.findall(text):
        target = raw.strip().split()[0].strip("<>")
        if not target or target.startswith(SKIP_PREFIXES):
            continue
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not target:
            continue
        resolved = (md.parent / target).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            errors.append(f"{md.relative_to(ROOT)}: link escapes repo: {raw}")
            continue
        if not resolved.exists():
            errors.append(f"{md.relative_to(ROOT)}: missing target: {raw}")

if errors:
    print("Broken internal Markdown links:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("Markdown links OK")
