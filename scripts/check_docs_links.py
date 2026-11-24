#!/usr/bin/env python3
"""Check relative Markdown links in repository documentation (read-only/offline)."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

LINK = re.compile(r'(?<!!)\[[^\]]+\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]+")?\)')
REFERENCE = re.compile(r'(?m)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)')
FENCE = re.compile(r'(?s)\x60{3}.*?\x60{3}')


def markdown_files(repo: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            capture_output=True, check=True, timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return sorted(repo.rglob("*.md"))
    return [
        repo / Path(name.decode("utf-8"))
        for name in result.stdout.split(b"\0")
        if name and name.lower().endswith(b".md")
    ]


def check(repo: Path) -> list[str]:
    issues: list[str] = []
    for document in markdown_files(repo):
        if not document.is_file():
            continue
        try:
            data = document.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as error:
            issues.append(f"{document.relative_to(repo)}: unreadable: {error}")
            continue
        data = FENCE.sub("", data)
        links = [match.group(1) for match in LINK.finditer(data)]
        links += [match.group(1) for match in REFERENCE.finditer(data)]
        for raw in links:
            target = raw.strip("<>")
            if target.startswith(("#", "mailto:", "tel:", "data:")):
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or target.startswith("//"):
                continue
            path = unquote(parsed.path)
            if not path:
                continue
            resolved = (document.parent / path).resolve()
            if not resolved.is_relative_to(repo.resolve()):
                issues.append(
                    f"{document.relative_to(repo)}: path escapes repository: {target}"
                )
            elif not resolved.exists():
                issues.append(
                    f"{document.relative_to(repo)}: missing local link: {target}"
                )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo = args.root.resolve()
    errors = check(repo)
    for item in errors:
        print("[BROKEN] " + item)
    if errors:
        print(f"[FAIL] {len(errors)} broken local link(s)")
        return 1
    print("[OK] Markdown local links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
