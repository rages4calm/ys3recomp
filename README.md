# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port, with unseen
code handled by the interpreter and the full campaign unfinished.

The current build boots through the **System Card reset vector**, using a clean
US BIOS and deterministic initial CPU/device state. It starts without an IPL
payload, forced PC/MPR mappings, an input script or a BRAM file. Blank,
unformatted BRAM is created in memory; guest saves remain session-only.

The **14,680-frame** normal-input reset route completes all **105 states,
115 actions and ten images**, retiring **432,875,213 native instructions and
zero interpreted**, with zero development RAM writes. A separate reset-to-600
capture proves 17,483,730 BIOS instructions execute natively before that original
reference boundary, plus four RAM instructions. The composed module contains
52,556 eligible source identities in 79 full MPR contexts, including 7,674 new
identities, across 257 C++ translation units and one header. These finite routes
establish measured execution; emission alone does not prove coverage.

Guest/source/CD state and raw 44.1 kHz Gear PCM match the retained shared
reference, with one explicit exception: an immediate paused input-release
snapshot reports the old button mask in the reference and the released mask in
the new run. All other fields match, and the next advancing state confirms the
release strictly. Both raw snapshots are retained. This is not a claim that all
105 raw button snapshots are identical.

## Play the local build

In a prepared checkout, double-click **Play Ys III.cmd**. It now selects the
qualified System Card reset build. Press Enter/Run at the System Card menu,
choose Beginning, then Proceed at the blank-BRAM prompt to reach the opening
town. **Native Files.cmd** opens the generated C++ folder.

Arrows move; Z is button I, X is II, Shift is Select and Enter is Run.
Space pauses, F11 toggles fullscreen and Esc exits. The launcher verifies the
selected inputs, module, runtime and adjacent SDL package. It downloads and
installs nothing. `python scripts/play_local.py --info` checks readiness without
opening a game. A fresh clone needs owner-supplied inputs and a qualified
private build; generated game source and assets are excluded from Git.

Audio defaults to raw 44.1 kHz with Gear timing; filtered 44.1/48 kHz and
explicit legacy timing remain available. The full reset route matches
10,821,162 cumulative PCM frames, hash `16077886581937742416`, with zero runtime
loss and later nonzero audio. Its first-ten-second WAV contains boot silence.
The separate paced menu check accepts 755,486 source frames through the real
default SDL device and verifies controls, guest/window captures and full
exposed guest/source/CD/PCM pause freeze and resume. That menu is silent; raw
telemetry omits negotiated device format fields. Neither check is a listening
or analog-quality test. Full route replays use muted unthrottled presentation.

The older **95,686-frame / 68-image** IPL-entry route also passes on ABI 17,
preserving 2,980,431,691 native + 981 interpreted retirements, 470,652 native
blocks and exact same-profile filtered 48 kHz PCM. It retains its inherited
709 assist transactions / 723 changed bytes and adds none. It remains separate
from the new unassisted reset route; no boss victory or campaign completion is
claimed.

The explicit `gear-good` unknown-CD response profile remains required: the reset
route records two `$FF` responses, while the older extended route records 54.
Unknown operations and REQUEST SENSE remain unimplemented. External Geargrafx
menu evidence matches an explicitly aligned 237-row / 60,672-pixel viewport at
frames 120 and 600; the raw full frames differ. Fifty finite authored parity
checks retain 36 known CSH timing differences of 18 ticks. This does not prove
whole-retail CPU/device timing or hardware parity.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi17
git -C .deps/pcenginerecomp-abi17 checkout --detach bb3b695b782352bdfacd8db877f2a843bd1242f1
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If `ctest` is unavailable, run
`python .deps/pcenginerecomp-abi17/scripts/check.py --build build/upstream`
and `python -m unittest discover -s tests -v`. The default empty-module host
uses interpreted execution. Current checks pass **411 consumer tests
with zero skips**, plus **34 shared suites / 386 Python tests, zero skips** on
a fresh 204-target shared build. Source verification checks the exact clean
54-file ABI 17 pin and source digest. See [development](docs/DEVELOPMENT.md),
[status](docs/STATUS.md) and [toolchain.json](toolchain.json) for contracts and
retained historical milestones.

Owner inputs stay read-only. No media, generated game code, captures, saves or
private evidence is distributed. All six bounded verification hosts are closed,
and all seven original inputs remain unchanged. Cross-process save persistence,
unvisited code and campaign completion remain unfinished. Deterministic reset
initialization is not hardware power-on certification.

**Clean Old Build Files.cmd** remains unchanged. The reviewed approximately
119 MiB, separate 63 MiB and newer 9 MiB compiler-intermediate plans are owner-run
only; none was executed. Qualified binaries, source, inputs and evidence stay
protected.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored project code is MIT licensed; that grants no rights to game,
firmware or game-derived output.
