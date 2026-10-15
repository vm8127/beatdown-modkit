"""Minimal glTF 2.0 binary (.glb) writer, standard library only.

Builds one scene of nodes with triangle meshes (positions, normals, one UV set, optional skin joints/weights), skins
(inverse bind matrices), animations (rotation/translation channels) and PNG textures embedded in the binary chunk.
Deterministic: the same input gives the same bytes.
"""
import json
import struct

FLOAT, UINT16, UINT32 = 5126, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


class Gltf:
    def __init__(self, generator="beatdown remake_assets"):
        self.j = {"asset": {"version": "2.0", "generator": generator}, "scene": 0, "scenes": [{"nodes": []}],
                  "nodes": [], "meshes": [], "materials": [], "textures": [], "images": [], "samplers": [],
                  "accessors": [], "bufferViews": [], "buffers": [], "skins": [], "animations": []}
        self.bin = bytearray()
        self.tex_index = {}
        self.time_index = {}

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.j["bufferViews"].append(v)
        return len(self.j["bufferViews"]) - 1

    def _accessor(self, view, ctype, count, typ, **kw):
        a = {"bufferView": view, "componentType": ctype, "count": count, "type": typ}
        a.update(kw)
        self.j["accessors"].append(a)
        return len(self.j["accessors"]) - 1

    def vec(self, values, n):
        """Float VECn attribute accessor (min/max included for positions)."""
        flat = [c for v in values for c in v]
        view = self._view(struct.pack(f"<{len(flat)}f", *flat), ARRAY_BUFFER)
        kw = {}
        if n == 3:
            kw = {"min": [min(v[i] for v in values) for i in range(3)], "max": [max(v[i] for v in values) for i in range(3)]}
        return self._accessor(view, FLOAT, len(values), f"VEC{n}", **kw)

    def joints(self, values):
        """JOINTS_0: 4 joint indices per vertex (u16)."""
        flat = [c for v in values for c in v]
        view = self._view(struct.pack(f"<{len(flat)}H", *flat), ARRAY_BUFFER)
        return self._accessor(view, UINT16, len(values), "VEC4")

    def floats(self, values, typ):
        """Plain float accessor (no buffer target): typ SCALAR, VEC3, VEC4, MAT4; values are tuples (or floats)."""
        flat = [c for v in values for c in v] if typ != "SCALAR" else list(values)
        kw = {"min": [min(values)], "max": [max(values)]} if typ == "SCALAR" else {}
        return self._accessor(self._view(struct.pack(f"<{len(flat)}f", *flat)), FLOAT, len(values), typ, **kw)

    def indices(self, idx):
        big = max(idx) > 0xFFFF
        data = struct.pack(f"<{len(idx)}{'I' if big else 'H'}", *idx)
        return self._accessor(self._view(data, ELEMENT_ARRAY_BUFFER), UINT32 if big else UINT16, len(idx), "SCALAR")

    def texture(self, key, png):
        """Embed a PNG once per key; returns the texture index."""
        if key in self.tex_index:
            return self.tex_index[key]
        if not self.j["samplers"]:
            self.j["samplers"].append({"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497})
        self.j["images"].append({"bufferView": self._view(png), "mimeType": "image/png", "name": str(key)})
        self.j["textures"].append({"sampler": 0, "source": len(self.j["images"]) - 1})
        self.tex_index[key] = len(self.j["textures"]) - 1
        return self.tex_index[key]

    def material(self, name, texture=None, color=(1, 1, 1, 1), alpha_mask=False):
        m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": list(color), "metallicFactor": 0.0,
                                                   "roughnessFactor": 1.0}}
        if texture is not None:
            m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": texture}
        if alpha_mask:
            m["alphaMode"] = "MASK"
            m["alphaCutoff"] = 0.5
            m["doubleSided"] = True
        self.j["materials"].append(m)
        return len(self.j["materials"]) - 1

    def mesh(self, name, primitives):
        """primitives: [(positions, normals, uvs, indices, material[, joints, weights])]; normals/uvs may be None;
        joints/weights: 4 per vertex (skinned meshes)."""
        prims = []
        for pos, nrm, uv, idx, mat, *skin in primitives:
            attrs = {"POSITION": self.vec(pos, 3)}
            if skin and skin[0]:
                attrs["JOINTS_0"] = self.joints(skin[0])
                attrs["WEIGHTS_0"] = self.vec(skin[1], 4)
            if nrm:
                attrs["NORMAL"] = self.vec(nrm, 3)
            if uv:
                attrs["TEXCOORD_0"] = self.vec(uv, 2)
            p = {"attributes": attrs, "indices": self.indices(idx), "mode": 4}
            if mat is not None:
                p["material"] = mat
            prims.append(p)
        self.j["meshes"].append({"name": name, "primitives": prims})
        return len(self.j["meshes"]) - 1

    def node(self, name, mesh=None, children=None, root=True, **kw):
        n = {"name": name}
        if mesh is not None:
            n["mesh"] = mesh
        if children:
            n["children"] = children
        n.update(kw)
        self.j["nodes"].append(n)
        i = len(self.j["nodes"]) - 1
        if root:
            self.j["scenes"][0]["nodes"].append(i)
        return i

    def skin(self, joints, inverse_binds, skeleton=None, name=None):
        """joints: node indices; inverse_binds: 16 floats per joint, column-major (glTF order)."""
        s = {"joints": list(joints), "inverseBindMatrices": self.floats(inverse_binds, "MAT4")}
        if skeleton is not None:
            s["skeleton"] = skeleton
        if name:
            s["name"] = name
        self.j["skins"].append(s)
        return len(self.j["skins"]) - 1

    def animation(self, name, channels, extras=None):
        """channels: [(node, path 'rotation'|'translation', times, values)], LINEAR. Identical key time lists share
        one input accessor."""
        samplers, chans = [], []
        for node, path, times, values in channels:
            key = tuple(times)
            if key not in self.time_index:
                self.time_index[key] = self.floats(times, "SCALAR")
            out = self.floats(values, "VEC4" if path == "rotation" else "VEC3")
            samplers.append({"input": self.time_index[key], "output": out, "interpolation": "LINEAR"})
            chans.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
        a = {"name": name, "channels": chans, "samplers": samplers}
        if extras:
            a["extras"] = extras
        self.j["animations"].append(a)
        return len(self.j["animations"]) - 1

    def glb(self):
        j = {k: v for k, v in self.j.items() if v != []}
        j["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(j, separators=(",", ":"), sort_keys=True).encode()
        js += b" " * (-len(js) % 4)
        b = bytes(self.bin) + b"\0" * (-len(self.bin) % 4)
        total = 12 + 8 + len(js) + 8 + len(b)
        return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js +
                struct.pack("<II", len(b), 0x004E4942) + b)
