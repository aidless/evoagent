from __future__ import annotations

import argparse
import json
from pathlib import Path

from .autonomy import EvolutionPolicy, evolve_autonomously
from .core import candidate_id, evaluate, evolve, load_json, propose, rollback, save_json
from .experience import AdaptiveProposer, ExperienceStore


def init(root: Path) -> None:
    (root / ".evo" / "runs").mkdir(parents=True, exist_ok=True)
    (root / ".evo" / "history").mkdir(parents=True, exist_ok=True)
    seed = root / "seed.json"
    if not (root / ".evo" / "active.json").exists():
        save_json(root / ".evo" / "active.json", load_json(seed))


def main() -> None:
    parser = argparse.ArgumentParser(prog="evoagent")
    parser.add_argument(
        "command", choices=["init", "evolve", "autoevolve", "status", "rollback"]
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument("--patience", type=int)
    parser.add_argument("--max-candidates", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "init":
        init(root)
        print(
            json.dumps(
                {
                    "initialized": str(root),
                    "active_id": candidate_id(load_json(root / ".evo" / "active.json")),
                }
            )
        )
    elif args.command == "evolve":
        print(json.dumps(evolve(root), ensure_ascii=False, indent=2))
    elif args.command == "autoevolve":
        config = load_json(root / "evo.json")
        policy = EvolutionPolicy.from_config(config)
        if args.max_rounds or args.patience or args.max_candidates:
            policy = EvolutionPolicy(
                max_rounds=args.max_rounds or policy.max_rounds,
                max_candidates_per_round=args.max_candidates
                or policy.max_candidates_per_round,
                patience=args.patience or policy.patience,
                min_gain=policy.min_gain,
                require_statistical_gate=policy.require_statistical_gate,
                allow_revisit=policy.allow_revisit,
            )
        store = ExperienceStore(root / ".evo" / "experience.json")
        adaptive = AdaptiveProposer(store, propose)
        result = evolve_autonomously(root, evaluate, adaptive, policy)
        print(json.dumps(result.report, ensure_ascii=False, indent=2))
    elif args.command == "status":
        active = load_json(root / ".evo" / "active.json")
        status = {"active_id": candidate_id(active), "candidate": active}
        memory = ExperienceStore(root / ".evo" / "experience.json")
        status["experience"] = memory.summary()
        autonomy = root / ".evo" / "autonomy-last.json"
        if autonomy.exists():
            last = load_json(autonomy)
            status["last_autonomy"] = {
                "run_id": last.get("run_id"),
                "promoted": last.get("promoted"),
                "stop_reason": last.get("stop_reason"),
            }
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"rolled_back": str(rollback(root))}))


if __name__ == "__main__":
    main()
