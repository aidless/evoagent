# FAILURE_MODES

Measured by `scripts/toy_trace.py` and stored in `evidence/toy-trace.json`.
`make check` reruns the controller and fails if the stable fields change.
These are properties of the toy 4-case loop. They are not measurements of a
trained agent.

The benchmark is `examples/benchmark.json`: four strings. The evaluator
passes a case when optional `trim_whitespace` / `normalize_case` flags make
the input match the expected string. `seed.json` sets both flags to false
and passes 1/4.

## Benchmark overfitting / Goodhart

`evo.json` ships a mutation menu of three hand-written flag dicts. The third
is `{"normalize_case": true, "trim_whitespace": true}`, which is the exact
pair the evaluator rewards.

With the statistical gate turned off, `evolve` promotes that authored
candidate (`f8a196f466db`) and the score goes from 1/4 to 4/4. The trace
field `promoted_candidate_equals_authored_mutation` is true. The loop
selected a listed config. It did not search for a policy, and this demo has
no hidden set.

## min_gain noise

Shipped `min_gain` is 0.01. One case is 0.25 of the score, so the legacy
rule cannot reject a single lucky case.

Measured with the statistical gate off and a menu that contains only
`{"normalize_case": true}`: the candidate scores 2/4, the gain is 0.25, and
`evolve` promotes it (`legacy_gate_promotes_one_case_gain`).

Measured with the shipped statistical gate left on, against the authored
4/4 candidate: `legacy_promoted` is true and `promoted` is false. The stored
reason is `mcnemar_not_significant` (p = 0.25, n = 4). The bootstrap
interval on this seed is [0.25, 1.0], so `bootstrap_ci_not_positive` does
not fire. That reject is a property of this 4-row sample, not a calibrated
claim about noise in a real benchmark.

`latency_increase` moves between runs. The trace drops `latency_regression`
if a slow host adds it. On the runs used to write the file, latency stayed
inside the 20% budget, so the reject did not depend on it.

## Safety gate bypass

`safety_check` rejects a candidate when its canonical JSON is larger than
`max_candidate_bytes` or contains a `forbidden_tokens` substring
(case-insensitive). Shipped tokens include `shutdown /s` and `rm -rf`.

Caught (`forbidden_token_caught`): `{"instruction": "please shutdown /s"}`
returns `forbidden_token:shutdown /s`.

Not caught (`forbidden_token_bypass_split_fields`):
`{"cmd": "shutdown", "flag": "/s"}` returns `safe: true`, `reason: "ok"`.
The token is split across fields, so the substring is absent.
`{"note": "shutdown  /s"}` (two spaces) is also accepted. The gate does not
look at what the evaluator will do.

## Rollback corruption

`rollback` copies the newest `.evo/history/*.json` onto `.evo/active.json`
and then deletes that history file. It does not hash the snapshot.

Measured (`rollback_restores_seed`): after a real promotion, rollback
restores the seed and the history directory is empty.

Measured (`rollback_installs_tampered_snapshot`): replacing the snapshot
bytes with other JSON makes rollback install that JSON
(`active_equals_tampered_json: true`). That path does not compare a hash
before the copy.

Measured (`rollback_corrupt_snapshot_drops_history`): replacing the snapshot
with `{not json` raises `JSONDecodeError` after `active.json` has been
overwritten and the history file has been unlinked. The previous active
policy is gone, and so is the only snapshot.

## Not a measured failure

`research/findings.md` says ten rounds plateaued at `f8a196f466db`. That id
is the solved toy policy. The trace records one follow-up round that does
not promote, and `json_files_with_that_id_excluding_this_trace` is empty.
The ten-round count stays prose.
