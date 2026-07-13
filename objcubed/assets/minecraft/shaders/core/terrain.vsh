#version 410
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:globals.glsl>
#moj_import <minecraft:chunksection.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV2;

uniform sampler2D Sampler0;
uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;

out vec4 lightColor;
out vec2 texCoord;
out vec2 texCoord2;
out vec3 Pos;
flat out float transition;

out vec2 ocSurfaceCoord;
flat out vec4 ocSurfaceP01;
flat out vec4 ocSurfaceP23;
flat out vec4 ocSurfaceUV01;
flat out vec4 ocSurfaceUV23;
flat out vec4 ocSurfaceMap;
flat out vec4 ocSurfaceOverlay;

flat out int isCustom;
flat out int noshadow;

#moj_import <objmc_tools.glsl>

vec4 minecraft_sample_lightmap(sampler2D lightMap, ivec2 uv) {
    return texture(lightMap, clamp(uv / 256.0, vec2(0.5 / 16.0), vec2(15.5 / 16.0)));
}

// OC_SURFACE_V4_ONLY_v1_5
void main() {
    ocSurfaceCoord = vec2(0.0);
    ocSurfaceP01 = vec4(0.0);
    ocSurfaceP23 = vec4(0.0);
    ocSurfaceUV01 = vec4(0.0);
    ocSurfaceUV23 = vec4(0.0);
    ocSurfaceMap = vec4(0.0);
    ocSurfaceOverlay = vec4(1.0);
    texCoord2 = UV0;
    transition = 0;
    isCustom = 0;
    noshadow = 0;
    Pos = Position + (ChunkPosition - CameraBlockPos) + CameraOffset;
    vertexColor = Color;
    lightColor = minecraft_sample_lightmap(Sampler2, UV2);
    texCoord = UV0;
    
    //objmc
    #define BLOCK
    #moj_import <objmc_main.glsl>

    gl_Position = ProjMat * ModelViewMat * vec4(Pos, 1.0);
    sphericalVertexDistance = fog_spherical_distance(Pos);
    cylindricalVertexDistance = fog_cylindrical_distance(Pos);
}
