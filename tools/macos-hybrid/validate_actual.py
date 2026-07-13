#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG = "OC_SURFACE_V4_ONLY_v1_5"


def die(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


plugin = ROOT / "objcubed.js"
shader_root = ROOT / "objcubed/assets/minecraft/shaders"
main = shader_root / "include/objmc_main.glsl"
fragment = shader_root / "include/objmc_static_fragment.glsl"
manifest_path = ROOT / "HYBRID_SURFACE_PATCH.json"
for path in (plugin, main, fragment, manifest_path):
    if not path.exists():
        die(f"missing {path.relative_to(ROOT)}")

plugin_text = plugin.read_text(encoding="utf-8")
main_text = main.read_text(encoding="utf-8")
fragment_text = fragment.read_text(encoding="utf-8")
all_shader_text = "\n".join(p.read_text(encoding="utf-8") for p in shader_root.rglob("*.glsl"))
all_shader_text += "\n" + "\n".join(p.read_text(encoding="utf-8") for p in shader_root.rglob("*.vsh"))
all_shader_text += "\n" + "\n".join(p.read_text(encoding="utf-8") for p in shader_root.rglob("*.fsh"))

if len(plugin_text.splitlines()) < 5000:
    die("objcubed.js looks truncated")
if TAG not in plugin_text or TAG not in main_text or TAG not in fragment_text:
    die("surface-v4-only tag missing")
if "OC_STATIC_META_STRIDE = 9" not in plugin_text:
    die("9-texel metadata stride missing")
if "normalizeStaticObj" not in plugin_text or "ocTriangulateFace" not in plugin_text:
    die("automatic polygon normalization/triangulation missing")
if "buildStaticSurfacePlan" not in plugin_text or "nativeCount" not in plugin_text:
    die("native rectangle fast path missing")
if "ocCorner == 0 || ocCorner == 2" not in main_text:
    die("provoking-vertex metadata fetch gate missing")
if "ocResolveStaticUvFast" not in fragment_text:
    die("precomputed fragment path missing")
if "fwidth(" in fragment_text or "/ den" in fragment_text:
    die("expensive per-fragment barycentric path remains")
if "subgroupQuadBroadcast" in all_shader_text or "GL_KHR_shader_subgroup" in all_shader_text or "OC_HAS_SUBGROUP" in all_shader_text:
    die("subgroup code remains in runtime shaders")
if "OC_STATIC_FALLBACK" in plugin_text or "full-v2" in main_text:
    die("legacy fallback remains")
if "const result = await buildOutput(cfg, objs, mtl);" not in plugin_text:
    die("runExport still contains fallback orchestration")
if "staticSurface: true" not in plugin_text:
    die("single Surface-v4 backend is not forced")
if "minecraft:single" not in plugin_text:
    die("model-specific atlas source missing")
if "source: 'item', prefix: 'item/'" in plugin_text:
    die("broad item atlas source still present")
if "flat flat" in all_shader_text:
    die("duplicate flat qualifier")

for name in ("item", "entity", "block", "terrain"):
    vsh = shader_root / f"core/{name}.vsh"
    fsh = shader_root / f"core/{name}.fsh"
    vt = vsh.read_text(encoding="utf-8")
    ft = fsh.read_text(encoding="utf-8")
    if not vt.startswith("#version 410") or not ft.startswith("#version 410"):
        die(f"{name} shader is not GLSL 410")
    if "ocSurfaceOverlay" not in vt or "ocSurfaceOverlay" not in ft:
        die(f"{name} flat overlay varying missing")
    if "flat out float transition" not in vt or "flat in float transition" not in ft:
        die(f"{name} transition is not flat")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
expected = {
    "patch": TAG,
    "backend": "surface-v4-only-static",
    "shader_version": 410,
    "subgroup": False,
    "fallback": False,
    "native_rectangle_fast_path": True,
    "provoking_vertex_metadata_fetch": True,
    "non_planar_quad_policy": "automatic triangulation",
}
for key, value in expected.items():
    if manifest.get(key) != value:
        die(f"manifest {key!r}: expected {value!r}, got {manifest.get(key)!r}")

print("surface-v4-only checkout validation passed")
