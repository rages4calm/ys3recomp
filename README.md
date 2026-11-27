# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**Development has collected Power Ring, Crystal, Tablet and Plate Mail in Tigre Mine.**
Plate Mail and Power Ring are equipped. Adol is alive at the Plate Mail chest,
with **90/100 HP** at frame **220,716**. The next boss has not been reached.
The assisted route passes native/reference, repeat and paced TCP audio checks;
Play uses the newly qualified build.

The selected ABI29 SDK is
[`25ead81`](https://github.com/rages4calm/pcenginerecomp/commit/25ead81d73ac3ea555db6d5d25e4171ce9f5cd0c),
with 130 runtime/tooling source files. It removes inactive title-adapter work
from adapter-free instruction loops and adds source-bound offline BRAM diagnostics.
The upstream throughput measurement was inconclusive; no percentage speedup is claimed.

One regeneration and audited compiler-cache miss combine the SDK migration and
new gaps. The module contains **71,919 guarded identities**: 71,767 observed,
2,619 declared, and 152 declared-only. It retains all 69,689 previous identities
and adds **2,230 emitted identities**. The 2,240 new observation memberships
include ten previously declared-only identities. Compilation is not execution proof.

One new-SDK cold reconstruction reaches frame **197,076** with
**6,021,101,711 native / zero interpreted instructions**, exact original HOST/CORE
and source counts, and 66,692 executed identities. Older SDK checkpoints retain
their original packages. The new **23,640-frame** route then executes
**737,438,604 native / zero interpreted instructions**, replacing 14,358,536
fallback retirements. Of the added identities, **2,087 execute**
and **143 remain unexercised**. Fresh execution by this binary
witnesses **69,619 identities**, leaving
**2,300 compiled identities unexercised**.

Fifteen own-build waypoints support short future forks. Fresh 120-frame
native/repeat/reference forks and 600-frame paced TCP audio pass. The living
checkpoint's **6,758,540,315 native / zero interpreted** lifetime combines a cold
prefix and restored suffixes from this binary; it is not a continuous campaign.

Verified development assists journal 124 expected-byte edits to position copies
and living HP. MAX HP, experience, gold and quest flags are not edited. The game
naturally raises MAX HP from 90 to 100 and awards the Tablet. Unassisted cuts
and literal reference-write replay are retained. SAVE/LOAD menus were exercised;
a usable game save and cross-process persistence remain unverified. Unseen
source variants retain interpreter fallback. This bounded assisted route does
not establish campaign completion.

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

The selected [ABI29 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/25ead81d73ac3ea555db6d5d25e4171ce9f5cd0c)
provides mixed live-overlay and history preparation, feedback, shared emission
and audited additive checkpoint continuation. It also supplies optional title
adapters and operation-local verified-input reuse; game enhancements still need
consumer implementation. Shared CPU/device semantics and generation remain upstream; this project
owns game configuration, coverage and verification. The previous qualified
ABI29 build is retained.

## Audio and checkpoints

Ordinary restore requires exact-build checkpoints and explicit reference capability.
The toolkit's [audited additive continuation](https://github.com/rages4calm/pcenginerecomp/blob/25ead81d73ac3ea555db6d5d25e4171ce9f5cd0c/docs/CHECKPOINT_CONTINUATIONS.md)
is a separate, qualified module-only path with the same SDK and compiler/dependency
closure. It does not retroactively admit older ordinary-build checkpoints.
Original ABI28 captures remain source evidence; their checkpoints are never imported into ABI29.
Fresh native/repeat/reference forks compare the entire current machine core with
only four tier counters normalized. The guard and all other CORE/HOST bytes,
RAM, pixels, source counts and guest PCM remain strict.

The current paced 600-frame check verifies at least 441,703 fresh nonzero PCM
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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-current62b
git -C .deps/pcenginerecomp-current62b checkout --detach 25ead81d73ac3ea555db6d5d25e4171ce9f5cd0c
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
