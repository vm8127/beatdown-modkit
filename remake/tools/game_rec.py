"""Record fighters from the sandbox PCSX2 (tools/pcsx2.py) for the game-vs-remake combat comparison.

Polls fighter fields over PINE as fast as it can (one batched message per sample) and writes one CSV row per
change: wall time (s), then per fighter slot: action, motion frame, x, z, facing, hp, state, status, posture,
combo count, last input, control bits. Optionally presses keys at given times (posted to the sandbox window
only, like `pcsx2.py keys`), so a combo's inputs and its result land in one file.

  python remake/tools/game_rec.py out.csv --slots 0 3 --secs 4 --keys "0.2:square 0.45:square 0.7:square"
  python remake/tools/game_rec.py out.csv --slots 0 3 --secs 3 --keys "0.2:right+square" --hold right:0.1-0.3

Keys: `T:keys` presses at T seconds (keys as pcsx2.py names them, "a+b" together, held 50 ms); `--hold K:T0-T1`
holds a key (a direction) over a span. Times are wall-clock; the game runs at 60 frames per second, so a game
frame is about 16.7 ms (`frame` column = round(t * 60)). Standard library only; needs the sandbox running.
"""
import argparse
import csv
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import pcsx2  # noqa: E402

FIGHTERS = 0x006CFB70
SIZE = 0x4730
# (name, offset, size, kind): kind i = signed, u = unsigned, f = float
FIELDS = [("action", 0x4346, 2, "i"), ("mframe", 0x2D4, 4, "i"), ("x", 0x2AC, 4, "f"), ("z", 0x2B4, 4, "f"),
          ("facing", 0x2D0, 4, "f"), ("hp", 0x441C, 2, "i"), ("state", 0x4378, 4, "u"), ("status", 0x438C, 4, "u"),
          ("posture", 0x4390, 1, "u"), ("combo", 0x450C, 1, "u"), ("last_input", 0x4510, 4, "i"),
          ("control", 0x4388, 4, "u"), ("motion", 0x3FA4, 2, "i"), ("speed", 0x3FE8, 4, "f")]


class FastPine(pcsx2.Pine):
    """pcsx2.Pine on one kept-open socket (a new connection per message caps it near 100 samples/s)."""
    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", pcsx2.PINE_PORT), timeout=10)

    def _recv(self, n):
        data = b""
        while len(data) < n:
            part = self.s.recv(n - len(data))
            if not part:
                raise OSError("PINE closed the connection")
            data += part
        return data

    def call(self, ops, reply_size):
        msg = b"".join(ops)
        self.s.sendall(struct.pack("<I", len(msg) + 4) + msg)
        n, = struct.unpack("<I", self._recv(4))
        data = self._recv(n - 4)
        if data[0] != 0:
            raise SystemExit("PINE refused the request (is a game running?)")
        return data[1:]


def sample(pine, slots):
    ops = []
    for s in slots:
        base = FIGHTERS + s * SIZE
        for _, off, size, _ in FIELDS:
            ops.append(struct.pack("<BI", pine.READ[size], base + off))
    data = pine.call(ops, 0)
    out, p = [], 0
    for s in slots:
        for _, _, size, kind in FIELDS:
            raw = data[p:p + size]
            p += size
            if kind == "f":
                out.append(round(struct.unpack("<f", raw)[0], 3))
            else:
                out.append(int.from_bytes(raw, "little", signed=kind == "i"))
    return out


def press_thread(keys, holds, t0):
    events = []
    for tok in keys.split():
        t, k = tok.split(":", 1)
        names = [pcsx2.BUTTON_KEYS.get(n.lower(), n) for n in k.split("+")]
        events.append((float(t), names, True))
        events.append((float(t) + 0.05, names, False))
    for h in holds:
        k, span = h.split(":")
        a, b = span.split("-")
        name = pcsx2.BUTTON_KEYS.get(k.lower(), k)
        events.append((float(a), [name], True))
        events.append((float(b), [name], False))
    events.sort(key=lambda e: e[0])
    for t, names, down in events:
        while time.perf_counter() - t0 < t:
            time.sleep(0.001)
        for n in names:
            pcsx2.post_key(n, down)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--slots", type=int, nargs="+", default=[0, 3])
    ap.add_argument("--secs", type=float, default=3.0)
    ap.add_argument("--keys", default="")
    ap.add_argument("--hold", nargs="*", default=[])
    a = ap.parse_args()
    pine = FastPine()
    cols = ["t", "frame"] + [f"{n}{s}" for s in a.slots for n, *_ in FIELDS]
    rows, last = [], None
    t0 = time.perf_counter()
    th = threading.Thread(target=press_thread, args=(a.keys, a.hold, t0), daemon=True)
    th.start()
    n = 0
    while time.perf_counter() - t0 < a.secs:
        v = sample(pine, a.slots)
        n += 1
        t = time.perf_counter() - t0
        if v != last:
            rows.append([round(t, 4), round(t * 60)] + v)
            last = v
    th.join(timeout=1)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"{len(rows)} rows ({n} samples, {n / a.secs:.0f}/s) -> {a.out}")


if __name__ == "__main__":
    main()
