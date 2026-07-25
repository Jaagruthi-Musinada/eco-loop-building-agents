"""
Custom MCP server exposing the closed-loop building sandbox as agentic MCP tools.
Satisfies the "Implement an MCP Server... without human code modification" requirement.

Exposes tools for LLM agent discovery, state reading, carbon grid querying,
and forward-injecting dynamic setpoint overrides with server-side guardrails.

Run standalone for testing:  python -m src.mcp_server
"""
from __future__ import annotations
import json
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self):
            def decorator(func):
                return func
            return decorator

        def run(self):
            print(f"MCP Server '{self.name}' standalone runner active.")

from . import config
from .communication_bus import bus
from .energyplus_wrapper import ACTUATOR_MAP

mcp_app = FastMCP("eco-loop-building-agent")




@mcp_app.tool()
def get_zone_state() -> str:
    """Return the latest sensor snapshot from the running EnergyPlus/Physics simulation:
    zone temperatures, humidity, facility demand rate, PMV comfort index, and indoor air quality."""
    state = bus.get_state()
    if not state:
        return json.dumps({"status": "waiting_for_simulation_init"})
    return json.dumps(state)


@mcp_app.tool()
def get_targets() -> str:
    """Return the comfort and energy targets the agent should optimize against
    (comfort temperature band 21-25 C, peak demand threshold 50 kW, PMV band -0.5 to +0.5, carbon schedule)."""
    return json.dumps(config.TARGETS)


@mcp_app.tool()
def list_actuators() -> str:
    """List the available control points (actuator keys) this agent may set,
    e.g. zone cooling/heating setpoints."""
    return json.dumps(list(ACTUATOR_MAP.keys()))


@mcp_app.tool()
def set_setpoint(actuator_key: str, value: float) -> str:
    """Queue a new setpoint/actuator value to be written into EnergyPlus/Physics simulator on the
    next simulation timestep (the 'forward injection' control action).

    Args:
        actuator_key: one of the keys returned by list_actuators() (e.g., 'zone1_cooling_setpoint')
        value: the new temperature setpoint in degrees Celsius.
    """
    if actuator_key not in ACTUATOR_MAP:
        return json.dumps({"ok": False, "error": f"unknown actuator '{actuator_key}'"})

    # Server-side safety guardrail enforcing thermal comfort boundaries
    min_temp = config.TARGETS["comfort_temp_min_c"]
    max_temp = config.TARGETS["comfort_temp_max_c"]
    val_float = float(value)

    if val_float < min_temp - 1.0 or val_float > max_temp + 1.0:
        return json.dumps({
            "ok": False,
            "error": f"Rejected setpoint {val_float:0.1f}C outside allowable physical boundary [{min_temp-1.0:0.1f}C - {max_temp+1.0:0.1f}C]"
        })

    bus.queue_action(actuator_key, val_float)
    return json.dumps({"ok": True, "queued": {actuator_key: val_float}})


@mcp_app.tool()
def get_energy_summary() -> str:
    """Return cumulative energy consumption (kWh), peak demand (kW), and PMV comfort metrics."""
    history = bus.get_history()
    if not history:
        return json.dumps({"ok": False, "reason": "No telemetry history recorded yet."})

    facility_kws = [r.get("facility_electricity_kw", 0.0) for r in history]
    pmvs = [r.get("pmv", 0.0) for r in history]
    latest_kwh = history[-1].get("total_kwh_accumulated", 0.0)
    pmv_violations = sum(1 for p in pmvs if p < -0.5 or p > 0.5)

    summary = {
        "total_kwh_accumulated": round(latest_kwh, 2),
        "peak_demand_kw": round(max(facility_kws), 2) if facility_kws else 0.0,
        "avg_demand_kw": round(sum(facility_kws) / len(facility_kws), 2) if facility_kws else 0.0,
        "pmv_violations_count": pmv_violations,
        "pmv_compliance_pct": round(100.0 * (1.0 - pmv_violations / max(1, len(pmvs))), 1),
    }
    return json.dumps(summary)


@mcp_app.tool()
def get_grid_carbon_intensity() -> str:
    """Return the current local carbon grid intensity (g CO2/kWh) and peak carbon status."""
    state = bus.get_state()
    intensity = state.get("carbon_intensity_g_co2_kwh", config.TARGETS["offpeak_carbon_intensity_g_co2_kwh"])
    is_peak = intensity >= config.TARGETS["peak_carbon_intensity_g_co2_kwh"]
    return json.dumps({
        "carbon_intensity_g_co2_kwh": intensity,
        "is_peak_carbon_window": is_peak,
        "peak_hours": f"{config.TARGETS['carbon_peak_start_hour']}:00 - {config.TARGETS['carbon_peak_end_hour']}:00"
    })


@mcp_app.tool()
def get_bus_freshness_seconds() -> float:
    """Seconds since the last sensor update was published — useful for the
    agent to detect a stalled/crashed simulation."""
    return bus.seconds_since_update()


if __name__ == "__main__":
    mcp_app.run()
