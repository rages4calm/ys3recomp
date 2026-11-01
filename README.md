# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI28 with fixed CD timing is selected.** The verified **104,745-frame** reset
route retires **3,209,517,525 native instructions and zero interpreted instructions**.
The campaign remains unfinished; unseen code retains interpreter fallback.

The assisted route covers item use, damage/death/continue, mine combat,
the wizard's defeat and Long Sword reward, miner dialogue, the deeper-mine boss,
town/lodge return and Alcaino combat. Separate own-native checkpoint windows
cover **432**, **2,232**, **960** and **1,716** frames. These are bounded checks,
not campaign completion or one continuous cold run. The newest window continues
beyond the waterfall through cavern traversal and combat; the next boss is unverified.

The official module contains **58,035 source identities**, retaining all 58,032
previous keys and adding three that compile and execute. Across 83 MPR contexts,
947 C++ units and one header, **53,606 identities execute** in the qualified route;
4,429 compiled keys remain unexercised. Unsupported and excluded observations are zero.

The new 1,716-frame window retires **54,249,829 native / zero interpreted** instructions,
promoting three interpreted reference retirements. All 35 controls and 37 full
RAM/image observations match the authentic reference; no new data or code writes
occur in this window. Retained verified data assists remain labeled separately.
TCP checks compare CPU/source/device state, RAM, images and digital PCM.

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

The selected [ABI28 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/9d219b7a27fa67ff3f31a124e5d449b7eaf1789b)
uses the official provenance-preserving composer and stable emitter.
The [semantic step validator](https://github.com/rages4calm/pcenginerecomp/commit/929dcc3b9affe3af70eeaa49c6091baceb1bf056)
is separately pinned. Shared CPU/device semantics and generation remain
upstream; this project owns game configuration, coverage and verification.
The prior qualified ABI28 build is retained.

## Audio and checkpoints

The fresh native reset is compared with an explicitly checkpoint-linked ABI27
source reference. Original captures retain their ABI, checkpoint origin and
retirement counts; reconstruction is excluded from compilation history and
execution totals. Failed runs remain failed. The final native qualifier starts
from reset in one process. Discovery and debugging use exact-build checkpoints.

The ABI27-to-ABI28 comparison admits the source-derived fixed-timing field and
five tier counters; all other machine-core bytes remain strict. All 26 main-route
checkpoint comparisons pass. Historical captures keep their original labels;
no cross-ABI checkpoint is converted or imported. `gear-distance` remains a
separate opt-in timeline without this native-route qualification.

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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-recovery50-delta
git -C .deps/pcenginerecomp-recovery50-delta checkout --detach 9d219b7a27fa67ff3f31a124e5d449b7eaf1789b
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
