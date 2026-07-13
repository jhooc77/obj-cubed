#version 410
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
// (no minecraft:light.glsl: 26.2 block pipelines don't provide the Lighting
// UBO it declares, and the BLOCK branch of objmc_light.glsl doesn't need it)

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;

in vec4 lightColor;
in vec2 texCoord;
in vec2 texCoord2;
in vec3 Pos;
in float transition;

in vec2 ocSurfaceCoord;
flat in vec4 ocSurfaceP01;
flat in vec4 ocSurfaceP23;
flat in vec4 ocSurfaceUV01;
flat in vec4 ocSurfaceUV23;
flat in vec4 ocSurfaceMap;

flat in int isCustom;
flat in int noshadow;

out vec4 fragColor;

#moj_import <objmc_static_fragment.glsl>

// OC_HYBRID_SURFACE_PATCH_v1_2
void main() {
    vec4 color;
    if (ocSurfaceMap.w > 0.5) {
        vec2 ocLocalUv;
        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord  + ocLocalUv * ocSurfaceMap.xy;
        vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
        color = mix(texture(Sampler0, ocSample0), texture(Sampler0, ocSample1), transition);
    } else {
        color = isCustom == 1 ? mix(texelFetch(Sampler0, ivec2(texCoord * textureSize(Sampler0, 0)), 0), texelFetch(Sampler0, ivec2(texCoord2 * textureSize(Sampler0, 0)), 0), transition) : mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);
    }

    //custom lighting
    #define BLOCK
    #moj_import<objmc_light.glsl>

#ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {
        discard;
    }
#endif
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
