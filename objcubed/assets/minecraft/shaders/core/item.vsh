#version 410
// Ask for subgroup quad operations only when the driver advertises them.
// Apple OpenGL 4.1 does not, so it never sees an unknown #extension line.
#ifdef GL_KHR_shader_subgroup_quad
#extension GL_KHR_shader_subgroup_quad : enable
#define OC_HAS_SUBGROUP 1
#else
#define OC_HAS_SUBGROUP 0
#endif
#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>
#moj_import <minecraft:globals.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in vec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler0;
uniform sampler2D Sampler2;


out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;

out vec4 lightColor;
out vec4 overlayColor;
out vec2 texCoord;
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
    overlayColor = vec4(1);
    lightColor = texture(Sampler2, vec2(UV2 / 16) / vec2(textureSize(Sampler2, 0)));
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, Color);

    //objmc
    #define ENTITY
    #moj_import <objmc_main.glsl>

    gl_Position = ProjMat * ModelViewMat * vec4(Pos, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Pos);
    cylindricalVertexDistance = fog_cylindrical_distance(Pos);
}
