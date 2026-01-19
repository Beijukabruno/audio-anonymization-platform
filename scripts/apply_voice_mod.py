#!/usr/bin/env python3
"""Standalone inference script for voice modification on audio files.

Usage:
  Single file: python scripts/apply_voice_mod.py --wav input.wav --params params/mixed_medium_alt.json --out output.wav
  Folder batch: python scripts/apply_voice_mod.py --folder no_pii --params params/mixed_medium_alt.json

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
from glob import glob

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


def process_audio_file(input_path, output_path, anonymize_fn, params):
    """Process a single audio file with voice modification."""
    print(f"Processing: {input_path}")
    
    # Load audio
    x, fs = sf.read(input_path)
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
    sf.write(output_path, y, fs, subtype="PCM_16")
    print(f"  → Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Apply voice modification to audio files")
    parser.add_argument("--wav", help="Input WAV path (for single file processing)")
    parser.add_argument("--folder", help="Input folder path (for batch processing)")
    parser.add_argument("--params", required=True, help="Path to params JSON (e.g., params/mixed_medium_alt.json)")
    parser.add_argument("--out", help="Output WAV path (only for single file mode)")
    args = parser.parse_args()

    if not args.wav and not args.folder:
        parser.error("Either --wav or --folder must be specified")
    
    if args.wav and args.folder:
        parser.error("Specify either --wav or --folder, not both")

    if not os.path.exists(args.params):
        raise FileNotFoundError(f"Params JSON not found: {args.params}")

    params = json.load(open(args.params, "r"))
    anonymize_fn = _resolve_anonymize_fn()

    # Single file mode
    if args.wav:
        if not os.path.exists(args.wav):
            raise FileNotFoundError(f"Input WAV not found: {args.wav}")
        
        output_path = args.out or "modified.wav"
        process_audio_file(args.wav, output_path, anonymize_fn, params)
        
    # Folder batch mode
    else:
        if not os.path.isdir(args.folder):
            raise FileNotFoundError(f"Input folder not found: {args.folder}")
        
        # Find all audio files
        audio_extensions = ['*.wav', '*.WAV', '*.mp3', '*.flac', '*.ogg', '*.m4a']
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(glob(os.path.join(args.folder, ext)))
        
        if not audio_files:
            print(f"No audio files found in {args.folder}")
            return
        
        print(f"Found {len(audio_files)} audio file(s) in {args.folder}")
        
        # Process each file
        for input_path in audio_files:
            basename = os.path.basename(input_path)
            name_without_ext = os.path.splitext(basename)[0]
            output_filename = f"anonymisation_{name_without_ext}.wav"
            output_path = os.path.join(args.folder, output_filename)
            
            try:
                process_audio_file(input_path, output_path, anonymize_fn, params)
            except Exception as e:
                print(f"  ✗ Error processing {basename}: {e}")
                continue
        
        print(f"\n✓ Batch processing complete!")


if __name__ == "__main__":
    main()
