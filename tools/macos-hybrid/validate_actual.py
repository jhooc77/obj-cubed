#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG = "OC_HYBRID_SURFACE_PATCH_v1_4"


def die(msg: str) -> None:
    raise SystemExit(f"validation failed: {msg}")


def without_subgroup_branch(text: str) -> str:
    """Return the source that remains when the outer OC_HAS_SUBGROUP is false."""
    marker = "#if OC_HAS_SUBGROUP"
    start = text.find(marker)
    if start < 0:
        die("missing OC_HAS_SUBGROUP wrapper")

    depth = 0
    outer_else_start = None
    outer_else_end = None
    outer_end_start = None
    outer_end_end = None
    pattern = re.compile(r"(?m)^(?P<indent>\s*)#(?P<kind>if|ifdef|ifndef|else|endif)\b.*$")
    for match in pattern.finditer(text, start):
        kind = match.group("kind")
        if kind in {"if", "ifdef", "ifndef"}:
            depth += 1
        elif kind == "else":
            if depth == 1 and outer_else_start is None:
                outer_else_start = match.start()
                outer_else_end = match.end()
        elif kind == "endif":
            depth -= 1
            if depth == 0:
                outer_end_start = match.start()
                outer_end_end = match.end()
                break
    if outer_else_start is None or outer_end_start is None:
        die("malformed OC_HAS_SUBGROUP wrapper")
    return text[:start] + text[outer_else_end:outer_end_start] + text[outer_end_end:]


def without_extension_fast_paths(text: str, macro: str) -> str:
    """Select the #else branch of every `#ifdef macro` block.

    The static exact-geometry optimization intentionally uses subgroup calls inside
    `#ifdef GL_KHR_shader_subgroup_quad`. On Apple OpenGL that macro is absent, so
    validation of the no-subgroup source must discard those true branches before
    checking that no lane operation remains.
    """
    opener = f"#ifdef {macro}"
    pattern = re.compile(r"(?m)^\s*#(?P<kind>if|ifdef|ifndef|else|endif)\b.*$")
    while True:
        start = text.find(opener)
        if start < 0:
            return text
        depth = 0
        else_start = else_end = None
        end_start = end_end = None
        for match in pattern.finditer(text, start):
            kind = match.group("kind")
            if kind in {"if", "ifdef", "ifndef"}:
                depth += 1
            elif kind == "else" and depth == 1 and else_start is None:
                else_start, else_end = match.start(), match.end()
            elif kind == "endif":
                depth -= 1
                if depth == 0:
                    end_start, end_end = match.start(), match.end()
                    break
        if end_start is None:
            die(f"malformed #ifdef {macro} block")
        replacement = text[else_end:end_start] if else_start is not None else ""
        text = text[:start] + replacement + text[end_end:]


plugin = ROOT / "objcubed.js"
main = ROOT / "objcubed/assets/minecraft/shaders/include/objmc_main.glsl"
if not plugin.exists() or not main.exists():
    die("not running in an obj-cubed checkout")

plugin_text = plugin.read_text(encoding="utf-8")
main_text = main.read_text(encoding="utf-8")
if len(plugin_text.splitlines()) < 5000:
    die("objcubed.js looks truncated")
if len(main_text.splitlines()) < 800:
    die("objmc_main.glsl looks truncated")
if TAG not in plugin_text or TAG not in main_text:
    die("surface-v1.4 patch tag missing")
if "OC_STATIC_META_STRIDE = 10" not in plugin_text:
    die("surface-v4 compact metadata stride missing")
if "cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw)" not in plugin_text:
    die("static position stream was not removed")
if "cfg.staticSurface ? 0 : Math.ceil(data.uvs.length * 2 / tw)" not in plugin_text:
    die("static UV stream was not removed")
if "cfg.staticSurface ? 0 : Math.ceil(data.vertices.length * 2 / tw)" not in plugin_text:
    die("static index stream was not removed")

prefix = main_text.split("#if OC_HAS_SUBGROUP", 1)[0]
if "ivec4(12, 34, 57, 255)" not in prefix:
    die("surface-v4 marker missing")
for forbidden in ("getvert(", "getpos(", "getuv("):
    if forbidden in prefix:
        die(f"legacy fetch remains in static-v4 path: {forbidden}")
if "ocPackedFlags" not in prefix:
    die("v1.3 deterministic edge-owner flags were not preserved")
if "ocCarrierOrigin = subgroupQuadBroadcast" not in prefix:
    die("subgroup-capable exact static geometry fast path missing")
if "staticSurface: !(this.hasAnims" not in plugin_text:
    die("automatic static selection missing")
if "!cbParts.includes('scale')" not in plugin_text:
    die("RGB scale compatibility gate missing")
if "OC_STATIC_FALLBACK" not in plugin_text:
    die("transparent full-backend fallback missing")
if "minecraft:single" not in plugin_text:
    die("narrow atlas source missing")
if "source: 'item', prefix: 'item/'" in plugin_text:
    die("broad item atlas source still present")
if "subgroupQuadBroadcast" not in main_text:
    die("original full-v2 decoder was not preserved")
if "BOX-PACKING" not in main_text:
    die("equipment decoder appears missing")
if "legacy decoder fixture" in main_text:
    die("fixture decoder was accidentally installed")
no_subgroup = without_subgroup_branch(main_text)
no_subgroup = without_extension_fast_paths(no_subgroup, "GL_KHR_shader_subgroup_quad")
if "subgroupQuadBroadcast" in no_subgroup:
    die("subgroup call remains in macOS OpenGL preprocessing path")

for name in ("item", "entity", "block", "terrain"):
    vsh = ROOT / f"objcubed/assets/minecraft/shaders/core/{name}.vsh"
    fsh = ROOT / f"objcubed/assets/minecraft/shaders/core/{name}.fsh"
    vt = vsh.read_text(encoding="utf-8")
    ft = fsh.read_text(encoding="utf-8")
    if not vt.startswith("#version 410"):
        die(f"{name}.vsh is not GLSL 410")
    if "#ifdef GL_KHR_shader_subgroup_quad" not in vt:
        die(f"{name}.vsh lacks conditional subgroup feature detection")
    if not ft.startswith("#version 410"):
        die(f"{name}.fsh is not GLSL 410")
    if "objmc_static_fragment.glsl" not in ft:
        die(f"{name}.fsh lacks surface fragment helper")
    if "transition > 0.0" not in ft or "texture(Sampler0, ocSample0)" not in ft:
        die(f"{name}.fsh lacks the one-sample static fast path")

manifest = json.loads((ROOT / "HYBRID_SURFACE_PATCH.json").read_text(encoding="utf-8"))
if manifest.get("patch") != TAG:
    die("manifest patch version mismatch")
if manifest.get("static_backend") != "surface-v4-compact-metadata":
    die("manifest static backend mismatch")
if manifest.get("static_face_metadata_texels") != 10:
    die("manifest metadata stride mismatch")
if manifest.get("static_legacy_streams") is not False:
    die("manifest says static legacy streams remain enabled")

print("actual checkout validation passed")
