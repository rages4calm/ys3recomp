# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **89,556-frame** TCP/audio route retires **2,749,030,708 native
instructions and zero interpreted instructions**. It retains the miner and deeper
boss reward, then continues through the Chester confrontation, automatic mine
entrance return and dialogue confirming the Mayor is safe.

The official module contains **56,205 original source identities** in
81 full MPR contexts, across 272 C++ translation units and one header.
All 55,723 previous identities remain; 482 additions execute for 86,138
newly native retirements on the same route. Separately, 101 previously compiled
identities execute 2,703 native hits beyond the prior route. Emission and
execution are measured separately; unseen code retains interpreter fallback.

The new 8,052-frame scene interval retires 256,505,896 native instructions
and zero interpreted instructions. The fresh same-control replay matches all
1,937 controls, 4,393 states, 1,917 images, individual source totals, assist
journals and digital PCM. All 280 verified data-CAS transactions are retained;
the new interval needs no additional writes. HP60 refill remains unverified.
Full campaign and cross-process saves remain unfinished. Digital PCM matching
does not establish listening or hardware parity.

## Play the local build

In a prepared checkout, double-click **Play Ys III.cmd**. Press Enter/Run at
the System Card menu, choose Beginning, then Proceed at the blank-BRAM prompt.
**Native Files.cmd** opens the privately generated C++ folder. A fresh clone
needs owner-supplied media and a qualified private build; generated game source,
assets, captures and saves are excluded from Git.

Arrows move; Z jumps (button I), X attacks (button II). Shift opens the
Command menu (Select), and Enter is Run.
Space pauses, F11 toggles fullscreen and Esc exits. The launcher verifies the
selected inputs, module, runtime and adjacent SDL package; it downloads and
installs nothing. `python scripts/play_local.py --info` checks readiness without
opening a game. Cross-process saves are not implemented.

The toolkit remains pinned to ABI18 at
`6935e46ff8aefacf8ea058a385198299c4e2cd5c`. The composed profile retains its
original ABI17 lineage and the actual ABI18 labels of the new closed captures.
This union represents multiple executions. It was re-emitted and rebuilt for
the current post-statue batch. Earlier finite migration and route
proofs remain retained separately; newer upstream ABIs are not selected here.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

Both module runs match 66,014,986 cumulative 44.1 kHz PCM frames,
hash `1782564511339026912`, including 62,741,630 mixed-nonzero frames
and zero synthesis loss. The capped ten-second WAV covers silent boot; later
audio is verified cumulatively. Fast-forward SDL presentation is muted.
Independent Geargrafx confirms the bounded progression and HP-only assist
behavior, with differing stats, positions and timing. No whole-route reference
audio, listening or hardware parity is claimed.

The prior whole-span exclusion has been replaced by an explicit original-only
selection. The three verified originals are emitted; the historical temporary
identity stays omitted. Its 101 profile hits belong to an aggregate multi-run
profile, not this execution. The older 95,686-frame IPL-entry route remains a
separate retained milestone and was not repeated here.

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
uses interpreted execution. The consumer suite passes **510 tests with zero skips**;
retained upstream checks passed **36 shared suites / 468 Python tests, zero skips**.
Verification requires the exact clean 60-file source digest and ABI. Historical
captures retain their original ABI labels; fresh ABI18 execution captures are
checked as ABI18. Emission counts alone establish no runtime coverage.

See [status](docs/STATUS.md), [development](docs/DEVELOPMENT.md) and
[toolchain.json](toolchain.json) for measured scopes and historical milestones.
Owner inputs remain read-only. Earlier work removed only reviewed
compiler intermediates from its failed build, preserving qualified evidence.
**Clean Old Build Files.cmd** removes unbound compiler intermediates with visible
progress, a private receipt and a final result that stays open. It is repeatable;
use `--no-pause --preview` to review without deleting. It preserves qualified
packages, generated native source, inputs and replay evidence. GitHub contains
authored source, so it cannot restore those excluded private artifacts.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
