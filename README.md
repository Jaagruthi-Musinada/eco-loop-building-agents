# Eco-Loop Building Agents

Autonomous closed-loop building energy control PoC: **EnergyPlus** (digital building
sandbox) ↔ **MCP tool layer** ↔ **local open-source LLM** (the "brain").

The LLM reads live zone sensor data every simulation timestep, reasons about comfort
vs. energy targets, and writes new setpoints/ECMs straight back into the running
EnergyPlus simulation — no human in the loop.

## Folder structure

```
eco-loop-building-agents/
├── README.md                  <- you are here
├── requirements.txt
├── .env.example                <- copy to .env, fill in model/API config
├── models/
│   ├── baseline.idf             <- put your EnergyPlus building model here
│   ├── baseline_modified.idf    <- auto-saved copy the loop writes edits to
│   └── weather/
│       └── site.epw              <- EnergyPlus weather file
├── src/
│   ├── config.py                <- central config (paths, LLM endpoint, targets)
│   ├── energyplus_wrapper.py    <- runs the sim, exposes sensors, accepts actuator writes
│   ├── communication_bus.py     <- thread-safe shared state between EnergyPlus <-> LLM
│   ├── mcp_server.py            <- MCP server exposing get_state / set_setpoint / etc.
│   ├── llm_agent.py             <- calls the local LLM with tool-calling, drives decisions
│   ├── control_loop.py          <- ties everything together (the orchestrator)
│   └── main.py                  <- entry point: `python -m src.main`
├── dashboard/
│   └── app.py                    <- Streamlit dashboard: baseline vs closed-loop kWh/comfort
├── docs/
│   └── ARCHITECTURE.md          <- system architecture doc (deliverable #4)
├── logs/                        <- run logs + JSON metric exports land here
└── tests/
    └── test_wrapper.py           <- sanity tests for the wrapper/bus
```

## Quick start

```bash
# 1. System dependency: EnergyPlus (v23+ recommended)
#    Download installer for your OS: https://energyplus.net/downloads
#    After install, note the path, e.g. /usr/local/EnergyPlus-24-1-0

# 2. Python deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Local LLM (pick one)
#    Option A: Ollama (simplest)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1        # or qwen2.5, mistral, etc.
#    Option B: any self-hosted OpenAI-compatible server (vLLM, LM Studio, etc.)

# 4. Configure
cp .env.example .env
# edit .env: set ENERGYPLUS_DIR, IDF path, EPW path, LLM base URL/model name

# 5. Run the baseline (no AI control) to get a comparison reference
python -m src.main --mode baseline

# 6. Run the closed loop
python -m src.main --mode closed-loop

# 7. View results
streamlit run dashboard/app.py
```

## How the loop works (also see docs/ARCHITECTURE.md)

1. **EnergyPlus → bus**: at every zone timestep, `energyplus_wrapper.py` reads sensor
   handles (zone temp, RH, energy meters, PMV) via the EnergyPlus Python API callback
   and writes them into `communication_bus.py` as the latest state snapshot.
2. **bus → LLM (via MCP tools)**: `control_loop.py` wakes the LLM agent every N
   timesteps (not every timestep — keeps latency manageable). The agent calls MCP
   tools (`get_zone_state`, `get_energy_summary`, `get_targets`) to pull only what it
   needs, keeping the prompt small.
3. **LLM reasons**: compares state against `config.py` targets (comfort band, peak
   demand threshold, grid carbon intensity schedule) and decides ECMs — e.g. shift a
   setpoint, stagger a fan schedule, pre-cool before a peak window.
4. **LLM → bus → EnergyPlus**: the agent calls the `set_setpoint` / `set_schedule` MCP
   tool, which writes to the bus; the wrapper's actuator callback picks it up and
   applies it to the live simulation on the next timestep — this is the "forward
   injection."
5. **Logging**: every cycle appends a row to `logs/run_<timestamp>.jsonl` with raw
   metrics + the LLM's action + its stated reasoning, which both the dashboard and the
   architecture doc pull from.

## Priority order if you're short on time

1. Get EnergyPlus running standalone with a stock example .idf (Ex: `5ZoneAirCooled.idf`
   ships with EnergyPlus under `ExampleFiles/`). Confirm you can read sensor values via
   the Python API before touching the LLM.
2. Get the bus + a **hardcoded rule-based** "fake LLM" wired end-to-end first — proves
   the closed loop before you add real LLM latency/parsing risk.
3. Swap the fake LLM for the real one with tool calling.
4. Add the dashboard last — it's the easiest 25% of the score and easy to cut scope on.
