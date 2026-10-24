# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA).

**This is an early hybrid milestone. It is not a completed native port.**
The shared tool translates identified HuC6280 instructions into guarded C++;
unseen code continues through its interpreter. Actual retired instruction counts,
source identities and replay results determine coverage, not executable format
or the amount of generated source.

The current **95,686-frame** TCP route adds **886 normal-input frames** beyond
the retained 94,800-frame prefix, through corridor traversal, boss combat and
an equipment-menu return. The expanded module adds **three observed source
identities**, moving **43 retirements from interpreted to native execution**
when compared with the old module on that same extended route. It retires
**2,980,431,691 native + 981 interpreted** instructions. All 68 image/checkpoint
states, exposed guest/source/CD diagnostics and same-profile PCM/WAV remain
exact. The route adds no new RAM edits to its inherited assisted prefix.
The player ends at 20/40 HP with the boss alive and equipment unchanged;
this establishes no boss victory or campaign completion.

The tool pin stays `3bd06b5055c92e9f368aab7023098ff8aa796854`, ABI **16**,
with no runtime migration. The new module contains 44,882 eligible source
identities in 57 full MPR contexts. Its 208 C++ translation units and one header
were built through one fresh 234-step official desktop build. Old and expanded
modules each complete the extended route using default Gear filtered 48 kHz.
The retained three-mode 94,800-frame route and its two headless references
remain separate historical evidence. Full MPR/source identities, native byte
guards and all four excluded source variants remain intact. See
[status](docs/STATUS.md) for measured results and limits and
[toolchain.json](toolchain.json) for historical milestones.

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
The existing approximately 119 MiB plan and a separate approximately 63 MiB
review of newer private intermediates remain owner-run plans. Neither was
executed. The root cleanup command is unchanged.

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

The retained and extended routes use the explicit reference-emulator
`gear-good` response profile. The 95,686-frame route records 54 unknown
command attempts, all `$FF`, with 54 accepted reference responses; the older
94,800-frame record remains 53. Strict mode still faults. Unknown operations
and REQUEST SENSE remain unimplemented, without hardware qualification.
Initial formatted blank BRAM is read-only; guest SAVE/LOAD stays within one
process. Internal held-DAC/CDDA latch state remains separately qualified;
the route does not establish retail latch-port usage.

Audio defaults to raw 44.1 kHz with Gear timing. Filtered playback is opt-in at
44.1 or 48 kHz. Explicit `--audio-timing legacy` preserves the earlier PCM path.
The new 95,686-frame comparison covers default Gear filtered 48 kHz on the old
and expanded modules. It does not repeat the retained legacy/off matrix or add
a new headless retail reference. Its processed PCM has 76,771,220 output /
70,533,559 source frames, hash `3837543589595640322` and zero runtime discard;
the strict native-source qualifier verifies exact same-profile PCM/WAV conservation.

Full-route playback is unthrottled with intentionally muted SDL presentation.
A separate paced check on the new package verifies device acceptance, input,
captures and source/processing/CD pause freeze and resume. It submitted 773,361
frames at 48 kHz with zero runtime loss, 2,481 host presentation drops and an
empty final queue. This is startup/device evidence, without a listening claim.
Full-route WAV capture is capped at the first 30 guest seconds; cumulative
PCM and checkpoints verify later audio.

**339 consumer tests pass without skips.** The unchanged
shared checker passed **33 suites / 328 Python tests, zero skips**, reusing the
retained empty-module desktop build. No fresh shared build is claimed.
Finite Geargrafx BRK, work-RAM alias, sprite and retained audio checks stay
historical evidence. These do not establish independent retail-mix, listening,
analog or hardware parity. See [development](docs/DEVELOPMENT.md) for the strict
native-gain provenance contract. Host save persistence, authentic console reset
and campaign completion remain unfinished.

Game configuration, overlay discovery, native coverage, enhancements, launcher
and extended gameplay checks belong here. Shared CPU/device semantics, media,
generation and reusable host features belong in the tool project. Improvements
must retain the reference path and measured native/interpreted accounting.

Authored project code is MIT licensed. That license grants no rights to the
game, firmware or game-derived output.
