#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path

TAG3 = 'OC_HYBRID_SURFACE_PATCH_v1_2'
TAG4 = 'OC_HYBRID_SURFACE_PATCH_v1_3'
HERE = Path(__file__).resolve().parent


def fail(msg):
    raise RuntimeError(msg)

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        fail(f'{label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)

def replace_between(text, start_marker, end_marker, replacement, label):
    i = text.find(start_marker)
    if i < 0: fail(f'{label}: start marker missing')
    j = text.find(end_marker, i)
    if j < 0: fail(f'{label}: end marker missing')
    return text[:i] + replacement.rstrip() + '\n\n' + text[j:]

def load(name):
    p = HERE / 'src-v4' / name
    if not p.exists(): fail(f'missing template {p}')
    return p.read_text(encoding='utf-8')

def patch_plugin(path: Path):
    text = path.read_text(encoding='utf-8')
    if TAG4 in text:
        print('[skip] plugin already surface-v4')
        return
    if TAG3 not in text:
        fail('objcubed.js is not the expected hybrid v1.2 source')

    helper = load('static_surface_plugin.js')
    section6 = '    // =========================================================\n    // Section 6: Pixel Encoding'
    text = replace_between(text, '// OC_HYBRID_SURFACE_PATCH_v1_2', section6, helper, 'static helper')

    old = '''        const uvH  = Math.ceil(nfaces / tw);
        const texH = th;
        const vpH  = Math.ceil(data.positions.length * 3 / tw);
        const vtH  = Math.ceil(data.uvs.length * 2 / tw);
        const vH   = Math.ceil(data.vertices.length * 2 / tw); // includes all frames'''
    new = '''        // Surface-v4 stores only compact face metadata (9 texels/face).
        // Full-v2 keeps the original position/UV/index streams unchanged.
        const uvH  = Math.ceil((cfg.staticSurface ? nfaces * OC_STATIC_META_STRIDE : nfaces) / tw);
        const texH = th;
        const vpH  = cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw);
        const vtH  = cfg.staticSurface ? 0 : Math.ceil(data.uvs.length * 2 / tw);
        const vH   = cfg.staticSurface ? 0 : Math.ceil(data.vertices.length * 2 / tw); // includes all frames'''
    text = replace_once(text, old, new, 'compact static layout')

    text = replace_once(text,
        '        put(0, 0, 12, 34, 56, 255);',
        '        put(0, 0, 12, 34, cfg.staticSurface ? 57 : 56, 255);',
        'static marker')
    text = replace_once(text,
        '        put(5, 0, Math.trunc(vpH/256)%256, vpH%256, Math.trunc(vtH/256)%256, 255);',
        '        put(5, 0, Math.trunc((cfg.staticSurface ? uvH : vpH)/256)%256,\n'
        '                  (cfg.staticSurface ? uvH : vpH)%256, Math.trunc(vtH/256)%256, 255);',
        'static metadata height')
    text = replace_once(text,
        '            cb%256, cfg.staticSurface ? 3 : 2, 255);',
        '            cb%256, cfg.staticSurface ? 4 : 2, 255);',
        'surface header version')
    text = replace_once(text,
        '        put(7, 0, frameH%256, nvertices%256, vtH%256, 255);',
        '        put(7, 0, frameH%256, nvertices%256, cfg.staticSurface ? 0 : vtH%256, 255);',
        'static vt height')
    text = replace_once(text,
        '        const { dynamics } = assignSlotMarkers(buildDisplayTransforms(cfg));',
        '        const { dynamics } = cfg.staticSurface\n'
        '            ? { dynamics: [] }\n'
        '            : assignSlotMarkers(buildDisplayTransforms(cfg));',
        'skip static slot markers')
    text = replace_once(text,
        '                staticFirstObj, cfg, tw, ty, headerRows, put, faceEmission',
        '                staticFirstObj, data, cfg, tw, ty, headerRows, put, faceEmission',
        'pass indexed data')

    anchor = '        const bakeOffset = [cfg.offset[0], cfg.offset[1] - 0.5, cfg.offset[2]];\n'
    text = replace_once(text, anchor, anchor + '        if (!cfg.staticSurface) {\n', 'open legacy stream guard')
    end_anchor = '''        for (let i = 0; i < data.vertices.length; i++) {
            const pixels = vertPixels(data.vertices[i]);
            for (const [j, pxArr] of pixels.entries()) {
                const p = i*2+j;
                put(p%tw, ybase+Math.floor(p/tw), ...pxArr);
            }
        }

        // Round-trip verification'''
    end_repl = '''        for (let i = 0; i < data.vertices.length; i++) {
            const pixels = vertPixels(data.vertices[i]);
            for (const [j, pxArr] of pixels.entries()) {
                const p = i*2+j;
                put(p%tw, ybase+Math.floor(p/tw), ...pxArr);
            }
        }
        }

        // Round-trip verification'''
    text = replace_once(text, end_anchor, end_repl, 'close legacy stream guard')

    text = replace_once(text,
        '''        // Position data
        let ybase = headerRows+uvH+texH;''',
        '''        if (cfg.staticSurface && (uvClamped || data.uvs.some(uv => uv.some(v => v < -1e-6 || v > 1 + 1e-6))))
            surfaceWarning('some UVs fall outside the 0..1 frame (tiling/negative) and were clamped — those faces may look wrong. Keep the model UV-mapped inside the texture frame.');

        // Position data
        let ybase = headerRows+uvH+texH;''',
        'static UV warning')

    text = replace_once(text,
        "            if (mk[0]!==12||mk[1]!==34||mk[2]!==56||mk[3]!==255) {",
        "            if (mk[0]!==12||mk[1]!==34||mk[2]!==(cfg.staticSurface?57:56)||mk[3]!==255) {",
        'verify static marker')
    verify_start = '            // Verify first position (shader decodes as v*scale+offset)\n'
    text = replace_once(text, verify_start, '            if (cfg.staticSurface) {\n'
        '                const m0 = rd(0, headerRows);\n'
        '                const mx = m0[0] * 256 + m0[1];\n'
        '                const my = m0[2] * 256 + m0[3];\n'
        '                if (mx !== 0 || my !== headerRows) {\n'
        "                    verifyWarns.push('static metadata pointer mismatch');\n"
        '                    console.error(`[obj3-verify] static pointer: enc=[${mx},${my}] expected=[0,${headerRows}]`);\n'
        '                }\n'
        '            } else {\n' + verify_start, 'open verifier split')
    verify_end = '''            // Verify last frame's first vertex
            if (nframes > 1) {
                const lastIdx = (nframes-1) * nvertices;
                const lp = lastIdx * 2;
                const la = rd(lp%tw, vtxBase+Math.floor(lp/tw));
                const decLPi = la[0]*65536+la[1]*256+la[2];
                const srcLast = data.vertices[lastIdx];
                if (srcLast) {
                    if (decLPi !== srcLast[0]) { verifyWarns.push('last frame mismatch'); console.error(`[obj3-verify] vert[${lastIdx}].pos: enc=${decLPi} exp=${srcLast[0]}`); }
                }
            }
        } catch(e)'''
    text = replace_once(text, verify_end, verify_end.replace('\n        } catch(e)', '\n            }\n        } catch(e)'), 'close verifier split')

    text = text.replace("' · surface-v3'", "' · surface-v4'")
    path.write_text(text, encoding='utf-8')
    print('[ok] optimized plugin surface-v4')


def patch_main(path: Path):
    text = path.read_text(encoding='utf-8')
    if TAG4 in text:
        print('[skip] main already surface-v4')
        return
    if TAG3 not in text:
        fail('objmc_main.glsl is not expected hybrid v1.2')
    static = load('objmc_static_vertex_hybrid.glsl').rstrip()
    idx = text.find('#if OC_HAS_SUBGROUP')
    if idx < 0: fail('legacy subgroup split missing')
    text = static + '\n\n' + text[idx:]

    old = '''int corner = gl_VertexID % 4;
ivec2 atlasSize = textureSize(Sampler0, 0);
vec2 onepixel = 1./atlasSize;
ivec2 uv = ivec2((UV0 * atlasSize));
vec3 posoffset = vec3(0);
float scale = 1;
vec3 rotation = vec3(0);
int headerheight = 0;
ivec4 t[16];
//read uv offset
t[0] = ivec4(texelFetch(Sampler0, uv, 0) * 255.0 + 0.5);
ivec2 uvoffset = ivec2(t[0].r*256 + t[0].g, t[0].b*256 + t[0].a);
//find and read topleft pixel
ivec2 topleft = uv - uvoffset;
//if topleft marker is correct
ivec4 marker = ivec4(texelFetch(Sampler0, topleft, 0)*255.0+0.5);'''
    new = '''int corner = ocCorner;
ivec2 atlasSize = ocAtlasSize;
vec2 onepixel = 1.0 / vec2(atlasSize);
ivec2 uv = ocPixel;
vec3 posoffset = vec3(0);
float scale = 1;
vec3 rotation = vec3(0);
int headerheight = 0;
ivec4 t[16];
t[0] = ocOffsetPixel;
ivec2 uvoffset = ocUvOffset;
ivec2 topleft = ocTopLeft;
ivec4 marker = ocMarker;'''
    text = replace_once(text, old, new, 'reuse initial legacy probe')

    pattern = re.compile(r'''    ivec2 ocFallbackAtlasSize = textureSize\(Sampler0, 0\);.*?    ivec4 ocFallbackMarker = ivec4\(texelFetch\(Sampler0, ocFallbackTopLeft, 0\) \* 255\.0 \+ 0\.5\);''', re.S)
    text, n = pattern.subn('''    ivec2 ocFallbackTopLeft = ocTopLeft;
    ivec4 ocFallbackMarker = ocMarker;''', text, count=1)
    if n != 1: fail(f'reuse fallback probe: found {n}')
    text = text.replace('// Static v3 models were handled above.', '// Static v4 models were handled above.')
    text = text.replace('if (ocFallbackHeader6.b != 3)', 'if (ocFallbackHeader6.b != 4)')
    path.write_text(text, encoding='utf-8')
    print('[ok] optimized main surface-v4')


def optimize_sample_branch(text: str, path_name: str) -> str:
    old = '        color = mix(texture(Sampler0, ocSample0), texture(Sampler0, ocSample1), transition);'
    new = '''        color = transition > 0.0
            ? mix(texture(Sampler0, ocSample0), texture(Sampler0, ocSample1), transition)
            : texture(Sampler0, ocSample0);'''
    if old not in text:
        fail(f'{path_name}: static sample block missing')
    text = text.replace(old, new, 1)

    if path_name == 'item.fsh':
        text = replace_once(text,
            '        color = mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);',
            '        color = transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord);',
            'item legacy single sample')
    elif path_name == 'block.fsh':
        old2 = '        color = isCustom == 1 ? mix(texelFetch(Sampler0, ivec2(texCoord * textureSize(Sampler0, 0)), 0), texelFetch(Sampler0, ivec2(texCoord2 * textureSize(Sampler0, 0)), 0), transition) : mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);'
        if old2 in text:
            text = text.replace(old2, '''        if (isCustom == 1) {
            ivec2 ocLegacy0 = ivec2(texCoord * textureSize(Sampler0, 0));
            color = transition > 0.0
                ? mix(texelFetch(Sampler0, ocLegacy0, 0), texelFetch(Sampler0, ivec2(texCoord2 * textureSize(Sampler0, 0)), 0), transition)
                : texelFetch(Sampler0, ocLegacy0, 0);
        } else {
            color = transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord);
        }''', 1)
    elif path_name == 'terrain.fsh':
        text = text.replace('        color = mix(sampleColor(texCoord), sampleColor(texCoord2), transition);',
                            '        color = transition > 0.0 ? mix(sampleColor(texCoord), sampleColor(texCoord2), transition) : sampleColor(texCoord);', 1)
    return text


def patch_fragments(core: Path, include: Path):
    shutil.copy2(HERE / 'src-v4' / 'objmc_static_fragment.glsl', include / 'objmc_static_fragment.glsl')
    for name in ('item.fsh','entity.fsh','block.fsh','terrain.fsh'):
        p = core / name
        text = p.read_text(encoding='utf-8')
        if TAG4 in text:
            continue
        text = text.replace(TAG3, TAG4)
        text = optimize_sample_branch(text, name)
        p.write_text(text, encoding='utf-8')
    print('[ok] optimized fragment sampling')


def patch_tools(repo: Path):
    src = repo / 'tools' / 'macos-hybrid' / 'src'
    src.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE/'src-v4'/'static_surface_plugin.js', src/'static_surface_plugin.js')
    shutil.copy2(HERE/'src-v4'/'objmc_static_vertex_hybrid.glsl', src/'objmc_static_vertex_hybrid.glsl')
    shutil.copy2(HERE/'src-v4'/'objmc_static_fragment.glsl', src/'objmc_static_fragment.glsl')
    manifest_path = repo/'HYBRID_SURFACE_PATCH.json'
    obj = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    obj['patch'] = TAG4
    obj['static_backend'] = 'surface-v4-compact-metadata'
    obj['static_face_metadata_texels'] = 9
    obj['static_legacy_streams'] = False
    manifest_path.write_text(json.dumps(obj, indent=2)+'\n', encoding='utf-8')


