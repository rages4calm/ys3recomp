# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI29 with observation-history v2 and shared native emission is selected.**
The assisted route reaches the **volcano snake's defeat and Stone Idol reward**.
The next boss has not been reached; the campaign remains unfinished.

The current own-build checkpoint at frame **136,505** records **4,148,299,112
native / zero interpreted** instructions. This is a cold Town checkpoint followed
by linked continuation, not a single-process campaign run. The separately replayed
**104,745-frame** cold route records **3,209,517,525 native / zero interpreted**;
the retained forward route reaches **114,813 / 3,527,737,024 native / zero interpreted**.
Verified historical assists cover navigation, HP, combat, death/continue and rewards.

The official module contains **63,651 source identities**, preserving all 59,258
prior keys and adding **4,393**. Every addition executes natively. The verified
route union exercises **60,693 identities**; **2,958 compiled keys remain
unexercised**. Shared emission produces **48 C++ units**, compared with 947 before.
The former **8,691,740 interpreted retirements** in the linked boss traversal now
execute natively. Unseen game code retains interpreter fallback.

TCP source, CPU/timing, recorded RAM, pixels and guest digital audio match the
original verified route. Fresh own-build native/repeat/interpreter forks compare
whole machine state with only four execution-tier counters normalized. Two paced
120-frame TCP runs confirm fresh nonzero SDL audio acceptance with zero observed
active drops. These are bounded assisted and internal-reference checks, not
campaign completion, listening, independent-console or hardware qualification.
The selected unknown-CD policy remains `nec-invalid`; unknown operations are unimplemented.

See [STATUS](docs/STATUS.md) for the migration and historical evidence. Generated
source and qualified builds are private local artifacts; this repository contains
the authored consumer project, configuration, launchers and synthetic tests.

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
owns game configuration, coverage and verification. The prior ABI28 build is retained.

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
