# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA).

**This is an early hybrid milestone. It is not a completed native port.**
The shared tool translates identified HuC6280 instructions into guarded C++;
unseen code continues through its interpreter. Actual retired instruction counts,
source identities and replay results determine coverage, not executable format
or the amount of generated source.

On the retained 93,735-frame route, native execution increased from **0.17%
to 95.34%, then 99.99997%**. The current module covers 44,832 observed identities
in 57 mappings. Exactly **981 retirements remain interpreted** around an
excluded temporary-code-patch span. All 25 guest image hashes and exposed guest
diagnostics still match; total retired work is unchanged. This route includes
journaled assistance and ends at a first-boss encounter, without a victory or
campaign-completion claim.

The current tool pin is `df7e16d465b1618e936d2750bdbe3259b56996a9`, ABI **13**.
The initial qualified `33fe46d4274584da5ba55b419a240f248df4158d` baseline is
retained in [toolchain.json](toolchain.json). See [status](docs/STATUS.md) for
the evidence and limits.

The current Windows desktop build places its pinned `SDL3.dll` beside the
executable. Startup, TCP controls and audio are verified with SDK directories
removed from the child PATH and an empty working directory. The loaded SDL
module is checked against that adjacent file; no SDK PATH workaround is needed.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-accuracy
git -C .deps/pcenginerecomp-accuracy checkout --detach df7e16d465b1618e936d2750bdbe3259b56996a9
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If the toolchain omits `ctest`, run
`python .deps/pcenginerecomp-accuracy/scripts/check.py --build build/upstream` and
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
CDDA mixing, bounded WAV capture and optional SDL playback. The retained route
is checked with audio disabled and enabled; native work and guest images remain
exact. Digital PCM reproducibility and device-stream acceptance have separate
evidence. The current sound fix averages ordinary ultrasonic PSG waveform
periods 1–5, matching Geargrafx's tested unfiltered half-gain digital profile
while preserving oscillator state. Expanded independent checks cover 49,258 PSG
stereo pairs across 3,262 authored cases and raw ADPCM decoder/control state at
all 16 rates. Filtered,
resampled, full mixed and analog audio correctness remain unqualified.
The retained gameplay route's PCM and bounded WAV remain unchanged; that route
provides regression evidence, while authored reference vectors demonstrate the
ultrasonic correction.
Host save persistence, authentic console reset and campaign completion remain
unfinished.

Game configuration, overlay discovery, native coverage, enhancements, launcher
and extended gameplay checks belong here. Shared CPU/device semantics, media,
generation and reusable host features belong in the tool project. Improvements
must retain the reference path and measured native/interpreted accounting.

Authored project code is MIT licensed. That license grants no rights to the
game, firmware or game-derived output.
