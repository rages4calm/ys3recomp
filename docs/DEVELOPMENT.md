# Consumer development

Read the pinned toolkit's ownership and architecture documents before integration.
Keep its active checkout untouched. This repository owns game configuration,
source selection, adapters, coverage, launchers and bounded gameplay checks.
CPU/device/audio semantics, media, generation and reusable hosts remain upstream.

## Current closed reset-extension workflow

The final host pin is `95fe3e07e63b0869de8c9d7b70681b5c557abf01`, ABI17,
descriptor schema1, with 57-file canonical source SHA256
`60c37d9fb5b1a1318cd2509c7ac1cc45c03a9939116d04e836aa67e0e03c4ffb`.
Use `.deps/pcenginerecomp-abi17-cue`, LF source bytes, the official descriptor/
build/verify APIs, adjacent SDL package hashes, sanitized child PATH and empty
working directory. Owner inputs remain immutable.

The current retail path still uses the matching owner CHD, TOC, clean US BIOS
and libchdr. New read-only BIN/CUE support has its own synthetic/independent
fixture scope; do not relabel the CHD route as a retail CUE test or convert or
extract owner media. Reset-super retains deterministic initialization and
implicit blank-unformatted volatile BRAM, without IPL payload, forced PC/MPR,
input script, seed file or RAM writes. Unknown-CD `gear-good` stays explicit.

These examples name generic private artifacts, not distributed fixtures. Every
descriptor/build/replay/qualification output must be new.

```powershell
$tool = (Resolve-Path '.deps/pcenginerecomp-abi17-cue').Path
$batch = '.local/new-extension-batch'
$project = (Get-Location).Path
$env:PYTHONPATH = "$project;$tool"
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m scripts.verify_tool --tool-root $tool
python -m scripts.prepare_reset_descriptor --tool-root $tool --expected-revision 95fe3e07e63b0869de8c9d7b70681b5c557abf01 --expected-abi 17 --expected-source-sha256 60c37d9fb5b1a1318cd2509c7ac1cc45c03a9939116d04e836aa67e0e03c4ffb --reference-launch PRIVATE_RESET_LAUNCH --reference-receipt PRIVATE_RESET_REFERENCE --module PRIVATE_EXPANDED_MODULE --out "$batch/project-expanded.toml"
python -m pcerecomp.project build "$batch/project-expanded.toml" --build-dir "$batch/build-expanded" --desktop --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++ --cmake-arg=-DSDL3_DIR=SDL3_CMAKE_DIRECTORY
python -m scripts.replay_reset_extension --tool-root $tool --expected-revision 95fe3e07e63b0869de8c9d7b70681b5c557abf01 --descriptor "$batch/project-expanded.toml" --build-dir "$batch/build-expanded" --baseline-receipt PRIVATE_CLOSED_DISCOVERY --baseline-receipt-sha256 EXACT_BASELINE_SHA256 --out "$batch/replay-expanded" --verify-only
python -m scripts.replay_reset_extension --tool-root $tool --expected-revision 95fe3e07e63b0869de8c9d7b70681b5c557abf01 --descriptor "$batch/project-expanded.toml" --build-dir "$batch/build-expanded" --baseline-receipt PRIVATE_CLOSED_DISCOVERY --baseline-receipt-sha256 EXACT_BASELINE_SHA256 --out "$batch/replay-expanded"
```

The original generation pin remains
`bb3b695b782352bdfacd8db877f2a843bd1242f1` in
`.deps/pcenginerecomp-abi17`, source
`5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d`
(54files). Native source union/emission and same-route native gain were checked
there first. CLI reproduction also requires the matching pre-migration consumer
revision or preserved source epoch as well as that clone: `expand_native.py`
verifies the current manifest and has no independent old-tool override.
The later57-file media
host reused the same module without re-emission; it is a separate full-route
migration gate with exact counts and byte-identical code capture. The replay
helper accepts only these two reviewed revision/source/file-count pairs; it
does not mutate the old reset helper's fixed tool globals.

