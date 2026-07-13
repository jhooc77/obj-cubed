# surface-v4-only v1.5.1 hotfix

Base package: `obj-cubed-surface-v4-only-v1.5.zip`

Minecraft 26.1.2 compiles `block.fsh` and `terrain.fsh` without an
`overlayColor` varying. The shared `objmc_light.glsl` introduced an
unconditional reference to that entity-only varying, which made all block and
terrain pipelines fail resource-pack reload.

The v1.5.1 package wraps `ocLightingOverlay` in `#ifdef ENTITY`. No exporter
layout, model metadata, geometry, texture, or rendering algorithm changed.
`test/unit/surface-v4-only.test.mjs` pins the shared-include contract so every
`overlayColor` reference remains entity-guarded. The same guard is applied to
`tools/macos-hybrid/optimize_surface_v4_only.py` so rebuilding from a clean base
does not reintroduce the invalid shared include.

Patched `objmc_light.glsl` SHA-256:
`1D9047E8E9985FE72429FA93909C4268B2A00210301456BDA2FAFEADFDC9EE2D`
