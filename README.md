# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Development has reached Tigre Mine's lower passage and NPC/chest room.**
Adol completes the room dialogue and remains alive with **88 HP** at frame
**197,076**. The original chest is still closed; no named reward is claimed.
The assisted route passes native/reference, repeat and paced TCP audio checks;
Play uses the newly qualified build.

The new ABI29 SDK pin is
[`824bb7a`](https://github.com/rages4calm/pcenginerecomp/commit/824bb7afaa9d0f35c25c7a8c834c22fdaaafb3a8),
with 127 runtime/tooling source files. Its new audited cold baseline reaches
the Time Ring checkpoint at frame **186,482**, executing **5,686,836,373 native
and zero interpreted instructions**. All 66,373 source identities from the
retained route execute again, with exact original HOST/CORE and source counts.
Older SDK checkpoints retain their original owning packages.

The Tigre discovery route collects nine phases into one native extension.
The qualified module contains **69,689 guarded identities**: 69,527 observed,
2,619 declared, and 162 declared-only. Its 375 newly compiled identities comprise
291 executed-source gaps and 84 additional static candidates. Static declaration
membership and emission do not establish execution. The new **10,594-frame**
route executes **334,265,338 native and zero interpreted instructions**, replacing
127,306 fallback retirements. All 291 newly observed gaps execute; the 84 new
static candidates remain unexercised. Fresh 120-frame native/repeat/reference
forks and 600-frame paced TCP audio pass.

Fresh execution by this binary witnesses **22,583 identities**; 47,106 remain
unexercised by it. The separately recorded imported baseline witnesses 66,373;
the mixed-package lineage witnesses 66,692, leaving 2,997 unexercised. Its linked
**6,021,101,711 native / zero interpreted** total is not a single-binary cold run.

Verified development assists comprise three local position placements and one
HP refill, seven expected-byte writes in total. Original checkpoints and literal
reference-write replay are retained. Unseen source variants retain interpreter
fallback; this bounded assisted route does not establish campaign completion.

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

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/824bb7afaa9d0f35c25c7a8c834c22fdaaafb3a8)
provides mixed live-overlay and history preparation, feedback, shared emission
and audited additive checkpoint continuation. It also supplies optional title
adapters and operation-local verified-input reuse; game enhancements still need
consumer implementation. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build is retained.

## Audio and checkpoints

Ordinary restore requires exact-build checkpoints and explicit reference capability.
The toolkit's [audited additive continuation](https://github.com/rages4calm/pcenginerecomp/blob/824bb7afaa9d0f35c25c7a8c834c22fdaaafb3a8/docs/CHECKPOINT_CONTINUATIONS.md)
is a separate, qualified module-only path with the same SDK and compiler/dependency
closure. It does not retroactively admit older ordinary-build checkpoints.
Original ABI28 captures remain source evidence; their checkpoints are never imported into ABI29.
Fresh native/repeat/reference forks compare the entire current machine core with
only four tier counters normalized. The guard and all other CORE/HOST bytes,
RAM, pixels, source counts and guest PCM remain strict.

The current paced 600-frame check verifies at least 441,441 fresh nonzero PCM
frames accepted by SDL beyond imported audio, with zero unexpected active drops. Planned pause clears and shutdown drains
are counted separately. The fast-forward route compares guest digital PCM; it
does not claim a newly captured boot WAV or listening/hardware parity.

The selected `nec-invalid` CD policy returns an invalid-command response with
sense for unknown commands. It does not implement those operations. Historical
`gear-good` qualifications keep their original compatibility labels; that response
profile is not selected. Default synthesized Q remains in use for this disc.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current61
git -C .deps/pcenginerecomp-current61 checkout --detach 824bb7afaa9d0f35c25c7a8c834c22fdaaafb3a8
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
