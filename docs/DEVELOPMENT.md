# Consumer development

Read the pinned tool's `AGENTS.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`,
`docs/CONSUMER.md` and `docs/AUDIO_OUTPUT.md` before changing integration.
Keep its active checkout untouched. Use an isolated clean dependency at the
manifest pin and one new private scratch batch. Keep all older qualified
artifacts and original inputs unchanged.

## Regenerate and build for ABI 13

The current capture-only pin keeps ABI 13 and descriptor schema 1 unchanged.
The coverage expansion composes the retained profile with a fresh restored-source
window, then uses the shared emitter to generate 208 translation units and one
header. All 209 source artifacts are bound to the new module manifest. The old
208-artifact module remains unchanged for the baseline comparison. Rebuild
compiled objects when changing generated sources or the pinned runtime.

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
$tool = (Resolve-Path '.deps/pcenginerecomp-capture').Path
$batch = '.local/new-private-batch'
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

## Select and qualify filtered audio

With the current `.deps/pcenginerecomp-capture` checkout, descriptor preparation
also accepts `--audio-profile raw|filtered` and `--audio-rate 44100|48000`.
These require `--audio on`; raw 48 kHz is rejected. Omitting both preserves the
original raw 44.1 kHz descriptor and PCM schema. Filtered without a rate selects
44.1 kHz. For example, prepare a new descriptor using the retained ABI-13 module:

```powershell
python scripts/prepare_descriptor.py --tool-root $tool --inputs .local/batch-001/inputs.json --module .local/batch-003/native-observed/module.cpp --audio on --audio-profile filtered --audio-rate 48000 --out "$batch/project-filtered-48000.toml"
```

Build each descriptor through the shared `pcerecomp.project build` command.
For packaged route verification, use its corresponding executable, descriptor
and build directory with `replay_route.py --desktop-packaged --audio-output on
--audio-profile filtered --audio-rate 48000 --audio-frames 1440000`. Keep the
original route, historical executable anchor and other arguments shown below.
Run a separate explicit `raw` / `44100` bridge with a 1,323,000-frame WAV cap.
Each run needs its own new output directory. Profile/rate overrides are recorded
and must agree with the official descriptor; they cannot be hidden in the
frozen original route arguments.

The raw bridge must match the previous qualified raw route exactly. The
filtered 48 kHz candidate must match a separately retained new headless
reference, including processed PCM and WAV bytes. At every checkpoint, all
original guest/native/source diagnostics and the filtered profile's raw source
PCM projection must match the old raw route. Source activity stays in the
44.1 kHz domain; processed frame counts, WAV and queue telemetry use output
frames. The exact 48 kHz count is `floor(source_frames * 160 / 147)`, with
31 source frames of latency and no flushed tail. Intermediate desktop pending
frames must fit the 8,192-output-frame ring; final pending frames must be zero.

Use the distinct schema-2 DSP qualifier with a reviewed, hash-bound expectation:

```powershell
python scripts/qualify_dsp.py --baseline-receipt OLD_RAW_RECEIPT --raw-receipt NEW_RAW_RECEIPT --candidate-receipt NEW_FILTERED_RECEIPT --audio-expectation REVIEWED_DSP_EXPECTATION --out NEW_QUALIFICATION
```

Its expectation binds the exact tool/source/ABI, original route and blank seed,
raw bridge, processed reference run/receipt/WAV, actual upstream qualification
and independently reviewed Gear evidence. It accepts only the finite raw
44.1 kHz to filtered 48 kHz comparison; no generic list of guest or PCM fields
may be ignored. Official descriptor/build, executable and adjacent DLL are
rehashed. Earlier schema-1 qualification remains unchanged.

`wav_metrics.py analyze WAV --out NEW_JSON` records exact integer PCM metrics;
`wav_metrics.py compare LEFT RIGHT --out NEW_JSON` compares equal-rate,
equal-length PCM16 stereo WAVs. It preserves and rechecks both inputs, rejects
geometry mismatches and never resamples or infers perceptual quality.

