QMT-MCP for Windows x64
=======================

This package runs QMT-MCP without Docker, a system Python installation, or a
system .NET installation. It does not contain QMT or any broker software.

The package includes a Python 3.11 runtime selected for compatibility with
broker-provided xtquant extensions. The native launcher uses static-token auth
and local state; OAuth and PostgreSQL remain available in the Linux appliance.

First run
---------
1. Start QmtMcp.Launcher.exe.
2. Open Setup and select your QMT client executable, or choose Detect client.
3. Review the detected xtquant and userdata paths, then save the profile. If the
   QMT installation does not include xtquant, download/install its Python SDK in
   the broker client, or extract the broker SDK and browse to the import root
   whose child folder is named xtquant.
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
