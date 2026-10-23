# Consumer status - 23 October 2026

The ABI 13 audio upgrade is verified on Windows x64. This is a bounded hybrid
port foundation; full native coverage and a finished game port remain unfinished.

| Evidence | Result | Scope |
|---|---|---|
| Current tool | `9be8686554e1c6037411944da695a194d9c0ac2d`, ABI 13, descriptor schema 1 | Exact clean published pin and source digest; no runtime fork |
| Regeneration | 44,832 identities / 57 full MPR contexts, 207 translation units and one generated header | Existing ABI-12 observations regenerated; every generated artifact hash pinned; no reused ABI-12 objects |
| Audio-off bridge | Complete 93,735-frame route passes | All 25 image hashes, 25 checkpoint states, final guest diagnostics and original native tier counts exact |
| Audio-on route | Same complete route passes with PCM enabled | Same 709 edits / 723 changed bytes, no new assistance; only the added validated audio object is separate |
| Native execution | 2,920,491,782 native + 981 interpreted, **99.99996641% native** | Total 2,920,492,763 unchanged; 981 guard misses; all 460,685 block transfers native, zero interpreted |
| Digital PCM | 69,095,406 stereo frames, 44,100 Hz signed 16-bit; peak 13,000; zero runtime queue discard | Exact shared-reference PCM hash `7177686580420813080`; headless synthesis opens no device |
| Source activity | PSG 27,644,755, ADPCM 4,030,681, CDDA 49,762,727, mixed 65,958,163 nonzero frames | Source counts overlap; digital activity is separate from audible correctness |
| Bounded WAV | First 1,323,000 stereo frames / 5,292,044 bytes, truncation reported | First 30 guest seconds; byte-identical to retained upstream WAV; private output only |
| Paced SDL consumer | 709,078 frames submitted, device opens and queue drains; mute false | Separate short bootstrap using explicit hash-pinned SDK DLL search path; pause freezes guest/PCM and clears queue, resume advances |
| Authored checks | 76 consumer tests; 27 upstream suites; all 252 frontend tests pass with desktop enabled | Windows x64, clean empty-module test build; six desktop skips in the separate fallback invocation |

The exact source SHA256 is
`f873f8d0e06418dffbf1ed478cd46bf1eae6fdf4511fc2797db8193bf04c99f6`
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

PCM hashes reproduce the shared implementation's digital result. Independent
upstream Geargrafx 1.8.4 evidence covers 56 authored raw CDDA stereo pairs
(including 16 data-track silent pairs) and 24 settled PSG waveform-phase checks.
It does not establish full mixed/PSG/ADPCM PCM, reference resampling, analog
levels or independent retail-route/hardware parity. Prior 78-plan native
capture-module reference checks retain their original scope.

The first audio-off attempt completed the route/images but failed the consumer
harness's incorrect expectation of a disabled PCM object. The pinned runner
omits that object entirely when off. The harness was corrected against a real
authored runner/TCP test, and a fresh complete audio-off replay passed. The
failed attempt stays separate and is not counted as qualified.

The current pin's Windows embedded desktop consumer build omits `SDL3.dll`
beside its executable. The first bounded desktop startup therefore failed
before entering the guest and is retained. The successful paced check uses a
child-only SDK search path with an explicit DLL hash, without altering tool
source, build receipt or adjacent-output hashes. This is SDK-backed execution,
not a self-contained desktop package; the defect is reported upstream.

The paced check accepts/drains a real default SDL device stream, with
1,273 pause-flush presentation drops,
peak input queue 1,566 frames and zero
runtime loss. It is not a listening or analog loopback result. Unthrottled SDL
intentionally mutes speaker presentation while PCM/WAV generation continues.
The full route's headless PCM evidence is separate from this paced device test.

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
