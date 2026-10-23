# Consumer status — 23 October 2026

The second native-coverage milestone is verified. This is a bounded hybrid port
foundation, not complete native recompilation or a finished game port.

| Evidence | Result | Scope |
|---|---|---|
| Initial consumer build | Tool `33fe46d4274584da5ba55b419a240f248df4158d`, ABI 12, regenerated 785-site module | Separate build; active tool checkout not modified by this consumer |
| Initial replay | 5,050,558 native + 2,915,442,205 interpreted instructions, **0.17% native** | Complete retained 93,735-frame route and 25 image hashes match |
| First expanded replay | 2,048 identities in nine mappings; 2,784,362,065 native + 136,130,698 interpreted, **95.34% native** | Preserved as the previous consumer baseline |
| Current native module | 44,832 eligible observed identities across all 57 full MPR contexts | Shared upstream emitter; exact byte guards; four patch-span identities deliberately excluded |
| Current replay | 2,920,491,782 native + 981 interpreted, **99.99996641% native** | Same 2,920,492,763 retired instructions; 136,129,717 additional native retirements over the previous baseline |
| Block transfers | All 460,685 execute natively; zero interpreted | 121,557 transfers moved from interpreter to native; total and effects unchanged |
| Equivalence | All 25 guest PNG hashes, final exposed CPU/device/source diagnostics and 709 edit transactions match | Only TCP port and explicit tier/guard-miss counters differ; block-instruction totals conserved |
| Synthetic checks | 19 pinned upstream suites, 202 frontend tests discovered with four desktop skips; 60 consumer tests pass | Existing qualified empty-module build reused; authored inputs only; Windows x64 |
| Shared build/identity contract | Source, descriptor, module, input, executable and adjacent-output identities verified before/after | Official shared build/verify APIs; consumer-owned bounded TCP execution; clean exit and unchanged inputs |

Both tool revisions use ABI 12. Current code pin is
`639e377e0d17318f7034b2c661cada609d84ed48`; qualification uses Clang 22.1.8,
CMake 3.31.12, Ninja and Python 3.14.5 on Windows x64. CTest is absent from this
toolchain, so the documented upstream `scripts/check.py` fallback and consumer
unittest suite supplied the checks. Other hosts and a consumer SDL build are
not qualified by this batch.

## Observed-code expansion

The raw profile recorded 44,836 executed identities in 57 full MPR contexts
with no dropped/unreadable retirements. Batch one selected its hottest 2,048
original-code identities. This batch emits every eligible observation through
the pinned upstream range-exclusion interface, preserving the complete original
capture's hash, hit totals and completeness.

The journal verifies restoration of the original jump code. The entire temporary
patch span is excluded across all mappings and source variants, including its
original variants: four identities accounting for 981 original-profile hits.
The replay confirms exactly 981 interpreted retirements/guard misses. Auditing
all 709 edited ranges against every observed instruction-fetch address finds
only the two patch apply/restore transactions overlapping source; both are
fully excluded. No other assisted source bytes are promoted.

The gates were at least 99.9999% native execution and 136 million added native
retirements over the previous consumer baseline. Both passed. Raw capture,
generated code, module manifest, exclusion audit and replay receipts stay
private. Unvisited code/overlays remain unqualified and may interpret or stop
explicitly. A complete observed profile is not a complete game.

## Execution supervision

The first attempt used the shared `project.run` wrapper's 600-second wall
limit and stopped at frame 79,483; it is retained as a failed attempt. The
successful retry used the same binary and original route arguments under the
consumer TCP harness's explicit 1,800-second watchdog, finishing in about
840 seconds. Official `project verify` results and immutable build/output
bindings were checked before and after. The receipt states that the descriptor's
600-second execution limit was not applied. This is consumer-supervised route
qualification, not a shared `project.run` execution qualification.

These native counts are coverage evidence. This batch makes no gameplay speedup
claim; the monolithic module and concurrent host work affect wall time.

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

Next useful work is fresh bounded capture in unvisited scenes and extended
progression. Later shared-tool performance improvements need a deliberate pin
upgrade and affected checks. Shared semantics and reusable host features stay
upstream. Native coverage beyond this route needs its own execution evidence.
