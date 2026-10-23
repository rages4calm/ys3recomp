# Consumer status - 23 October 2026

Opt-in filtered audio and 48 kHz resampling are verified on Windows x64 with
ABI 13 and descriptor schema 1. This remains a bounded hybrid port foundation;
full native coverage and a finished game port remain unfinished.

| Evidence | Result | Scope |
|---|---|---|
| Current tool | `72bd5a2d4616d50d8b19f0d78c5af6ddfbd1c777`, ABI 13, schema 1 | Exact clean source pin; no runtime fork |
| Module | 44,832 identities / 57 full MPR contexts, 207 translation units and one generated header | All 208 retained ABI-13 artifacts rehashed and reused unchanged; fresh official builds |
| Official builds | Raw 44.1 kHz, filtered 44.1 kHz and filtered 48 kHz | Separate descriptors/build bindings and adjacent pinned SDL DLL |
| Full TCP routes | Fresh raw 44.1 kHz and filtered 48 kHz packages pass all 93,735 frames | All 25 images/checkpoint states and three endpoint observations; separate matching headless references |
| Native execution | 2,920,491,782 native + 981 interpreted, **99.99996641% native** | Total 2,920,492,763 unchanged; 981 guard misses; all 460,685 block transfers native, zero interpreted |
| Raw bridge | Original PCM and first-30-second WAV unchanged | Default/raw schema and digital output remain exact against the previous qualified package |
| Filtered source projection | Original 69,095,406 source frames, raw PCM hash, peak and activity unchanged | Every guest/native/source diagnostic remains exact at all matched observations |
| Filtered output | 75,205,884 stereo frames at 48 kHz; peak 13,355; zero runtime discard | PCM hash `8515195911678413936`; processed output matches the new headless reference |
| Filtered WAV | First 1,440,000 output frames / 5,760,044 bytes, truncation reported | First 30 guest seconds; byte-identical packaged/headless WAV, private output only |
| Paced playback | Separate filtered 44.1 and 48 kHz checks pass | TCP input, guest/window captures, pause freeze, resume advance, actual package/DLL and device telemetry |
| Consumer checks | 190 synthetic tests pass | Legacy raw qualification remains unchanged; new profile, DSP, WAV and qualification rejection cases |
| Shared checks | 28 suites / 291 Python tests with desktop enabled | Fresh embedded and standalone runs have zero skips; clean default configuration separately has eight intentional desktop skips |

The exact source SHA256 is
`0bfa0312dfaa28e4ae0371007385086c885d8fd6f4e5a231870f4d61b557aef3`
(53 relevant files). Clang 22.1.8, CMake 3.31.12, Ninja, Python 3.14.5 and
SDL 3.4.18 are the qualified local toolchain. Other hosts/controllers remain
unqualified. All seven protected inputs, the original capture and generated
module hashes remain unchanged. No owner installation or saves are used.

## Audio profiles and independent evidence

The default raw profile stays at 44,100 Hz signed 16-bit stereo with its old
telemetry schema. The full raw route retains 69,095,406 frames, peak 13,000,
PCM hash `7177686580420813080` and zero runtime discard. Its overlapping
nonzero source counts remain PSG 27,644,755, ADPCM 4,030,681 and CDDA 49,762,727;
mixed activity remains 65,958,163. Its first 1,323,000-frame WAV is unchanged.

Filtered playback is opt-in at 44.1 or 48 kHz. Geargrafx 1.8.4 independently
matches 59,505 filtered PSG stereo frames across 3,266 authored cases and
34,112 filtered held-ADPCM stereo frames across 17 cases. The external
implementation is separately compiled from hash-bound unmodified sources.
PSG checks include chunk sizes 1 and 509; ADPCM filtering is checked sample by
sample, without an ADPCM chunk-invariance claim. These qualify finite digital
filter stages rather than independent retail-route mixed audio.

