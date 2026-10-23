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
checkpoints and exposed guest/source diagnostics remain exact. The current
ABI16 migration retains those counts and both ABI15 audio profiles. Legacy
and default Gear timing each match a fresh headless reference. The
original 25-checkpoint prefix also remains exact. The inherited route uses
journaled assistance; this extension adds no RAM edits and establishes no boss victory or campaign completion.

The current tool pin is `3bd06b5055c92e9f368aab7023098ff8aa796854`, ABI **16**.
All 209 native source artifacts were regenerated and freshly rebuilt. Three
complete TCP routes qualify legacy audio, default Gear audio and audio off.
The toolkit adds base PC Engine `$F8..$FB` work-RAM aliases, BRK execution,
and guest-clock sprite collision/overflow events. There are 234 supported
opcode encodings; 22 reserved slots still trap. Full MPR/source identities
and native byte guards remain intact. Historical
milestones remain in [toolchain.json](toolchain.json); see
[status](docs/STATUS.md) for measured results and limits.

The current Windows desktop build places its pinned `SDL3.dll` beside the
executable. Startup, TCP controls and audio are verified with SDK directories
removed from the child PATH and an empty working directory. The loaded SDL
module is checked against that adjacent file; no SDK PATH workaround is needed.

## Open the local build

In a prepared development checkout, double-click **Play Ys III.cmd** to open
the privately selected qualified executable with a visible window and audio.
**Native Files.cmd** opens its generated C++ folder. The public repository keeps
those game-derived files in `.local/`, outside Git. A fresh clone needs the
owner's inputs and a qualified private build before these commands can run.

Arrows move; Z is button I, X is II, Shift is Select and Enter is Run.
Space pauses, F11 toggles fullscreen and Esc exits. Guest saves remain
session-only. The launcher verifies the selected inputs, module, runtime and
adjacent SDL package before starting; it does not install or download anything.
`python scripts/play_local.py --info` checks readiness without opening a game.

**Clean Old Build Files.cmd** runs the guarded cleanup plan retained locally.
It removes reviewed obsolete compiler intermediates while keeping qualified
executables, native source, inputs and verification receipts. The local runner
refuses changed files or paths outside its exact reviewed plan.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi16
git -C .deps/pcenginerecomp-abi16 checkout --detach 3bd06b5055c92e9f368aab7023098ff8aa796854
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If the toolchain omits `ctest`, run
`python .deps/pcenginerecomp-abi16/scripts/check.py --build build/upstream` and
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

The current route uses an explicit reference-emulator `gear-good` response.
New diagnostics identify all 53 unknown-command attempts as `$FF`, retaining
their counts and the last supplying command-latch write's CPU/source context.
Strict mode still faults on that command; unknown operations and REQUEST SENSE
remain unimplemented. This is a compatibility condition, without hardware
qualification. Initial formatted blank BRAM is read-only; guest SAVE/LOAD stays
within one process. Internal held-DAC/CDDA latch state remains separately
qualified; the route does not establish retail latch-port usage.

Audio defaults to raw 44.1 kHz with Gear timing. Filtered playback is opt-in at
44.1 or 48 kHz. Explicit `--audio-timing legacy` preserves the earlier PCM path.
The current filtered 48 kHz Gear and legacy routes each match a separately
frozen ABI16 headless run at all 39 checkpoints and three endpoints. Default
desktop Gear matches explicitly selected headless Gear. Both retain their
earlier PCM/WAV; audio off retains every exposed guest/native/source diagnostic.

A separate paced Gear 48 kHz check verifies actual device acceptance, input,
captures and pause/resume with zero runtime loss. The bounded WAV covers only
the first 30 guest seconds; cumulative PCM and checkpoints check the later route.
Independent Geargrafx checks cover finite BRK, work-RAM alias and sprite-event
cases, alongside retained audio checks. **324 consumer tests and 33 shared
suites / 328 Python tests pass, without skips.** These do not establish
independent retail-mix, listening, analog or hardware parity.
See [development](docs/DEVELOPMENT.md) for regeneration and
the explicit migration qualification matrix.
Host save persistence, authentic console reset and campaign completion remain
unfinished.

Game configuration, overlay discovery, native coverage, enhancements, launcher
and extended gameplay checks belong here. Shared CPU/device semantics, media,
generation and reusable host features belong in the tool project. Improvements
must retain the reference path and measured native/interpreted accounting.

Authored project code is MIT licensed. That license grants no rights to the
game, firmware or game-derived output.
