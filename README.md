# Ys III native-port project

An incremental PC Engine CD consumer of
[pcenginerecomp](https://github.com/rages4calm/pcenginerecomp), starting with
*Ys III: Wanderers from Ys* (USA).

**This is an early hybrid milestone. It is not a completed native port.**
The shared tool translates identified HuC6280 instructions into guarded C++;
unseen code continues through its interpreter. Actual retired instruction counts,
source identities and replay results determine coverage, not executable format
or the amount of generated source.

The initial tool pin is `33fe46d4274584da5ba55b419a240f248df4158d`, runtime ABI
**12**. See [toolchain.json](toolchain.json) for build/input identities and
[status](docs/STATUS.md) for the current consumer qualification.

## Build without game inputs

Requires Python 3.11+, CMake 3.20+, a C++20 compiler, Ninja and Git.

```sh
git clone https://github.com/rages4calm/pcenginerecomp .deps/pcenginerecomp
git -C .deps/pcenginerecomp checkout --detach 33fe46d4274584da5ba55b419a240f248df4158d
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

If the toolchain omits `ctest`, run
`python .deps/pcenginerecomp/scripts/check.py --build build/upstream` and
`python -m unittest discover -s tests -v` instead.

The default host has no game module and uses interpreted execution. Authored
upstream synthetic suites qualify the runtime and direct emitter separately.
No retail input is needed to build or run these tests. Source verification
rejects the wrong commit, dirty tracked source, hidden index flags or the wrong
ABI. An intentional development override must name the exact clean commit.

## Private game development

Supply your own matching disc and System Card BIOS. No media, generated game
code, game captures or saves are distributed. Existing owner inputs remain
read-only. The qualified upstream private route can be reused by a local
developer who already has that evidence; see [development](docs/DEVELOPMENT.md).

The current route uses an explicit reference-emulator `gear-good` response for
an unknown CD command. That condition does not implement the unknown operation
or establish hardware correctness. Initial formatted blank BRAM is read-only;
guest SAVE/LOAD stays within one process. Host save persistence, decoded/mixed
audio, authentic console reset and campaign completion remain unfinished.

Game configuration, overlay discovery, native coverage, enhancements, launcher
and extended gameplay checks belong here. Shared CPU/device semantics, media,
generation and reusable host features belong in the tool project. Improvements
must retain the reference path and measured native/interpreted accounting.

Authored project code is MIT licensed. That license grants no rights to the
game, firmware or game-derived output.
