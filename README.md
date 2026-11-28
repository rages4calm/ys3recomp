# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Development has reached the next boss beyond the Plate Mail cavern in Tigre Mine.**
The opening fight, fire and blue projectiles are captured; Adol is alive with
**82/100 HP** at frame **224,324**. The boss has not been defeated.
Power Ring, Crystal, Tablet and Plate Mail remain held; Plate Mail and Power Ring
are equipped. Play uses the qualified expanded build.

The selected ABI29 SDK remains
[`2143123`](https://github.com/rages4calm/pcenginerecomp/commit/2143123c0b9fa9fec064c55dad14973dfc6eca5b),
with 136 runtime/tooling source files. One additive build adds **541 guarded
identities**, bringing the catalogue to **72,460 emitted / 72,309
observed / 2,619 declared**. Compilation and execution remain separate.

The new **3,488-frame** checkpoint-based route executes **110,485,710 native /
zero interpreted instructions**, with zero guard misses. Fresh native and
independent-reference runs match at **55 semantic boundaries**, including full
RAM, RGB, digital PCM and HOST/CORE state apart from four execution-tier counters.
Verified position and health assists accelerate traversal; original game code
remains unchanged. This is bounded assisted progression, not campaign completion.

Fresh 120-frame native/repeat/reference checks and 600-frame paced TCP audio
checks pass from the retained pre-boss stairs waypoint. They are separate from
the active boss endpoint. Current-binary fresh execution witnesses
**14,296 identities**; **58,164
compiled identities remain unexercised**. The prior full cold reconstruction is
retained historical evidence; it was not rerun or attributed to this new binary.

Typed checkpoint diagnostics and upstream rendering helpers are available.
Softness and persistence remain at zero; the original world view remains selected.
Game-specific widescreen, settings UI and persistent saves remain future work.
SAVE/LOAD menu exercise does not establish usable saves or cross-process
persistence. Unseen source variants retain fallback.

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

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/2143123c0b9fa9fec064c55dad14973dfc6eca5b)
provides mixed live-overlay and history preparation, feedback, shared emission
and audited additive checkpoint continuation. It also supplies optional title
adapters and operation-local verified-input reuse; game enhancements still need
consumer implementation. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build is retained.

## Audio and checkpoints

Ordinary restore requires exact-build checkpoints and explicit reference capability.
The toolkit's [audited additive continuation](https://github.com/rages4calm/pcenginerecomp/blob/2143123c0b9fa9fec064c55dad14973dfc6eca5b/docs/CHECKPOINT_CONTINUATIONS.md)
is a separate, qualified module-only path with the same SDK and compiler/dependency
closure. It does not retroactively admit older ordinary-build checkpoints.
Original ABI28 captures remain source evidence; their checkpoints are never imported into ABI29.
Fresh native/repeat/reference forks compare the entire current machine core with
only four tier counters normalized. The guard and all other CORE/HOST bytes,
RAM, pixels, source counts and guest PCM remain strict.

The current paced 600-frame check executes 18,702,174 native / zero interpreted
instructions and accepts at least 441,857 fresh nonzero PCM frames beyond imported
audio. Zero unexpected active drops are observed; 388 planned pause-tail
frames are accounted separately. This is bounded SDL delivery evidence, not
listening or hardware equivalence. No new boot WAV is claimed.

The selected `nec-invalid` CD policy returns an invalid-command response with
sense for unknown commands. It does not implement those operations. Historical
`gear-good` qualifications keep their original compatibility labels; that response
profile is not selected. Default synthesized Q remains in use for this disc.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current63
git -C .deps/pcenginerecomp-current63 checkout --detach 2143123c0b9fa9fec064c55dad14973dfc6eca5b
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