Keep paced device checks separate from the unthrottled full route. At both
filtered rates, verify actual device-open/mute state, queried SDL format/rate,
bounded queue and drops, pause freeze, resume advance, TCP input and captures,
loaded package identity and protected inputs. Filtered 44.1 kHz has an identity
output resampler; a CDDA-dominated opening can remain identical to raw PCM.
Device acceptance does not establish listening, analog or hardware parity.

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
an existing SDK at build time. The current pin packages `SDL3.dll` beside the
consumer executable and includes it in the official build/output binding.
A missing or changed packaged DLL invalidates the retained build. The prior
SDK-PATH workaround remains historical evidence only.

For a packaged full-route replay, select the official desktop binary/build and
add `--desktop-packaged --audio-output on --audio-frames 1323000` to the replay
arguments above. The mode requires `--project-verify-only`. It resolves the
existing guest input arguments to the same absolute files, creates a new empty
working directory, strips empty/relative and all SDL-containing directories
(including packaged bin) from child PATH, and clears SDL dummy-driver overrides.
The private receipt retains exact original/child PATH and removed entries.

The harness runs hidden and unthrottled. At initial and final guest pauses,
Windows process-module inspection binds the same PID and executable to the
actual loaded SDL path/hash; it must equal the adjacent packaged DLL. Official
project bindings and exact adjacent outputs are checked before and after.

Qualify with `scripts/qualify_desktop.py --baseline-receipt` pointing to the
retained completed headless audio-on receipt, `--candidate-receipt` pointing
to the new packaged replay receipt, and a new `--out`. The qualifier separately
checks exact desktop audio/presentation schemas and muted-device accounting,
then compares every original guest diagnostic, all checkpoint states/images,
native/interpreted/block/guard counts, core PCM and bounded WAV hash to the
headless baseline. No original guest field is projected away. This proves
same-route packaged execution and digital reproducibility, not full-game or
independent analog/audio parity.

Normal guest-paced SDL output and headless full-route PCM have distinct
receipts. Unthrottled desktop output intentionally mutes speakers while PCM
and WAV continue. Check device-open success, fast-forward mute, source loss,
submitted/dropped/queued frames, pause freeze/queue clearing and resumed
advancement. A dummy device or accepted/drained SDL stream does not establish
what a listener hears, analog levels or independent mixed-audio parity.

Build the consumer's authored sandbox tests and run the pinned upstream
`scripts/check.py` fallback plus `python -m unittest discover -s tests -v`.
The current pin discovers the parent CMake cache and SDK in an embedded SDL
build. The unchanged checker at `--build build/upstream` runs all 28 shared
suites and 294 Python tests without a discovery adapter or test-path overrides;
the fresh qualified embedded build has zero skips. SDL dummy video/audio
drivers are appropriate for authored host suites. The separate clean default
configuration intentionally skips eight desktop tests. Retain actual skips
and suite results separately from the real-device test.

## Extend coverage with a restored-source capture window

The capture-only ABI-13 pin adds `--code-capture-start-frame` to the shared
host. Use the consumer's managed `replay_route.py --capture-start-frame FRAME`
option rather than embedding output flags in the immutable route. The chosen
frame must be an existing paused checkpoint before the route ends and strictly
after every journaled code patch has been restored. `--capture-limit` optionally
selects 1 through 65,536 identities; the managed default is 65,536.

The supervisor reads back every restored original byte, retains the full
logical PC, eight MPRs, physical fetch addresses, bytes, generations and counters,
and checks that the guest stays paused through that proof. Only then does the
next advance begin. Capture output is a new `observed-code.json` in the replay
directory. The shared loader checks its format, exact source mappings, complete
retirement accounting and zero loss. The runner's actual start frame, ticks and
native/interpreted counters must match the paused proof, and observed retirements
must equal the final-minus-start count. An unreached or ambiguous window fails.
Direct or shared-verify-only supervision is required; the shared `project.run`
wrapper is not used for managed capture.

The existing assisted prefix temporarily changes code before restoring it.
Do not capture that prefix from launch. Keep its prior immutable profile and
collect new instructions only after restoration. Observation files and generated
code remain private, including excluded source variants.

`merge_observations.py` composes two to sixteen complete profiles through the
verified shared capture API. Its private manifest uses schema 1 and kind
`ys3-observation-union`, an explicit `output_runtime_abi` of 12 or 13, and an
`inputs` list. Each input binds a capture path/SHA256 plus an `epoch` with a
unique label, declared start/end frames and hash-bound evidence paths. For example:

