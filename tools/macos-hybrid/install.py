#!/usr/bin/env python3
"""Install the obj³ hybrid static-surface backend into an upstream checkout.

External workflow stays the same:
  * load objcubed.js in Blockbench
  * export to the resource-pack root

Backend selection is automatic:
  * static, non-equipment OBJ -> surface carrier format v3.1 (no subgroup needed)
  * geometry animation / equipment -> original format (runs when subgroup exists)

The patched shaders compile at GLSL 4.10.  The full legacy path is compiled only
when GL_KHR_shader_subgroup_quad is exposed by the active backend.  On macOS
OpenGL, static models still work and unsupported legacy models are hidden rather
than making the whole resource pack fail.  On Vulkan / supporting OpenGL, both
paths work.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PATCH_TAG = "OC_HYBRID_SURFACE_PATCH_v1_3"
OLD_PATCH_TAG = "OC_STATIC_SURFACE_PATCH_v1"
PREVIOUS_PATCH_TAG = "OC_HYBRID_SURFACE_PATCH_v1"
HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
STATIC_JS = SRC / "static_surface_plugin.js"
STATIC_VERTEX = SRC / "objmc_static_vertex_hybrid.glsl"
STATIC_FRAGMENT = SRC / "objmc_static_fragment.glsl"

VARYING_DECL_V = """out vec2 ocSurfaceCoord;
flat out vec4 ocSurfaceP01;
flat out vec4 ocSurfaceP23;
flat out vec4 ocSurfaceUV01;
flat out vec4 ocSurfaceUV23;
flat out vec4 ocSurfaceMap;
"""
VARYING_DECL_F = """in vec2 ocSurfaceCoord;
flat in vec4 ocSurfaceP01;
flat in vec4 ocSurfaceP23;
flat in vec4 ocSurfaceUV01;
flat in vec4 ocSurfaceUV23;
flat in vec4 ocSurfaceMap;
"""
VARYING_INIT = """    ocSurfaceCoord = vec2(0.0);
    ocSurfaceP01 = vec4(0.0);
    ocSurfaceP23 = vec4(0.0);
    ocSurfaceUV01 = vec4(0.0);
    ocSurfaceUV23 = vec4(0.0);
    ocSurfaceMap = vec4(0.0);
