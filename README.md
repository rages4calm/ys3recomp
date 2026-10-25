# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **27,490-frame** reset route extends the retained Tigre route by
**980 ordinary-input frames** to test a Healing Herb. Its case retires
**28,321,867 native and zero interpreted instructions**: selection, activation,
healing from 011 through 017 to 020 HP, and visible item consumption. This is
a fully native bounded item-use case; it does not establish all combat or bosses.

The full replay retires **810,116,411 native and 22 interpreted instructions**,
promoting **121 retirements** on the same route. All 22 remaining interpreted
retirements belong to the retained prefix, with none inside the new case.
Forty-five new eligible identities bring the module to 52,754 in 79 full MPR
contexts, across 258 C++ translation units and one header.

The new case exercises 220 identities absent from the shorter route: 175 were
already compiled and 45 required expansion. Together those new keys retire
7,156 instructions natively. This separates new executed coverage, compilation
gain and the case's total native work. Source emission alone proves no execution.

The route uses the System Card reset vector, deterministic initialization and
implicit blank-unformatted BRAM. It leaves town, selects Tigre and enters its
cave; ordinary damage lowers HP to 011 before the Herb restores 020. Gold stays
900. There are no payloads, state restores, forced PC/MPR, owner saves, BRAM
files or development memory writes. Development write permission is enabled in
the private test host, with every raw write counter and ledger remaining zero.
Guest saves remain volatile and process-local.

All settled CPU/MPR/source/generation/CD/PCM checkpoints, per-key total hits,
178 images and the bounded WAV match apart from measured execution tiers.
Immediate input-intent observations are checked within each run; the original
opening's state54/55 witness remains the sole fixed timing exception. All 121
retained controls and 132 prefix images are preserved before the item case.
The fresh lossless source capture covers frames 26,510 through 27,490; it is
explicitly checked as that window, without relabeling it a reset-zero capture.

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
preserved in the source lineage. This batch combines the previous ABI18 profile
with a fresh ABI18 item-case window, retaining their original labels; the
union is not one execution. Before expansion, the
complete **19,126-frame route** was repeated on ABI18 with matching execution
tiers, all 38,235 source keys and per-key hits, 71 images and digital audio.
The longer discovery and expanded replay then used that same frozen tool.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

The extended route's raw 44.1 kHz Gear audio matches 20,263,879 cumulative PCM frames, hash
`10159753993186495202`, including 18,947,032 mixed-nonzero frames and zero runtime
loss. The matching WAV is capped at the first ten guest seconds of silent boot;
later game audio is verified through cumulative PCM. These full replays are
unthrottled with muted SDL presentation. No new paced-device or listening test
is claimed for this package; the earlier silent-menu device check is historical.
The earlier 5,526-frame ABI18 startup check remains retained separately.

The original six-byte exclusion remains across four profile variants / 1,009
profile hits. This route actually executes three excluded identities / 22
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
Owner inputs remain read-only. The previous batch removed only reviewed
compiler intermediates from its failed build, preserving qualified evidence.
Broader cleanup plans remain unchanged and need revalidation before use.
**Clean Old Build Files.cmd** remains unchanged.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
