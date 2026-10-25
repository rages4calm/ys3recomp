# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA). This is an early hybrid port: unseen code
still uses the interpreter, and the full campaign remains unfinished.

The current **28,249-frame** reset route adds a verified low-HP damage, death
and Continue case. One paused development edit sets current HP from 20 to 1;
ordinary bat contact then reaches zero, Game Over appears, and Run/Continue
returns Adol to the bridge with 20 HP. This assisted progression is explicitly
separate from unassisted play and campaign completion.

The new **759-frame case executes 23,924,761 native and zero interpreted
instructions**. It exercises **832 identities absent from the retained reset
route captures**, all already compiled, for 1,731,089 native hits. The existing native package is
reused without emission or rebuilding; compilation gain is zero. Its module
still contains 52,754 eligible identities in 79 full MPR contexts, across
258 C++ translation units and one header.

The full replay retires **834,041,172 native and 22 interpreted instructions**.
All 22 interpreted retirements remain in the retained prefix; both the Herb
case and this death/Continue case have zero interpreted retirements.
The exact assisted recipe passes a fresh same-package TCP/audio replay with
455 states, 187 images, per-source hit counts and one journaled HP transaction.

The route uses the System Card reset vector, deterministic initialization and
implicit blank-unformatted BRAM. All 167 nonterminal retained controls and
178 images are checked before the edit at frame 27,490. The HP write uses
expected bytes, a pre-request journal, ACK and readback; it changes one data
byte without advancing guest time. Max HP, program code, items and game flags
receive no development edits. Original-input and code-capture history checks
exclude the HP byte and its mirrors from instruction fetches before and after.

The fresh lossless ABI18 capture covers frames 27,490 through 28,249 and all
10,100 case identities. It retains its actual window and ABI. Raw permission
and the single write request/changed-byte count remain visible. CPU/MPR/source
generations/CD/PCM, images and the bounded WAV match across the repeat. Immediate
input intent is checked within each run; the original state54/55 witness remains
the sole fixed timing exception. Guest saves remain volatile and process-local.
Boss phases, other combat paths and the complete campaign remain unfinished.

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
preserved in the source lineage. The module remains the previously qualified
ABI18 composed profile. This batch adds an assisted death-case capture and
same-package repeat without re-emission. Historical labels remain unchanged;
the composed profile is not one execution. Before expansion, the
complete **19,126-frame route** was repeated on ABI18 with matching execution
tiers, all 38,235 source keys and per-key hits, 71 images and digital audio.
The longer discovery and expanded replay then used that same frozen tool.

The shared toolkit adds explicit base HuCard startup and mapper support. Its
authored fixtures have separate Geargrafx/native/TCP/PSG checks. **Ys III still
uses the owner's CHD**; this batch adds no retail HuCard/CUE test or media
conversion. The earlier full-route ABI17 media migration remains retained.

The extended route's raw 44.1 kHz Gear audio matches 20,823,365 cumulative PCM frames, hash
`15233839849680885939`, including 19,390,686 mixed-nonzero frames and zero runtime
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
Owner inputs remain read-only. Earlier work removed only reviewed
compiler intermediates from its failed build, preserving qualified evidence.
Broader cleanup plans remain unchanged and need revalidation before use.
**Clean Old Build Files.cmd** remains unchanged.

This consumer owns game configuration, source selection, native coverage,
adapters and launchers. Shared CPU/device semantics, media and generation remain
upstream. Authored code is MIT licensed; that grants no rights to game, firmware
or game-derived output.
