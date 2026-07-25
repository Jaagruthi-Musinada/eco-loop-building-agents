"""
In-memory, thread-safe communication bus.

Serves as the central real-time communication bus between the simulation thread
(EnergyPlus / Physics Simulator) and the LLM Cognitive Agent / MCP server thread.
Stores latest snapshot state, queued forward-injected actions, and history metrics.
"""
from __future__ import annotations
import threading
import time
from typing import Any, Optional


class CommunicationBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._pending_actions: dict[str, float] = {}
        self._history: list[dict[str, Any]] = []
        self._last_update_ts: float = 0.0

    # ---- EnergyPlus / Physics Simulator -> Bus ----
    def publish_state(self, state: dict[str, Any]) -> None:
        """Called by energyplus_wrapper on every timestep."""
        with self._lock:
            self._state = dict(state)
            self._history.append(dict(state))
            self._last_update_ts = time.time()

    def get_state(self) -> dict[str, Any]:
        """Called by the LLM agent / MCP tools to read the latest sensor snapshot."""
        with self._lock:
            return dict(self._state)

    def get_history(self) -> list[dict[str, Any]]:
        """Returns the full historical sequence of telemetry records."""
        with self._lock:
            return list(self._history)

    # ---- LLM Agent / MCP Server -> Bus ----
    def queue_action(self, actuator_key: str, value: float) -> None:
        """
        Called by MCP `set_setpoint` tool.
        Enqueues forward-injected control actions for the simulation loop.
        """
        with self._lock:
            self._pending_actions[actuator_key] = float(value)

    def drain_actions(self) -> dict[str, float]:
        """
        Called by energyplus_wrapper's actuator callback each timestep.
        Returns and clears whatever actions the LLM has queued.
        """
        with self._lock:
            actions, self._pending_actions = self._pending_actions, {}
            return actions

    def seconds_since_update(self) -> float:
        with self._lock:
            if self._last_update_ts == 0.0:
                return 999.0
            return time.time() - self._last_update_ts

    def clear(self) -> None:
        with self._lock:
            self._state.clear()
            self._pending_actions.clear()
            self._history.clear()
            self._last_update_ts = 0.0


# Single shared instance imported by every module in the process.
bus = CommunicationBus()
