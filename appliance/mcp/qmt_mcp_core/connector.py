"""Background trader connector (feature 005).

Once readiness reports QMT logged-in, runs the `xttrader` start+connect handshake
with capped exponential backoff, idempotently, and reconnects on drop. It updates
`HealthState.xttrade` only — it exposes NO write/trade tools (constitution II); it
just establishes the session that a future feature 004 plugs query tools into.

Disabled by default (`QMT_ENABLE_CONNECTOR=0`). Without broker programmatic
permission, `connect_fn` returns "not_authorized" and the server stays healthy —
that boundary is what is testable today (004 is permission-blocked).

`connect_fn` returns one of: "connected" | "not_authorized" | "error".
`attempt()` is the unit-tested seam; `run()` loops it with backoff.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from .health import HealthState


class TraderConnector:
    def __init__(
        self,
        health: HealthState,
        *,
        connect_fn: Callable[[], str],
        is_logged_in: Callable[[], bool],
        is_connected: Callable[[], bool] | None = None,
        max_retry: int = 8,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
    ):
        self.health = health
        self._connect = connect_fn
        self._is_logged_in = is_logged_in
        self._is_connected = is_connected
        self.max_retry = max(1, max_retry)
        self.backoff_base = max(0.1, backoff_base)
        self.backoff_max = max(self.backoff_base, backoff_max)
        self.attempts = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def attempt(self) -> str:
        """Run one connect attempt when appropriate; update health; return state."""
        # Idempotent: already connected (and still connected) -> no-op.
        if self.health.xttrade == "connected":
            if self._is_connected is None or self._is_connected():
                return "connected"
            # session dropped -> fall through and reconnect

        if not self._is_logged_in():
            self.health.xttrade = "trader-not-ready"
            return "trader-not-ready"

        self.health.xttrade = "connecting"
        try:
            result = self._connect()
        except Exception as exc:
            self.health.last_error = f"{type(exc).__name__}: {exc}"[:200]
            result = "error"

        if result == "connected":
            self.health.xttrade = "connected"
            self.health.last_error = ""
            self.attempts = 0
        elif result == "not_authorized":
            self.health.xttrade = "not_authorized"
        else:
            self.health.xttrade = "error"
            self.attempts += 1
        return self.health.xttrade

    def backoff_s(self) -> float:
        return min(self.backoff_base * (2 ** min(self.attempts, 20)), self.backoff_max)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                state = self.attempt()
            except Exception:  # pragma: no cover - defensive
                state = "error"
            # Connected: poll slowly to detect drops. Not authorized: this won't
            # change without operator action, so also back off to the cap.
            if state == "connected":
                wait = self.backoff_max
            elif state == "not_authorized":
                wait = self.backoff_max
            else:
                wait = self.backoff_s()
            self._stop.wait(wait)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, name="qmt-connector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