Bind the closed discovery's actual kind/phase journal directly. Preserve the
first114 opening actions,105states/10images and fresh14,680-frame boundary;
defer the old terminal quit until the actual final finish. The current recipe
has60ordinary advance requests plus finish,227raw states,71images and357action
rows through19,126 frames. Every request/action/image/state must be present;
no invented adapter receipt or relabeled replay kind is permitted.

Immediate extension input statuses are raw transport diagnostics. Validate
within each run that CPU/time/all MPRs/source/generations/CD/PCM and retired
counts are unchanged from the preceding settled state, except a mask equal to
the exact prior or requested buttons. After advance1..600, require the exact
requested mask and frame boundary. Compare all settled checkpoints strictly
apart from measured native/interpreted redistribution. The original prefix's
fixed hash-bound state54/action58/frame11,660 witness may retain prior1 or show
release0, but every other field and actual opening native count stays exact;
strict advancing state55 confirms release. Retain all raw variants and typed
annotations; do not mask arbitrary inputs, IRQs or timing fields.

For historical bindings whose public path changed, supply only an explicit
`--baseline-epochs PRIVATE_EXACT_EPOCH_MAP`: schema1, mappings of original path,
expected SHA256 and preserved path, each rehashed. Never search for substitutes
or reconstruct missing evidence. The original baseline and failed attempts stay
immutable. Interactive lease keepalives belong in separate raw heartbeat logs,
not deterministic route actions or states.

Capture original source from before the first reset instruction, capacity65,536,
complete with zero loss/unreadable instructions. Verify initial BIOS vector,
all CPU/MPR/source bytes, no RAM-write access and exact per-tier/source retired
hit conservation after natural TCP quit. The new profile combines ABI17 source
observations from multiple runs:52,677eligible/79MPR contexts,257translation
units+oneheader,121neweligible identities. Profile composition is not a single
execution proof. Keep the six-byte historical exclusion across all4variants;
its984profile hits differ from this route's actual3identities/3interpreted hits.

Same-route native work changes from564,265,156N/20,674I to564,285,827N/3I;
gain20,671, with63,473native blocks/zero interpreted and3guard misses. Reset
prefix work remains432,875,213N/0I. Preserve full CPU/MPR/source/CD/PCM/images;
capture/emission totals alone do not establish execution. Native gain and the
new shared toolkit migration need separate passing qualifiers before publication.

Raw44100 Gear audio requires source frames equal
`floor(ticks * 44100 / 21477273)`. The full route has14,098,470PCM frames,
hash`4270652294026774565`,13,022,805mixed-nonzero and zero runtime loss. Final
drain and the matching441,000-frame WAV stay strict. The first10guest seconds
are boot silence; later nonzero audio is cumulative PCM evidence. Full replays
are unthrottled and SDL-muted. No new paced-device/listening/analog claim follows;
the prior first-reset silent-menu device test remains historical.

Current regression passes452consumer tests, zero skips; shared checks
pass35suites/420Python tests, zero skips. Six independent Gear CUE fixtures and
finite authored native/TCP checks do not prove whole-retail CPU/device timing,
hardware parity or a native-only complete game. A separate5,526-frame CHD gate
checks20states/twoimages/177sectors with152,630,394N/0I. The prior95,686-frame
IPL regression was not repeated here. Unknown operations/REQUEST SENSE,
cross-process saves and campaign completion remain unfinished. No cleanup ran;
revalidate owner-run plans after final source/metadata changes.

## Historical first-reset workflow (original ABI17 pin)

The following examples require the matching historical consumer revision and
frozen original ABI17 pin. In particular, `scripts.replay_reset` is intentionally
fixed to that original54-file source and does not select the new57-file host.
The current entry point for closed extension recipes is documented above.

The clean pin for this historical workflow is `bb3b695b782352bdfacd8db877f2a843bd1242f1`, ABI 17,
schema 1. Its 54-file canonical source digest is
`5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d`.
Clone with LF bytes into `.deps/pcenginerecomp-abi17`. Official verify/build
bindings and actual adjacent SDL hashes are required before and after execution.

