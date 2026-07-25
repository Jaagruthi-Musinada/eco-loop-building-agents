"""Entry point: python -m src.main --mode {baseline|closed-loop} --provider {auto|ollama|openai|autonomous}"""
import argparse
from .control_loop import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eco-Loop Building Agents")
    parser.add_argument(
        "--mode",
        choices=["baseline", "closed-loop"],
        default="closed-loop",
        help="baseline = fixed setpoint control (reference run). closed-loop = autonomous AI control.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "ollama", "openai", "autonomous"],
        default="auto",
        help="LLM provider: auto (tries local Ollama/OpenAI, falls back to autonomous AI engine)",
    )
    args = parser.parse_args()
    run(mode=args.mode, provider=args.provider)
