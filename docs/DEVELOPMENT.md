# Consumer development

Read the pinned tool's `AGENTS.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`,
`docs/CONSUMER.md` and `docs/AUDIO_OUTPUT.md` before changing integration.
Keep its active checkout untouched. Use an isolated clean dependency at the
manifest pin and one new private scratch batch. Keep all older qualified
artifacts and original inputs unchanged.

## Regenerate and build for ABI 13

The current pin accepts retained ABI-12 observation captures for regeneration.
It requires new ABI-13 translations and a matching runtime; never reuse ABI-12
compiled objects. Full MPR mappings and exact source bytes still guard execution.
The partitioned manifest pins every translation unit and generated header.
Preserve the entire generated directory. The consumer delegates generation,
CPU/device/audio semantics and build identity to the shared tool.

These commands require the existing private evidence and input configuration;
substitute their locations. Use a fresh batch, redirect Python/compiler Temp
there, and reuse immutable dependencies/media read-only.

```powershell
$evidence = 'TOOL_EVIDENCE_ROOT'
$tool = (Resolve-Path '.deps/pcenginerecomp-audio').Path
$batch = '.local/batch-003'
New-Item -ItemType Directory -Path "$batch/temp" -Force
$env:TEMP = (Resolve-Path "$batch/temp").Path
$env:TMP = $env:TEMP
$env:PYTHONPATH = $tool
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python scripts/verify_tool.py --tool-root $tool
python scripts/expand_native.py --tool-root $tool --route "$evidence/.local/boss-check/attempt8/route.json" --capture "$evidence/.local/native-coverage/profile/observed-code.json" --out "$batch/native-observed"
python scripts/prepare_descriptor.py --tool-root $tool --inputs .local/batch-001/inputs.json --module "$batch/native-observed/module.cpp" --audio on --out "$batch/project-native.toml"
python -m pcerecomp.project build "$batch/project-native.toml" --build-dir "$batch/build-native" --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++
```

`expand_native.py` validates restoration of the journaled temporary code patch,
excludes its entire physical span across all mappings/source variants through
the upstream range-exclusion API, and refuses any other assisted write that
intersects observed instruction-fetch bytes. The original complete capture
hash, hit totals and completeness stay intact. Counts from emission/build
receipts establish no execution coverage on their own.

`prepare_descriptor.py` derives the ABI from the verified tool and accepts
`--audio on|off`. Schema 1 retains explicit tool/source/module/input hashes,
loader/MPR values, response profile and limits. Initial formatted blank BRAM
is a read-only seed; guest writes remain volatile. No owner install/save is used.

## Verify the retained route with audio

Preserve the immutable route and historical executable anchor. It contains
ordinary-input checkpoints and separately journaled assisted progression;
this batch adds no edits. The source route and all expected-byte transactions
must remain unchanged. Select the old executable with `--source-binary` if
its original build location has changed; its hash must still match the route.

Run the same full route twice through `scripts/replay_route.py`, with the
following shared arguments and a fresh output directory for each run:

```powershell
$binary = "$batch/build-native/build/bin/pce-consumer.exe"
$common = @('--tool-root', $tool, '--evidence-root', $evidence,
  '--route', "$evidence/.local/boss-check/attempt8/route.json",
  '--binary', $binary, '--source-binary', 'HISTORICAL_BINARY',
  '--project-descriptor', "$batch/project-native.toml",
  '--project-build', "$batch/build-native",
  '--project-verify-only', '--ignore-tier-counters')
python scripts/replay_route.py @common --audio-output off --out "$batch/replay-audio-off"
python scripts/replay_route.py @common --audio-output on --audio-frames 1323000 --out "$batch/replay-audio-on"
```

The explicit audio override is appended to the frozen guest argument vector
and recorded separately. This mode uses the consumer's 1,800-second watchdog.
Official `project verify` and the complete immutable build/output binding are
checked before/after. The descriptor's 600-second `project.run` limit is
explicitly not applied. This is consumer-supervised qualification, not a
shared `project.run` execution qualification.

