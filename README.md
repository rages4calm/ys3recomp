# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **21,934-frame** reset route adds **2,808 ordinary-input frames**
beyond the retained route. The expanded module retires **639,924,808 native
and three interpreted instructions**, moving **909 retirements** from the
interpreter on that same extended route. Three new eligible identities bring
the module to 52,680 identities in 79 full MPR contexts, across 257 C++
translation units and one header. Source emission alone proves no execution.

The extension exercises 1,051 source identities absent from the shorter route:
1,048 were already compiled and three required this expansion. Together they
retire 2,424,502 instructions natively in the final replay. This separates newly
executed coverage from newly generated source.

The route boots through the System Card reset vector with a clean US BIOS,
deterministic initialization and implicit blank-unformatted BRAM. It uses no IPL
payload, forced PC/MPR mapping, input script, BRAM file or development RAM write.
It reaches the town, enters a shop and buys a Healing Herb for 100G, leaving
900G and a visible HP display of 020. The extension exercises the Equipment and
Inventory windows; equipping and item use remain unverified. This route does
not establish leaving town or campaign completion. Guest saves remain volatile
and process-local.

All settled CPU/MPR/source/generation/CD/PCM checkpoints match apart from the
measured execution tiers. Immediate input-status observations retain their raw
prior/requested masks and are checked within each run before the next strict
advancing checkpoint. The original opening's one witnessed state54/55 timing
case remains explicit; there is no broad button, IRQ or timing normalization.
The original 114 opening actions and the retained route's next 60 control
requests are preserved. Their terminal quit is deferred until this extension
ends; no state restore or development assist is used.

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

The toolkit pin is now ABI 18 at
`6935e46ff8aefacf8ea058a385198299c4e2cd5c`. The original ABI17 profile is
preserved and combined with the actual ABI18 discovery capture. Their union
retains both original labels and is not one execution. Before expansion, the
complete **19,126-frame route** was repeated on ABI18 with matching execution
tiers, all 38,235 source keys and per-key hits, 71 images and digital audio.
The longer discovery and expanded replay then used that same frozen tool.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

The extended route's raw 44.1 kHz Gear audio matches 16,168,349 cumulative PCM frames, hash
`16485684417233013891`, including 15,092,682 mixed-nonzero frames and zero runtime
loss. The matching WAV is capped at the first ten guest seconds of silent boot;
later game audio is verified through cumulative PCM. These full replays are
unthrottled with muted SDL presentation. No new paced-device or listening test
is claimed for this package; the earlier silent-menu device check is historical.
The earlier 5,526-frame ABI18 startup check remains retained separately.

The original six-byte exclusion remains across four profile variants / 987
profile hits. This route actually executes three excluded identities / three
interpreted hits. The composed ABI18 profile is a union of observations from
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
git clone -c core.autocrlf=false https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp-abi18
git -C .deps/pcenginerecomp-abi18 checkout --detach 6935e46ff8aefacf8ea058a385198299c4e2cd5c
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If `ctest` is unavailable, run
`python .deps/pcenginerecomp-abi18/scripts/check.py --build build/upstream`
and `python -m unittest discover -s tests -v`. The default empty-module host
uses interpreted execution. The consumer suite passes **476 tests with zero skips**;
upstream checks pass **36 shared suites / 468 Python tests, zero skips**.
Verification requires the exact clean 60-file source digest and ABI. Historical
captures retain their original ABI labels; fresh ABI18 execution captures are
checked as ABI18. Emission counts alone establish no runtime coverage.

See [status](docs/STATUS.md), [development](docs/DEVELOPMENT.md) and
[toolchain.json](toolchain.json) for measured scopes and historical milestones.
Owner inputs remain read-only. The reviewed cleanup plans remain owner-run;
no deletion was performed. Revalidate plans after source or metadata changes
before running them. **Clean Old Build Files.cmd** remains unchanged.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
