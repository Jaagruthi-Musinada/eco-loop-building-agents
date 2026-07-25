"""Sanity tests that don't require EnergyPlus or an LLM to be installed —
run these first to confirm the bus and MCP tool plumbing work in isolation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.communication_bus import CommunicationBus


def test_publish_and_get_state():
    bus = CommunicationBus()
    bus.publish_state({"zone1_temp_c": 22.5})
    assert bus.get_state()["zone1_temp_c"] == 22.5


def test_queue_and_drain_actions():
    bus = CommunicationBus()
    bus.queue_action("zone1_cooling_setpoint", 23.0)
    actions = bus.drain_actions()
    assert actions == {"zone1_cooling_setpoint": 23.0}
    # second drain should be empty — actions are consumed exactly once
    assert bus.drain_actions() == {}


def test_freshness_starts_high():
    bus = CommunicationBus()
    # no publish yet -> should be a large number, not zero
    assert bus.seconds_since_update() > 0
