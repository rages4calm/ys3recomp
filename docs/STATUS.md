# Consumer status — 23 October 2026

The first native-coverage milestone is verified. This is a bounded hybrid port
foundation, not complete native recompilation or a finished game port.

| Evidence | Result | Scope |
|---|---|---|
| Initial consumer build | Tool `33fe46d4274584da5ba55b419a240f248df4158d`, ABI 12, regenerated 785-site module | Separate build; active tool checkout not modified by this consumer |
| Initial replay | 5,050,558 native + 2,915,442,205 interpreted instructions, **0.17% native** | Complete retained 93,735-frame route and 25 image hashes match |
| Current native module | 2,048 observed original-code identities across nine full MPR contexts | Direct upstream C++ emission with exact byte guards; cold code remains interpreted |
| Current replay | 2,784,362,065 native + 136,130,698 interpreted, **95.34% native** | Same 2,920,492,763 retired instructions; 2,779,311,507 additional native retirements |
| Equivalence | All 25 guest PNG hashes, final exposed CPU/device/source diagnostics and 709 edit transactions match | Only TCP port and explicit tier/guard-miss counters differ; block-instruction totals conserved |
| Build without game inputs | 19 upstream suites, 202 frontend tests discovered with four desktop skips; 45 consumer tests pass | Empty module selection; authored synthetic inputs only; Windows x64 |
| Shared consumer contract | Tool-source, descriptor, module, input, executable and adjacent-output identities verified before/after execution | Shared build/run API used directly; clean exit and all protected hashes unchanged |

Both tool revisions use ABI 12. Current code pin is
`639e377e0d17318f7034b2c661cada609d84ed48`; qualification uses Clang 22.1.8,
CMake 3.31.12, Ninja and Python 3.14.5 on Windows x64. CTest is absent from this
toolchain, so the documented upstream `scripts/check.py` fallback and consumer
unittest suite supplied the checks. Other hosts and a consumer SDL build are
not qualified by this batch.

## Why these native identities

The separate raw profile recorded 44,836 executed instruction identities in
57 full MPR contexts with no dropped/unreadable retirements. Its hottest 2,048
original-code identities accounted for 95.34% of observed hits. This supported
a target of at least 90% native execution and two billion additional native
retirements on the same route; both gates passed.

The journal verifies restoration of the original jump code. Selection excludes
the conflicting temporary-patch identity, then ranks the remaining identities
by actual hits. Raw capture, selection receipt, selected subset, generated
module and build/run receipts remain private. A subset's completeness describes
that subset, not the complete raw profile or unvisited game code. Unselected
identities and unseen overlays still use the interpreter or stop explicitly
on unsupported semantics.

## Qualification limits

The route preserves ordinary-input checkpoints and separately journaled assisted
progression. It reaches a first-storehouse-boss encounter and visible enemy
damage; it does not establish an unassisted encounter, victory or campaign
completion. The same 709 transactions replay with no new assists.

The explicit `gear-good` reference-emulator unknown-command response is used
51 times. Strict-mode behavior remains unresolved; no unknown operation or
hardware behavior is certified. Startup is the existing BIOS-backed IPL-entry
sandbox rather than authentic reset. Initial blank formatted BRAM is read-only,
guest SAVE/LOAD is process-local, and audible output/persistent host saves
remain unfinished.

Independent evidence retains its upstream scope: Geargrafx 1.8.4 checks cover
78 authored capture-module plans, 156 CPU/MPR/clock states and 78 complete
work-RAM comparisons per tier. Prior independent title checks cover specific
town/combat/status and assist behaviors. Neither provides independent whole-route,
boss, campaign, audio or hardware parity for this consumer.

Next useful work is measured cold-code/overlay expansion and extended game
progression. Shared semantics and reusable host features stay upstream. Native
coverage beyond this route needs its own execution evidence.
