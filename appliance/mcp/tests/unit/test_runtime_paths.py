from __future__ import annotations

from qmt_mcp_core.runtime_paths import runtime_path


def test_native_windows_path_keeps_drive_and_normalizes_separators() -> None:
    assert runtime_path(r"D:/QMT/userdata_mini", "nt") == r"D:\QMT\userdata_mini"


def test_wine_z_drive_path_maps_to_posix_root_for_posix_helpers() -> None:
    assert runtime_path(r"Z:\broker\userdata_mini", "posix") == "/broker/userdata_mini"


def test_legacy_posix_conversion_preserves_non_z_drive_behavior() -> None:
    assert runtime_path(r"D:\QMT\userdata_mini", "posix") == "/QMT/userdata_mini"


def test_empty_path_stays_empty() -> None:
    assert runtime_path("   ", "nt") == ""
