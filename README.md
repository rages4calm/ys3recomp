# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Development has reached the next boss beyond the Plate Mail cavern in Tigre Mine.**
The opening fight, fire and blue projectiles are captured; Adol is alive with
**82/100 HP** at frame **224,324**. The boss has not been defeated.
Power Ring, Crystal, Tablet and Plate Mail remain held; Plate Mail and Power Ring
are equipped. Play now uses the newly qualified room-expansion build.

The build SDK is now ABI29
[`62c706c`](https://github.com/rages4calm/pcenginerecomp/commit/62c706c51e3e7b8d59c235c30093cc47f95af1f3),
with 138 runtime/tooling source files. **The full 136-selector matrix passes
and Play selects the new build.** One recoverable build
reuses the merged room history and adds **12,854 identities**, yielding
**85,314 emitted / 85,184 observed / 2,619 declared**, with 130 declared-only.
Fresh current-binary execution witnesses **83,231 identities**; **2,083 compiled
identities remain unexercised**. The 525 interpreted source identities observed
in this matrix belong to selector 135's frontier.

One fresh cold reconstruction reaches frame **224,324** with
**6,872,766,466 native / zero interpreted instructions / zero guard misses**.
It preserves the retained assisted route and exact original source counts;
only the new package's own checkpoints are restored.

Across **135 native-qualified selectors**, bounded native/reference checks retire
**2,256,852,676 native / zero interpreted instructions / zero guards**.
That promotes **37,007,421 formerly interpreted retirements** on those same
selectors. All 136 cases together execute 2,281,234,306 native + 726,584 interpreted
instructions. Selector 135 passes the fixed CD-audio leadout boundary but retains
those **726,584 interpreted instructions and guards**, alongside 24,381,630 native
instructions; full CORE/HOST equality and native qualification are withheld for
that frontier. Full RAM, RGB, digital PCM, controls and source counts agree.

The checks use fresh isolated processes and verified loader warps. Sixty cases
complete 600 exercise frames; 16 stop on death and 60 leave the selected room.
Those 76 incomplete exercises do not establish complete room or campaign coverage.
Separate 120-frame native/repeat/reference and 600-frame process-muted paced-audio
checks pass from the new cold run's own safe pre-boss checkpoint.

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

The build [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/62c706c51e3e7b8d59c235c30093cc47f95af1f3)
provides mixed live-overlay and history preparation, feedback, shared emission
and audited additive checkpoint continuation. It also supplies optional title
adapters and operation-local verified-input reuse; game enhancements still need
consumer implementation. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build remains available as the prior runnable package.

## Audio and checkpoints

Ordinary restore requires exact-build checkpoints and explicit reference capability.
The new recovery-built package establishes a fresh cold baseline and restores
only its own checkpoints. [Toolkit issue 60](https://github.com/rages4calm/pcenginerecomp/issues/60)
is fixed upstream in
[`98a5e83`](https://github.com/rages4calm/pcenginerecomp/commit/98a5e83d20d41a56676ca8d932417f7b05971f75),
which has not been adopted by this 62c706c package. Adopting that fix requires
new preparation and a fresh cold baseline; it cannot admit 2143123/62c706c
packages through a newer controller alone. This milestone stays on its frozen
pin and owning-package restores. Historical cache-producer continuations keep their
original scope. Original ABI28 captures remain source evidence; their checkpoints
are never imported into ABI29.

The new package's 120-frame native/repeat/reference forks execute 3,743,555
instructions per run, with zero native fallback and zero guards. Native/repeat
checkpoint bytes match exactly. Native/reference full CORE/HOST matches with only
four execution-tier counters normalized; guards remain strict. Its 600-frame
paced native/reference checks execute 18,728,072
instructions each and generate 442,281 fresh PCM frames. The real SDL queue
accepts at least 441,856 fresh nonzero frames, with zero observed active drops;
planned pause tails are 388 native / 362 reference frames. These processes stay
muted. Fresh typed comparisons and the full room matrix pass. Numerical PCM
and bounded SDL delivery do not establish listening or
hardware equivalence.

The selected `nec-invalid` CD policy returns an invalid-command response with
sense for unknown commands. It does not implement those operations. Historical
`gear-good` qualifications keep their original compatibility labels; that response
profile is not selected. Default synthesized Q remains in use for this disc.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current65
git -C .deps/pcenginerecomp-current65 checkout --detach 62c706c51e3e7b8d59c235c30093cc47f95af1f3
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
