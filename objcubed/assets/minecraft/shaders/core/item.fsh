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
flat in float transition;

in vec2 ocSurfaceCoord;
flat in vec4 ocSurfaceP01;
flat in vec4 ocSurfaceP23;
flat in vec4 ocSurfaceUV01;
flat in vec4 ocSurfaceUV23;
flat in vec4 ocSurfaceMap;
flat in vec4 ocSurfaceOverlay;

flat in int isCustom;
flat in int isGUI;
flat in int isHand;
flat in int noshadow;

out vec4 fragColor;

#moj_import <objmc_static_fragment.glsl>

// OC_SURFACE_V4_ONLY_v1_5
void main() {
    // objmc debug bypass (isCustom == 2 flag set in vertex shader)
    if (isCustom == 2) {
        fragColor = vec4(overlayColor.rgb, 1.0);
        return;
    }

    vec4 color;
    if (isCustom == 1) {
        vec2 ocUv;
        float ocNextV;
        if (!ocResolveStaticUvFast(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                                   ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap,
                                   ocUv, ocNextV)) discard;
        vec4 ocColor0 = texture(Sampler0, ocUv);
        color = transition > 0.0
            ? mix(ocColor0, texture(Sampler0, ocUv + vec2(0.0, ocNextV)), transition)
            : ocColor0;
    } else if (isCustom == 3) {
        discard;
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
