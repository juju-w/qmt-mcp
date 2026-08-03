QMT-MCP for Windows x64
=======================

This package runs QMT-MCP without Docker, a system Python installation, or a
system .NET installation. It does not contain QMT or any broker software.

First run
---------
1. Start QmtMcp.Launcher.exe.
2. Open Setup and select your QMT client executable, or choose Detect client.
3. Review the detected xtquant and userdata paths, then save the profile. If
   xtquant is supplied separately, place its import root below
   %LOCALAPPDATA%\QMT-MCP\sdk\<broker> for automatic discovery, or browse to it.
4. Choose Start. Complete broker login in the normal QMT window when prompted.
5. When Market data is Ready, copy the local MCP connection from Status.

The launcher supports Simplified Chinese and English. It follows the Windows
display language on first run and remembers the language selected in the header.

Security
--------
- MCP binds to 127.0.0.1 only.
- The bearer token is encrypted for the current Windows user with DPAPI.
- The launcher never automates passwords, captcha, MFA, agreements, or trades.
- Account query and trading remain disabled unless explicitly configured and
  supported by the connected QMT account.

Data and logs
-------------
Per-user state is stored under %LOCALAPPDATA%\QMT-MCP. Use Diagnostics in the
launcher to open logs or create a redacted support archive.

Project: https://github.com/juju-w/qmt-mcp
