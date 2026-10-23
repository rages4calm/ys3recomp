# Consumer status - 23 October 2026

The ABI 13 audio upgrade, corrected SDL packaging and ordinary ultrasonic PSG
correction are verified on Windows x64. This is a bounded hybrid port foundation;
full native coverage and a finished game port remain unfinished.

| Evidence | Result | Scope |
|---|---|---|
| Current tool | `df7e16d465b1618e936d2750bdbe3259b56996a9`, ABI 13, descriptor schema 1 | Exact clean published pin and source digest; no runtime fork |
| Module | 44,832 identities / 57 full MPR contexts, 207 translation units and one generated header | Previously regenerated for ABI 13; all 208 files rehashed and reused unchanged for this source-only correction |
| Audio-off bridge | Retained complete 93,735-frame ABI-12-to-13 qualification | All 25 images/checkpoint states and original guest/native work exact; not rerun for this PSG-only correction |
| Audio-on route | Same complete route passes with PCM enabled | Same 709 edits / 723 changed bytes, no new assistance; only the added validated audio object is separate |
| Native execution | 2,920,491,782 native + 981 interpreted, **99.99996641% native** | Total 2,920,492,763 unchanged; 981 guard misses; all 460,685 block transfers native, zero interpreted |
| Digital PCM | 69,095,406 stereo frames, 44,100 Hz signed 16-bit; peak 13,000; zero runtime queue discard | Exact shared-reference PCM hash `7177686580420813080`; headless synthesis opens no device |
| Source activity | PSG 27,644,755, ADPCM 4,030,681, CDDA 49,762,727, mixed 65,958,163 nonzero frames | Source counts overlap; digital activity is separate from audible correctness |
| Bounded WAV | First 1,323,000 stereo frames / 5,292,044 bytes, truncation reported | First 30 guest seconds; byte-identical to retained upstream WAV; private output only |
| Paced SDL consumer | 710,526 frames submitted, device opens and queue drains; mute false | Separate packaged short bootstrap without SDK PATH; live loaded DLL hash/path verified, pause freezes guest/PCM, resume advances |
| Authored checks | 116 consumer tests; current upstream 27 suites / 273 frontend tests pass with desktop enabled | Current standalone upstream suite has zero skips; fresh embedded build has one SDK-discovery skip, whose original packaging test body passed separately with explicit SDK discovery |

The exact source SHA256 is
`f2615f6278c030542fdef56e1709e6891f6e349662b2869a3a11f606a0431caf`
(50 relevant files). Clang 22.1.8, CMake 3.31.12, Ninja, Python 3.14.5 and
SDL 3.4.18 are the qualified local toolchain. Other hosts/controllers are
unqualified. All protected input hashes and the original capture remain unchanged.

## Native coverage history and source exclusions

The initial ABI-12 replay retired 5,050,558 native and 2,915,442,205 interpreted
instructions (0.17%). The first 2,048-identity module reached 95.34%; the second
44,832-identity module reached the present 99.99996641%. Those receipts and
tool revisions remain preserved. This ABI upgrade changes no tier counts.

The raw capture has 44,836 identities / 57 mappings and no dropped/unreadable
retirements. The verified-restored temporary jump patch's entire six-byte span
is excluded across all mappings and source variants: four identities / 981
original-profile hits. The complete original capture hash/counters/completeness
remain unchanged. Auditing all 709 assist transactions against observed
instruction-fetch addresses finds only the excluded apply/restore overlaps.
No other assisted source bytes are promoted. Unvisited code remains unqualified.

## Execution and audio evidence

Both complete replays use the consumer's explicit 1,800-second watchdog, with
official shared project verification and full immutable build/output bindings
before and after. The descriptor's 600-second `project.run` wall limit is not
applied; these are consumer-supervised route qualifications. The older ABI-12
600-second attempt failed and remains recorded separately. Current replay
receipts preserve every original guest diagnostic, source identity, mapping,
clock, instruction/block count and image. Only TCP port metadata is normalized
in final runner comparison; historical tier splits are normalized solely when
checking the earlier original runner, not the current ABI-12-to-13 comparison.

