# Security Policy

## Threat model

EvoAgent is designed to keep an LLM-driven agent from causing irreversible or unobservable harm. The model is treated as untrusted. All safety, durability and rollback invariants are enforced outside the model.

The model cannot:

- Modify its own evaluator, promotion gate or hidden benchmarks.
- Sign or change trust roots.
- Bypass approvals for external or irreversible actions.
- Repeat a side effect that has already been recorded.
- Reset budgets after a crash.

## Reporting vulnerabilities

Please report security issues privately to <security@aidless.dev> (replace with your own contact before publishing). Do not open public issues for suspected vulnerabilities.

When reporting, please include:

- The affected commit or release.
- A reproducer or failing scenario.
- The impact you observed.

## Supported versions

| Version | Supported |
| --- | --- |
| latest  | yes |
| older   | best effort |

## Hardening checklist for operators

- Run with sandbox=`workspace-write` for non-system operations.
- Keep the model `reasoning_effort` aligned with what the catalog advertises.
- Disable `supports_parallel_tool_calls` for models with unstable streaming tool calls.
- Keep the answer key and the L3 hidden benchmark outside the candidate workspace.
- Always verify a signed bundle before activating any candidate.
- Restrict outbound network from worker processes.
- Rotate provider API keys regularly and never commit them to the repository.
