"""Central configuration, loaded from environment variables (.env)."""
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


ROOT = Path(__file__).resolve().parent.parent

ENERGYPLUS_DIR = os.getenv("ENERGYPLUS_DIR", "/usr/local/EnergyPlus-24-1-0")
IDF_PATH = ROOT / os.getenv("IDF_PATH", "models/baseline.idf")
EPW_PATH = ROOT / os.getenv("EPW_PATH", "models/weather/site.epw")
OUTPUT_DIR = ROOT / os.getenv("OUTPUT_DIR", "logs/eplus_out")

# LLM Agent settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")  # "auto", "ollama", "openai", "autonomous"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/api/chat")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

# Simulation engine: "auto" picks EnergyPlus if pyenergyplus is present, else physics sandbox
SIMULATION_ENGINE = os.getenv("SIMULATION_ENGINE", "auto")

AGENT_DECISION_INTERVAL_TIMESTEPS = int(
    os.getenv("AGENT_DECISION_INTERVAL_TIMESTEPS", "6")
)

# Comfort and energy target boundaries
TARGETS = {
    "comfort_temp_min_c": float(os.getenv("COMFORT_TEMP_MIN_C", "21.0")),
    "comfort_temp_max_c": float(os.getenv("COMFORT_TEMP_MAX_C", "25.0")),
    "peak_demand_threshold_kw": float(os.getenv("PEAK_DEMAND_THRESHOLD_KW", "50.0")),
    "pmv_band": (-0.5, 0.5),  # ASHRAE 55 acceptable comfort range
    "max_co2_ppm": 800.0,
    "carbon_peak_start_hour": 14,  # 2 PM
    "carbon_peak_end_hour": 19,    # 7 PM
    "peak_carbon_intensity_g_co2_kwh": 480.0,
    "offpeak_carbon_intensity_g_co2_kwh": 210.0,
}

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