PCM hashes reproduce the shared implementation's digital result. The current
tool corrects ordinary PSG waveform periods 1–5 by observing their complete-cycle
mean while preserving oscillator state. Independent Geargrafx 1.8.4 checks cover
49,258 exact raw signed-16 stereo PSG pairs in the unfiltered half-gain profile
across 3,262 authored cases, including six waveform indices and two noise seeds.
The old sampling implementation fails
the same independent plan. Raw ADPCM decoder state is checked at all 16 rates:
108 main checkpoints and five continuous control checkpoints. Finite-stop callback
phase residue differs by two ticks; that stopped phase is not claimed identical.
Other instruction-edge control alignments remain unqualified. Earlier 56 raw CDDA
stereo pairs and 78-plan native capture-module checks retain their original scope.
Filtered/scaled Gear output, mixed/resampled PCM, analog sound, hardware and
independent retail-route audio parity remain unqualified.

The new packaged route matches the new headless PCM reference at every checkpoint
and final observation, with byte-identical bounded WAV output. Its PCM and WAV
also remain unchanged from the old packaged route: this is regression evidence;
the ultrasonic correction is demonstrated by the authored reference vectors.
The old packaged route remains frozen. Only explicitly declared PSG activity,
mixed activity, peak and PCM hash may change; all original guest state, images, source/mappings,
native/interpreted counts, sample counts, ADPCM/CDDA activity and runtime loss
stay exact. The consumer qualifier binds the new reference and independently
reviewed qualification files by hash and retains both old and new PCM values.
This milestone declares no permitted PCM differences from the old route.

An initial headless reference completed the route but failed its final tool-identity
metadata consistency guard while the consumer manifest transitioned to the new pin.
Its failure remains preserved. A fresh reference with the pin settled supplies the
qualified comparison; the packaged candidate started after the pin transition.

The first audio-off attempt completed the route/images but failed the consumer
harness's incorrect expectation of a disabled PCM object. The pinned runner
omits that object entirely when off. The harness was corrected against a real
authored runner/TCP test, and a fresh complete audio-off replay passed. The
failed attempt stays separate and is not counted as qualified.

The current pin corrects the earlier Windows embedded-consumer packaging
failure. The official fresh desktop build now places `SDL3.dll` beside its
executable and pins both in `output_files`. All prior audio/failed-startup
receipts remain preserved as history. Current execution requires no SDK PATH
workaround: the child starts in a new empty working directory with all empty,
relative, packaged-bin and SDL-DLL-containing PATH entries removed. Exact PATH,
removed entries and cwd are retained privately. Windows module inspection at
startup and final guest pause ties the same PID/executable to the adjacent
packaged DLL's actual loaded path and hash.

The complete packaged desktop replay matches the retained headless audio route:
all 93,735 frames, 25 image hashes and checkpoint states, 709 transactions and
every original guest/native diagnostic remain exact. Only separately validated
desktop presentation/audio-host additions and TCP port metadata are outside
the guest comparison. Digital PCM counts/hash and the first-30-second WAV bytes
remain exact. The full run is explicitly unthrottled, so all device presentation
frames are intentionally muted/dropped; the runtime PCM queue loses none.
This source-clock measurement is separate from the paced device-stream check.
One intermediate TCP checkpoint observes 29 generated PCM frames pending in
the source ring before the host drain. The qualifier checks every checkpoint
against the pinned 8,192-frame ring bound, zero source loss, equal muted
submitted/dropped counts and an empty SDL queue. All settled final observations
and the runner require zero pending frames. Core PCM/guest comparisons stay exact.
The earlier ABI-13 generated module is reused with all 208 artifact hashes
verified, preserving source exclusions, without a runtime fork.

The paced check accepts/drains a real default SDL device stream, with
2,680 pause-flush presentation drops,
peak input queue 1,583 frames and zero
runtime loss. It is not a listening or analog loopback result. Unthrottled SDL
intentionally mutes speaker presentation while PCM/WAV generation continues.
The full route's muted PCM evidence is separate from this paced device test.

## Remaining limits

The retained route includes ordinary-input checkpoints and journaled assisted
progression to a first-storehouse-boss encounter with visible enemy damage.
It establishes no unassisted encounter, victory or campaign completion.
The explicit `gear-good` unknown-CD response is still used 51 times; strict
unknown-operation semantics remain unresolved. Startup is the BIOS-backed
IPL-entry sandbox rather than authentic reset. Initial blank formatted BRAM is
read-only; guest SAVE/LOAD stays process-local. Persistent host saves and full
console compatibility remain unfinished. Native counts are coverage evidence,
not a gameplay speed claim. Fresh scenes/progression need their own bounded
execution evidence, and future pins require deliberate regeneration/rebuild.
