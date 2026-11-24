# EvoAgent

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  [![CI](https://github.com/aidless/evoagent/actions/workflows/audit.yml/badge.svg)](https://github.com/aidless/evoagent/actions/workflows/audit.yml)

Package **0.1.0** (`pyproject.toml`, `src/evoagent/__init__.py`). The audit workflow runs on Python 3.12 and executes `make check`.

## Problem

EvoAgent scores a JSON config on a frozen benchmark in a temporary directory, and it atomically promotes that config only when a safety check and a minimum-gain compare both pass, keeping a rollback snapshot.
`make check` recomputes this on a toy benchmark of 4 string cases: the seed passes 1/4, and a hand-written mutation list already contains the flag pair that passes 4/4. That is the controller mechanic, not evidence that an agent improved.
With the statistical gate shipped in `evo.json` left on, that 1/4 to 4/4 score change is rejected. Scores that need `benchmarks/raw/` or a private model run are not produced here.

## Run

Declared third-party imports are `cryptography` and `requests` (see `requirements.txt`). The toy loop itself is standard-library code. One install needs network; `make check` does not download data and does not call a model.

```bash
python3 -m pip install -e .
make check
```

`make check` runs `python3 -m unittest discover -s tests` and then `python3 scripts/toy_trace.py --check evidence/toy-trace.json`. The second command reruns the controller and diffs the stable fields against the committed trace. A mismatch exits 1. Some tests skip when a private registry or local model weights are absent. A skip is not a pass of that private data.

Manual equivalent, from a clean tree, if you only want the toy loop:

```bash
PYTHONPATH=src python3 -m evoagent.cli init
PYTHONPATH=src python3 -m evoagent.cli evolve
PYTHONPATH=src python3 -m evoagent.cli status
```

On the shipped `evo.json`, `evolve` does **not** promote. The legacy score rule would, and the statistical gate rejects the sample (McNemar p = 0.25). The post-step that reads `benchmarks/raw/gsm8k-test.jsonl` records `verified: false` because that file is not in the repository.

## What the trace records

Source: `scripts/toy_trace.py`. Artifact: `evidence/toy-trace.json`. Failure notes: `FAILURE_MODES.md`.

| State | Measured result |
|---|---|
| Shipped config, seed to the authored 4/4 candidate | `legacy_promoted: true`, `promoted: false`, reason `mcnemar_not_significant`, active id stays `1edc29a02951` (the seed) |
| Statistical gate off | Promotes the authored `normalize_case` + `trim_whitespace` candidate, id `f8a196f466db`, score 4/4 |
| Next round from that candidate | No gain. All three menu entries are the same id. `promoted: false` |
| Statistical gate off, only the case-fold mutation | Promotes a 2/4 candidate. Gain is 0.25, and `min_gain` is 0.01 |
| Safety | `shutdown /s` is rejected. `{"cmd":"shutdown","flag":"/s"}` is accepted |
| Rollback | Restores the seed. A rewritten snapshot is installed with no hash check. A non-JSON snapshot leaves `active.json` unreadable and deletes the history file |

Wall-clock fields (`duration_s`, `latency_s`, `latency_increase`, `run_id`) are not part of the diff. `latency_regression` is omitted from stored reason lists because a slow host can add it without changing this sample's decision.

## Plateau sentence

`research/findings.md` says ten rounds stayed at score 1.0 on active id `f8a196f466db`. That id is the content hash of the solved toy policy above, and `make check` recomputes one follow-up round that does not promote. No committed JSON or JSONL file contains ten rounds. The ten-round count is not a result of this repository.

## Not results

These appear in older notes and are **not** recomputed by `make check`. Do not cite them as outcomes of a fresh clone.

- Model scores in the previous README (including 135/135 and 40.0% vs 33.3%). They are not in a rerunnable data file here.
- Soak cycle counts in `docs/p0-durable-runtime-and-soak-report.md`.
- `benchmarks/registry-v2/summary.json` records `tasks: 360`. The task and answer files next to it are redacted stubs, so that count is a label, not a run.
- Anything under `benchmarks/raw/`. That directory is gitignored.
- `research/prompt-candidates*/` JSON files record an author-machine GGUF path and are not a setup guide.

Workstation absolute paths in those older notes are the author's machine layout from the day they were written. They are not setup instructions. This README has none.

## GitHub About

The repository description is not stored in git. As of this change it still says the plateau is documented, which this tree does not support. Replacement text, within GitHub's 350-character description limit:

```text
Toy config controller (v0.1.0): safety gate, min-gain compare, atomic promote, rollback. The demo is 4 string cases, not real agent improvement. make check recomputes the trace.
```

## Layout

```text
src/evoagent/     controller (evolve, safety_check, rollback)
examples/         4-case benchmark and evaluator
scripts/toy_trace.py
evidence/toy-trace.json
tests/            unittest suite run by make check
```

The shipped loop edits JSON configs. It does not rewrite its own Python.
