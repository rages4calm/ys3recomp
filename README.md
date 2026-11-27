# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Adol returns to Sarina and receives the Time Ring from the mayor.**
The exchange occurs at frame **185,562**. Adol reaches the outside of the
mayor's house at frame **186,482**, with **90/90 HP**.

The new **12,655-frame** route retires **364,331,034 native and zero interpreted
instructions**, replacing 87,262 fallback retirements. All **518 new source
identities execute**. It uses ordinary controls with no new assists; earlier
verified assists remain part of its ancestry.

The module contains **69,314 guarded source identities**. Fresh execution by
this binary witnesses **25,206** identities; **44,108** remain unexercised by it.
The separately named mixed-package qualified lineage witnesses 66,373, including
imported baseline evidence. Its 2,941 unexercised identities include 78 declared-only
entries. Unseen source variants retain interpreter fallback.

The selected ABI29 toolkit is
[`d14ce07`](https://github.com/rages4calm/pcenginerecomp/commit/d14ce0763271a66a2a7d9d7be5f100774c897d51),
with 123 runtime/tooling source files. One new audited cold baseline reaches
frame 173,827 with 5,322,505,339 native and zero interpreted instructions.
The supported additive-module continuation preserves that checkpoint unchanged
and imports its work into the new package. The linked **5,686,836,373 native /
zero interpreted** total is a qualified multi-package lineage, not a single
binary's cold campaign. Older ordinary-build checkpoints remain with their packages.

Original-program checks cover 71 control boundaries; the new native scenario
keeps those 71 inputs with six semantic checkpoints. Fresh 120-frame
native/repeat/reference forks and a 600-frame paced SDL audio check pass.
A separate 1,802-frame current-binary cold-entry smoke matches a fresh interpreter
reference; it does not repeat the full cold prefix. Unknown CD commands receive
the `nec-invalid` response.

See [STATUS](docs/STATUS.md) for measured scopes and historical evidence.
Generated source, builds, game inputs and raw proof remain private.
The [remaster direction](docs/REMASTER_DIRECTION.md) records presentation,
controller and save improvements and their individual readiness.

## Play the local build

In a prepared checkout, double-click **Play Ys III.cmd**. Press Enter/Run at
the System Card menu, choose Beginning, then Proceed at the blank-BRAM prompt.
**Native Files.cmd** opens the selected generated C++ folder. A fresh clone
needs owner-supplied media and a qualified private build; generated game source,
assets, captures and saves are excluded from Git.

Arrows move; Z jumps (button I), X attacks (button II). Shift opens the
Command menu (Select), and Enter is Run. Space pauses, F11 toggles fullscreen
and Esc exits. The launcher verifies the selected inputs, module, runtime and
adjacent SDL package; it downloads and installs nothing.
`python scripts/play_local.py --info` checks readiness without opening a game.
Guest saves are volatile; cross-process game saves are not implemented.

**Controllers:** the host automatically uses the first SDL-recognized gamepad,
including one connected during play. Keep the game window focused.

| Controller input | Ys III action |
| --- | --- |
| D-pad or left stick | Move |
| A / Cross (bottom face button) | Jump / button I |
| B / Circle (right face button) | Attack / button II |
| Back / Select | Command menu |
| Start | Run / confirm |

Keyboard controls remain available for pause, fullscreen and exit. The shared
host's virtual-device checks cover mapping, hot-plugging and input release;
physical-controller verification is separate.

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/d14ce0763271a66a2a7d9d7be5f100774c897d51)
provides mixed live-overlay and history preparation, feedback, shared emission
and audited additive checkpoint continuation. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build is retained.

## Audio and checkpoints

Ordinary restore requires exact-build checkpoints and explicit reference capability.
The toolkit's [audited additive continuation](https://github.com/rages4calm/pcenginerecomp/blob/d14ce0763271a66a2a7d9d7be5f100774c897d51/docs/CHECKPOINT_CONTINUATIONS.md)
is a separate, qualified module-only path with the same SDK and compiler/dependency
closure. It does not retroactively admit older ordinary-build checkpoints.
Original ABI28 captures remain source evidence; their checkpoints are never imported into ABI29.
Fresh native/repeat/reference forks compare the entire current machine core with
only four tier counters normalized. The guard and all other CORE/HOST bytes,
RAM, pixels, source counts and guest PCM remain strict.

The current paced 600-frame check verifies fresh nonzero PCM accepted by SDL beyond
imported audio, with zero active drops. Planned pause clears and shutdown drains
are counted separately. The fast-forward route compares guest digital PCM; it
does not claim a newly captured boot WAV or listening/hardware parity.

The selected `nec-invalid` CD policy returns an invalid-command response with
sense for unknown commands. It does not implement those operations. Historical
`gear-good` qualifications keep their original compatibility labels; that response
profile is not selected. Default synthesized Q remains in use for this disc.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current60
git -C .deps/pcenginerecomp-current60 checkout --detach d14ce0763271a66a2a7d9d7be5f100774c897d51
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

The default empty-module host uses interpreted execution. Public tests use
authored synthetic fixtures, without game inputs.
See [status](docs/STATUS.md), [development](docs/DEVELOPMENT.md) and
[toolchain.json](toolchain.json) for measured scopes and historical milestones.

Owner inputs remain read-only. **Clean Old Build Files.cmd** removes unbound
compiler intermediates with visible progress and a private receipt; use
`--no-pause --preview` to review without deleting. This command handles compiler
files; it does not retire historical test runs. The current and one prior
qualified build remain ready to use. Required closed verification records are
compressed inside `.local/evidence-history`, with per-file hashes and an index.
Obsolete build copies are deleted rather than moved elsewhere on the drive.
GitHub contains authored source and cannot restore excluded private artifacts.

Authored code is MIT licensed; that grants no rights to game, firmware or
game-derived output.
