# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **65,044-frame** reset route normally earns Roy's Pendant and the
Storehouse Key, defeats the wizard and picks up the **Long Sword** through ordinary
controls. Both the pickup message and the named Equipment slot are captured.
Verified living-HP/max-HP and guarded vertical movement assists speed up testing;
quest flags, equipment and program code receive no developer writes. This is
assisted testing, separate from campaign completion.

The official module contains **54,000 eligible identities** in 80 full MPR
contexts, across 262 C++ translation units and one header. All 53,302 prior
identities are preserved. All **698 additions execute**, promoting **30,879
retirements** from interpretation to native execution in the fresh TCP/audio replay.

The matching route retires **1,978,101,467 native and 75 interpreted instructions**,
down from 30,954 interpreted with the prior module on these same controls. The
remaining 75 fallbacks stay in the original six-byte exclusion. This remains a
hybrid port; unseen overlays and the full campaign remain unfinished.

The actual defeat effects are followed by an empty arena and settled EXP 210 to 410,
gold 374 to 574 and natural HP/max HP 40. Zero enemy-bar pixels alone are insufficient:
the wizard was still alive at an earlier zero-bar checkpoint. No developer write
occurs during victory settlement or the ordinary reward pickup.

All 3,334 states, 1,437 images, source identities, retirement totals, data-CAS
journals and digital PCM match the fresh replay, allowing only proved execution
tier promotions and validated immediate-input transport differences. Interrupted
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
the current wizard defeat/reward batch. Earlier finite migration and route proofs
remain retained separately; newer upstream ABIs are not selected by this batch.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

Both module runs match 47,946,299 cumulative 44.1 kHz PCM frames, hash
`4333397609570816573`, including 45,303,544 mixed-nonzero frames and zero
synthesis loss. The WAV is capped at ten guest seconds of silent boot; later game
audio is verified through cumulative PCM. Fast-forward SDL presentation is muted.
No new paced-device or listening test is claimed. Independent original-program
Geargrafx also confirms wizard defeat and the named Long Sword through ordinary
controls. Its timing, defensive stats and audio are separate; no full-route
independent image/audio parity is claimed.

The original six-byte exclusion remains across 4 profile variants / 1,213
profile hits. This route retires 75 interpreted instructions in that excluded
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
