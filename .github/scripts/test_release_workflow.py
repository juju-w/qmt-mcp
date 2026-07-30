from pathlib import Path
import unittest


WORKFLOW = Path(__file__).parents[1] / "workflows" / "release.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_uses_existing_tag_without_target_commitish(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("tag_name: ${{ needs.prepare.outputs.tag }}", workflow)
        self.assertNotIn("target_commitish:", workflow)


if __name__ == "__main__":
    unittest.main()