```sh
python scripts/merge_observations.py --tool-root TOOL --manifest PRIVATE_MANIFEST --out NEW_PRIVATE_PROFILE
python scripts/expand_native.py --tool-root TOOL --route EXTENDED_ROUTE --capture NEW_PRIVATE_PROFILE/observations.json --out NEW_PRIVATE_MODULE
```

The union retains exact PC/all-MPR/physical/source-byte identities, separate byte
variants and summed original tier hits. It rejects incomplete inputs, overflow
and excess capacity. Its epochs are provenance declarations bound to evidence;
the combined profile is not a single execution or measured native gain.
Emission still excludes every byte of each verified temporary-code span across
all mappings and checks all assist writes against observed instruction fetches.

Build the old and expanded modules with the same verified capture-only pin,
descriptor inputs and filtered 48 kHz audio selection. Replay the same frozen
extended route with the same managed capture boundary on both packages, then run:

```sh
python scripts/qualify_native_audio.py --baseline-receipt OLD_MODULE_RECEIPT --candidate-receipt EXPANDED_MODULE_RECEIPT --prefix-frame ORIGINAL_ENDPOINT --min-native-gain 1 --out NEW_QUALIFICATION
```

This finite ABI-13 qualifier requires every original guest/source diagnostic,
image, assist and processed/raw PCM value to match at every checkpoint and three
endpoint observations. WAV bytes stay exact. Native/interpreted and block totals
are conserved while their tier split may change; positive native gain is required
both overall and after the prefix endpoint. Both raw window captures must retain
identical source identities and per-identity total hits. Only a fully validated
runner capture-window object is handled separately. Actual descriptor/build,
module sources, executable, DLL, protected inputs and captures are rehashed.
Unreviewed ABIs, timing profiles or capture contracts are refused.

Long frontier sessions must keep the TCP connection active: the server closes
an idle connection after five seconds. A paused status heartbeat preserves the
connection without advancing guest time. Keep exploration bounded and retain
failed attempts separately. The boot WAV cap does not reach a late frontier;
cumulative PCM hashes and new checkpoint counters qualify its digital output.
Do not describe the boot WAV as an audible recording of the later encounter.

## Publication and future batches

For an intentional sound correction, retain the old packaged route and compare
the new packaged replay with `scripts/qualify_audio_upgrade.py`. Its
`--baseline-receipt`, `--candidate-receipt`, `--audio-expectation` and `--out`
arguments identify private evidence. The expectation binds the exact new tool
revision/source digest/ABI, original route identities, complete headless reference
runner/checkpoints/WAV and reviewed upstream/independent qualification hashes.
Explicit JSON pointers verify those qualification linkages. A reviewed attestation
may adapt an existing evidence schema while retaining its raw qualification hash;
it must describe the actual reviewed evidence and its limits.

The default permits no PCM changes. Only explicitly declared `psg_nonzero`,
`mixed_nonzero`, `pcm_hash` and `peak` may differ from the old route, and each new
value must equal the new reference at every checkpoint and final observation.
Original guest state, images, source/mappings, assistance, native/interpreted work,
sample counts, ADPCM/CDDA activity, format, runtime loss and WAV bounds stay exact.
Intermediate WAV drain metadata is validated separately because host snapshots
can precede draining; final PCM/WAV is strict. The bounded new WAV must match the
new headless reference byte-for-byte. Both old and new audio measurements remain
in the qualification, alongside independent-reference scope. Unknown ABIs or
diagnostic schemas require deliberate contract review.

Read source and affected contracts before deliberately upgrading `toolchain.json`.
Pins identify a complete clean commit, exact source digest and matching ABI.
Preserve initial/historical qualification and record the actual compiler/options,
all generated-artifact hashes and input identities privately.

Use fresh private output directories and preserve older qualified artifacts.
Reuse immutable inputs/dependencies, stop owned processes and retain reproducible
receipts. Do not use a workbench or per-batch storage accounting workflow, and do
not delete unrelated files.

Stage only explicit authored files, review `git diff --cached`, then run
`git diff --cached --check` and `python scripts/audit_public.py` before pushing.
Never publish media, game-generated source/captures/PCM, saves, private paths,
receipts or chat coordination. The audit is a focused check, not a complete
legal or secret scanner. Unvisited code and new progression need fresh bounded
execution evidence; current audio/coverage checks are not campaign completion.
