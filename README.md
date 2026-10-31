# Ys III native-port project

An incremental PC Engine CD native port of *Ys III: Wanderers from Ys* (USA),
built with [pcenginerecomp](https://github.com/rages4calm/pcenginerecomp).
**ABI26 is now selected.** The qualified **102,802-frame** reset route retires
**3,122,661,937 native instructions and zero interpreted instructions**.
The full campaign remains unfinished; unseen code retains interpreter fallback.

The route covers herb use, damage/death/continue, mine combat and equipment,
the wizard and deeper-mine boss rewards, miner dialogue, town/lodge return,
Alcaino's first combat room and downward/upward movement in its next diagonal
stair room. It uses verified HP/movement development assists and original game
code. This is bounded assisted verification, not campaign completion.

The new module contains **57,752 source identities** in 83 full MPR contexts,
across 943 stable C++ translation units and one header. All 57,545 previous
identities remain; all 207 additions execute. The fresh route exercises 54,610
identities; 3,142 retained compiled keys are not exercised by this route.
Compared with the same ABI26 discovery controls, **3,433 interpreted retirements
are now native**, including 68 block instructions. No source variant was
excluded or unsupported. Emission totals alone are not execution evidence.

Actual TCP comparisons preserve exact settled CPU/source/device state, RAM,
535 guest images and digital PCM. All 5,257 frame steps retain bounded progress
polls and match the actual paused endpoint; polling cadence may differ.
All 300 data-CAS assists have literal authority, alias/footprint exclusions,
full RAM readbacks and typed write-effect proofs. No program, quest, item,
equipped-weapon or STR bytes were edited.

The new ABI26 route is 791 frames longer than the retained ABI18 route because
its early state-aware prefix and reviewed navigation/menu controls differ.
Its terminal room and down/up control capability are verified separately;
positions, rewards and timing are not cross-ABI parity claims.

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

The selected [ABI26 toolkit](https://github.com/rages4calm/pcenginerecomp/commit/1be93679c3318c667f97f55cb37af625a86ad875)
uses the official provenance-preserving composer and stable emitter.
The [semantic step validator](https://github.com/rages4calm/pcenginerecomp/commit/929dcc3b9affe3af70eeaa49c6091baceb1bf056)
is separately pinned. Shared CPU/device semantics and generation remain
upstream; this project owns game configuration, coverage and verification.

A separate **ABI27 candidate** now tests the toolkit's opt-in
[`nec-invalid` CD profile](https://github.com/rages4calm/pcenginerecomp/commit/d71add52a88ab18084ecd3ea856b9b4df80a7469)
through the first unknown command and subsequent disc read.
Fresh checkpoint restores and paced audio pass with zero interpreter fallback.
The legacy response profile also retains exact source-key retirement counts.
This is a bounded toolkit test; **Play remains on the fully qualified ABI26 build**.

## Audio and checkpoints

Both full-route runs match 75,779,095 cumulative 44.1 kHz PCM frames,
hash `6699622511181680977`, including 71,964,477 mixed-nonzero frames and zero
synthesis loss. The capped ten-second WAV covers boot; later sound is verified
cumulatively. Full-route fast-forward SDL presentation is muted.

Fresh same-build checkpoint restores match complete immediate and continued
checkpoint files and machine cores. Each 60-frame suffix executes 1,851,616
native instructions with zero fallback. A separate paced 120-frame check
executes 3,703,226 native instructions and accepts at least 87,720 newly
generated PCM frames into SDL beyond imported audio. Active playback has zero
reported drops; 729 frames cleared at the planned pause and seven at shutdown
are accounted separately. This is device-submission evidence, not listening or
hardware parity. Closed journals have verified lossless archives; originals
and historical failures remain retained privately.

The explicit `gear-good` compatibility response remains required for unknown
`$FF` CD requests; accepting them does not implement their operations.
The toolkit models fixed-format REQUEST SENSE responses.
Deterministic reset and finite reference checks do not establish hardware,
whole-campaign or analog-audio parity.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-diagnostics43
git -C .deps/pcenginerecomp-diagnostics43 checkout --detach 1be93679c3318c667f97f55cb37af625a86ad875
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

The default empty-module host uses interpreted execution. The consumer suite
passes 550 tests without skips; the ABI26 migration passes 126 affected upstream
profile/capture/emission/project checks. Historical captures retain their
original ABI labels and checkpoint origins.

See [status](docs/STATUS.md), [development](docs/DEVELOPMENT.md) and
[toolchain.json](toolchain.json) for measured scopes and historical milestones.
Owner inputs remain read-only. **Clean Old Build Files.cmd** removes unbound
compiler intermediates with visible progress and a private receipt; use
`--no-pause --preview` to review without deleting. It preserves qualified
packages, generated native source, inputs and replay evidence. GitHub contains
authored source and cannot restore excluded private artifacts.
Numbered candidate build folders use the same cleanup protections.

Authored code is MIT licensed; that grants no rights to game, firmware or
game-derived output.
