# macOS hybrid backend tooling

This directory applies the compatibility backend without changing the Blockbench UI or export workflow.

Automatic backend selection:

- static, non-equipment OBJ: surface-v3 carriers; no subgroup operations; exact `item_display` XYZ scale and both rotations
- geometry animation, equipment, or RGB geometry-scale mode: original full-v2 carrier decoder
- macOS OpenGL 4.1: surface-v3 renders; unsupported full-v2 models are hidden instead of invalidating the entire resource pack
- Vulkan / subgroup-capable OpenGL: both backends render

The installer also replaces the broad `item/` blocks-atlas source with one `minecraft:single` source per exported obj³ texture, avoiding vanilla armor item multi-atlas bake failures.

Run from the repository root:

```bash
python3 tools/macos-hybrid/install.py .
```

The branch workflow applies this installer to the real upstream checkout, validates the result, commits the generated source changes, and uploads a patched-source artifact.
