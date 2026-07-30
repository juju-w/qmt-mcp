from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from release_policy import (
    Commit,
    finalize_changelog,
    increment_version,
    parse_header,
    release_bump,
    validate_version,
    validation_errors,
)


class ReleasePolicyTests(unittest.TestCase):
    def test_conventional_headers(self):
        self.assertIsNotNone(parse_header("feat(release): automate publishing"))
        self.assertIsNotNone(parse_header("fix!: change a public contract"))
        self.assertIsNone(parse_header("Add automatic publishing"))
        self.assertIsNone(parse_header("feat(Release): uppercase scope"))

    def test_validation_reports_title_and_commit(self):
        errors = validation_errors(
            [Commit("a" * 40, "Add files")],
            title="Release automation",
        )
        self.assertEqual(len(errors), 2)

    def test_release_bump_precedence(self):
        self.assertEqual(release_bump([Commit("a", "docs: update guide")]), "patch")
        self.assertEqual(
            release_bump([Commit("a", "fix: bug"), Commit("b", "feat(cli): add command")]),
            "minor",
        )
        self.assertEqual(
            release_bump([Commit("a", "feat(api)!: replace contract")]),
            "major",
        )
        self.assertEqual(
            release_bump([Commit("a", "fix(api): behavior", "BREAKING CHANGE: response changed")]),
            "major",
        )
        self.assertEqual(
            release_bump([Commit("a", "chore(release): v1.2.3 [skip ci]")]),
            "none",
        )

    def test_semver_increment(self):
        self.assertEqual(increment_version("1.2.3", "patch"), "1.2.4")
        self.assertEqual(increment_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(increment_version("1.2.3", "major"), "2.0.0")
        with self.assertRaises(ValueError):
            validate_version("v1.2.3")

    def test_finalize_changelog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(
                "# Changelog\n\n"
                "## [Unreleased]\n\n"
                "### Added\n"
                "- Automatic releases.\n\n"
                "## [0.2.0] - 2026-06-04\n\n"
                "- Previous release.\n\n"
                "[Unreleased]: https://github.com/example/repo/compare/v0.2.0...HEAD\n"
                "[0.2.0]: https://github.com/example/repo/compare/v0.1.0...v0.2.0\n",
                encoding="utf-8",
            )

            finalize_changelog(
                path,
                "0.3.0",
                "v0.2.0",
                "https://github.com/example/repo",
                "2026-07-30",
            )
            result = path.read_text(encoding="utf-8")

        self.assertIn("## [Unreleased]\n\nNo unreleased changes yet.", result)
        self.assertIn("## [0.3.0] - 2026-07-30\n\n### Added", result)
        self.assertIn("[Unreleased]: https://github.com/example/repo/compare/v0.3.0...HEAD", result)
        self.assertIn("[0.3.0]: https://github.com/example/repo/compare/v0.2.0...v0.3.0", result)


if __name__ == "__main__":
    unittest.main()
