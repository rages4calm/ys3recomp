# Ys III remaster direction

The target is a polished native PC remaster that preserves Ys III's character,
art and gameplay while making the complete experience comfortable on modern
displays and controllers. Full native coverage and game progression continue
alongside presentation work.

## Presentation

- Render additional world content for true widescreen. Adapt camera bounds,
  room edges, sprites and HUD placement together. Preserve an original-view
  option and handle menus, dialogue, transitions and cutscenes deliberately.
- Offer crisp integer scaling, fractional square pixels and clear aspect
  choices. Label stretched output accurately.
- Make Sharp, CRT, Smooth and LCD shaders optional choices with consistent
  previews and readable text. Keep presentation settings separate from guest
  simulation and original digital audio.
- Give options, prompts and overlays a coherent visual style that suits the
  game's art. Check small windows, fullscreen and high-DPI displays.

## Controls and everyday use

- Provide controller-friendly options, readable button prompts and consistent
  navigation, with keyboard support and configurable bindings.
- Implement dependable process-independent saves with a defined local format,
  recovery behavior and tests. Current guest BRAM is volatile. Owner inputs and
  existing saves remain protected.
- Keep startup, settings and returning to play straightforward. Packaging and
  first-run setup must explain the required owner-supplied media clearly.

## Implementation and acceptance

Use the shared toolkit's desktop presentation, renderer callbacks, controller
support and development APIs. Ys III owns the game-specific world renderer,
camera and HUD adaptation. Shared defects belong upstream after local diagnosis;
do not maintain a private runtime fork.

For presentation-only changes, compare the same owning-build checkpoint and
bounded inputs across modes. Guest CPU, RAM, source identities, clocks and PCM
must agree; inspect both the original guest image and the final presented image.
Test real scene boundaries and controller flows before calling a feature ready.
Reuse completed route checks when their exact contracts remain unchanged.

The selected ABI29 toolkit already contains the presentation and widescreen
callback interfaces. The current game still uses its original world view; a
Ys III widescreen renderer, unified options interface and persistent saves are
future implementation work. Bounded native route qualification does not establish
full-game or campaign completion. Publication to a storefront is a separate task.
