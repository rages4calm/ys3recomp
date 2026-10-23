# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA).

**This is an early hybrid milestone. It is not a completed native port.**
The shared tool translates identified HuC6280 instructions into guarded C++;
unseen code continues through its interpreter. Actual retired instruction counts,
source identities and replay results determine coverage, not executable format
or the amount of generated source.

The current 94,800-frame TCP route includes 1,065 normal-input frames beyond
the original first-boss approach, through combat, Game Over and Continue.
The expanded module adds **47 observed source identities**, moving **3,461
retirements from interpreted to native execution** on that same extended route.
It retires **2,953,438,406 native + 981 interpreted** instructions. All 39 image
checkpoints, exposed guest/source diagnostics and filtered 48 kHz PCM match the
old module; total retired work is unchanged. The original 25-checkpoint prefix
also remains exact. The inherited route uses journaled assistance; this extension
adds no RAM edits and establishes no boss victory or campaign completion.

The current tool pin is `c5aa9a26125edabdbe98a68bf716bff6eacd310e`, ABI **13**.
It adds a gated source-capture window without changing audio semantics. The
initial qualified baseline and previous milestones remain in
[toolchain.json](toolchain.json). See [status](docs/STATUS.md) for the evidence
and limits.

The current Windows desktop build places its pinned `SDL3.dll` beside the
executable. Startup, TCP controls and audio are verified with SDK directories
removed from the child PATH and an empty working directory. The loaded SDL
module is checked against that adjacent file; no SDK PATH workaround is needed.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-capture
git -C .deps/pcenginerecomp-capture checkout --detach c5aa9a26125edabdbe98a68bf716bff6eacd310e
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If the toolchain omits `ctest`, run
`python .deps/pcenginerecomp-capture/scripts/check.py --build build/upstream` and
`python -m unittest discover -s tests -v` instead.

The default host has no game module and uses interpreted execution. Authored
upstream synthetic suites qualify the runtime and direct emitter separately.
No retail input is needed to build or run these tests. Source verification
rejects the wrong commit, dirty tracked source, hidden index flags or the wrong
ABI. The current source digest is also checked through the upstream consumer
API; clone with LF source bytes as shown. An intentional development override
must name the exact clean commit. Private native builds additionally use the
shared descriptor/build/verify contract to pin module, inputs and executable.

## Private game development

Supply your own matching disc and System Card BIOS. No media, generated game
code, game captures or saves are distributed. Existing owner inputs remain
read-only. The qualified upstream private route can be reused by a local
developer who already has that evidence; see [development](docs/DEVELOPMENT.md).

The current route uses an explicit reference-emulator `gear-good` response for
an unknown CD command. That condition does not implement the unknown operation
or establish hardware correctness. Initial formatted blank BRAM is read-only;
guest SAVE/LOAD stays within one process. ABI 13 adds digital PSG, ADPCM and
CDDA mixing, bounded WAV capture and optional SDL playback. The original prefix
retains its audio-disabled/enabled qualification. The current extended route is
freshly checked with filtered 48 kHz audio. Digital PCM reproducibility and
device-stream acceptance have separate evidence. The current sound fix averages
ordinary ultrasonic PSG waveform
periods 1–5, matching Geargrafx's tested unfiltered half-gain digital profile
while preserving oscillator state. Expanded independent checks cover 49,258 PSG
stereo pairs across 3,262 authored cases and raw ADPCM decoder/control state at
all 16 rates.

Audio defaults to the original raw 44.1 kHz profile. Opt-in filtered playback
adds PSG/ADPCM filtering and supports 44.1 or 48 kHz output. Independent
Geargrafx checks match 59,505 filtered PSG and 34,112 filtered ADPCM stereo
frames. Separate authored checks cover the deterministic 64-tap resampler;
these do not establish parity with Geargrafx's resampler.

The prior raw and filtered packages retain their qualified original route and
headless-reference evidence. The current old-module and expanded-module packages
match processed and raw-source PCM throughout the extended route. A separate
paced 48 kHz check verifies device acceptance, pause/resume, controls and captures.
The bounded WAV covers the first 30 guest seconds; cumulative PCM and checkpoints
check the later section. These are digital and device-stream checks; independent
retail-mix, listening, analog and hardware parity remain unqualified.
See [development](docs/DEVELOPMENT.md) for capture and qualification.
Host save persistence, authentic console reset and campaign completion remain
unfinished.

Game configuration, overlay discovery, native coverage, enhancements, launcher
and extended gameplay checks belong here. Shared CPU/device semantics, media,
generation and reusable host features belong in the tool project. Improvements
must retain the reference path and measured native/interpreted accounting.

Authored project code is MIT licensed. That license grants no rights to the
game, firmware or game-derived output.
