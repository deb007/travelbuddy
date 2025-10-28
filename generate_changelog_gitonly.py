#!/usr/bin/env python3
"""
Pure Git-based changelog generator for CI use.
It finds merged PRs between the latest two tags, extracts titles and authors,
and prints an LLM-ready changelog prompt.

Usage:
    python generate_changelog_gitonly.py
"""

import subprocess
import re
from datetime import datetime


def run(cmd: list[str]) -> str:
    """Run a git command and return stdout."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    res.check_returncode()
    return res.stdout.strip()


def get_tags() -> list[str]:
    """Return all tags sorted by creation date."""
    tags = run(["git", "tag", "--sort=creatordate"]).splitlines()
    return [t for t in tags if t]


def get_commits(from_tag: str, to_tag: str) -> list[str]:
    """Return commits between two tags."""
    log_format = "%H|%an|%s"
    log_output = run(
        ["git", "log", f"{from_tag}..{to_tag}", f"--pretty=format:{log_format}"]
    )
    return log_output.splitlines()


def parse_pr_from_message(msg: str) -> tuple[int | None, str]:
    """
    Try to extract PR number and title from a commit message.
    Looks for patterns like 'Merge pull request #123 from ...'
    """
    merge_match = re.search(r"Merge pull request #(\d+)", msg)
    if merge_match:
        pr_number = int(merge_match.group(1))
        return pr_number, msg
    # fallback: look for (#123)
    inline_match = re.search(r"\(#(\d+)\)", msg)
    if inline_match:
        return int(inline_match.group(1)), msg
    return None, msg


def generate_changelog():
    tags = get_tags()
    if len(tags) < 2:
        print("⚠️ Not enough tags found to compare. Need at least 2.")
        return

    from_tag, to_tag = tags[-2], tags[-1]
    print(f"🔍 Generating changelog between {from_tag} → {to_tag}\n")

    commits = get_commits(from_tag, to_tag)
    pr_entries = {}
    for line in commits:
        sha, author, subject = line.split("|", 2)
        pr_number, _ = parse_pr_from_message(subject)
        if not pr_number:
            continue

        if pr_number not in pr_entries:
            pr_entries[pr_number] = {
                "titles": set(),
                "authors": set(),
            }
        pr_entries[pr_number]["titles"].add(subject)
        pr_entries[pr_number]["authors"].add(author)

    if not pr_entries:
        print("⚠️ No merged PRs found between these tags.")
        return

    print("🧾 PRs collected:\n")
    for pr_number, data in sorted(pr_entries.items()):
        title_preview = next(iter(data["titles"]))
        authors_str = ", ".join(sorted(data["authors"]))
        print(f"- #{pr_number} {title_preview} (Thanks {authors_str})")

    print("\n\n---\n")
    print("LLM Task: Please group the above PRs into:")
    print("""
1. 🚀 New Features
2. ⚙️ Improvements
3. 🐛 Bug Fixes
4. 🔒 Security Fixes
5. 🌐 Translations
6. 🧩 Others

Keep all PR numbers and authors. Improve phrasing but do not remove credits.
""")


if __name__ == "__main__":
    generate_changelog()
