# Consumer development

Read the pinned toolkit's ownership and architecture documents before integration.
Keep its active checkout untouched. This repository owns game configuration,
source selection, adapters, coverage, launchers and bounded gameplay checks.
CPU/device/audio semantics, media, generation and reusable hosts remain upstream.

## Pin, regenerate and build

The current source pin is `e0f67bf64fe670723acd4443b0da76f3bfe8276f`, ABI 15,
descriptor schema 1. Its 53-file source SHA256 is
`38573f59cd17b1b9c640337ac6c1d9db80b3dc926d42312f8cedfd28d7959dd7`.
Clone with LF source bytes as shown in README. `verify_tool.py` rejects the
wrong revision/ABI/digest, dirty source, concealed index changes and shadow files.

ABI 12/13/14 captures remain immutable offline inputs. Re-emit them through the
shared tool and rebuild every compiled object. Never relabel capture metadata.
The retained expanded profile has 44,883 identities, of which 44,879 are eligible
in 57 full MPR contexts. Its ABI 15 module has 208 C++ translation units and one
header. Compared with ABI 13, all operations, guards and exclusions stay exact;
only the 208 ABI assertions change. The header is identical.

These examples require private input configuration and retained evidence. Use
new output directories and reuse original inputs/dependencies read-only:

```powershell
$tool = (Resolve-Path '.deps/pcenginerecomp-abi15').Path
$batch = '.local/new-private-batch'
$profile = 'PRIVATE_OBSERVATION_PROFILE'
$route = 'PRIVATE_EXTENDED_ROUTE'
$inputs = 'PRIVATE_INPUT_CONFIGURATION'
New-Item -ItemType Directory -Path "$batch/temp" -Force
$env:TEMP = (Resolve-Path "$batch/temp").Path
$env:TMP = $env:TEMP
$env:PYTHONPATH = $tool
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python scripts/verify_tool.py --tool-root $tool
python scripts/expand_native.py --tool-root $tool --route $route --capture $profile --out "$batch/native"
python scripts/prepare_descriptor.py --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio on --audio-profile filtered --audio-rate 48000 --audio-timing legacy --out "$batch/project-legacy.toml"
python scripts/prepare_descriptor.py --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio on --audio-profile filtered --audio-rate 48000 --out "$batch/project-gear.toml"
python scripts/prepare_descriptor.py --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio off --out "$batch/project-off.toml"
python -m pcerecomp.project build "$batch/project-gear.toml" --build-dir "$batch/build-gear" --desktop --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++ --cmake-arg=-DSDL3_DIR=SDL3_CMAKE_DIRECTORY
```

Build each descriptor separately through the official contract. No SDK, media
or dependencies are fetched implicitly. The shared Windows build packages its
pinned SDL DLL beside the executable. The manifest binds every generated source
and header; preserve that entire directory and the official build receipt.

`expand_native.py` validates the journal's restored bytes, excludes the entire
temporary-code span across every mapping/variant, and refuses other assisted
writes overlapping instruction fetches. Exact PC, all eight MPRs, physical
addresses and source bytes distinguish overlays. The profile's original hash,
completeness and hit totals stay intact. Emission counts prove no execution.

## Run and qualify the ABI 15 matrix

Run the same frozen 94,800-frame route through TCP on all three new packages:

1. Explicit legacy filtered 48 kHz must reproduce the qualified ABI 13 package's
   exposed guest/native/source state, processed/raw-source PCM and bounded WAV.
2. Default Gear filtered 48 kHz must match a fresh separately frozen ABI 15
   headless reference at all 39 checkpoints and three endpoints.
3. Audio off must retain exposed guest/native/source state and omit all PCM,
   WAV and device-output diagnostics.

Use `replay_route.py` with the matching binary, descriptor and build directory,
`--project-verify-only --desktop-packaged`, the immutable source-route binary
anchor, and the same input/route evidence. Enabled runs select
`--audio-output on --audio-profile filtered --audio-rate 48000 --audio-frames 1440000`.
Only the legacy run adds `--audio-timing legacy`; omit timing to exercise default
Gear. The off run supplies only `--audio-output off`. Each run needs a new output
directory. Duplicate timing arguments, including equals forms, fail before launch.

The retained route can contain historical tier counters. Replay may use
`--ignore-tier-counters` for that historical comparison; the final migration
qualifier separately requires exact current native/interpreted/block counts.
Every source/guest/image diagnostic remains retained. Current counts are
2,953,438,406 native, 981 interpreted, 981 guard misses and 466,118 native block
transfers with zero interpreted blocks. The ABI upgrade adds no native coverage.

```sh
python scripts/qualify_abi15.py --baseline-receipt OLD13_RECEIPT --legacy-receipt NEW15_LEGACY --gear-receipt NEW15_GEAR --off-receipt NEW15_OFF --expectation REVIEWED_MATRIX --out NEW_QUALIFICATION
```

The strict expectation hash-binds both full headless reference receipts, runs
and WAVs; exact tool/source/ABI, route and module identities; actual upstream
qualification; and separately scoped independent evidence. New consumer receipts
require timing in their normalized selection. The pinned frozen headless adapter
retains its two-key selection only when actual argv, PCM marker and root
qualification independently establish timing. Raw receipts are never rewritten.

