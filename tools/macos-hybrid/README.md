# Surface-v4-only tooling

This fork intentionally has one renderer: a static, GLSL 4.10, subgroup-free
Surface-v4 backend. It does not contain or fall back to Full-v2.

Supported:

- static OBJ items, `item_display`, blocks, hand/GUI/fixed/ground/head/shelf contexts
- exact display translation, XYZ scale, `left_rotation`, and `right_rotation`
- multiple textures/atlas, texture-frame animation, tint/hue/hurt behavior, emissive faces
- automatic N-gon, concave quad, non-affine quad, and non-planar quad triangulation

Not supported in this branch:

- geometry/bone/morph animation
- worn equipment/armor (ordinary armor items can still use a static item model)
- RGB-driven geometry scale

Run from the repository root:

```bash
python3 tools/macos-hybrid/install.py .
python3 tools/macos-hybrid/validate_actual.py
```

The optimizer is idempotent. Exact rectangular faces with direct color and a
static texture use a native UV fast path; remaining faces use compact metadata,
provoking-vertex-only fetches, and precomputed fragment equations.
