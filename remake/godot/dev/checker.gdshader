shader_type spatial;
// 1 m checker squares in world space, so every box gets the same scale whatever its size.
// Used by the dev arena's floor and walls (see the material in dev_arena.tscn).

uniform vec4 color_a : source_color = vec4(0.42, 0.42, 0.45, 1.0);
uniform vec4 color_b : source_color = vec4(0.32, 0.32, 0.35, 1.0);

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	// Pick the two axes along the face, so walls get squares too.
	vec3 n = abs(world_normal);
	vec2 uv = n.y > 0.5 ? world_pos.xz : (n.x > n.z ? world_pos.zy : world_pos.xy);
	vec2 cell = floor(uv + 0.001);
	float parity = mod(cell.x + cell.y, 2.0);
	ALBEDO = mix(color_a.rgb, color_b.rgb, parity);
	ROUGHNESS = 0.9;
}
