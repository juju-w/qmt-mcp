from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "launcher" / "packaging" / "package-windows.ps1"
INSTALLER = ROOT / "launcher" / "packaging" / "qmt-mcp-launcher.iss"
ICON = ROOT / "launcher" / "src" / "QmtMcp.Launcher.Desktop" / "Assets" / "app-icon.ico"


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

    def test_icon_contains_native_tray_and_window_sizes(self) -> None:
        data = ICON.read_bytes()
        reserved, image_type, count = struct.unpack_from("<HHH", data)
        self.assertEqual((reserved, image_type), (0, 1))
        sizes = set()
        for index in range(count):
            width, height = struct.unpack_from("<BB", data, 6 + index * 16)
            sizes.add((width or 256, height or 256))
        self.assertEqual(
            sizes,
            {(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
             (48, 48), (64, 64), (128, 128), (256, 256)},
        )


if __name__ == "__main__":
    unittest.main()
