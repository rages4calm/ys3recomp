# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **67,628-frame** reset route normally earns Roy's Pendant and the
Storehouse Key, defeats the wizard and obtains the Long Sword. It then tests mine
damage, natural death, visible Game Over and ordinary Continue. Continue restores
40/40 HP but removes the Long Sword; ordinary pickup reacquires it, confirmed by
the toast and named Equipment slot. The retained route uses verified HP/vertical
assists. The new post-reward sequence makes **no additional memory edits**.

The official module contains **54,036 eligible identities** in 80 full MPR
contexts, across 262 C++ translation units and one header. All 54,000 prior
identities are preserved. All **36 additions execute**, promoting **39 retirements**
from interpretation to native execution. Another **489 already-compiled identities**
execute 78,230 native retirements beyond the previous qualified route; those are
additional execution coverage, separate from the 39 promotions.

The new **2,584-frame post-reward sequence executes 79,905,621 native and zero
interpreted instructions**. The full matching route retires **2,058,007,088 native
and 75 interpreted instructions**, down from 114 interpreted with the prior module
on these same controls. The remaining 75 fallbacks stay in the original six-byte
exclusion. This remains a hybrid port; the full campaign is unfinished.

All 3,422 states, 1,486 images, source identities, retirement totals, retained
data-CAS journals and digital PCM match the fresh rebuilt replay, allowing only
proved execution-tier promotions and validated immediate-input transport
differences. No developer writes resurrect HP0 or alter quest flags, STR,
equipment or program code. Failed or incomplete experiments remain separately preserved and
excluded from native qualification. Miner return and the next boss remain open.

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
the current post-reward death/Continue batch. Earlier finite migration and route
proofs remain retained separately; newer upstream ABIs are not selected here.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

Both module runs match 49,851,059 cumulative 44.1 kHz PCM frames, hash
`11441753128665845047`, including 47,070,275 mixed-nonzero frames and zero
synthesis loss. The WAV is capped at ten guest seconds of silent boot; later game
audio is verified through cumulative PCM. Fast-forward SDL presentation is muted.
No new paced-device or listening test is claimed. Independent original-program
Geargrafx confirms the same qualitative death, Continue reward loss and ordinary
reacquisition. Stats, checkpoint positions and timing differ; only the bounded
Game Over text pixels are compared directly, not whole-route images or audio.

The original six-byte exclusion remains across 4 profile variants / 1,266
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
