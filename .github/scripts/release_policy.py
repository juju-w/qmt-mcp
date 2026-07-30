#!/usr/bin/env python3
"""Conventional Commit validation and deterministic SemVer release helpers."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

COMMIT_TYPES = (
    "feat",
    "fix",
    "docs",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "style",
    "revert",
)
HEADER_RE = re.compile(
    rf"^(?P<type>{'|'.join(COMMIT_TYPES)})"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?"
    r"(?P<breaking>!)?: (?P<description>\S.*)$"
)
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
BREAKING_RE = re.compile(r"(?m)^BREAKING[ -]CHANGE:\s+\S")


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str = ""


def parse_header(subject: str) -> re.Match[str] | None:
    return HEADER_RE.fullmatch(subject)


def validate_version(version: str) -> re.Match[str]:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError(f"invalid SemVer: {version}")
    return match


def increment_version(current: str, bump: str) -> str:
    match = validate_version(current)
    major = int(match["major"])
    minor = int(match["minor"])
    patch = int(match["patch"])
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "none":
        return f"{major}.{minor}.{patch}"
    raise ValueError(f"unknown bump: {bump}")


def release_bump(commits: list[Commit]) -> str:
    bump = "none"
    for commit in commits:
        match = parse_header(commit.subject)
        if not match:
            continue
        if match["type"] == "chore" and match["scope"] == "release":
            continue
        if match["breaking"] or BREAKING_RE.search(commit.body):
            return "major"
        if match["type"] == "feat":
            bump = "minor"
        elif bump == "none":
            bump = "patch"
    return bump


def git_commits(base: str | None, head: str) -> list[Commit]:
    revision = f"{base}..{head}" if base else head
    output = subprocess.check_output(
        ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", revision],
        text=True,
    )
    commits: list[Commit] = []
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, body = record.split("\x1f", 2)
        commits.append(Commit(sha=sha, subject=subject, body=body))
    return commits


def validation_errors(commits: list[Commit], title: str | None = None) -> list[str]:
    errors: list[str] = []
    if title is not None and not parse_header(title):
        errors.append(f"PR title is not Conventional Commit format: {title!r}")
    for commit in commits:
        if not parse_header(commit.subject):
            errors.append(f"{commit.sha[:12]} has invalid subject: {commit.subject!r}")
    return errors


def finalize_changelog(
    path: Path,
    version: str,
    previous_tag: str,
    repository: str,
    release_date: str,
) -> None:
    validate_version(version)
    text = path.read_text(encoding="utf-8")
    marker = "## [Unreleased]"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"{path} has no {marker} section")
    next_section = re.search(r"(?m)^## \[[^\n]+\]", text[start + len(marker) :])
    if not next_section:
        raise ValueError(f"{path} has no released section after {marker}")
    end = start + len(marker) + next_section.start()
    unreleased = text[start + len(marker) : end].strip()
    if not unreleased or unreleased == "No unreleased changes yet.":
        unreleased = "See the generated GitHub release notes for the complete change list."

    replacement = (
        f"{marker}\n\n"
        "No unreleased changes yet.\n\n"
        f"## [{version}] - {release_date}\n\n"
        f"{unreleased}\n\n"
    )
    text = text[:start] + replacement + text[end:]

    unreleased_link = f"[Unreleased]: {repository}/compare/v{version}...HEAD"
    link_pattern = re.compile(r"(?m)^\[Unreleased\]: .+$")
    if link_pattern.search(text):
        text = link_pattern.sub(unreleased_link, text, count=1)
    else:
        text = text.rstrip() + f"\n\n{unreleased_link}\n"

    version_link = f"[{version}]: {repository}/compare/{previous_tag}...v{version}"
    if not re.search(rf"(?m)^\[{re.escape(version)}\]: ", text):
        text = text.rstrip() + f"\n{version_link}\n"
    path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-range")
    validate.add_argument("--base", required=True)
    validate.add_argument("--head", default="HEAD")
    validate.add_argument("--title")

    next_version = subparsers.add_parser("next-version")
    next_version.add_argument("--current", required=True)
    next_version.add_argument("--base-ref")
    next_version.add_argument("--head", default="HEAD")

    version = subparsers.add_parser("validate-version")
    version.add_argument("version")

    changelog = subparsers.add_parser("finalize-changelog")
    changelog.add_argument("--path", type=Path, required=True)
    changelog.add_argument("--version", required=True)
    changelog.add_argument("--previous-tag", required=True)
    changelog.add_argument("--repository", required=True)
    changelog.add_argument("--date", default=date.today().isoformat())
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "validate-range":
        errors = validation_errors(git_commits(args.base, args.head), args.title)
        if errors:
            print("Conventional Commit validation failed:")
            for error in errors:
                print(f"  - {error}")
            print("Expected: type(scope): description")
            return 1
        print("Conventional Commit validation passed.")
        return 0
    if args.command == "next-version":
        bump = release_bump(git_commits(args.base_ref, args.head))
        print(f"bump={bump}")
        print(f"version={increment_version(args.current, bump)}")
        return 0
    if args.command == "validate-version":
        validate_version(args.version)
        print(args.version)
        return 0
    if args.command == "finalize-changelog":
        finalize_changelog(
            args.path,
            args.version,
            args.previous_tag,
            args.repository.rstrip("/"),
            args.date,
        )
        print(args.version)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
