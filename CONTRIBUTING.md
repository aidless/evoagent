# Contributing to EvoAgent

Thanks for your interest in improving the agent. Contributions are welcome through issues and pull requests.

## Before opening a pull request

- Search existing issues to avoid duplicates.
- Discuss large refactors in an issue first.
- Keep changes focused and reviewable.
- Do not commit API keys, private signing material, hidden benchmark answers or local run artifacts.

## Development setup

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

The project requires Python 3.10 or newer and depends on `cryptography` for signed bundles.

## Coding style

- Keep modules small and single purpose.
- Put the security gate outside the model; never rely on prompt instructions alone.
- New side effects must declare a `ToolManifest`.
- New persistent actions must update `RunState` and emit a hash-linked `EventLog` entry.
- New tests must cover both the happy path and at least one failure or recovery path.

## Pull request checklist

- Tests added or updated.
- `compileall` runs clean.
- Sensitive data scrubbed.
- Documentation updated for any user-visible change.
- Commit message references the relevant issue or design note.

## Code of conduct

Be respectful. Focus on the work, not the person. Assume good intent.