Separate authored DSP checks cover exact integer vectors, spectral behavior,
chunk invariance, frame accounting and raw preservation. At 44.1 kHz the output
resampler is identity. At 48 kHz the toolkit uses a deterministic 64-tap,
160-phase Q30 FIR: output frames equal `floor(source_frames * 160 / 147)`,
latency is 31 source frames, initial history is zero and no tail is flushed.
These checks do not claim Geargrafx resampler parity. The full filtered route
records mixed activity 71,837,781; source activity counters remain in the
44.1 kHz domain. Output frames, WAV and queue telemetry use the selected rate.

The distinct DSP qualifier compares old raw, new raw, new processed and new
headless reference observations. It requires every original guest diagnostic,
PC/MPR/source identity, clock, native/interpreted count, block count, image,
input and assist transaction to remain exact. Validated presentation metadata,
checkpoint WAV drain counters and the TCP port are handled separately.
Raw PCM/WAV must remain exact, filtered raw-source PCM must project exactly to
that baseline, and processed PCM/WAV must match the new reference. Exact
descriptor/build, executable, DLL and reviewed reference artifacts are rehashed.

## Packaged playback and execution limits

All fresh desktop packages place the pinned `SDL3.dll` beside the executable.
Tests start in new empty working directories with SDK directories and other
DLL search shortcuts removed from the child PATH. Live module inspection
binds the running PID/executable to the adjacent DLL's actual path and hash.
No SDK PATH workaround is needed.

The full route is hidden and unthrottled: SDL presentation is intentionally
muted and output frames are submitted/dropped equally, while PCM/WAV generation
continues without runtime loss. Intermediate pending output must fit the
8,192-frame ring; final observations require zero pending frames. Saturated
headless WAV telemetry establishes a possible bounded drain interval, not an
exact intermediate pending count. Headless synthesis opens no device.

Separate paced checks generate 710,526 source frames at each filtered rate.
The 44.1 kHz run submits 710,526 frames, with 2,393 presentation drops and a
1,364-frame peak queue. The 48 kHz run submits 773,361 frames, with 2,782 drops
and a 1,675-frame peak queue. Both finish with empty queues, zero runtime loss,
device open and mute false. Actual queried devices report respectively 44.1
and 48 kHz, stereo, numeric SDL format 33056. Pause freezes source/DSP/guest
state; resume advances it. The CDDA-dominated opening at 44.1 kHz retains raw
PCM, so this short check alone demonstrates no audible filter improvement.
Device acceptance and digital hashes do not establish listening, analog
loopback or hardware correctness.

The consumer supervises complete routes with its explicit 1,800-second
watchdog and official shared verification/build bindings before and after.
The descriptor's 600-second `project.run` limit is not applied. This is
consumer-supervised route qualification, separate from shared `project.run`.
The initial audio-off ABI-12-to-13 bridge remains retained; it was not rerun
for this source-compatible DSP upgrade. Prior attempts, failures and qualified
raw baselines remain frozen with explicit source-epoch preservation mappings.

## Native history and remaining scope

The initial replay retired 5,050,558 native and 2,915,442,205 interpreted
instructions (0.17%). The first 2,048-identity module reached 95.34%; the
44,832-identity module reached the present 99.99996641%. Emission and build
counts alone establish no executed coverage. Unvisited overlays are unqualified.

The raw capture contains 44,836 identities / 57 mappings with no lost or
unreadable retirements. The verified-restored temporary jump patch's entire
six-byte span is excluded across mappings and source variants: four identities
/ 981 original-profile hits. All 709 assisted transactions are checked against
observed instruction-fetch bytes; no other assisted code is promoted.

The unchanged route uses 709 edits / 723 changed bytes and ends at an assisted
first-storehouse-boss encounter with visible damage. It establishes no victory,
unassisted encounter or campaign completion. The explicit `gear-good` response
is still used for 51 unknown CD commands; those operations remain unimplemented.
Startup remains the BIOS-backed IPL-entry sandbox. Initial formatted blank
BRAM is read-only; guest SAVE/LOAD stays volatile within one process.
Persistent host saves, authentic console reset, independent whole-mix retail
audio parity, analog sound and hardware compatibility remain unfinished.
