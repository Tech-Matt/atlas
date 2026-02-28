# `locus overview` — Feature Spec

## Purpose
Provide an instant static snapshot of a codebase's structure and identity.
No LLM required. Pure filesystem analysis.

## Command Signature
```
locus overview [PATH] [--ignore PATTERN]...
```

## Output (two sections)

### Section 1 — Stats
- Total file count, directory count, total size on disk
- Language breakdown by file extension (top 5), with a simple bar chart

### Section 2 — Project Identity (Heuristics)
- Detected project type (Python package, Node project, C project, etc.)
- Likely entry point(s)
- Test directory presence
- Notable config files (CI, linters, etc.)

## Data Model
`scan(path) -> OverviewResult` where `OverviewResult` is a dataclass.

## Edge Cases
- Empty directories
- Symlinks (skip or follow? → skip for now)
- Binary files (count but don't inspect)
- Permission errors (warn and continue)

## Out of Scope (for now)
- AST-level analysis (no docstring checking yet)
- Import graph (Phase 2)
- TUI rendering (Phase 4)