Before comparing the capture-free ABI 15 runs, validate and rehash the original
ABI 13 managed capture and paused restored-source proof. Only its exact reviewed
capture-window metadata may then be handled separately. All 209 old/new generated
artifacts are rehashed, accepting only exact ABI assertion replacements. All
other instruction, block and per-identity retirement totals remain conserved.

At every Gear observation, source frames must equal
`floor(ticks * 44100 / 21477273)`. At 48 kHz, output frames equal
`floor(source_frames * 160 / 147)`, with 31 source frames of latency and no tail
flush. Gear PCM includes exactly `timing = "gear-v1"`; legacy omits that field.
Unknown fields, missing metadata, clock-edge drift and changed artifacts fail.

Keep the full direct TCP supervisor's 1,800-second watchdog separate from the
shared descriptor's 600-second `project.run` bound. The full route bypasses the
descriptor's shorter project.run wall bound and records that override. A separate finite
60-frame official run checks the wrapper with dummy SDL. It is not device
playback evidence or the full gameplay route.

## Playback, local commands and limits

The full routes are hidden/unthrottled, with intentionally muted SDL presentation
while guest-clock PCM generation continues. Check runtime discard separately
from presentation drops and pending frames. Settled/final drain boundaries require
zero pending output; intermediate pending frames must fit the 8,192-frame ring.

A separate paced Gear 48 kHz check uses a real device, sanitized child PATH and
an empty cwd. Inspect the actual loaded SDL path/hash in the same PID before and
after. Check TCP input, guest/window captures, complete source/processing/timing
pause freeze, resumed advancement, queue bounds and all seven original inputs
before launch and after exit. Never invent an extra pre-launch snapshot or a
successful listening test. Device acceptance and PCM hashes do not prove analog,
hardware or independent retail-mix correctness.

`Play Ys III.cmd` verifies the private selection and starts a visible paced manual
host. `Native Files.cmd` opens its C++ folder. `python scripts/play_local.py --info`
performs readiness checks without a game launch. A manual host removes the
600-second wall argument while retaining guest step/tick limits; it is separate
from `project.run`. It enables no TCP edits/captures or automatic assistance.
Guest saves remain volatile within that process. No owner installation/save is
used, modified or exported.

The pin does not expose new held-DAC/CDDA clock/latch fields through TCP. Keep
retail exposed-state regression separate from the upstream finite state tests.
The latch oracle covers nine cases and 367 checkpoints with PCM on and off,
pre-headroom. Retained ABI 14 timing checks cover 102 cases, 1,551 checkpoints and
75,137 stereo frames after integer headroom, with explicit stopped-phase and
single-tick overdue-callback limits. No retail latch-port usage is inferred.
The boot WAV covers only the first 30 guest seconds; cumulative PCM/checkpoints
verify the later section. Assisted progression is not campaign completion.
The explicit gear-good unknown-CD condition and IPL-entry sandbox remain visible.

## Authored checks and historical workflows

Run the consumer tests and the unchanged pinned shared checker after relevant
builds. The fresh embedded desktop build has 30 shared suites and 316 Python
tests without skips. The consumer has 283 passing tests. The clean default
configuration intentionally skips eight desktop cases. A fresh ABI 15-only
checkout may also skip optional historical c5 capture integration cases; the
owner's qualified checkout retains that pin and reports zero skips. Keep actual
skip counts separate from device evidence.

The older ABI 13 raw/filter/native-window workflows and finite qualifiers remain
unchanged in the source history. Use their corresponding source/toolchain epoch:
[retained development procedure](https://github.com/rages4calm/ys3recomp/blob/f7ad744bbdff792453360fd9d5eb7c97f7201326/docs/DEVELOPMENT.md).
The managed capture helper intentionally accepts only its reviewed ABI 13
contract. A new ABI 15 capture session needs a separate contract review; this
migration reuses the unchanged ABI 13 profile and creates no fresh retail capture.

## Preservation, cleanup and publication

Keep original inputs read-only, guest BRAM volatile, qualified executables and
module source intact. Archive exact bound source epochs before changing them;
resolve historical paths by original path plus expected digest. Never rebuild a
past binary and present it as the one that executed. A parser-only validation fix
can retain actual runtime evidence only with preserved executed source, exact
single-mode argv equivalence and separate rejection tests.

Reuse immutable dependencies. Remove obsolete unbound compiler intermediates
only after reviewing exact paths against all qualified hash graphs. Retain small
replayable receipts and stop owned processes. Do not use a workbench, per-batch
quota or accounting workflow, and never delete unrelated files. The owner-run
cleanup command retains its exact plan, containment/reparse/hash/protected-file
guards and post-checks; automatic tool policy blocked agent deletion, so no
cleanup completion is claimed.

Stage explicit authored files, review the diff, then run
`git diff --cached --check` and `python scripts/audit_public.py` before every push.
Only the three named root CMD entry points are allowed by the publication audit;
arbitrary CMD files, private inputs, generated game source/captures/PCM, saves,
absolute owner paths and coordination metadata remain excluded. Freeze runtime
evidence independently from final docs/launcher/cleanup metadata, then separately
verify the actual public commit and unchanged evidence after publication.