def validate(repo: Path):
    js = (repo/'objcubed.js').read_text(encoding='utf-8')
    main = (repo/'objcubed/assets/minecraft/shaders/include/objmc_main.glsl').read_text(encoding='utf-8')
    prefix = main.split('#if OC_HAS_SUBGROUP',1)[0]
    checks = {
        'plugin tag': TAG4 in js,
        'compact stride': 'OC_STATIC_META_STRIDE = 9' in js,
        'static streams removed': 'cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw)' in js,
        'marker57': 'ivec4(12, 34, 57, 255)' in prefix,
        'no static getpos': 'getpos(' not in prefix,
        'no static getvert': 'getvert(' not in prefix,
        'no static getuv': 'getuv(' not in prefix,
        'legacy subgroup kept': 'subgroupQuadBroadcast' in main.split('#if OC_HAS_SUBGROUP',1)[1],
        'single static sample': '? mix(texture(Sampler0, ocSample0)' in (repo/'objcubed/assets/minecraft/shaders/core/item.fsh').read_text(),
    }
    bad=[k for k,v in checks.items() if not v]
    if bad: fail('validation failed: '+', '.join(bad))
    print('[ok] surface-v4 structural validation')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('repo', nargs='?', type=Path, default=Path.cwd())
    args=ap.parse_args()
    repo=args.repo.resolve()
    patch_plugin(repo/'objcubed.js')
    patch_main(repo/'objcubed/assets/minecraft/shaders/include/objmc_main.glsl')
    patch_fragments(repo/'objcubed/assets/minecraft/shaders/core', repo/'objcubed/assets/minecraft/shaders/include')
    patch_tools(repo)
    validate(repo)
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print('ERROR:',e,file=sys.stderr)
        raise