Use the shared System Card reset mode with profile `super` and the matching
clean 256 KiB US BIOS. Omit payload/IPL, PC/MPR overrides, BRAM file and input
script. Initialization is `gear-deterministic-zero-v1`; implicit unformatted
BRAM is volatile. Select hybrid/continuous/joypad2/USA/multitap-off, raw44100
audio with default Gear timing and explicit `gear-good` compatibility. Do not
mistake deterministic reset initialization for hardware power-on certification.

These generic placeholders refer to existing private evidence. Every output
must be new; do not overwrite qualified receipts or relabel capture ABIs.

```powershell
$tool = (Resolve-Path '.deps/pcenginerecomp-abi17').Path
$batch = '.local/new-reset-batch'
$project = (Get-Location).Path
$env:PYTHONPATH = "$project;$tool"
$env:PYTHONSAFEPATH = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m scripts.verify_tool --tool-root $tool
python -m scripts.prepare_reset_descriptor --tool-root $tool --reference-launch PRIVATE_RESET_LAUNCH --reference-receipt PRIVATE_RESET_REFERENCE --module PRIVATE_NATIVE_MODULE --out "$batch/project-reset.toml"
python -m pcerecomp.project build "$batch/project-reset.toml" --build-dir "$batch/build-reset" --desktop --generator Ninja --cmake-arg=-DCMAKE_CXX_COMPILER=clang++ --cmake-arg=-DSDL3_DIR=SDL3_CMAKE_DIRECTORY
python -m scripts.replay_reset --tool-root $tool --descriptor "$batch/project-reset.toml" --build-dir "$batch/build-reset" --reference-launch PRIVATE_RESET_LAUNCH --reference-launch-sha256 EXACT_LAUNCH_SHA256 --reference-receipt PRIVATE_RESET_REFERENCE --reference-receipt-sha256 EXACT_REFERENCE_SHA256 --protected-inputs PRIVATE_SEVEN_ORIGINALS --input-status-bridge PRIVATE_AUDITED_INPUT_WITNESS --input-status-bridge-sha256 EXACT_WITNESS_SHA256 --out "$batch/replay-reset"
python -m scripts.qualify_reset_native --baseline-receipt PRIVATE_INTERPRETED_RESET --candidate-receipt "$batch/replay-reset/receipt.json" --reference-receipt PRIVATE_RESET_REFERENCE --provenance PRIVATE_RESET_PROVENANCE --out "$batch/native-qualified.json"
```

The reset harness calls official verify/command/build-binding APIs with its own
bounded TCP supervision; it does not claim an official `project.run` execution.
It starts paused at frame0, validates BIOS vector and all MPR/CPU/source identity,
reads original fetch bytes, disables RAM writes, then captures up to 65,536
identities from before the first instruction. Require complete capture, zero
loss/unreadable instructions and exact per-source/native/interpreted retirement
conservation. Preserve raw actions, states and images before comparisons, finish
through natural TCP quit and rehash all seven originals and consumed assets.

The main reset route replays the literal 115 ordinary actions through frame
14,680. The one audited immediate input-release snapshot at state54/action58
may differ only under an explicitly hash-bound witness: same frame/ticks,
previous mask1, requested/actual0, and every other guest/source/CD/PCM field
exact. Retain old/new/previous raw states and require the strict next advance2,
state55, frame11,662 with zero input. Do not generalize this to other inputs or
claim all raw snapshots match. An input ACK records intent, not application.

For BIOS timing evidence, use a separate same-package reset0-to600 capture.
`--stop-after-frame 600` selects the original reference boundary. Adding
`--prefix-images PRIVATE_MENU_IMAGE_RECEIPT --prefix-images-sha256 EXACT_SHA256`
records an explicit neutral advance120/capture/advance480/capture recipe,
retaining the extra raw state120. The full candidate/reference state at600 must
still match including actual tiers; that capture proves BIOS work by600, not
before120. Verify decoded RGB and actual PNG hashes. The external Gear menu
bridge compares only its declared aligned 237-row viewport at120 and600;
full raw frames differ, and no retail CPU/device tick parity follows.

