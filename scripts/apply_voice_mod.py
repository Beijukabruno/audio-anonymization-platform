#!/usr/bin/env python3
"""Standalone inference script for voice modification on a single WAV file.

Usage:
  python scripts/apply_voice_mod.py --wav input.wav --params params/mixed_medium_alt.json --out output.wav

This applies the anonymize() pipeline from vclm/voice_modification.py using the given params JSON
( e.g., {"resamp": 0.85} ).
"""
import argparse
import json
import os
import sys
import importlib
import numpy as np
import soundfile as sf

# Resolve anonymize() from vclm.voice_modification first; fall back to scripts.optimize

def _resolve_anonymize_fn():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for path in [os.path.join(base, "vclm"), os.path.join(base, "scripts"), base]:
        if path not in sys.path:
            sys.path.insert(0, path)

    candidates = [
        ("vclm.voice_modification", "anonymize"),
        ("scripts.optimize", "anonymize"),
        ("optimize", "anonymize"),
        ("voice_modification", "anonymize"),
    ]
    for mod_name, attr in candidates:
        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, attr, None)
            if callable(fn):
                return fn
        except Exception:
            continue
    raise ImportError("Could not resolve anonymize() function from available modules")


def main():
    parser = argparse.ArgumentParser(description="Apply voice modification to a WAV file")
    parser.add_argument("--wav", required=True, help="Input WAV path")
    parser.add_argument("--params", required=True, help="Path to params JSON (e.g., params/mixed_medium_alt.json)")
    parser.add_argument("--out", default="modified.wav", help="Output WAV path")
    args = parser.parse_args()

    if not os.path.exists(args.wav):
        raise FileNotFoundError(f"Input WAV not found: {args.wav}")
    if not os.path.exists(args.params):
        raise FileNotFoundError(f"Params JSON not found: {args.params}")

    params = json.load(open(args.params, "r"))
    anonymize_fn = _resolve_anonymize_fn()

    # Load audio
    x, fs = sf.read(args.wav)
    # soundfile returns float32/float64 in [-1, 1] for PCM; ensure float32
    x = x.astype(np.float32)

    # Handle mono vs stereo
    is_stereo = x.ndim == 2 and x.shape[1] > 1
    if is_stereo:
        flat = x.reshape(-1)
        y_flat = anonymize_fn(flat, fs, **params)
        y = np.array(y_flat, dtype=np.float32).reshape(x.shape)
    else:
        y = np.array(anonymize_fn(x, fs, **params), dtype=np.float32)

    # Write out as 16-bit PCM
    sf.write(args.out, y, fs, subtype="PCM_16")
    print(f"Saved modified audio to: {args.out}")


if __name__ == "__main__":
    main()
