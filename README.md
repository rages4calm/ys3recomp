# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI29 with observation-history v2 and shared native emission is selected.**
Adol trades hits with the winged boss in Alcaino Ruins and uses a Healing
Herb to recover from **4 to 90 HP**. The qualified living checkpoint is at
frame **160,457**. Defeating the boss and earning the Moon Statue remain ahead.

The new **1,327-frame** combat and recovery stretch retires **42,297,936
native and zero interpreted** instructions using controller inputs alone.
The linked checkpoint records **4,900,077,123 native and zero interpreted**.
A separate **1,226-frame** branch from 4 HP reaches Game Over with
**39,282,912 native and zero interpreted** instructions.

The module contains **68,059 source identities**. All **439 additions**
execute across these branches. The verified route union exercises **65,141**
identities. Unseen code uses interpreter fallback.

Both branches match the same-build interpreter at 73 cuts for RAM, guest
pixels, digital PCM, and exact source retirements. A paced TCP check during
the boss fight confirms fresh audio acceptance by SDL. Unknown CD commands
receive the `nec-invalid` response.

See [STATUS](docs/STATUS.md) for the migration and historical evidence. Generated
source and qualified builds are private local artifacts; this repository contains
the authored consumer project, configuration, launchers and synthetic tests.

The [remaster direction](docs/REMASTER_DIRECTION.md) targets true widescreen,
coherent presentation and options, comfortable controller use and dependable
saves while preserving the game's art and gameplay. Those improvements continue
alongside native coverage; their individual readiness remains explicit.

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

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/6a4c547aec434c504e90092262b2ee66fcba3998)
provides history-v2 preparation, feedback, shared emission and same-build reference
execution. Shared CPU/device semantics and generation remain upstream; this project
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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current51
git -C .deps/pcenginerecomp-current51 checkout --detach 6a4c547aec434c504e90092262b2ee66fcba3998
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
