# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **37,463-frame** reset route verifies ordinary purchases and
equipment selection for the Short Sword and Leather Armor, then mine attacks,
enemy kills, rewards, damage, Game Over and Continue. One new paused current-HP
refill changes 16 to 20; the retained route also includes its earlier HP1 setup.
This is assisted testing, separate from campaign completion.

The rebuilt module contains **53,153 eligible identities** in 79 full MPR
contexts, across 259 C++ translation units and one header. It preserves all
52,754 prior identities and adds 399. The matching TCP/audio replay executes
59 newly compiled keys for **77 additional native retirements**; the other
340 added keys are compiled coverage without execution proof in this replay.

The full route retires **1,114,973,224 native and 66 interpreted instructions**,
down from 143 interpreted on the identical baseline. All remaining fallbacks
are in the preserved original six-byte exclusion: 22 in the retained prefix
and 44 in the extension. This is still a hybrid port.

One measured **240-frame combat window executes 7,623,762 native and zero
interpreted instructions**. Ordinary attacks raise visible EXP from 0 to 62 and
gold from 200 to 204 while HP falls from 20 to 16. Later combat reaches zero HP,
Game Over appears, and ordinary Continue restores positive HP.

All 757 states, 340 images, source identities, per-key total hits, HP journals
and digital PCM match the fresh replay, with only the proved execution-tier
promotions and validated immediate-input transport differences. Original program
code and max HP receive no development edits in this qualified recipe. Guest
saves remain volatile. Boss encounters and the full campaign remain unfinished;
the later boss approach interrupted by a power outage is not qualified.

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

The toolkit remains pinned to ABI18 at
`6935e46ff8aefacf8ea058a385198299c4e2cd5c`. The composed profile retains its
original ABI17 lineage and the actual ABI18 labels of the new closed captures.
This union represents multiple executions. It was re-emitted and rebuilt for
the current combat batch. Earlier finite migration and route proofs remain
retained separately; newer upstream ABIs are not selected by this batch.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

The extended route's raw 44.1 kHz Gear audio matches 27,615,340 cumulative PCM frames, hash
`4692142117000696351`, including 25,402,413 mixed-nonzero frames and zero runtime
loss. The matching WAV is capped at the first ten guest seconds of silent boot;
later game audio is verified through cumulative PCM. These full replays are
unthrottled with muted SDL presentation. No new paced-device or listening test
is claimed for this package; the earlier silent-menu device check is historical.
The earlier 5,526-frame ABI18 startup check remains retained separately.

The original six-byte exclusion remains across four profile variants / 1,072
profile hits. This route retires 66 interpreted instructions in that excluded
span. The composed ABI18 profile is a union of observations from
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
Owner inputs remain read-only. Earlier work removed only reviewed
compiler intermediates from its failed build, preserving qualified evidence.
Broader cleanup plans remain unchanged and need revalidation before use.
**Clean Old Build Files.cmd** remains unchanged.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
