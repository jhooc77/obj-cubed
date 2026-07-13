#version 410
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:light.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;

in vec4 lightColor;
in vec4 overlayColor;
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
flat in int isGUI;
flat in int isHand;
flat in int noshadow;

out vec4 fragColor;

#moj_import <objmc_static_fragment.glsl>

// OC_HYBRID_SURFACE_PATCH_v1_4
void main() {
    // objmc debug bypass (isCustom == 2 flag set in vertex shader)
    if (isCustom == 2) {
        fragColor = vec4(overlayColor.rgb, 1.0);
        return;
    }

    vec4 color;
    if (ocSurfaceMap.w > 0.5) {
        vec2 ocLocalUv;
        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,
                               ocSurfaceMap.w, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord  + ocLocalUv * ocSurfaceMap.xy;
        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        } else {
            color = ocColor0;
        }
    } else {
        color = transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord);
    }

    //custom lighting
    #define ENTITY
    #moj_import<objmc_light.glsl>

    if (color.a < 0.1) {
        discard;
    }
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}
