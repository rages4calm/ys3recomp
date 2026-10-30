# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **102,011-frame** TCP/digital-audio route retires
**3,113,677,066 native instructions and zero interpreted instructions**.
It retains the lodge departure and first-room combat, then enters Alcaino's
next diagonal stair room and verifies movement down and back up its stairs.

The official module contains **57,545 original source identities** in
83 full MPR contexts, across 278 C++ translation units and one header.
All 57,523 previous identities remain. The 22 additions execute for 87 newly
native retirements on the same route; none is compiled-only. Source variants
remain distinct. One previously compiled identity also executes one new hit.
Unseen code retains interpreter fallback; full campaign coverage is unfinished.

The new 234-frame interval retires 7,159,222 native instructions with zero
fallback. The fresh same-control replay matches all 2,184 controls,
4,896 states and 2,132 images, source totals, canonical assist proofs and digital PCM.
All 284 retained data-CAS transactions remain; one new independently verified
living current-HP refill changes only its low byte from 30 to the read-only
maximum of 60. EXP rises from 1,280 to 1,324 and gold from 1,360 to 1,380.
The HUD may remain at HP030 after the raw refill.

This is assisted, bounded room/control verification. Native and independent
reference timings differ. The earlier unassisted first-room HP/phase difference
remains unresolved. Full campaign, cross-process saves, listening and hardware
parity remain unfinished.

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
`6935e46ff8aefacf8ea058a385198299c4e2cd5c`. Its composed profile retains the
original ABI17 lineage and actual ABI18 capture labels. This multi-run source
union was re-emitted and rebuilt for the current next-room batch.

Current ABI26 tooling includes state-aware TCP routes, exact-build developer
checkpoints, durable wire journals and streaming journal audits. The latest
[reviewed toolkit](https://github.com/rages4calm/pcenginerecomp/commit/2e203024ae4e03984c8000783d3c762e3855b9a2)
adds phase diagnostics without changing this candidate's ABI26 runtime/emitter
semantics. A fresh ABI26 candidate now passes the shop exit and town dialogue
through state-aware TCP controls with digital audio. An exact-build checkpoint
replays the 741-frame suffix in 13.67 seconds, preserving images, guest state
and digital PCM while keeping imported work separate. The reset route still
retires 25 interpreted instructions across 23 new source identities. Their
additive composition needs a supported toolkit contract that preserves the
original ABI18 and ABI26 capture provenance; this gap has been reported upstream.
The full Alcaino route has not migrated, so **Play remains on qualified ABI18**.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. Earlier finite migration proofs remain retained separately.

Both module runs match 75,196,020 cumulative 44.1 kHz PCM frames,
hash `7520645438990754195`, including 71,381,855 mixed-nonzero frames
and zero synthesis loss. The capped ten-second WAV covers silent boot; later
audio is verified cumulatively. Fast-forward SDL presentation is muted.
Independent Geargrafx confirms bounded stair entry, next-room control and the
HP-only assist, with differing positions and timing. Reported status equality
does not establish hidden audio-queue contents or whole-machine quiescence.
No whole-route reference audio, listening or hardware parity is claimed.

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
uses interpreted execution. The consumer suite passes **523 tests with zero skips**;
this batch also passes 68 upstream capture/emission/project checks. Retained
upstream checks passed 36 shared suites / 468 Python tests, zero skips.
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
