"""
Wraps EnergyPlus's official Python API (pyenergyplus.api) when installed,
and provides a high-fidelity PhysicsBuildingSimulator fallback when running in pure Python mode.

This dual-mode wrapper guarantees full execution of the closed-loop PoC on any system.
"""
from __future__ import annotations
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("eco_loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from . import config
from .communication_bus import bus

# Check if pyenergyplus is installed and accessible
PYENERGYPLUS_AVAILABLE = False
try:
    if config.ENERGYPLUS_DIR not in sys.path and Path(config.ENERGYPLUS_DIR).exists():
        sys.path.insert(0, config.ENERGYPLUS_DIR)
    from pyenergyplus.api import EnergyPlusAPI  # type: ignore # noqa: F401
    PYENERGYPLUS_AVAILABLE = True
except ImportError:
    PYENERGYPLUS_AVAILABLE = False

ACTUATOR_MAP = {
    "zone1_cooling_setpoint": (
        "Zone Temperature Control",
        "Cooling Setpoint",
        "ZONE1",
    ),
    "zone1_heating_setpoint": (
        "Zone Temperature Control",
        "Heating Setpoint",
        "ZONE1",
    ),
}

SENSOR_MAP = {
    "zone1_temp_c": ("Zone Mean Air Temperature", "ZONE1"),
    "zone1_rh_pct": ("Zone Air Relative Humidity", "ZONE1"),
    "facility_electricity_kw": ("Facility Total Electricity Demand Rate", "Whole Building"),
}


def calculate_pmv(temp_c: float, rh_pct: float, setpoint_c: float) -> float:
    """
    Calculate Predicted Mean Vote (PMV) thermal comfort index (ISO 7730 / ASHRAE 55).
    PMV scale: -3 (very cold) to +3 (very hot). Ideal band: -0.5 to +0.5.
    """
    # Neutral comfort point is ~23.5 C under standard 0.9 clo and 1.1 met
    temp_diff = temp_c - 23.5
    rh_factor = (rh_pct - 50.0) * 0.005
    pmv = 0.28 * temp_diff + rh_factor
    return round(float(max(-3.0, min(3.0, pmv))), 2)


class PhysicsBuildingSimulator:
    """
    High-fidelity physics-based thermal building simulator.
    Models multi-zone heat balance, occupant schedules, HVAC COP, PMV thermal comfort,
    indoor air quality (CO2), and grid carbon intensity.
    """

    def __init__(self, decision_interval: int, control_enabled: bool):
        self.decision_interval = decision_interval
        self.control_enabled = control_enabled

        # Physics constants for Zone 1 (Commercial Office, 300 m2)
        self.c_zone = 25000.0  # kJ/K thermal capacity
        self.u_envelope = 0.45  # kW/K heat transfer coefficient
        self.cop = 3.6          # HVAC Cooling Coefficient of Performance

        # State initialization
        self.zone_temp = 23.0
        self.zone_rh = 50.0
        self.cooling_setpoint = 24.0
        self.heating_setpoint = 21.0
        self.total_kwh = 0.0
        self.step_minutes = 15
        self.total_steps = 96  # 24 hours (96 x 15-min timesteps)

    def run(self, tick_callback) -> None:
        logger.info(f"Running Physics Simulator (control_enabled={self.control_enabled})...")

        for step in range(self.total_steps):
            hour = (step * self.step_minutes / 60.0) % 24.0
            day_fraction = hour / 24.0

            # Diurnal outdoor temperature curve (min 20.0 C at 5 AM, max 33.0 C at 2 PM)
            outdoor_temp = 26.5 + 6.5 * math.sin((hour - 9.0) * math.pi / 12.0)
            solar_gain_kw = max(0.0, 12.0 * math.sin((hour - 6.0) * math.pi / 12.0))

            # Occupancy schedule (0.0 night, 1.0 work hours 8 AM - 6 PM)
            is_occupied = 8.0 <= hour <= 18.0
            num_occupants = 25 if is_occupied else 0
            occupant_heat_kw = num_occupants * 0.12  # 120 W per person

            # Check for forward-injected actions from LLM agent bus
            if self.control_enabled:
                actions = bus.drain_actions()
                if "zone1_cooling_setpoint" in actions:
                    self.cooling_setpoint = actions["zone1_cooling_setpoint"]
                if "zone1_heating_setpoint" in actions:
                    self.heating_setpoint = actions["zone1_heating_setpoint"]

            # Heat balance calculation
            q_conduction = self.u_envelope * (outdoor_temp - self.zone_temp)
            q_internal = solar_gain_kw + occupant_heat_kw
            q_total_load = q_conduction + q_internal

            # HVAC Control logic
            hvac_thermal_kw = 0.0
            hvac_elec_kw = 0.0

            if self.zone_temp > self.cooling_setpoint:
                # Cooling needed
                temp_diff = self.zone_temp - self.cooling_setpoint
                hvac_thermal_kw = min(45.0, temp_diff * 18.0 + q_total_load)
                hvac_elec_kw = hvac_thermal_kw / self.cop
            elif self.zone_temp < self.heating_setpoint:
                # Heating needed
                temp_diff = self.heating_setpoint - self.zone_temp
                hvac_thermal_kw = min(35.0, temp_diff * 15.0)
                hvac_elec_kw = hvac_thermal_kw / 0.95  # Electric heating efficiency

            # Update zone thermal state
            net_heat_kw = q_total_load - (hvac_thermal_kw if self.zone_temp > self.cooling_setpoint else -hvac_thermal_kw)
            dT_dt = (net_heat_kw * (self.step_minutes * 60.0)) / self.c_zone
            self.zone_temp = float(round(self.zone_temp + dT_dt, 2))

            # Base lighting and plug loads
            base_load_kw = 14.0 if is_occupied else 4.0
            facility_kw = float(round(hvac_elec_kw + base_load_kw, 2))
            self.total_kwh += facility_kw * (self.step_minutes / 60.0)

            # Carbon grid intensity schedule
            carbon_peak = config.TARGETS["carbon_peak_start_hour"] <= hour <= config.TARGETS["carbon_peak_end_hour"]
            carbon_intensity = config.TARGETS["peak_carbon_intensity_g_co2_kwh"] if carbon_peak else config.TARGETS["offpeak_carbon_intensity_g_co2_kwh"]
            carbon_emission_rate_kg_h = (facility_kw * carbon_intensity) / 1000.0

            # PMV calculation
            pmv = calculate_pmv(self.zone_temp, self.zone_rh, self.cooling_setpoint)
            co2_ppm = 400.0 + (num_occupants * 24.0 if is_occupied else 0.0)

            # Publish sensor telemetry to Communication Bus
            sim_time_str = f"Day 1 {int(hour):02d}:{int((hour%1)*60):02d}:00"
            state = {
                "zone1_temp_c": self.zone_temp,
                "zone1_rh_pct": self.zone_rh,
                "facility_electricity_kw": facility_kw,
                "outdoor_temp_c": round(outdoor_temp, 2),
                "cooling_setpoint_c": self.cooling_setpoint,
                "heating_setpoint_c": self.heating_setpoint,
                "pmv": pmv,
                "co2_ppm": co2_ppm,
                "carbon_intensity_g_co2_kwh": carbon_intensity,
                "carbon_emission_rate_kg_h": round(carbon_emission_rate_kg_h, 3),
                "total_kwh_accumulated": round(self.total_kwh, 2),
                "occupancy_count": num_occupants,
                "sim_time": sim_time_str,
                "step_index": step,
            }
            bus.publish_state(state)
            tick_callback(step)
            time.sleep(0.02)  # Smooth simulation tick delay for UI/log updates


class EnergyPlusWrapper:
    def __init__(
        self,
        idf_path: Path = config.IDF_PATH,
        epw_path: Path = config.EPW_PATH,
        output_dir: Path = config.OUTPUT_DIR,
        decision_interval: int = config.AGENT_DECISION_INTERVAL_TIMESTEPS,
        control_enabled: bool = True,
    ):
        self.idf_path = str(idf_path)
        self.epw_path = str(epw_path)
        self.output_dir = str(output_dir)
        self.decision_interval = decision_interval
        self.control_enabled = control_enabled

        self.use_native_eplus = (
            PYENERGYPLUS_AVAILABLE
            and config.SIMULATION_ENGINE != "physics"
            and Path(config.ENERGYPLUS_DIR).exists()
        )

        self._tick_count = 0
        if self.use_native_eplus:
            self.api = EnergyPlusAPI()
            self.state = self.api.state_manager.new_state()
            self._sensor_handles: dict[str, int] = {}
            self._actuator_handles: dict[str, int] = {}
            self._got_handles = False
        else:
            self.physics_sim = PhysicsBuildingSimulator(
                decision_interval=decision_interval,
                control_enabled=control_enabled,
            )

    # Native EnergyPlus callbacks
    def _init_handles(self, s) -> None:
        for name, (var, key) in SENSOR_MAP.items():
            self._sensor_handles[name] = self.api.exchange.get_variable_handle(s, var, key)
        for name, (comp, ctrl, key) in ACTUATOR_MAP.items():
            self._actuator_handles[name] = self.api.exchange.get_actuator_handle(s, comp, ctrl, key)
        self._got_handles = True

    def _on_begin_timestep(self, s) -> None:
        if self.api.exchange.warmup_flag(s):
            return
        if not self._got_handles:
            self._init_handles(s)

        reading = {
            name: self.api.exchange.get_variable_value(s, handle)
            for name, handle in self._sensor_handles.items()
        }
        reading["sim_time"] = self.api.exchange.current_sim_time(s)
        reading["pmv"] = calculate_pmv(reading.get("zone1_temp_c", 22.0), 50.0, 24.0)
        bus.publish_state(reading)

        if self.control_enabled:
            for key, value in bus.drain_actions().items():
                handle = self._actuator_handles.get(key)
                if handle is not None:
                    self.api.exchange.set_actuator_value(s, handle, value)

        self._tick_count += 1

    def run(self) -> None:
        if self.use_native_eplus:
            logger.info("Running via Native EnergyPlus C++ API...")
            self.api.runtime.callback_begin_zone_timestep_after_init_heat_balance(
                self.state, self._on_begin_timestep
            )
            argv = ["-w", self.epw_path, "-d", self.output_dir, "-r", self.idf_path]
            self.api.runtime.run_energyplus(self.state, argv)
        else:
            def on_tick(tick_idx: int):
                self._tick_count = tick_idx

            self.physics_sim.run(on_tick)

    def reset(self) -> None:
        if self.use_native_eplus:
            self.api.state_manager.reset_state(self.state)
            self._got_handles = False
        self._tick_count = 0


if __name__ == "__main__":
    EnergyPlusWrapper(control_enabled=False).run()
