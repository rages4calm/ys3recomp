# Consumer development

Read the pinned toolkit's ownership and architecture documents before integration.
Keep its active checkout untouched. This repository owns game configuration,
source selection, adapters, coverage, launchers and bounded gameplay checks.
CPU/device/audio semantics, media, generation and reusable hosts remain upstream.

## Pin, regenerate and build

The current source pin is `3bd06b5055c92e9f368aab7023098ff8aa796854`, ABI 16,
descriptor schema 1. Its 54-file source SHA256 is
`720e3c1e980e3ad9d03b28cb4b31db696fe3bb27e687c0cf19bc3d0f3f1c9440`.
Clone with LF source bytes as shown in README. `verify_tool.py` rejects the
wrong revision/ABI/digest, dirty source, concealed index changes and shadow files.

ABI 12/13/14/15 captures remain immutable offline inputs. Re-emit them through the
shared tool and rebuild every compiled object. Never relabel capture metadata.
The retained expanded profile has 44,883 identities, of which 44,879 are eligible
in 57 full MPR contexts. Its ABI 16 module has 208 C++ translation units and one
header. Compared with ABI 15, all operations, guards and exclusions stay exact;
only the 208 ABI assertions change. The header is identical.

These examples require private input configuration and retained evidence. Use
new output directories and reuse original inputs/dependencies read-only:

```powershell
$tool = (Resolve-Path '.deps/pcenginerecomp-abi16').Path
$batch = '.local/new-private-batch'
$profile = 'PRIVATE_OBSERVATION_PROFILE'
$route = 'PRIVATE_EXTENDED_ROUTE'
$inputs = 'PRIVATE_INPUT_CONFIGURATION'
New-Item -ItemType Directory -Path "$batch/temp" -Force
$env:TEMP = (Resolve-Path "$batch/temp").Path
$env:TMP = $env:TEMP
$project = (Get-Location).Path
$env:PYTHONPATH = "$project;$tool"
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m scripts.verify_tool --tool-root $tool
python -m scripts.expand_native --tool-root $tool --route $route --capture $profile --out "$batch/native"
python -m scripts.prepare_descriptor --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio on --audio-profile filtered --audio-rate 48000 --audio-timing legacy --out "$batch/project-legacy.toml"
python -m scripts.prepare_descriptor --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio on --audio-profile filtered --audio-rate 48000 --out "$batch/project-gear.toml"
python -m scripts.prepare_descriptor --tool-root $tool --inputs $inputs --module "$batch/native/module.cpp" --audio off --out "$batch/project-off.toml"
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

## Run and qualify the ABI 16 matrix

Run the same frozen 94,800-frame route through TCP on all three new packages:

1. Explicit legacy filtered 48 kHz must match a separately frozen ABI 16
   headless run, including guest/source/native/CD state, PCM and bounded WAV.
2. Default Gear filtered 48 kHz must match a fresh separately frozen ABI 16
   headless reference at all 39 checkpoints and three endpoints.
3. Audio off must retain exposed guest/native/source state and omit all PCM,
   WAV and device-output diagnostics.

Use `python -m scripts.replay_route` with the matching binary, descriptor and build directory,
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
python -m scripts.qualify_abi16 --legacy-receipt NEW16_LEGACY --gear-receipt NEW16_GEAR --off-receipt NEW16_OFF --expectation REVIEWED_MATRIX --out NEW_QUALIFICATION
```

The strict expectation hash-binds both full headless reference receipts, runs
and WAVs; exact tool/source/ABI, route and module identities; actual upstream
qualification; and separately scoped independent evidence. Both new hosts
require three selection fields: profile, sample rate and timing. Packaged Gear
omits timing; headless Gear may explicitly select it. Preserve actual argv and
descriptors. Raw receipts are never rewritten. The separate ABI 15 conservation
report measures prior guest/native/source/image/PCM/WAV differences honestly.

Current ABI 16 qualification runs are capture-free. When comparing a historical
managed capture, rehash its raw data and paused restored-source proof first.
Only explicitly reviewed capture-window metadata may be handled separately. All
209 old/new generated artifacts are rehashed, accepting only exact 15-to-16 ABI
assertion replacements. All other instruction, block and per-identity retirement
totals remain conserved.

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

`cd_unknown` is retained and validated in every new status/final JSON. Its
opcode-attempt histogram includes strict faults; accepted responses must agree
with the old counter. Origin is the last CPU $1801 latch write supplying the
initial CDB byte before its first ACK: PC, ticks, all MPRs, mapped physical PC
and seven nullable pure source peeks. Later known commands do not replace the
last unknown record. It is not an ACK/retirement trace or implemented command.
Only this validated added diagnostic is separated for old-schema comparisons;
never broadly drop IRQ, generation or other guest fields. Current old fields
remain exact. Future sprite-IRQ differences require independent investigation.

The strict-policy prefix is separate expected-fault evidence, not a route pass.
The captured stop is a CD-specific bus fault; recorded child OS exit is 1 and
natural runtime exit was not verified. Keep the original failed outer assertion
and actual raw output. No retail run is repeated or relabeled to hide a harness
metadata or lifecycle mismatch.

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
builds. The fresh embedded desktop build has 33 shared suites and 328 Python
tests without skips. The consumer has 324 passing tests. The clean default
configuration intentionally skips eight desktop cases. A fresh ABI 16-only
checkout may also skip optional historical c5 capture integration cases; the
owner's qualified checkout retains that pin and reports zero skips. Keep actual
skip counts separate from device evidence.

The older ABI 13 raw/filter/native-window workflows and finite qualifiers remain
unchanged in the source history. Use their corresponding source/toolchain epoch:
[retained development procedure](https://github.com/rages4calm/ys3recomp/blob/f7ad744bbdff792453360fd9d5eb7c97f7201326/docs/DEVELOPMENT.md).
Managed capture accepts only explicitly reviewed ABI 13 or 16 contracts. The
actual capture ABI must match the selected runtime, with exact paused-window
counters, all MPRs, mapped physical/fetched-byte identity, restoration readback
and loss/capacity/hash checks. WRAM aliases do not merge source identities. The
ABI 16 loader is checked with authored two-byte BRK/wrapped-MPR observations;
this migration reuses the original ABI 13 retail profile and captures no new
retail game code. Unknown future ABIs remain rejected.

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
