# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **59,622-frame** reset route normally earns Roy's Pendant and the
Storehouse Key, then tests the wizard encounter: clones, projectiles, incoming
damage and ordinary sword damage. Verified living-HP/max-HP and guarded vertical
movement assists speed up testing. Quest flags, equipment and program code receive
no developer writes. This is assisted testing, separate from campaign completion.

The official module contains **53,302 eligible identities** in 79 full MPR
contexts, across 259 C++ translation units and one header. It preserves all
53,153 previously published identities and adds **149**, all executed in the fresh
TCP/audio replay for **1,701 genuinely new native retirements**. The deliberately
older execution baseline also lacks 112 retirements on already-published keys;
those are reported separately, giving 1,813 total measured promotions.

The matching route retires **1,811,024,403 native and 66 interpreted instructions**,
down from 1,879 interpreted on the same baseline. The remaining 66 fallbacks stay
in the original six-byte exclusion. This remains a hybrid port.

A clean **474-frame wizard-combat window executes 14,740,660 native and zero
interpreted instructions**. Player RAM HP falls from 99 to 59 while the enemy bar
loses 15 yellow pixels, replaced by red across all eight rows. This proves visible
boss damage, not a numeric boss-HP map or victory. No development edit occurs
inside this window.

All 2,055 states, 801 images, source identities, total retirement counts, data-CAS
journals and digital PCM match the fresh replay, with only proved execution-tier
promotions and validated immediate-input transport differences. Boss defeat,
rewards, the full campaign and cross-process saves remain unfinished. Interrupted
or failed experiments are retained separately and excluded from qualification.

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
the current boss-combat batch. Earlier finite migration and route proofs remain
retained separately; newer upstream ABIs are not selected by this batch.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

Both module runs match 43,949,545 cumulative 44.1 kHz PCM frames, hash
`12114718313764246034`, including 41,381,501 mixed-nonzero frames and zero synthesis
loss. The WAV is capped at ten guest seconds of silent boot; later game audio is
verified through cumulative PCM. Fast-forward SDL presentation is muted. No new
paced-device or listening test is claimed. Independent Geargrafx boss observations
have separate timing, stats and damage measurements; they are not full-route audio
or image parity. Earlier finite startup and device checks remain retained.

The original six-byte exclusion remains across 4 profile variants / 1,160
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
uses interpreted execution. The consumer suite passes **488 tests with zero skips**;
retained upstream checks passed **36 shared suites / 468 Python tests, zero skips**.
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
