from pathlib import Path
import unittest


WORKFLOW = Path(__file__).parents[1] / "workflows" / "release.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_release_uses_existing_tag_without_target_commitish(self) -> None:
        self.assertIn(
            "tag_name: ${{ needs.prepare.outputs.tag }}", self.workflow
        )
        self.assertNotIn("target_commitish:", self.workflow)

    def test_historical_retry_cannot_overwrite_shared_build_cache(self) -> None:
        cache_exports = [
            line.strip()
            for line in self.workflow.splitlines()
            if line.strip().startswith("cache-to:")
        ]

        self.assertEqual(len(cache_exports), 1)
        self.assertIn("publish_latest == 'true'", cache_exports[0])


if __name__ == "__main__":
    unittest.main()
