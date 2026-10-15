"""The 22-node body skeleton as glTF joints, shared by the model and animation converters.

Node order = the HAnim node index of the body clump (docs/FORMATS.md, "Skeleton and skinning"), which is also the
skin bone index and the animation track order (docs/ANIMATION.md). The joint names are fixed, so every model and
animation file built here has the same Skeleton3D bones in Godot and any clip plays on any M-body model.
"""
import math

import rwkit

SCALE = 0.1   # RenderWare units are about 10 cm

# Node index -> joint name. Sides from the bind pose (model faces +Z, so its right side is -X); not checked in-game.
BONE_NAMES = [
    "root", "hips", "thigh_r", "shin_r", "foot_r", "thigh_l", "shin_l", "foot_l",
    "spine", "chest", "head", "shoulder_r", "upperarm_r", "forearm_r", "hand_r", "handpoint_r",
    "shoulder_l", "upperarm_l", "forearm_l", "hand_l", "handpoint_l", "extra",
]
MOVING_NODES = (1, 8)   # the only nodes whose animation keys translate (hips and spine, both children of root)


def quat_from_rows(r):
    """RenderWare rotation rows (right, up, at; row vectors) -> glTF quaternion (x, y, z, w). The column matrix is
    the transpose; the stored animation quaternions use the same convention (checked against the bind pose)."""
    m = [[r[j][i] for j in range(3)] for i in range(3)]
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, 0.25 * s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s, (m[1][0] - m[0][1]) / s)
    n = math.sqrt(sum(c * c for c in q))
    q = tuple(round(c / n, 7) for c in q)
    return q if q[3] >= 0 else tuple(-c for c in q)


class Skeleton:
    """The body clump's 22 nodes: names, parents (node index, -1 for the root), local rotation rows and position."""
    def __init__(self, clump):
        nodes = rwkit.skeleton_nodes(clump)
        if len(nodes) != len(BONE_NAMES):
            raise ValueError(f"expected a {len(BONE_NAMES)}-node skeleton, got {len(nodes)}")
        frame_node = {f: k for k, f in nodes.items()}
        world = rwkit.world_matrices(clump.frames)
        self.parent, self.local, self.world = [], [], []
        for k in range(len(nodes)):
            fr = clump.frames[nodes[k]]
            p = frame_node.get(fr.parent, -1)
            # The root's parent is the clump frame (frame 0, identity in every clump seen); use its world matrix.
            m = rwkit.frame_matrix(fr) if p >= 0 else world[nodes[k]]
            self.parent.append(p)
            self.local.append(m)
            self.world.append(world[nodes[k]])

    def add_to(self, g):
        """Add the joint nodes (root at the scene root) and a skin; returns (joint node indices, skin index)."""
        idx = []
        for k, name in enumerate(BONE_NAMES):
            m = self.local[k]
            idx.append(g.node(name, root=self.parent[k] < 0,
                              translation=[round(c * SCALE, 6) for c in m[3][:3]],
                              rotation=list(quat_from_rows([row[:3] for row in m[:3]]))))
        for k, p in enumerate(self.parent):
            if p >= 0:
                g.j["nodes"][idx[p]].setdefault("children", []).append(idx[k])
        ibm = []
        for w in self.world:
            # Inverse of a rigid row-vector matrix: rotation transposed, position -p x R^T. glTF's column-major
            # order of the column matrix = the row-major order of RenderWare's row matrix.
            r = [row[:3] for row in w[:3]]
            rt = [[r[j][i] for j in range(3)] for i in range(3)]
            p = [c * SCALE for c in w[3][:3]]
            t = [-sum(p[i] * rt[i][j] for i in range(3)) for j in range(3)]
            ibm.append(tuple(round(c, 7) for c in rt[0] + [0.0] + rt[1] + [0.0] + rt[2] + [0.0] + t + [1.0]))
        return idx, g.skin(idx, ibm, skeleton=idx[0], name="body")