The full reset route uses raw44100 Gear PCM and a 441,000-frame WAV cap.
Validate `frames = floor(ticks * 44100 / 21477273)` at every observation.
Checkpoints can precede bounded host drain; validate full raw PCM/device fields
before separating WAV phase/presentation metadata. Final drain, PCM and WAV
must match strictly. The first ten guest seconds are silent boot samples;
later cumulative nonzero PCM is qualified separately. Full route SDL playback
is intentionally muted while unthrottled.

A separate paced reset-menu check verifies real default-device acceptance,
full exposed guest/source/CD/PCM pause freeze, drain settlement without a later
tail, resumed advancement, TCP input and guest/window captures. Silent samples
are valid acceptance evidence. Raw telemetry omits negotiated device format
fields; do not invent them or claim listening/analog quality. Earlier filtered
48 kHz device geometry remains historical evidence.

The new composed module contains 52,556 eligible identities / 79 MPR contexts,
257 translation units and one header. It combines observed ABI16/17 original
source without pretending to be one execution; the entire six-byte historical
assisted span stays excluded across all four variants / 981 profile hits.
No new reset assists are present. The separately rebuilt ABI17 IPL-entry route
retains all 95,686 frames / 68 images, actual tiers and same-profile filtered
48 kHz PCM; its inherited 709 transactions / 723 bytes remain disclosed.

Current checks pass 411 consumer tests with zero skips. The fresh
204-target shared build passes 34 suites / 386 Python tests, zero skips. Fifty
finite authored Geargrafx checks and aligned menu pixels do not establish full
retail CPU/device timing; 36 CSH cases retain an 18-tick difference. Keep
`gear-good` and unsupported unknown/REQUEST SENSE semantics visible. All six
bounded hosts close and all seven originals are rehashed; host saves and the
full campaign remain unfinished.

## Retained ABI 16 IPL-entry workflows

The following records and commands retain their original ABI16 scope. They are
separate from the current reset path and are not instructions to downgrade the
current tool pin. Existing immutable captures and receipts remain unchanged.
These archived CLI examples require the matching historical consumer revision
and its frozen ABI16 pin. They do not run unmodified under the current ABI17
manifest: in particular, `verify_tool` now defaults to ABI17. Use the current
reset workflow above as the entry point for this checkout.

### Retained pin, regenerate and build

The retained ABI16 source pin is `3bd06b5055c92e9f368aab7023098ff8aa796854`, ABI 16,
descriptor schema 1. Its 54-file source SHA256 is
`720e3c1e980e3ad9d03b28cb4b31db696fe3bb27e687c0cf19bc3d0f3f1c9440`.
Clone with LF source bytes as shown in README. `verify_tool.py` rejects the
wrong revision/ABI/digest, dirty source, concealed index changes and shadow files.

ABI 12/13/14/15 captures remain immutable offline inputs. Re-emit them through the
shared tool and rebuild every compiled object. Never relabel capture metadata.
The retained migration profile has 44,883 identities, of which 44,879 are
eligible in 57 full MPR contexts. Its ABI 16 module has 208 translation units and
one header; its migration changed only the 208 ABI assertions. That historical
proof remains separate from the new native-source expansion: 44,882 eligible
identities in the same 57 contexts, 208 translation units and one header. The
retained module uses ABI 16.

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

## Extend native coverage within ABI 16

The new route extends the qualified 94,800-frame / 39-image prefix to 95,686
frames / 68 images. Compare the old and expanded module on that same extended
route, using default Gear filtered 48 kHz and the unchanged ABI 16 source pin.
This source expansion does not imply a repeated legacy/off migration matrix or
a fresh independent headless retail reference. One new official desktop build
contains 208 translation units and one header. Emission of three additional
eligible identities proves no execution by itself.

The qualified endpoint reports 2,980,431,691 native and 981 interpreted
retirements, a 43-retirement native gain on the same extended route, and
470,652 native block transfers. The strict qualifier conserves total work. No new RAM
assists are permitted; replay only the frozen 709 expected-byte transactions /
723 changed bytes in the inherited prefix. Read back all six original temporary
code bytes while paused before starting the suffix capture. Preserve logical
PC, all eight MPRs, mapped physical/fetched-byte identity and source generations.
The entire six-byte source span remains excluded across all variants.