"""

GLSL_HEADER = """#version 410
// Ask for subgroup quad operations only when the driver advertises them.
// Apple OpenGL 4.1 does not, so it never sees an unknown #extension line.
#ifdef GL_KHR_shader_subgroup_quad
#extension GL_KHR_shader_subgroup_quad : enable
#define OC_HAS_SUBGROUP 1
#else
#define OC_HAS_SUBGROUP 0
#endif
"""

NO_SUBGROUP_FALLBACK = r'''
#if OC_HAS_SUBGROUP
if (!ocStaticHandled) {
__OC_LEGACY_SOURCE__
}
#else
// Static v3 models were handled above.  Legacy flat carriers and equipment need
// cross-invocation communication, so hide only those placeholders on backends
// without subgroup support.  Vanilla geometry remains untouched.
if (!ocStaticHandled) {
    ivec2 ocFallbackAtlasSize = textureSize(Sampler0, 0);
    ivec2 ocFallbackPixel = ivec2(UV0 * vec2(ocFallbackAtlasSize));
    ivec4 ocFallbackOffsetPixel = ivec4(texelFetch(Sampler0, ocFallbackPixel, 0) * 255.0 + 0.5);
    ivec2 ocFallbackUvOffset = ivec2(
        ocFallbackOffsetPixel.r * 256 + ocFallbackOffsetPixel.g,
        ocFallbackOffsetPixel.b * 256 + ocFallbackOffsetPixel.a
    );
    ivec2 ocFallbackTopLeft = ocFallbackPixel - ocFallbackUvOffset;
    ivec4 ocFallbackMarker = ivec4(texelFetch(Sampler0, ocFallbackTopLeft, 0) * 255.0 + 0.5);
    if (ocFallbackMarker == ivec4(12, 34, 56, 255)) {
        ivec4 ocFallbackHeader6 = getmeta(ocFallbackTopLeft, 6);
        if (ocFallbackHeader6.b != 3) {
            isCustom = 1;
            Pos = vec3(9999.0);
        }
    }
#ifdef ENTITY
    ivec4 ocFallbackArmor = ivec4(texelFetch(Sampler0, ivec2(0, 0), 0) * 255.0 + 0.5);
    if (ocFallbackArmor.rgb == ivec3(12, 34, 56) && ocFallbackArmor.a == 253) {
        isCustom = 1;
        Pos = vec3(9999.0);
    }
#endif
}
#endif
'''


def fail(message: str) -> RuntimeError:
    return RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise fail(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str, flags: int = 0) -> str:
    out, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise fail(f"{label}: expected exactly one regex match, found {count}")
    return out


def backup(path: Path) -> None:
    dst = path.with_name(path.name + ".pre-hybrid-surface")
    if not dst.exists():
        shutil.copy2(path, dst)


def require_clean(text: str, path: Path) -> None:
    if PATCH_TAG in text:
        return
    if OLD_PATCH_TAG in text:
        raise fail(
            f"{path} already contains the older static-only patch. Restore its "
            ".pre-static-surface backup or start from a clean upstream checkout."
        )
    if PREVIOUS_PATCH_TAG in text:
        raise fail(
            f"{path} already contains hybrid patch v1. Restore its "
            ".pre-hybrid-surface backup or start from a clean upstream checkout."
        )


def patch_plugin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    require_clean(text, path)
    if PATCH_TAG in text:
        print(f"[skip] plugin already patched: {path}")
        return
    helper = STATIC_JS.read_text(encoding="utf-8").rstrip()

    section6 = "    // =========================================================\n    // Section 6: Pixel Encoding"
    text = replace_once(text, section6, helper + "\n\n" + section6, "insert static surface helper")

    text = replace_once(
        text,
        "        const nframes   = objContents.length;",
        "        const nframes   = objContents.length;\n"
        "        if (cfg.staticSurface && nframes !== 1)\n"
        "            throw new Error('Static surface export requires one geometry frame.');\n"
        "        if (cfg.staticSurface && cfg.exportAsEquipment)\n"
        "            throw new Error('Equipment automatically uses the full carrier backend.');\n"
        "        const staticFirstObj = cfg.staticSurface ? parseObj(objContents[0], 0) : null;",
        "static backend guard",
    )

    text = replace_once(
        text,
        "            cb%256, 2, 255);",
        "            cb%256, cfg.staticSurface ? 3 : 2, 255);",
        "write static header version",
    )

    elements_pattern = r'''        // UV header \+ JSON elements\n        const elements = \[\];\n        for \(let i = 0; i < nfaces; i\+\+\) \{.*?        \}\n\n        // Texture rows'''
    elements_repl = '''        // UV header + JSON elements
        const elements = [];
        let staticSurfaceMeta = null;
        if (cfg.staticSurface) {
            staticSurfaceMeta = buildStaticSurfaceElements(
                staticFirstObj, cfg, tw, ty, headerRows, put, faceEmission
            );
            elements.push(...staticSurfaceMeta.elements);
        } else {
            for (let i = 0; i < nfaces; i++) {
                const px = i%tw, py = Math.floor(i/tw)+headerRows;
                put(px, py, Math.trunc(px/256)%256, px%256, Math.trunc(py/256)%256, py%256);
                const elem = {
                    from: [8,8,8], to: [24,24,8],
                    faces: { north: {
                        uv: [(px+0.1)*16/tw,(py+0.1)*16/ty,(px+0.9)*16/tw,(py+0.9)*16/ty],
                        texture: '#0', tintindex: 0,
                    }},
                };
                if (faceEmission[i] > 0) elem.light_emission = faceEmission[i];
                elements.push(elem);
            }
        }

        // Texture rows'''
    text = sub_once(text, elements_pattern, elements_repl, "replace carrier generation", re.S)

    text = replace_once(
        text,
        "        const debugInfo = `${nfaces} ${tPlural(nfaces, 'faces')} · ${nframes} ${tPlural(nframes, 'frames')} · ${tw}×${ty}px` + warnStr;",
        "        const debugInfo = `${nfaces} ${tPlural(nfaces, 'faces')} · ${nframes} ${tPlural(nframes, 'frames')} · ${tw}×${ty}px` + (cfg.staticSurface ? ' · surface-v3' : ' · full-v2') + warnStr;",
        "debug backend label",
    )
    text = replace_once(
        text,
        "        return { pngBuffer, rawBuf: buf, elements, nfaces, nvertices, nframes, tw, ty, debugInfo, faceGroups, faceBlocks, faceToPart, faceEmission };",
        "        return { pngBuffer, rawBuf: buf, elements, nfaces, nvertices, nframes, tw, ty, debugInfo, faceGroups, faceBlocks, faceToPart, faceEmission,\n"
        "            staticSurface: !!cfg.staticSurface,\n"
        "            staticModelTransformation: staticSurfaceMeta ? staticSurfaceMeta.modelTransformation : null };",
        "return backend metadata",
    )

    text = replace_once(
        text,
        "            if (key === 'gui') continue;",
        "            if (key === 'gui' && !cfg.staticSurface) continue;",
        "let vanilla handle static GUI transform",
    )

    text = replace_once(
        text,
        "    function calibratedElementsForSlot(baseElements, slot, markerId) {\n"
        "        const off = SLOT_OFFSETS[slot] || { x: 0, y: 0, z: 0 };",
        "    function calibratedElementsForSlot(baseElements, slot, markerId, staticSurface) {\n"
        "        // Surface carriers are the real model geometry. Legacy anchor and\n"
        "        // UV marker calibration applies only to flat carriers.\n"
        "        if (staticSurface) return baseElements;\n"
        "        const off = SLOT_OFFSETS[slot] || { x: 0, y: 0, z: 0 };",
        "surface slot calibration",
    )

    old_display_model = '''    function buildDisplayContextModel(modelBaseName, exportedSlots) {
        const tints = [{ type: 'minecraft:potion', default: -1 }];
        const ref = slot => `${EXPORT_NS}:item/${modelBaseName}_${slot}`;
        const cases = (exportedSlots || DISPLAY_SLOTS)
            .map(slot => ({
                when: slot,
                model: { type: 'minecraft:model', model: ref(slot), tints },
            }));
        const fallbackModel = {
            type: 'minecraft:model',
            model: ref('default'),
            tints,
        };
        if (cases.length === 0) return fallbackModel;
        return {
            type: 'minecraft:select',
            property: 'minecraft:display_context',
            cases,
            fallback: fallbackModel,
        };
    }'''
    new_display_model = '''    function buildDisplayContextModel(modelBaseName, exportedSlots, modelTransformation) {
        const tints = [{ type: 'minecraft:potion', default: -1 }];
        const ref = slot => `${EXPORT_NS}:item/${modelBaseName}_${slot}`;
        const modelFor = slot => {
            const node = { type: 'minecraft:model', model: ref(slot), tints };
            if (modelTransformation) node.transformation = modelTransformation;
            return node;
        };
        const cases = (exportedSlots || DISPLAY_SLOTS)
            .map(slot => ({ when: slot, model: modelFor(slot) }));
        const fallbackModel = modelFor('default');
        if (cases.length === 0) return fallbackModel;
        return {
            type: 'minecraft:select',
            property: 'minecraft:display_context',
            cases,
            fallback: fallbackModel,
        };
    }'''
    text = replace_once(text, old_display_model, new_display_model, "item wrapper transformation")

    text = replace_once(text, "    function buildItemSelector(modelBaseName, exportedSlots, baseItem) {",
                        "    function buildItemSelector(modelBaseName, exportedSlots, baseItem, modelTransformation) {",
                        "buildItemSelector signature")
    text = replace_once(text,
                        "{ when: modelBaseName, model: buildDisplayContextModel(modelBaseName, exportedSlots) },",
                        "{ when: modelBaseName, model: buildDisplayContextModel(modelBaseName, exportedSlots, modelTransformation) },",
                        "buildItemSelector model call")
    text = replace_once(text,
                        "    function mergeItemSelector(existing, modelBaseName, exportedSlots) {\n        const node = buildDisplayContextModel(modelBaseName, exportedSlots);",
                        "    function mergeItemSelector(existing, modelBaseName, exportedSlots, modelTransformation) {\n        const node = buildDisplayContextModel(modelBaseName, exportedSlots, modelTransformation);",
                        "merge selector transformation")

    exported_pattern = r'''            const exportedSlots = DISPLAY_SLOTS\.filter\(slot => \{.*?            \}\);'''
    exported_repl = '''            const exportedSlots = result.staticSurface
                ? DISPLAY_SLOTS.slice()
                : DISPLAY_SLOTS.filter(slot => {
                    if (slot === FALLBACK_SLOT) return true;
                    const off = SLOT_OFFSETS[slot] || { x:0, y:0, z:0 };
                    if (off.x !== 0 || off.y !== 0 || off.z !== 0) return true;
                    if (displayTransforms[slot] && !isIdentity(displayTransforms[slot])) return true;
                    return false;
                });'''
    text = sub_once(text, exported_pattern, exported_repl, "export all static display slots", re.S)

    text = replace_once(
        text,
        "                        calibratedElementsForSlot(result.elements, displayLookupSlot, markerId)),",
        "                        calibratedElementsForSlot(result.elements, displayLookupSlot, markerId, result.staticSurface)),",
        "surface slot writer",
    )
    text = replace_once(text,
                        "                    itemObj = mergeItemSelector(existing, modelName, exportedSlots);",
                        "                    itemObj = mergeItemSelector(existing, modelName, exportedSlots, result.staticModelTransformation);",
                        "merge static transform")
    text = replace_once(text,
                        "                    itemObj = buildItemSelector(modelName, exportedSlots, baseItem);",
                        "                    itemObj = buildItemSelector(modelName, exportedSlots, baseItem, result.staticModelTransformation);",
                        "build selector existing")
    text = replace_once(text,
                        "                itemObj = buildItemSelector(modelName, exportedSlots, baseItem);",
                        "                itemObj = buildItemSelector(modelName, exportedSlots, baseItem, result.staticModelTransformation);",
                        "build selector new")

    cfg_anchor = "                                animationEnabled: this.hasAnims && this.animationEnabled,"
    text = replace_once(
        text,
        cfg_anchor,
        cfg_anchor + "\n"
        "                                // Backend is automatic; the UI and export flow stay unchanged.\n"
        "                                staticSurface: !(this.hasAnims && this.animationEnabled) && !this.exportAsEquipment\n"
        "                                    && !cbParts.includes('scale'),",
        "automatic backend selection",
    )

    text = replace_once(
        text,
        "        const result = await buildOutput(cfg, objs, mtl);\n"
        "        onStatus(t('status_choose_location').replace('{info}', result.debugInfo));\n"
        "        await saveSingleOutput(result, displayTransforms, cfg);",
        "        let result;\n"
        "        try {\n"
        "            result = await buildOutput(cfg, objs, mtl);\n"
        "        } catch (e) {\n"
        "            if (!(cfg.staticSurface && e && e.ocStaticFallback)) throw e;\n"
        "            console.warn('[obj³] static surface fallback:', e.message);\n"
        "            surfaceWarning(e.message.replace(/^OC_STATIC_FALLBACK:\\s*/, '') +\n"
        "                ' — exported through the original full carrier backend.');\n"
        "            cfg = { ...cfg, staticSurface: false };\n"
        "            result = await buildOutput(cfg, objs, mtl);\n"
        "        }\n"
        "        onStatus(t('status_choose_location').replace('{info}', result.debugInfo));\n"
        "        await saveSingleOutput(result, displayTransforms, cfg);",
        "transparent static fallback",
    )

    # Stop stitching every namespace's item directory into blocks.png.  Add only
    # this exported obj³ texture; otherwise vanilla armor item models end up using
    # items.png and blocks.png at once and fail model baking.
    atlas_pattern = r'''    // assets/minecraft/atlases/blocks\.json.*?    function mergeBlocksAtlas\(existing\) \{.*?    \}\n'''
    atlas_repl = '''    // Add only exported obj³ textures to blocks.png. A broad `item/`
    // directory source also captures every vanilla item and causes multi-atlas
    // model-bake failures on 26.2.
    function objCubedAtlasSource(modelName) {
        const id = `${EXPORT_NS}:item/${modelName}`;
        return { type: 'minecraft:single', resource: id, sprite: id };
    }
    function buildBlocksAtlas(modelName) {
        return { sources: [objCubedAtlasSource(modelName)] };
    }
    function mergeBlocksAtlas(existing, modelName) {
        let sources = Array.isArray(existing.sources) ? existing.sources : [];
        sources = sources.filter(s => !(s &&
            (s.type === 'minecraft:directory' || s.type === 'directory') &&
            s.source === 'item' && (s.prefix === 'item/' || s.prefix === 'item')));
        const source = objCubedAtlasSource(modelName);
        const has = sources.some(s => s &&
            (s.type === 'minecraft:single' || s.type === 'single') &&
            s.resource === source.resource && (s.sprite || s.resource) === source.sprite);
        if (!has) sources.push(source);
        existing.sources = sources;
        return existing;
    }
'''
    text = sub_once(text, atlas_pattern, atlas_repl, "narrow block atlas source", re.S)
    text = replace_once(text,
                        "atlasObj = (existing && typeof existing === 'object') ? mergeBlocksAtlas(existing) : buildBlocksAtlas();",
                        "atlasObj = (existing && typeof existing === 'object') ? mergeBlocksAtlas(existing, modelName) : buildBlocksAtlas(modelName);",
                        "merge model-specific atlas")
    text = replace_once(text,
                        "atlasObj = buildBlocksAtlas();",
                        "atlasObj = buildBlocksAtlas(modelName);",
                        "build model-specific atlas")

    backup(path)
    path.write_text(text, encoding="utf-8")
    print(f"[ok] patched plugin: {path}")


def shader_header(text: str, path: Path) -> str:
    text = re.sub(r"^#version\s+\d+\s*$", "__OC_VERSION__", text, count=1, flags=re.M)
    text = re.sub(r"^#extension\s+GL_KHR_shader_subgroup_quad\s*:\s*\w+\s*\n", "", text, count=1, flags=re.M)
    if "__OC_VERSION__" not in text:
        raise fail(f"{path}: missing #version")
    return text.replace("__OC_VERSION__", GLSL_HEADER.rstrip(), 1)


def patch_vsh(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    require_clean(text, path)
    if PATCH_TAG in text:
        return
    text = shader_header(text, path)
    text = replace_once(text, "out float transition;\n", "out float transition;\n\n" + VARYING_DECL_V, f"varyings {path.name}")
    text = replace_once(text, "void main() {\n", "// " + PATCH_TAG + "\nvoid main() {\n" + VARYING_INIT, f"init {path.name}")
    backup(path)
    path.write_text(text, encoding="utf-8")


def static_sample_block(legacy: str) -> str:
    return f'''vec4 color;
    if (ocSurfaceMap.w > 0.5) {{
        vec2 ocLocalUv;
        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,
                               ocSurfaceMap.w, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord  + ocLocalUv * ocSurfaceMap.xy;
        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {{
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        }} else {{
            color = ocColor0;
        }}
    }} else {{
        color = {legacy};
    }}'''


def patch_fsh(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    require_clean(text, path)
    if PATCH_TAG in text:
        return
    text = re.sub(r"^#version\s+\d+\s*$", "#version 410", text, count=1, flags=re.M)
    text = replace_once(text, "in float transition;\n", "in float transition;\n\n" + VARYING_DECL_F, f"fragment varyings {path.name}")
    text = replace_once(text, "void main() {\n", "#moj_import <objmc_static_fragment.glsl>\n\n// " + PATCH_TAG + "\nvoid main() {\n", f"fragment helper {path.name}")

    if path.name == "item.fsh":
        old = "    vec4 color = mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);"
        text = replace_once(text, old, "    " + static_sample_block("transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord)"), "item sample")
    elif path.name == "entity.fsh":
        old = '''    vec4 color = transition > 0.0
        ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition)
        : texture(Sampler0, texCoord);'''
        legacy = "transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord)"
        text = replace_once(text, old, "    " + static_sample_block(legacy), "entity sample")
    elif path.name == "block.fsh":
        old = '''    vec4 color;
    if (isCustom == 1) {
        color = mix(texelFetch(Sampler0, ivec2(texCoord * textureSize(Sampler0, 0)), 0),
                    texelFetch(Sampler0, ivec2(texCoord2 * textureSize(Sampler0, 0)), 0), transition);
    } else {
        color = mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);
    }'''
        legacy = "isCustom == 1 ? mix(texelFetch(Sampler0, ivec2(texCoord * textureSize(Sampler0, 0)), 0), texelFetch(Sampler0, ivec2(texCoord2 * textureSize(Sampler0, 0)), 0), transition) : mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition)"
        text = replace_once(text, old, "    " + static_sample_block(legacy), "block sample")
    elif path.name == "terrain.fsh":
        old = "    vec4 color = mix(sampleColor(texCoord), sampleColor(texCoord2), transition);"
        new = '''    vec4 color;
    if (ocSurfaceMap.w > 0.5) {
        vec2 ocLocalUv;
        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,
                               ocSurfaceMap.w, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord + ocLocalUv * ocSurfaceMap.xy;
        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        } else {
            color = ocColor0;
        }
    } else {
        color = mix(sampleColor(texCoord), sampleColor(texCoord2), transition);
    }'''
        text = replace_once(text, old, new, "terrain sample")
    else:
        raise fail(f"unsupported fragment shader: {path}")
    backup(path)
    path.write_text(text, encoding="utf-8")


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    require_clean(text, path)
    if PATCH_TAG in text:
        return
    static = STATIC_VERTEX.read_text(encoding="utf-8").rstrip()
    legacy = text.rstrip()
    wrapped = NO_SUBGROUP_FALLBACK.replace("__OC_LEGACY_SOURCE__", legacy)
    combined = f"// {PATCH_TAG}\n{static}\n\n{wrapped.lstrip()}\n"
    backup(path)
    path.write_text(combined, encoding="utf-8")


def patch_pack(root: Path) -> None:
    shader_root = root / "assets" / "minecraft" / "shaders"
    core = shader_root / "core"
    include = shader_root / "include"
    main = include / "objmc_main.glsl"
    required = [main, STATIC_VERTEX, STATIC_FRAGMENT]
    for p in required:
        if not p.exists():
            raise fail(f"missing required file: {p}")
    patch_main(main)
    shutil.copy2(STATIC_FRAGMENT, include / "objmc_static_fragment.glsl")
    for name in ("item.vsh", "entity.vsh", "block.vsh", "terrain.vsh"):
        p = core / name
        if not p.exists(): raise fail(f"missing {p}")
        patch_vsh(p)
    for name in ("item.fsh", "entity.fsh", "block.fsh", "terrain.fsh"):
        p = core / name
        if not p.exists(): raise fail(f"missing {p}")
        patch_fsh(p)
    print(f"[ok] patched hybrid resource-pack shaders: {shader_root}")


def resolve_repo(repo: Path) -> tuple[Path, Path]:
    repo = repo.expanduser().resolve()
    plugin = repo / "objcubed.js"
    pack = repo / "objcubed"
    if not plugin.exists() or not (pack / "pack.mcmeta").exists():
        raise fail(
            f"{repo} is not an obj-cubed checkout. Expected objcubed.js and objcubed/pack.mcmeta."
        )
    return plugin, pack


def write_manifest(repo: Path) -> None:
    manifest = {
        "patch": PATCH_TAG,
        "upstream": "JagerMeistars/obj-cubed",
        "upstream_ref_tested": "6a85a1f30f5dd0843c656838c5ebca13f0e029ed",
        "automatic_backend": {
            "static_non_equipment": "surface-v3.1",
            "geometry_animation_equipment_or_rgb_geometry_scale": "full-v2-subgroup",
        },
        "shader_version": 410,
        "legacy_requires": "GL_KHR_shader_subgroup_quad (Vulkan is the macOS fallback)",
    }
    (repo / "HYBRID_SURFACE_PATCH.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", nargs="?", type=Path, default=Path.cwd(), help="upstream obj-cubed checkout (default: current directory)")
    ap.add_argument("--plugin", type=Path, help="patch only this objcubed.js")
    ap.add_argument("--pack", type=Path, help="patch only this resource-pack root")
    args = ap.parse_args()
    try:
        if args.plugin or args.pack:
            if args.plugin: patch_plugin(args.plugin.expanduser().resolve())
            if args.pack: patch_pack(args.pack.expanduser().resolve())
        else:
            plugin, pack = resolve_repo(args.repo)
            patch_plugin(plugin)
            patch_pack(pack)
            write_manifest(args.repo.expanduser().resolve())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Done. Blockbench usage is unchanged. Re-export static models to get surface-v3.1 PNGs.")
    print("Geometry animation/equipment remains available on subgroup-capable backends (Vulkan on macOS).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
