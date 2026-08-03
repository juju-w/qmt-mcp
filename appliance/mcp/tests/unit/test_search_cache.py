from pathlib import Path

from qmt_mcp_xtdata.search_cache import _cache_path_is_allowed


def test_posix_cache_path_stays_under_broker() -> None:
    assert _cache_path_is_allowed(Path("/broker/cache/instruments.json"), platform_name="posix")
    assert not _cache_path_is_allowed(Path("/broker/../etc/instruments.json"), platform_name="posix")
    assert not _cache_path_is_allowed(Path("/broker-copy/instruments.json"), platform_name="posix")


def test_windows_cache_path_stays_under_local_app_data() -> None:
    local_appdata = r"C:\Users\Example\AppData\Local"
    assert _cache_path_is_allowed(
        Path(r"C:\Users\Example\AppData\Local\QMT-MCP\cache\instruments.json"),
        platform_name="nt",
        local_appdata=local_appdata,
    )
    assert _cache_path_is_allowed(
        Path(r"c:\users\example\appdata\local\qmt-mcp\instruments.json"),
        platform_name="nt",
        local_appdata=local_appdata,
    )


def test_windows_cache_path_rejects_escape_and_other_drive() -> None:
    local_appdata = r"C:\Users\Example\AppData\Local"
    rejected = (
        r"C:\Users\Example\AppData\Local\QMT-MCP\..\outside.json",
        r"C:\Users\Example\AppData\Local\QMT-MCP-copy\instruments.json",
        r"D:\QMT-MCP\instruments.json",
    )
    for candidate in rejected:
        assert not _cache_path_is_allowed(
            Path(candidate),
            platform_name="nt",
            local_appdata=local_appdata,
        )


def test_windows_cache_path_requires_local_app_data() -> None:
    assert not _cache_path_is_allowed(Path(r"C:\QMT-MCP\instruments.json"), platform_name="nt")
