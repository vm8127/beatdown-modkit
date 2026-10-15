#!/usr/bin/env python3
"""Rebuild every game asset the Godot remake uses from your own unpacked disc.

    python remake/tools/remake_assets.py ISO remake/godot/assets_ripped

Checks the disc's MD5s (README.md) first and stops on a mismatch, then deletes and rewrites the output folder.
Deterministic: the same disc gives the same files. Standard library only. Never commit the output.

Converters (one module each, run in this order; --only picks some):
  models   character models, rigged -> models/*.glb (conv_models.py)
  anims    fighter animations on the body skeleton -> anims/*.glb (conv_anims.py)
"""
import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))   # bdkit.py, rwkit.py

import conv_anims  # noqa: E402
import conv_models  # noqa: E402

CONVERTERS = {"models": conv_models.convert, "anims": conv_anims.convert}

# README.md, "Before you start": the files the converters read, with their sizes and MD5s
DISC = {
    "SLUS_211.50": (5238064, "b2e575877da83f07d039f888db446697"),
    "XAF/CDATA.XAF": (57597952, "e54e4b47496fad24d933e027b9a0a554"),
    "XAF/DATA.XAF": (195262464, "7f783e16416d582be0880467e80522a7"),
    "XAF/FSCENE.XAF": (15722496, "42ecfc5de6ac1e298638600b833cd40f"),
    "XAF/FSTAGE.XAF": (101451776, "9332532ecc2ef385b402c0ec1f01ce65"),
    "XAF/GRAPH.XAF": (64227328, "75ae7e230fcde017a7b49a0707a6a481"),
    "XAF/SCRIPT.XAF": (8400896, "e9415720cfb21ed8ccc753ec7e880006"),
    "XAF/STAGE.XAF": (46284800, "7e68e323c79246b0ac4c2c0b1c3b75ac"),
}
MARKER = ".remake_assets"   # written into the output folder; only a folder with it (or an empty one) is wiped


def check_disc(iso):
    bad = []
    for rel, (size, md5) in DISC.items():
        p = os.path.join(iso, rel)
        if not os.path.isfile(p):
            bad.append(f"{rel}: missing")
            continue
        if os.path.getsize(p) != size:
            bad.append(f"{rel}: {os.path.getsize(p)} bytes, expected {size}")
            continue
        h = hashlib.md5()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        if h.hexdigest() != md5:
            bad.append(f"{rel}: MD5 {h.hexdigest()}, expected {md5}")
    if bad:
        sys.exit("Not the USA disc (SLUS-21150 v1.02) this tool expects:\n  " + "\n  ".join(bad) +
                 "\nUnpack your disc with: python tools/bdkit.py iso-extract <your .iso> ISO")


def reset_output(out):
    if os.path.isdir(out) and os.listdir(out):
        if not os.path.exists(os.path.join(out, MARKER)):
            sys.exit(f"{out} is not empty and was not made by this tool; refusing to delete it")
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, MARKER), "w") as f:
        f.write("Made by remake/tools/remake_assets.py from your disc. Never commit. Rerun the tool to rebuild.\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("iso", help="your unpacked disc (ISO/)")
    p.add_argument("out", help="output folder, e.g. remake/godot/assets_ripped (deleted and rewritten)")
    p.add_argument("--only", help="comma-separated converters: " + ", ".join(CONVERTERS))
    p.add_argument("--skip-md5", action="store_true", help="check sizes only (faster; for repeated runs)")
    a = p.parse_args()
    if a.skip_md5:
        for rel, (size, _) in DISC.items():
            q = os.path.join(a.iso, rel)
            if not os.path.isfile(q) or os.path.getsize(q) != size:
                sys.exit(f"{rel}: missing or wrong size; run without --skip-md5 for details")
    else:
        check_disc(a.iso)
    reset_output(a.out)
    only = a.only.split(",") if a.only else list(CONVERTERS)
    for name in only:
        print(f"{name}:")
        CONVERTERS[name](a.iso, a.out)
    print(f"done: {a.out}")


if __name__ == "__main__":
    main()
