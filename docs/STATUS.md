# Consumer status - 23 October 2026

Native coverage now extends beyond the original first-boss approach through
normal combat, a rendered Game Over, Continue and full-health recovery. This
remains a bounded hybrid milestone; unvisited code and the full campaign are
unfinished.

| Evidence | Result | Scope |
|---|---|---|
| Current tool | `c5aa9a26125edabdbe98a68bf716bff6eacd310e`, ABI 13, schema 1 | Exact clean capture-only pin; no runtime fork or audio-semantics change |
| Expanded module | 44,879 identities / 57 full MPR contexts | 47 new identities; 208 translation units and one header built through the official shared project contract |
| Extended route | 94,800 frames, including 1,065 new normal-input frames | Same frozen TCP recipe on old and expanded modules; no new RAM edits |
| Guest reproduction | All 39 image/checkpoint states and three endpoints match | Exact PC, all eight MPRs, fetch bytes/physical identity and source generations |
| Native execution | 2,953,438,406 native + 981 interpreted | Total 2,953,439,387; 466,118 native block transfers, zero interpreted |
| Measured gain | 3,461 retirements move from interpreted to native | Compared with 2,953,434,945 native + 4,442 interpreted on the same extended route |
| Original prefix | All 25 original checkpoints remain exact through frame 93,735 | Guest/source/images, original native counts and raw/processed PCM match the frozen prior package |
| Source window | Frame 93,735 to 94,800; 12,138 observed identities / 32,946,624 retirements | Fresh paused restored-byte proof; exact actual start frame/ticks/counters; complete with zero loss/unreadable instructions |
| Observation composition | 44,883 identities across two retained epochs | Original totals preserved; multi-run provenance is separate from execution proof |
| Exclusions | Four identities / 981 profile hits remain excluded | Entire restored temporary-code span excluded across all mappings/variants; zero unsupported observations |
| Digital audio | Filtered 48 kHz processed and raw-source PCM exact throughout the extended route | 76,060,360 output frames; peak 13,355; zero runtime discard; cumulative PCM hash `13785118638779356764` |
| Bounded WAV | First 1,440,000 output frames / 30 guest seconds are byte-identical | The boot WAV does not reach the late frontier; checkpoint/cumulative PCM verifies that section |
| Packaged device check | Separate paced filtered 48 kHz run passes | Adjacent pinned SDL, empty working directory, sanitized PATH, TCP input/captures, pause freeze and resumed advancement |
| Consumer checks | 237 tests pass, zero skips | Capture boundary/proof, profile union, source conservation and qualification rejection cases |
| Shared checks | 28 suites / 294 Python tests, zero skips | Fresh empty-module embedded desktop build; unchanged shared checker |

The exact source SHA256 is
`740f6a5f87aa865c49d538d7c424a8e5b88e903cb022ea0cfab5ab0e387e4b36`
(53 relevant files). Clang 22.1.8, CMake 3.31.12, Ninja, Python 3.14.5 and
SDL 3.4.18 are the qualified local toolchain. All seven protected inputs,
the original capture and all 208 old module artifacts remain unchanged. No
owner installation or saves are used. Older evidence remains frozen through
explicit source-epoch preservation mappings.

## What the new qualification proves

The baseline and expanded packages use the same verified capture-only runtime,
inputs, audio profile, controls and assistance journal. The native qualifier
conserves retired instruction and block totals at every exposed observation,
then requires positive native gain overall and after the original endpoint.
Every source identity and its total hit count also match between the two fresh
window captures; only native/interpreted attribution changes. Complete logical
PC, all MPRs and exact physical/fetch bytes remain distinct across overlays.
Emission and source-union counts alone are never accepted as execution evidence.

Before the source window starts, fresh TCP readback proves the six original
bytes restored and the guest paused without retired work. The actual runtime
gate begins at frame 93,735, tick 33,650,360,835, before the next instruction.
The shared capture loader independently validates both raw captures. The same
six-byte source exclusion is retained across the complete composed profile.
All 709 inherited edit transactions / 723 changed bytes are checked against
observed instruction fetches. The added combat/failure/recovery section makes
no further RAM edits.

This is consumer-supervised route qualification with a 1,800-second watchdog
and official descriptor/build verification before and after. The shared
descriptor's 600-second project.run limit is not applied. A newly built module,
an executed route and independent-reference evidence remain separate tiers.
The new section is a same-runtime reproduction check; no independent retail
oracle or hardware qualification has been added for it.

## Audio and package limits

The current pin adds capture gating and leaves the prior ABI-13 DSP unchanged.
Its default is raw 44.1 kHz; filtered playback is opt-in. The extended comparison
uses filtered-v1 48 kHz. It preserves 69,880,456 source frames, raw PCM hash
`4016269554691743388` and source activity as well as processed output at every
checkpoint. The boot WAV retains the original first-30-second bytes. Runtime
loss is zero. Full route playback is hidden and unthrottled: SDL presentation
is intentionally muted while PCM generation continues. Submitted/dropped
presentation frames are therefore equal; this is separate from runtime loss.

The separate paced package check opens the default stereo device at 48 kHz,
SDL numeric format 33056, unmuted, with an empty final queue and no runtime
discard. Actual loaded SDL path/hash matches the adjacent packaged DLL. TCP
input, guest/window captures, source/PCM pause freeze and resume advance pass.
Device acceptance and exact PCM do not establish listening, analog loopback,
whole-mix independent retail parity or hardware correctness.

The prior raw 44.1 kHz and filtered 48 kHz packages retain their full original
93,735-frame route and separate matching headless-reference evidence. Raw PCM
hash `7177686580420813080` and filtered prefix hash `8515195911678413936`
remain exact. Prior paced checks cover both 44.1 and 48 kHz. The initial
audio-off ABI-12-to-13 bridge is retained; it was not rerun for this source-only
coverage expansion.

Independent Geargrafx 1.8.4 evidence retains its finite scope: 49,258 raw PSG
stereo pairs across 3,262 authored cases, raw ADPCM decoder/control state at
all 16 rates, 59,505 filtered PSG frames across 3,266 cases and 34,112 filtered
held-ADPCM frames across 17 cases. The ADPCM stop-edge phase limitation remains.
Separate authored FIR checks qualify the deterministic 64-tap, 160-phase Q30
resampler, with 31 source frames of latency, zero initial history and no tail
flush; they do not establish Geargrafx resampler parity. No later timing/audio
ABI is adopted by this batch.

## Native history and unfinished work

The initial original-route replay retired 5,050,558 native instructions
(0.17%). The first 2,048-identity module reached 95.34%; the prior
44,832-identity module reached 2,920,491,782 native + 981 interpreted on that
93,735-frame route. The expanded module retains that prefix exactly and adds
qualified source for the later failure/recovery paths. Its 981 interpreted
retirements remain associated with the excluded temporary-code span; unseen
overlays remain hybrid and unqualified.

The inherited prefix uses assistance. The new normal-input continuation
establishes no boss victory, unassisted full encounter or campaign completion.
The explicit gear-good response remains a visible condition for unknown CD
commands; it does not implement those operations. Startup is still the
BIOS-backed IPL-entry sandbox. Initial formatted blank BRAM is read-only and
guest SAVE/LOAD is volatile within one process. Persistent host saves,
authentic console reset, other hosts/controllers and the full game remain
unfinished.