Both actual old/new runs need the official descriptor/build/verify guards,
`--project-verify-only --desktop-packaged`, default Gear filtered 48 kHz,
`--audio-frames 1440000`, and managed capture beginning exactly at frame 94,800.
Use the reviewed `--code-capture-start-frame 94800` option and an explicit
bounded capacity; never capture temporary cheat bytes or relabel the capture
ABI. Loss, unreadable observations, changed start counters or source bytes fail.

```sh
python -m scripts.qualify_native16 --baseline-receipt OLD_MODULE_EXTENDED_REPLAY --candidate-receipt NEW_MODULE_EXTENDED_REPLAY --prefix-receipt QUALIFIED_94800_GEAR_REPLAY --provenance REVIEWED_PROFILE_PROVENANCE --min-native-gain 43 --out NEW_QUALIFICATION
```

The schema-1 provenance kind is `ys3-native16-profile-provenance`. Its exact
eight file roles are `prefix_receipt`, `prefix_qualification`, `old_profile`,
`new_profile`, `old_selection`, `new_selection`, `merge_manifest` and
`merge_receipt`; every role has an explicit path and SHA256 binding. Reject
missing, unknown, swapped or changed roles. Verify both raw suffix captures'
exact source identities and total retired hits, the composed profile and
source exclusions, then reproducible emission through the pinned API. Profile
composition is a union of retained observations, not a single execution proof.

Preserve inherited checkpoint `source_capture_root`, route-level roots and PNG
references. Resolve each actual file by its recorded context and exact digest;
do not silently make a historical relative filename relative to a newer route.
A path-only correction needs a new qualifier output. Keep failed outputs and
executed source epochs unchanged. The inherited-relative-PNG correction was
qualified in a new output; the original failure remains retained.

Every guest/source/CD field stays exact apart from explicitly validated tier
accounting. At intermediate checkpoints, validate complete raw desktop audio
and bounded output drain first; only SDL presentation metadata and the two
validated WAV drain fields are separated from core equality. Preserve both raw
observations and full validated cores. Processing, source clock, cumulative PCM
hash, timing identity and activity counters remain exact. Endpoints require
complete drain and full core/WAV equality. Report precise difference paths.

Keep native/interpreted and block work conserved on the same route and require
the measured gain to come from the actual captured suffix. The retained 39-image
prefix and all 68 extended checkpoints / three endpoints must be checked. The
new endpoint's 54 `$FF` reference responses do not alter the older prefix's
53-response history or implement unknown CD operations. The full route remains
hidden/unthrottled with intentionally muted SDL presentation; the new package's
real-device paced startup check is separate from gameplay and listening proof.

## Retained ABI 16 migration matrix

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

The retained ABI 16 migration matrix is capture-free. The native-source
extension above instead uses actual ABI 16 suffix captures. When comparing a
historical managed capture, rehash its raw data and paused restored-source proof first.
Only explicitly reviewed capture-window metadata may be handled separately. The retained
migration rehashed all 209 old/new generated artifacts, accepting only exact
15-to-16 ABI assertion replacements. All other instruction, block and per-identity retirement
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
changes. The latest shared rerun passes 33 suites and 328 Python tests without
skips on the retained empty-module embedded desktop build; no fresh shared build
is claimed for the source expansion. The final consumer regression has 339
passing tests without skips, including inherited PNG-reference regression checks. The clean default
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
the retained migration reused the original ABI 13 retail profile and captured
no new retail game code. Unknown future ABIs remain rejected.

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
The existing approximately 119 MiB plan and separate approximately 63 MiB newer
private-intermediate plan remain owner-run only. Neither was executed and the
root cleanup CMD is unchanged. Qualified source, captures, PCM, executables,
SDL libraries and all bound receipts remain protected.

Stage explicit authored files, review the diff, then run
`git diff --cached --check` and `python scripts/audit_public.py` before every push.
Only the three named root CMD entry points are allowed by the publication audit;
arbitrary CMD files, private inputs, generated game source/captures/PCM, saves,
absolute owner paths and coordination metadata remain excluded. Freeze runtime
evidence independently from final docs/launcher/cleanup metadata, then separately
verify the actual public commit and unchanged evidence after publication.
