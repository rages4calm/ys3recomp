# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **19,126-frame** reset route adds **4,446 ordinary-input frames**
beyond the verified opening. The expanded module retires **564,285,827 native
and three interpreted instructions**, moving **20,671 retirements** from the
interpreter on that same route. Its 121 new eligible source identities bring
the module to 52,677 identities in 79 full MPR contexts, across 257 C++
translation units and one header. Source emission alone proves no execution.

The route boots through the System Card reset vector with a clean US BIOS,
deterministic initialization and implicit blank-unformatted BRAM. It uses no IPL
payload, forced PC/MPR mapping, input script, BRAM file or development RAM write.
It reaches the town, enters a shop and buys a Healing Herb for 100G, leaving
900G and a visible HP display of 020. Inventory/equipping and campaign completion
are not established. Guest saves remain volatile and process-local.

All settled CPU/MPR/source/generation/CD/PCM checkpoints match apart from the
measured execution tiers. Immediate input-status observations retain their raw
prior/requested masks and are checked within each run before the next strict
advancing checkpoint. The original opening's one witnessed state54/55 timing
case remains explicit; there is no broad button, IRQ or timing normalization.
The old terminal quit is deferred until the extension ends: the first 114
opening actions are preserved, rather than claiming all 115 already ran.

## Play the local build

In a prepared checkout, double-click **Play Ys III.cmd**. Press Enter/Run at
the System Card menu, choose Beginning, then Proceed at the blank-BRAM prompt.
**Native Files.cmd** opens the privately generated C++ folder. A fresh clone
needs owner-supplied media and a qualified private build; generated game source,
assets, captures and saves are excluded from Git.

Arrows move; Z is button I, X is II, Shift is Select and Enter is Run.
Space pauses, F11 toggles fullscreen and Esc exits. The launcher verifies the
selected inputs, module, runtime and adjacent SDL package; it downloads and
installs nothing. `python scripts/play_local.py --info` checks readiness without
opening a game. Cross-process saves are not implemented.

The current toolkit pin is ABI 17 at
`95fe3e07e63b0869de8c9d7b70681b5c557abf01`. A separate full-route migration
check reuses the expanded module without re-emission and preserves actual
native/interpreted counts and the complete code capture byte-for-byte. The new
shared media support adds read-only BIN/CUE mixed data/audio handling, checked
with synthetic tests and six independent Gear fixtures. **This retail route
still uses the owner's CHD**; no retail CUE, conversion or extraction claim is
made.

Raw 44.1 kHz Gear audio matches 14,098,470 cumulative PCM frames, hash
`4270652294026774565`, including 13,022,805 mixed-nonzero frames and zero runtime
loss. The matching WAV is capped at the first ten guest seconds of silent boot;
later game audio is verified through cumulative PCM. These full replays are
unthrottled with muted SDL presentation. No new paced-device or listening test
is claimed for this package; the earlier silent-menu device check is historical.

The original six-byte exclusion remains across four profile variants / 984
profile hits. This route actually executes three excluded identities / three
interpreted hits. The composed ABI17 profile is a union of observations from
multiple runs, not one execution. The older 95,686-frame IPL-entry route passed
in the prior milestone; it was not repeated here and retains its disclosed
709 assist transactions / 723 changed bytes.

The explicit `gear-good` compatibility response remains required for unknown
`$FF` CD requests. Unknown operations and REQUEST SENSE remain unsupported.
Deterministic reset is not hardware power-on certification. Earlier finite
Geargrafx menu/audio/CPU checks do not establish whole-retail timing, listening,
analog quality or hardware parity.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi17-cue
git -C .deps/pcenginerecomp-abi17-cue checkout --detach 95fe3e07e63b0869de8c9d7b70681b5c557abf01
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If `ctest` is unavailable, run
`python .deps/pcenginerecomp-abi17-cue/scripts/check.py --build build/upstream`
and `python -m unittest discover -s tests -v`. The default empty-module host
uses interpreted execution. Current checks pass **452 consumer tests
with zero skips**, plus **35 shared suites / 420 Python tests, zero skips**.
Verification requires the exact clean 57-file source digest and ABI. Native
source generation for this module used the retained original ABI17 pin; the
unchanged emitter/module contract was verified separately from host migration.
CLI reproduction of that generation also requires the matching pre-migration
consumer revision or preserved source epoch, as well as the old toolkit clone.

See [status](docs/STATUS.md), [development](docs/DEVELOPMENT.md) and
[toolchain.json](toolchain.json) for measured scopes and historical milestones.
Owner inputs remain read-only. The reviewed cleanup plans remain owner-run;
no deletion was performed. Revalidate plans after source or metadata changes
before running them. **Clean Old Build Files.cmd** remains unchanged.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
