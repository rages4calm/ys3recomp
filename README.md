# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Adol defeats the winged boss in Alcaino Ruins and receives the Moon Statue.**
The game displays the named reward, and the qualified checkpoint reaches
frame **164,251** with **90 HP**.

The assisted **3,794-frame** continuation retires **121,514,843
native and zero interpreted instructions**, converting 7,304
previous fallback retirements. The linked own-build route records
**5,021,591,966 native and zero interpreted** instructions.
Verified assists include 9 current-HP refills and two
boss-HP reductions that preserve ordinary attacks for the finishing blows.

The latest selected toolkit is ABI29 revision
[`1c765dc`](https://github.com/rages4calm/pcenginerecomp/commit/1c765dcd96923e806bf8009245d8fe4d1e16c402).
Its 118 runtime and tooling source files match the final public update
[`5a8e325`](https://github.com/rages4calm/pcenginerecomp/commit/5a8e325860966b338bb13f10e09a65669c60eb64).
It supplies disc-source diagnostics, live-overlay branch discovery, input profiles
and presentation controls.
A bulk read-only sweep adds candidates from authentic paused RAM, alongside
all genuine execution history. The module contains **68,387 source
identities**, of which **65,396** execute across the verified route
union. **2,991 compiled identities remain unexercised**, including the
78 declared-only identities. Unseen source variants retain interpreter fallback.

Same-build interpreter comparisons match the controls, full RAM, guest pixels,
digital PCM and exact retired source identities. The upgraded build replays
the retained routes and natural Game Over branch. A separate paced TCP check
during the defeat sequence verifies fresh nonzero audio accepted by SDL.
Unknown CD commands receive the `nec-invalid` response.

See [STATUS](docs/STATUS.md) for measured scopes and historical evidence.
Generated game source and qualified builds are private local artifacts.
The repository contains authored consumer source, configuration, launchers and
synthetic tests. The [remaster direction](docs/REMASTER_DIRECTION.md) records
presentation, controller and save improvements and their individual readiness.

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

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/1c765dcd96923e806bf8009245d8fe4d1e16c402)
provides mixed live-overlay and history preparation, feedback, shared emission
and same-build reference execution. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build is retained.

## Audio and checkpoints

Use exact-build checkpoints and explicit reference capability. Original ABI28
captures remain source evidence; their checkpoints are never imported into ABI29.
Fresh native/repeat/reference forks compare the entire current machine core with
only four tier counters normalized. The guard and all other CORE/HOST bytes,
RAM, pixels, source counts and guest PCM remain strict.

Separate paced 120-frame runs verify fresh nonzero PCM accepted by SDL beyond
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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current58c
git -C .deps/pcenginerecomp-current58c checkout --detach 1c765dcd96923e806bf8009245d8fe4d1e16c402
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
