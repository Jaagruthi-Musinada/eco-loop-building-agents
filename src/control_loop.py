"""
Control Loop Orchestrator.

Ties everything together:
  - Starts EnergyPlus or Physics Simulator in a background thread
  - On the main thread, polls the bus and triggers LLM agent decision cycles
  - Logs structured telemetry + LLM actions + reasoning to JSONL for dashboard rendering
"""
from __future__ import annotations
import argparse
import json
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger("eco_loop")


from . import config
from .communication_bus import bus
from .energyplus_wrapper import EnergyPlusWrapper
from .llm_agent import LLMAgent


def run(mode: str = "closed-loop", provider: str = "auto") -> Path:
    control_enabled = (mode == "closed-loop")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = config.LOG_DIR / f"run_{mode}_{run_id}.jsonl"
    logger.info(f"Starting run '{mode}' (provider={provider}), logging to {log_path}")

    # Reset bus for clean run context
    bus.clear()

    wrapper = EnergyPlusWrapper(control_enabled=control_enabled)
    sim_thread = threading.Thread(target=wrapper.run, daemon=True)
    sim_thread.start()

    agent = LLMAgent(provider=provider) if control_enabled else None
    last_seen_tick = -1

    with open(log_path, "w", encoding="utf-8") as log_file:
        while sim_thread.is_alive():
            time.sleep(0.05)
            state = bus.get_state()
            if not state:
                continue

            tick = wrapper._tick_count
            record = {
                "ts": time.time(),
                "sim_time": state.get("sim_time"),
                "mode": mode,
                "state": state,
            }

            due = (
                control_enabled
                and tick != last_seen_tick
                and tick % config.AGENT_DECISION_INTERVAL_TIMESTEPS == 0
            )
            if due:
                last_seen_tick = tick
                reasoning = agent.run_decision_cycle()
                record["llm_reasoning"] = reasoning
                logger.info(f"[Step {tick}] {reasoning}")

            log_file.write(json.dumps(record) + "\n")
            log_file.flush()

    sim_thread.join(timeout=5.0)
    logger.info(f"Run complete. Log saved at {log_path}")
    return log_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "closed-loop"], default="closed-loop")
    parser.add_argument("--provider", choices=["auto", "ollama", "openai", "autonomous"], default="auto")
    args = parser.parse_args()
    run(args.mode, args.provider)
