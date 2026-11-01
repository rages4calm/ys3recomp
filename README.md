# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI28 with fixed CD timing is selected.** The verified **104,745-frame** reset route retires
**3,209,517,525 native instructions and zero interpreted instructions**.
The full campaign remains unfinished; unseen code retains interpreter fallback.

The assisted route covers item use, damage/death/continue, mine combat,
the wizard's defeat, Long Sword acquisition and equipment, miner dialogue,
the deeper-mine boss and rewards, town/lodge return and Alcaino combat.
Separate own-native checkpoint extensions cover **432** combat frames,
**2,232** stair/combat frames and **960** new waterfall cavern frames. These
are bounded assisted checks, not campaign completion or one continuous cold run.

The official module contains **58,032 source identities** in 83 MPR contexts,
across 947 C++ translation units and one header. All 58,031 previous identities
remain; the one addition compiles and executes. The checks exercise **53,576**
identities; 4,456 compiled keys remain unexercised. No captured variant is excluded
or unsupported. Compilation alone is not execution evidence.

TCP verification compares settled CPU/source/device state, full RAM, guest
images and digital PCM. The fresh main route retains 5,523 bounded steps and
309 typed data assists. The three extensions retire 13,795,134, 70,860,852 and
**30,980,373 native instructions**, respectively, with **zero interpreted
instructions**. The new waterfall window promotes its reference's sole
interpreted retirement and matches all 89 controls and 94 RAM/image observations.

The waterfall window includes one verified living-HP refill, 28 to 60, leaving
the natural maximum unchanged. Its unassisted checkpoints are retained. Assists
require exact expected bytes, full RAM readbacks, source-alias exclusions and
typed write-effect proofs. No program, quest, item, equipment or STR bytes were
edited. Imported prefixes and overlapping source histories are not new execution.

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

The selected [ABI28 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/a96e7891c33690d41f6fe12ce1904fe160a0c9a2)
uses the official provenance-preserving composer and stable emitter.
The [semantic step validator](https://github.com/rages4calm/pcenginerecomp/commit/929dcc3b9affe3af70eeaa49c6091baceb1bf056)
is separately pinned. Shared CPU/device semantics and generation remain
upstream; this project owns game configuration, coverage and verification.
The qualified ABI27 build is retained.

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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi28-timing48
git -C .deps/pcenginerecomp-abi28-timing48 checkout --detach a96e7891c33690d41f6fe12ce1904fe160a0c9a2
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
