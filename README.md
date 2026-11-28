# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Development has collected Power Ring, Crystal, Tablet and Plate Mail in Tigre Mine.**
Plate Mail and Power Ring are equipped. Adol is alive at the Plate Mail chest,
with **90/100 HP** at frame **220,716**. The next boss has not been reached.
Retained route evidence and fresh native/reference, repeat and paced TCP audio
checks pass; Play uses the newly qualified build.

The selected ABI29 SDK is
[`2143123`](https://github.com/rages4calm/pcenginerecomp/commit/2143123c0b9fa9fec064c55dad14973dfc6eca5b),
with 136 runtime/tooling source files. This is a migration-only batch: **zero new
native identities and no new story milestone**. The module preserves all
**71,919 guarded identities**: 71,767 observed, 2,619 declared and 152 declared-only.
Compilation is separate from execution proof.

Typed checkpoint inspection/comparison, corrected frame-latched burst border
color, immutable port-render layers and completed-frame presentation effects are
available. Softness and persistence remain at their default zero; the original
Ys III world view remains selected. These helpers do not implement a game-specific
widescreen renderer, settings UI or persistent saves.

One fresh cold reconstruction reaches frame **220,716** with
**6,758,540,315 native / zero interpreted instructions**, witnessing **69,619
identities**. It checks exact retained source counts, complete original HOST/CORE,
1,068 RGB samples and 35 semantic boundaries. The **542 historical CAS
transactions** comprise 418 older transactions and 124 B062 position/HP edits;
this update adds no assist recipe. Old checkpoints remain bound to their original
packages. This is assisted retained-route reconstruction, not campaign completion.

Fresh 120-frame native/repeat/reference forks and 600-frame paced TCP audio
pass using typed checkpoint reports and strict source/RAM/RGB/digital-PCM checks.
Only four tier counters differ in the fresh reference comparison. The selected
checkpoint is frame **220,836**, after the verification fork; the cold story
endpoint remains frame 220,716. Fresh current-binary execution witnesses
**69,619 identities**, leaving
**2,300 compiled identities unexercised**.

Power Ring, Crystal, Tablet and Plate Mail remain collected; Plate Mail and
Power Ring remain equipped, with 90/100 HP. The next boss remains ahead.
SAVE/LOAD menu exercise and opaque BRAM extraction do not establish a usable
save or cross-process persistence. Unseen source variants retain fallback.

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