The audio-on run creates only a bounded new `audio.wav` in its output directory.
The 1,323,000-frame cap retains the first 30 guest seconds; it does not limit
route duration. The harness checks PCM format, file size, frame count/hash and
truncation telemetry. Headless PCM generation opens no playback device.

Then qualify each replay with `scripts/qualify_audio.py`:

```powershell
python scripts/qualify_audio.py --baseline-receipt .local/batch-002/replay-native-extended/receipt.json --candidate-receipt "$batch/replay-audio-on/receipt.json" --reference-run "$evidence/.local/boss-check/attempt8/run.json" --audio-reference-run "$evidence/.local/audio-batch/native-desktop-final/run.json" --audio-output on --out "$batch/audio-on-qualified.json"
```

Use the audio-off candidate and `--audio-output off` for the bridge. The
qualifier preserves all original diagnostics, images, checkpoint states,
source generations, mappings, clocks, edit counts and total native/interpreted
work. It separately validates only the added ABI-13 headless `audio_output`
object, rejecting unknown fields, malformed values or runtime queue loss.
Audio-on PCM fields must match the retained shared-tool result exactly;
audio-off must omit the PCM object exactly as the reference runner does.
Existing native counts must
stay exact, including guard misses and block transfers. Unlike a coverage
expansion, this upgrade permits no tier redistribution or native-count gain.
That comparison is reproducibility within the shared implementation, not an
independent whole-route audio/console oracle.

## Optional SDL and authored checks

Use the official build command's `--desktop` and explicit `SDL3_DIR` to select
an existing SDK. The current pin has a Windows embedded-consumer packaging
issue: it can omit `SDL3.dll` beside the executable. The verified paced test
uses a child-only SDK `bin` search path with an explicit DLL hash, while keeping
the source, build receipt and adjacent-output set unchanged. This establishes
SDK-backed execution, not a self-contained desktop package. The defect is
reported upstream; adopt a fix only in a deliberate later pin upgrade.

Normal guest-paced SDL output and headless full-route PCM have distinct
receipts. Unthrottled desktop output intentionally mutes speakers while PCM
and WAV continue. Check device-open success, fast-forward mute, source loss,
submitted/dropped/queued frames, pause freeze/queue clearing and resumed
advancement. A dummy device or accepted/drained SDL stream does not establish
what a listener hears, analog levels or independent mixed-audio parity.

Build the consumer's authored sandbox tests and run the pinned upstream
`scripts/check.py` fallback plus `python -m unittest discover -s tests -v`.
For an embedded SDL test build, the upstream fallback finds its binaries in
`build/upstream` but its desktop detection expects a cache in that directory.
Run the same Python suite with explicit `PCE_TEST_HEADLESS`/`PCE_TEST_DESKTOP`
paths, then `pce-desktop-tests` and `pce-audio-host-tests` as well. SDL dummy
video/audio drivers are appropriate for these authored host suites. Retain
actual skips and suite results, separately from the real-device test.

## Publication and future batches

Read source and affected contracts before deliberately upgrading `toolchain.json`.
Pins identify a complete clean commit, exact source digest and matching ABI.
Preserve initial/historical qualification and record the actual compiler/options,
all generated-artifact hashes and input identities privately.

Use exactly 1,073,741,824 bytes of new disposable-output allowance per coherent
batch, shared with jointly running upstream work. Account for builds, generated
source, captures/logs, dependencies and external Temp/CrashDumps growth. Reuse
existing artifacts; do not delete unrelated files to make room. Stop owned
processes and retain small reproducible receipts.

Stage only explicit authored files, review `git diff --cached`, then run
`git diff --cached --check` and `python scripts/audit_public.py` before pushing.
Never publish media, game-generated source/captures/PCM, saves, private paths,
receipts or chat coordination. The audit is a focused check, not a complete
legal or secret scanner. Unvisited code and new progression need fresh bounded
execution evidence; current audio/coverage checks are not campaign completion.
