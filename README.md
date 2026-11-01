# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI27 is selected.** The verified **104,745-frame** reset route retires
**3,209,517,525 native instructions and zero interpreted instructions**.
The full campaign remains unfinished; unseen code retains interpreter fallback.

The assisted route covers item use, damage/death/continue, mine combat,
the wizard's defeat, Long Sword acquisition and equipment, miner dialogue,
the deeper-mine boss and rewards, town/lodge return and Alcaino combat.
A separate read-only **432-frame** native checkpoint extension advances farther
through that combat area. These are bounded checks, not campaign completion.
The earlier ABI26 staircase check remains historical evidence for that build;
the current endpoint is the actual Alcaino combat frontier.

The official module contains **58,002 source identities** in 83 MPR contexts,
across 947 C++ translation units and one header. All 57,752 previous identities
remain, and all **250 additions compile and execute** across the route and
extension. The two checks exercise 53,528 identities; 4,474 retained compiled
keys are not exercised here. No observed source variant is excluded or unsupported.
Compilation alone is not execution evidence.

TCP verification compares settled CPU/source/device state, full RAM, guest
images and digital PCM. All 5,523 main-route steps have bounded progress checks;
6,899 previously interpreted retirements become native on the same ABI27 controls.
The separate extension promotes seven more retirements, executing 13,795,134
native instructions with zero fallback. Its imported prefix is not counted again.
All 309 main-route assists have exact-byte authority, full RAM readbacks,
source-alias exclusions and typed write-effect proofs. No program, quest,
item, equipped-weapon or STR bytes were edited.

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

The selected [ABI27 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/d71add52a88ab18084ecd3ea856b9b4df80a7469)
uses the official provenance-preserving composer and stable emitter.
The [semantic step validator](https://github.com/rages4calm/pcenginerecomp/commit/929dcc3b9affe3af70eeaa49c6091baceb1bf056)
is separately pinned. Shared CPU/device semantics and generation remain
upstream; this project owns game configuration, coverage and verification.
The qualified ABI26 build is retained.

## Audio and checkpoints

The fresh native reset is compared with an explicitly checkpoint-linked ABI27
source reference. Original captures retain their ABI, checkpoint origin and
retirement counts; reconstruction is excluded from compilation history and
execution totals. Failed runs remain failed. The final native qualifier starts
from reset in one process. Discovery and debugging use exact-build checkpoints.

Same-build restores match whole immediate and continued checkpoint files and
machine cores over 60 fresh native frames. A separate paced 120-frame check
verifies fresh nonzero PCM accepted by SDL beyond imported audio, with zero
active drops. Planned pause clears and shutdown drains are counted separately.
The main route's fast-forward presentation is muted; its digital PCM and capped
boot WAV are compared independently. This is not listening or hardware parity.

The selected `nec-invalid` CD policy receives complete unknown commands and
returns an invalid-command response with sense. It does not implement those
unknown operations. Differences from independent references remain documented;
the historical `gear-good` response is not the selected policy.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi27-unknown46
git -C .deps/pcenginerecomp-abi27-unknown46 checkout --detach d71add52a88ab18084ecd3ea856b9b4df80a7469
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
`--no-pause --preview` to review without deleting. It preserves qualified
packages, generated native source, inputs and replay evidence. GitHub contains
authored source and cannot restore excluded private artifacts.

Authored code is MIT licensed; that grants no rights to game, firmware or
game-derived output.
