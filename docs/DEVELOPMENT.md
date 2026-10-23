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
$tool = (Resolve-Path '.deps/pcenginerecomp-next').Path
python scripts/prepare_private.py --evidence-root $evidence --tool-root $tool --out .local/batch-001
$module = (Resolve-Path '.local/batch-001/native-baseline/module.cpp').Path
cmake -S . -B .local/batch-001/build-baseline -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ "-DPCE_MODULE_SOURCE=$module"
cmake --build .local/batch-001/build-baseline --parallel 4
python .deps/pcenginerecomp-next/scripts/check.py --build .local/batch-001/build-baseline/upstream
python scripts/replay_route.py --tool-root $tool --evidence-root $evidence --route "$evidence/.local/boss-check/attempt8/route.json" --binary .local/batch-001/build-baseline/upstream/pce-headless.exe --out .local/batch-001/replay-baseline
```

If the upstream active build has replaced the historical binary, select its
retained immutable copy with `--source-binary HISTORICAL_BINARY`. Its SHA256
must still match the unchanged route. The receipt records that explicit
identity anchor and preserves the original command; this does not change the
candidate binary that runs or relax the input checks.

## Build the measured native subset

This requires the retained upstream raw capture and a new output batch. Keep
all artifacts private. The profile is a complete observed route; the selected
output is explicitly a frequency-ranked subset.

```powershell
python scripts/select_canonical.py --tool-root $tool --route "$evidence/.local/boss-check/attempt8/route.json" --capture "$evidence/.local/native-coverage/profile/observed-code.json" --out .local/batch-001/selection --max-identities 2048
$env:PYTHONPATH = $tool
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pcerecomp emit-capture .local/batch-001/selection/selected.json --out .local/batch-001/native-2048
python scripts/prepare_descriptor.py --tool-root $tool --inputs .local/batch-001/inputs.json --module .local/batch-001/native-2048/module.cpp --out .local/batch-001/project-native.toml
python -m pcerecomp.project build .local/batch-001/project-native.toml --build-dir .local/batch-001/build-native --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++
```

For full qualification, pass the shared descriptor/build to the route harness
using `--project-descriptor` and `--project-build`, together with the build's
`build/bin/pce-consumer` executable (`.exe` on Windows). Keep the source route
and historical binary anchor unchanged. Use `--ignore-tier-counters` only for
the candidate's intended tier change. The harness launches the shared upstream
run API, verifies its qualified receipt, and retains the original diagnostics.

Then run `scripts/qualify_coverage.py` with `--baseline-receipt`,
`--candidate-receipt`, `--reference-run`, a new `--out` JSON path,
`--min-native-fraction 0.9` and `--min-native-gain 2000000000`. This checks the
original full runner result, before/after state, images, edits and conserved
instruction totals. Only the ephemeral TCP port and named tier counters are
normalized. Source generations and device fields stay exact.

The shared development launcher is `python -m pcerecomp.project run DESCRIPTOR
--build-dir BUILD --receipt NEW_JSON --dev-port 0 --start-paused`. Connect using
the upstream TCP client. The descriptor bounds the process to 600 wall seconds;
guest saves stay volatile. The upstream API's explicit `--desktop` build option
accepts a matching existing SDL SDK, but this consumer batch qualifies only the
headless host and its guest-frame output.

## Expand to all eligible observed code

`scripts/expand_native.py` uses the same pinned upstream `emit_capture` API
against the original complete capture. It verifies the restored patch journal,
excludes entire temporary-code spans through the upstream range-selection
interface, and rejects any other recorded assist that overlaps observed source.
It preserves the original capture hash, hit totals and completeness, reporting
excluded identities/retirements separately. Generated files stay private.

```powershell
$batch = '.local/batch-002'
python scripts/expand_native.py --tool-root $tool --route "$evidence/.local/boss-check/attempt8/route.json" --capture "$evidence/.local/native-coverage/profile/observed-code.json" --out "$batch/native-observed"
python scripts/prepare_descriptor.py --tool-root $tool --inputs .local/batch-001/inputs.json --module "$batch/native-observed/module.cpp" --out "$batch/project-native.toml"
python -m pcerecomp.project build "$batch/project-native.toml" --build-dir "$batch/build-native" --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++
```

Use a new batch directory and redirect compiler/Python Temp there. Reuse the
retained raw capture and input configuration read-only. Emission and build
receipts are not execution evidence.

Long TCP routes may use the replay harness's explicit `--project-verify-only`
with `--project-descriptor` and `--project-build`. The official upstream
`project verify` command checks the descriptor, source, module and inputs before
and after; the consumer binds that result to the original build receipt and
checks the exact executable/adjacent-output hashes. It launches the original
route arguments under the consumer's 1,800-second watchdog. The descriptor's
600-second `project.run` wall limit is explicitly not applied in this mode;
the receipt records that distinction. Normal mode still uses `project.run`.
Do not call a verify-only replay a shared `project.run` qualification.

Compare against the previous consumer replay using `qualify_coverage.py` with
`--allow-baseline-tier-change`. This permits only the named tier-counter splits
between that previous baseline and the original runner reference, conserving
retired/block totals and every other diagnostic. The new candidate still has
to match images, edits, inputs and guest state. For this batch the gates are
`--min-native-fraction 0.999999 --min-native-gain 136000000`; the known excluded
span accounts for 981 original-profile retirements. Report the actual remainder
and retain any failed bounded attempt separately.

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
