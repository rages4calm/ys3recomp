# Consumer development

Read the pinned tool's `AGENTS.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md` and
`docs/DEVELOPMENT.md` before changing integration. Do not alter its active
checkout. Use an isolated clean dependency at the manifest pin, and place
consumer outputs under one private scratch batch.

## Reproduce the retained qualified route

These commands require the existing private upstream evidence and read-only
inputs. Substitute its location for `TOOL_EVIDENCE_ROOT`. It is distinct from
the immutable source dependency. Commands below use PowerShell variables.

```powershell
$evidence = 'TOOL_EVIDENCE_ROOT'
$tool = (Resolve-Path '.deps/pcenginerecomp').Path
python scripts/prepare_private.py --evidence-root $evidence --tool-root $tool --out .local/batch-001
$module = (Resolve-Path '.local/batch-001/native-baseline/module.cpp').Path
cmake -S . -B .local/batch-001/build-baseline -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ "-DPCE_MODULE_SOURCE=$module"
cmake --build .local/batch-001/build-baseline --parallel 4
python .deps/pcenginerecomp/scripts/check.py --build .local/batch-001/build-baseline/upstream
python scripts/replay_route.py --tool-root $tool --evidence-root $evidence --route "$evidence/.local/boss-check/attempt8/route.json" --binary .local/batch-001/build-baseline/upstream/pce-headless.exe --out .local/batch-001/replay-baseline
```

If the upstream active build has replaced the historical binary, select its
retained immutable copy with `--source-binary HISTORICAL_BINARY`. Its SHA256
must still match the unchanged route. The receipt records that explicit
identity anchor and preserves the original command; this does not change the
candidate binary that runs or relax the input checks.

Preparation verifies the canonical `execution-boss.json` linked receipts and all
protected inputs, records local input paths/hashes privately and regenerates
the initial module through the upstream frontend. It copies no media. Output
directories must be new. Keep Python/compiler Temp under the batch as well.

Replay imports the verified upstream TCP client. It preserves loader, input,
response-profile and edit-journal arguments; compares retained guest image
hashes and exposed final guest diagnostics; then quits its own child. It writes
bounded logs and receipts only to its selected output directory. It creates
no extra image copies. A changed module may use `--ignore-tier-counters` to
compare guest results while allowing only `native_steps`/`interpreter_steps`
to differ. Source generations, PC, mappings, clocks and device fields remain
subject to comparison. This is internal reproducibility evidence, not a second
independent implementation or hardware test.

The retained route includes ordinary-input and assisted progression. Each
expected-byte memory transaction is replayed at its recorded pause. Temporary
jump code was restored before the final encounter. Do not use a patched code
capture for native promotion. Preserve unassisted checkpoints and label the
assisted portion independently.

## Deliberate upgrades

Change `toolchain.json` only after reviewing the new upstream contract and
affected tests. Keep the initial qualified revision in qualification history.
A temporary CMake `PCE_EXPECTED_REVISION` override must be a full clean commit
and still satisfy the manifest ABI. Record all actual options, source identity,
compiler, generated-module identity and input hashes in the private receipt.
Never use an override to conceal an uncommitted tool patch.

Use observed PCs, full MPR maps and exact source identities to choose a bounded
coverage milestone. Retain unresolved returns, indirect jumps, mappings and
source variants. A native source guard must reject changed overlay bytes before
retirement. Compare native/interpreted retired totals over the same route and
report game-specific rendering and assistance independently.

## Output and publication

The allowance is exactly 1 GiB of new disposable output per coherent batch,
shared with upstream when jointly running. Account for every named build,
dependency, Temp, log and capture root. Reuse immutable inputs and dependencies.
Do not silently substitute a smaller or larger allowance.

Run consumer tests and affected upstream checks. Stage explicit authored files,
inspect `git diff --cached`, then run `python scripts/audit_public.py` and
`git diff --cached --check` before publication. The audit is a bounded focused
check, not a complete legal or secret scanner. `.gitignore` alone is insufficient.
Never publish private receipts, media bytes, translated game code, captures,
saves, local machine paths or coordination IDs.
