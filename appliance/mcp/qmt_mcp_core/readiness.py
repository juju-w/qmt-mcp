"""Background readiness probe (feature 005).

Polls two signals and drives the live `xtdata` / `qmt_login` state on HealthState:

  - filesystem signal: QMT `userdata_mini` session artifacts present (cheap, no SDK)
  - SDK signal: a cheap `xtdata` call succeeds (the truth data tools care about)

The probe never blocks MCP startup. `step()` performs exactly one poll and is the
unit-tested seam; `run()` loops it on an interval in a daemon thread. The probe
takes its signals as injected callables so it can be tested without Wine/xtquant.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from .audit import now_iso
from .health import HealthState


class ReadinessProbe:
    def __init__(
        self,
        health: HealthState,
        *,
        fs_ready: Callable[[], bool],
        sdk_ready: Callable[[], bool],
        poll_s: float = 5.0,
    ):
        self.health = health
        self._fs_ready = fs_ready
        self._sdk_ready = sdk_ready
        self.poll_s = max(0.1, poll_s)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def step(self) -> str:
        """Run one poll; update health; return the resulting `xtdata` state."""
        self.health.last_probe_at = now_iso()
        try:
            fs = bool(self._fs_ready())
        except Exception:
            fs = False

        if not fs:
            self.health.qmt_login = "awaiting"
            self.health.xtdata = "awaiting_login"
            return self.health.xtdata

        self.health.qmt_login = "logged_in"
        try:
            sdk = bool(self._sdk_ready())
        except Exception as exc:
            self.health.last_error = f"{type(exc).__name__}: {exc}"[:200]
            sdk = False

        if sdk:
            self.health.xtdata = "ready"
            self.health.last_error = ""
        else:
            # Logged in but the xtdata probe isn't passing (warming up or regressed).
            self.health.xtdata = "degraded"
        return self.health.xtdata

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self.step()
            except Exception:  # pragma: no cover - defensive: never kill the loop
                pass
            self._stop.wait(self.poll_s)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, name="qmt-readiness", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
