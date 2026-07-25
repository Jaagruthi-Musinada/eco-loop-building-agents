"""
Unit tests for MCP server tools, physics simulator, and LLM agent decision loop.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.communication_bus import bus
from src.energyplus_wrapper import EnergyPlusWrapper, PhysicsBuildingSimulator, calculate_pmv
from src import mcp_server as tools
from src.llm_agent import LLMAgent, AutonomousReasoningEngine


def test_pmv_calculation():
    # Test neutral thermal comfort
    pmv_neutral = calculate_pmv(23.5, 50.0, 24.0)
    assert -0.2 <= pmv_neutral <= 0.2

    # Test warm thermal comfort
    pmv_warm = calculate_pmv(27.0, 50.0, 24.0)
    assert pmv_warm > 0.5


def test_mcp_tools_and_guardrails():
    bus.clear()
    bus.publish_state({
        "zone1_temp_c": 23.5,
        "zone1_rh_pct": 50.0,
        "facility_electricity_kw": 18.0,
        "cooling_setpoint_c": 24.0,
        "sim_time": "Day 1 12:00:00",
    })

    # Test get_zone_state
    state_res = json.loads(tools.get_zone_state())
    assert state_res["zone1_temp_c"] == 23.5

    # Test get_targets
    targets_res = json.loads(tools.get_targets())
    assert "comfort_temp_min_c" in targets_res

    # Test valid setpoint queueing
    set_res = json.loads(tools.set_setpoint("zone1_cooling_setpoint", 23.0))
    assert set_res["ok"] is True
    assert bus.drain_actions() == {"zone1_cooling_setpoint": 23.0}

    # Test invalid setpoint rejection (safety guardrail)
    invalid_res = json.loads(tools.set_setpoint("zone1_cooling_setpoint", 35.0))
    assert invalid_res["ok"] is False
    assert "Rejected" in invalid_res["error"]


def test_autonomous_reasoning_engine():
    bus.clear()
    bus.publish_state({
        "zone1_temp_c": 24.0,
        "zone1_rh_pct": 50.0,
        "facility_electricity_kw": 20.0,
        "cooling_setpoint_c": 24.0,
        "carbon_intensity_g_co2_kwh": 480.0,
        "occupancy_count": 25,
        "sim_time": "Day 1 15:00:00",  # Peak carbon hour
    })


    engine = AutonomousReasoningEngine()
    reasoning = engine.run_decision_cycle()
    assert "AI Agent Decision" in reasoning

    # Verify action was queued on the bus
    actions = bus.drain_actions()
    assert "zone1_cooling_setpoint" in actions
    assert actions["zone1_cooling_setpoint"] == 24.5  # Load shedding setpoint during peak carbon


def test_physics_simulator_run():
    bus.clear()
    wrapper = EnergyPlusWrapper(control_enabled=True)
    assert wrapper._tick_count == 0

    # Run a short simulation pass
    wrapper.run()
    assert wrapper._tick_count > 0
    assert len(bus.get_history()) > 0
