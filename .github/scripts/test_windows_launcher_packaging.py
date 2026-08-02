from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "launcher" / "packaging" / "package-windows.ps1"
INSTALLER = ROOT / "launcher" / "packaging" / "qmt-mcp-launcher.iss"


class WindowsLauncherPackagingTests(unittest.TestCase):
    def test_python_runtime_download_is_versioned_and_hash_verified(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("$PythonVersion = '3.12.10'", script)
        self.assertIn("4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3", script)
        self.assertIn("Get-FileHash -Algorithm SHA256", script)
        self.assertIn("--require-hashes", script)
        self.assertIn("'restore', $Project, '--runtime', 'win-x64', '--locked-mode'", script)

    def test_zip_and_installer_share_one_staging_directory(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Compress-Archive -Path (Join-Path $StageDirectory '*')", script)
        self.assertIn('"/DStageDir=$StageDirectory"', script)
        self.assertIn("LAUNCHER_SHA256SUMS", script)

    def test_installer_is_per_user_and_x64(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("DefaultDirName={localappdata}\\Programs\\QMT-MCP", installer)
        self.assertIn("PrivilegesRequired=lowest", installer)
        self.assertIn("ArchitecturesAllowed=x64compatible", installer)


if __name__ == "__main__":
    unittest.main()
