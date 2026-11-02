# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI28 with additive profile composition and fixed CD timing is selected.**
The fresh **104,745-frame** reset retires **3,209,517,525 native / zero interpreted**
instructions. Twelve separate own-checkpoint windows reach frame **114,051** and
**3,503,969,331 native / zero interpreted** instructions. The campaign remains
unfinished; unseen code retains interpreter fallback.

The assisted route covers item use, damage/death/continue, mine combat,
the wizard's defeat and Long Sword reward, miner dialogue, the deeper-mine boss,
town/lodge return and Alcaino combat. The twelve continuation windows cover
**432 / 2,232 / 960 / 1,716 / 504 / 678 / 522 / 336 / 342 / 288 / 336 / 960 frames** through deeper cavern traversal
and combat. These are bounded checkpoint-linked checks; the next boss is unverified.

The official module contains **58,039 source identities**, retaining all 58,035
prior keys and adding four that compile and execute. Across 83 MPR contexts,
947 C++ units and one header, **53,616 identities execute** in the qualified route;
4,423 compiled keys remain unexercised. Six retained identities are newly
exercised too. Unsupported and excluded observations are zero.

The additive composer preserves original raw captures and earlier contributions
within unchanged public limits. All thirteen route windows pass independent TCP
source, CPU/device, checkpoint, full RAM, image and digital-audio comparisons.
The latest **288 + 336 + 960 frames** retire **49,685,371 native / zero interpreted**
instructions and exercise two more previously compiled identities, with no new
writes, emission or rebuild. Earlier assisted progression retains a verified
living-HP refill from 30 to 60.
The earlier single 678-frame section retains its three verified position/HP edits.

Fresh tests at the new endpoint compare whole immediate and continued checkpoint
files, CORE/HOST, RAM, pixels and per-key counts over two 60-frame branches.
A separate paced 120-frame run confirms fresh nonzero PCM accepted by SDL with
zero observed active drops. Repeat, audio and exploratory forks are excluded
from route totals and coverage. Further movement discovers two uncompiled source
variants and two fallback retirements; that fork is preserved separately and
excluded from the zero-fallback route. No campaign, listening or hardware claim.

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

The selected [ABI28 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/cd5bff67b323098979345f76d5b87075fc628e72)
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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-additive51
git -C .deps/pcenginerecomp-additive51 checkout --detach cd5bff67b323098979345f76d5b87075fc628e72
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
