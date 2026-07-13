#version 410
// Ask for subgroup quad operations only when the driver advertises them.
// Apple OpenGL 4.1 does not, so it never sees an unknown #extension line.
#ifdef GL_KHR_shader_subgroup_quad
#extension GL_KHR_shader_subgroup_quad : enable
#define OC_HAS_SUBGROUP 1
#else
#define OC_HAS_SUBGROUP 0
#endif
// 26.2 validates shader-declared uniforms against the pipeline: variants with
// NO_CARDINAL_LIGHTING (energy_swirl, eyes, ...) do not provide the Lighting
// UBO, so light.glsl (which declares it) must be compiled out there — same
// guard vanilla 26.2 uses.
#if defined(PER_FACE_LIGHTING) || !defined(NO_CARDINAL_LIGHTING)
#moj_import <minecraft:light.glsl>
#endif
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>
#moj_import <minecraft:globals.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler0;
#ifndef NO_OVERLAY
uniform sampler2D Sampler1;
#endif
#ifndef EMISSIVE
uniform sampler2D Sampler2;
#endif

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
#ifdef PER_FACE_LIGHTING
out vec4 vertexPerFaceColorBack;
out vec4 vertexPerFaceColorFront;
#else
out vec4 vertexColor;
#endif

out vec4 lightColor;
out vec4 overlayColor;
out vec2 texCoord;
// texCoord2 is written by objmc_main.glsl's animated-texture path (issue #9).
// entity.fsh deliberately ignores it (entity frames hard-step, no GPU fade),
// but the varying must be declared so the shared include compiles here.
out vec2 texCoord2;
out vec3 Pos;
out float transition;

out vec2 ocSurfaceCoord;
flat out vec4 ocSurfaceP01;
flat out vec4 ocSurfaceP23;
flat out vec4 ocSurfaceUV01;
flat out vec4 ocSurfaceUV23;
flat out vec4 ocSurfaceMap;

flat out int isCustom;
flat out int isGUI;
flat out int isHand;
flat out int noshadow;

#moj_import <objmc_tools.glsl>

// OC_HYBRID_SURFACE_PATCH_v1_2
void main() {
    ocSurfaceCoord = vec2(0.0);
    ocSurfaceP01 = vec4(0.0);
    ocSurfaceP23 = vec4(0.0);
    ocSurfaceUV01 = vec4(0.0);
    ocSurfaceUV23 = vec4(0.0);
    ocSurfaceMap = vec4(0.0);
    Pos = Position;
    texCoord = UV0;
    lightColor = vec4(1);
    overlayColor = vec4(1);
#ifndef NO_OVERLAY
    overlayColor = texelFetch(Sampler1, UV1, 0);
#endif
#ifdef PER_FACE_LIGHTING
    vec2 light = minecraft_compute_light(Light0_Direction, Light1_Direction, Normal);
    vertexPerFaceColorBack = minecraft_mix_light_separate(-light, Color);
    vertexPerFaceColorFront = minecraft_mix_light_separate(light, Color);
#elif defined(NO_CARDINAL_LIGHTING)
    vertexColor = Color;
#else
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, Color);
#endif
#ifndef EMISSIVE
    lightColor = texture(Sampler2, vec2(UV2 / 16) / vec2(textureSize(Sampler2, 0)));
#endif
#ifdef APPLY_TEXTURE_MATRIX
    texCoord = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif

    //objmc
    #define ENTITY
    #moj_import <objmc_main.glsl>

    gl_Position = ProjMat * ModelViewMat * vec4(Pos, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Pos);
    cylindricalVertexDistance = fog_cylindrical_distance(Pos);

}
