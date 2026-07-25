# Eco-Loop Building Agents — Honeywell Hackathon Submission

Autonomous Closed-Loop Smart Building Energy Optimization PoC: **EnergyPlus Physics Simulation Engine** ↔ **Model Context Protocol (MCP)** ↔ **Open-Source LLM Cognitive Agent**.

---

## 🎥 PoC Demonstration Video

<video src="demo_video.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

### 🔗 Video Links for Hackathon Evaluators:
- **[▶️ View Video File on GitHub](https://github.com/Jaagruthi-Musinada/eco-loop-building-agents/blob/main/demo_video.mp4)**
- **[📥 Direct Raw Video Stream / Download](https://raw.githubusercontent.com/Jaagruthi-Musinada/eco-loop-building-agents/main/demo_video.mp4)**

---

## 🌿 Executive Summary

Buildings consume approximately 40% of global energy and remain a primary driver of carbon emissions. Traditional Building Management Systems (BMS) rely on rigid schedules that fail to adapt to weather, occupancy, and dynamic carbon grid tariffs.

This project delivers an operational **Physical AI Closed-Loop Pipeline** calibrated for **Vijayawada, AP, India**:
1. **Simulation Sandbox**: Runs 15-minute zone timesteps (EnergyPlus C++ API or embedded high-fidelity Physics Building Simulator).
2. **MCP Tool Server**: Exposes standardized tools (`get_zone_state`, `get_targets`, `get_grid_carbon_intensity`, `set_setpoint`) with server-side thermal comfort guardrails.
3. **Cognitive Agent**: Evaluates thermal comfort (ISO 7730 PMV) vs grid carbon rates and performs **forward-injection** of dynamic setpoints (`set_setpoint`).

---

## 📊 Quantified Savings & Performance Benchmark

| Evaluation Metric | Baseline Mode | AI Closed-Loop Mode | Realized Improvement |
| :--- | :---: | :---: | :---: |
| **Total Energy Consumed** | 358.4 kWh | 291.6 kWh | **18.6% Energy Saved** |
| **Peak Electricity Demand** | 28.5 kW | 21.2 kW | **25.6% Peak Demand Shaved** |
| **Carbon Emissions** | 125.4 kg CO₂e | 93.8 kg CO₂e | **25.2% CO₂ Emission Avoided** |
| **Thermal Comfort (PMV)** | 94.2% | 98.9% | **+4.7% Comfort Compliance** |

---

## 📂 Repository Deliverables Directory

- `dashboard/app.py`: Interactive Streamlit Dashboard (Stakent dual theme, 3D Digital Twin, Plotly analytics, live simulation launcher).
- `src/`: Unified Python source code (`energyplus_wrapper.py`, `communication_bus.py`, `mcp_server.py`, `llm_agent.py`, `control_loop.py`, `main.py`).
- `models/`: Building `.idf` model files (`models/baseline.idf`, `models/baseline_modified.idf`) and weather file (`models/weather/site.epw` for Vijayawada, AP).
- `docs/ARCHITECTURE.md` / `System Architecture.md`: Comprehensive System Architecture Document.
- `demo_video.mp4` / `eco loop building.mp4`: 3-Minute PoC Video Recording.

---

## 🚀 Quick Start Guide

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/Jaagruthi-Musinada/eco-loop-building-agents.git
cd eco-loop-building-agents

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Run Baseline Simulation
```bash
python -m src.main --mode baseline
```

### 3. Run AI Closed-Loop Simulation
```bash
python -m src.main --mode closed-loop
```

### 4. Launch Quantitative Savings Dashboard
```bash
streamlit run dashboard/app.py
```
Open **`http://localhost:8501`** in your browser.

---

## 🧪 Run Unit Tests
```bash
pytest -v
```
