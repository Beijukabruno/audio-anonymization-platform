#!/usr/bin/env python3
"""Standalone inference script for voice modification on audio files.

Usage:
  WAV file:   python scripts/apply_voice_mod.py --wav input.wav --params params/mixed_medium_alt.json --out output.wav
  MP3 file:   python scripts/apply_voice_mod.py --mp3 input.mp3 --params params/mixed_medium_alt.json --out output.wav
  Folder batch: python scripts/apply_voice_mod.py --folder no_pii --params params/mixed_medium_alt.json

This applies the anonymize() pipeline from vclm/voice_modification.py using the given params JSON
( e.g., {"resamp": 0.85} ).
"""
import argparse
import json
import os
import sys
import time
import numpy as np
import soundfile as sf
from glob import glob
from pydub import AudioSegment
from io import BytesIO
import logging

# Setup debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - [%(levelname)s] - %(message)s')

# Add the scripts directory to sys.path to import optimize module
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# Import anonymize function from optimize module
from optimize import anonymize


def load_audio_file(input_path):
    """Load audio file in any supported format.
    
    Returns:
        tuple: (audio_data as np.float32, sample_rate)
    """
    logging.info(f"=== LOADING AUDIO FILE ===")
    logging.info(f"Path: {input_path}")
    logging.info(f"File size: {os.path.getsize(input_path) / (1024*1024):.2f} MB")
    
    _, ext = os.path.splitext(input_path)
    ext = ext.lower()
    
    load_start = time.time()
    
    if ext in ['.mp3', '.m4a', '.ogg', '.flac']:
        logging.info(f"Detected format: {ext} - using pydub")
        # Use pydub for formats not natively supported by soundfile
        audio = AudioSegment.from_file(input_path)
        
        logging.info(f"Audio properties from pydub:")
        logging.info(f"  - Duration: {len(audio) / 1000:.2f} seconds")
        logging.info(f"  - Sample rate: {audio.frame_rate} Hz")
        logging.info(f"  - Channels: {audio.channels}")
        logging.info(f"  - Sample width: {audio.sample_width} bytes")
        
        # Convert to numpy array
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        logging.info(f"After np.array conversion - shape: {samples.shape}, dtype: {samples.dtype}")
        
        # Normalize to [-1, 1] range
        if audio.sample_width == 2:  # 16-bit
            samples = samples / 32768.0
            logging.info(f"Normalized for 16-bit audio")
        elif audio.sample_width == 4:  # 32-bit
            samples = samples / 2147483648.0
            logging.info(f"Normalized for 32-bit audio")
        
        # Handle stereo -> mono conversion if needed
        if audio.channels == 2:
            logging.info(f"Stereo detected - converting to mono")
            samples = samples.reshape((-1, 2))
            logging.info(f"Reshaped for stereo processing - shape: {samples.shape}")
            samples = samples.mean(axis=1)
            logging.info(f"After stereo-to-mono conversion - shape: {samples.shape}")
        elif audio.channels > 2:
            logging.warning(f"Audio has {audio.channels} channels - converting first 2 to mono")
            samples = samples.reshape((-1, audio.channels))
            samples = samples[:, :2].mean(axis=1)
            logging.info(f"After multi-channel-to-mono conversion - shape: {samples.shape}")
        
        load_time = time.time() - load_start
        logging.info(f"Load time: {load_time:.2f} seconds")
        logging.info(f"Final audio array shape: {samples.shape}, dtype: {samples.dtype}")
        logging.info(f"Audio value range: [{samples.min():.4f}, {samples.max():.4f}]")
        
        return samples, audio.frame_rate
    else:
        logging.info(f"Detected format: {ext} - using soundfile")
        # Use soundfile for WAV and other formats it supports natively
        x, fs = sf.read(input_path)
        x = x.astype(np.float32)
        
        logging.info(f"Audio properties from soundfile:")
        logging.info(f"  - Duration: {len(x) / fs:.2f} seconds")
        logging.info(f"  - Sample rate: {fs} Hz")
        if x.ndim == 1:
            logging.info(f"  - Channels: 1 (mono)")
        else:
            logging.info(f"  - Channels: {x.shape[1]}")
        
        load_time = time.time() - load_start
        logging.info(f"Load time: {load_time:.2f} seconds")
        logging.info(f"Final audio array shape: {x.shape}, dtype: {x.dtype}")
        logging.info(f"Audio value range: [{x.min():.4f}, {x.max():.4f}]")
        
        return x, fs


def process_audio_file(input_path, output_path, anonymize_fn, params):
    """Process a single audio file with voice modification."""
    logging.info(f"===== PROCESSING AUDIO FILE =====")
    logging.info(f"Input: {input_path}")
    logging.info(f"Output: {output_path}")
    logging.info(f"Parameters: {params}")
    
    # Load audio (supports WAV, MP3, M4A, OGG, FLAC)
    load_start = time.time()
    x, fs = load_audio_file(input_path)
    load_elapsed = time.time() - load_start
    logging.info(f"✓ Audio loading completed in {load_elapsed:.2f}s")
    logging.info(f"  Input shape: {x.shape}, Sample rate: {fs}Hz, Dtype: {x.dtype}")

    # Handle mono vs stereo
    is_stereo = x.ndim == 2 and x.shape[1] > 1
    logging.info(f"Audio is {'stereo' if is_stereo else 'mono'}")
    
    logging.info(f"\n--- Starting voice modification with {len(params)} parameter groups ---")
    
    # Process with anonymize function
    anon_start = time.time()
    try:
        if is_stereo:
            logging.info(f"Processing stereo audio, flattening...")
            flat = x.reshape(-1)
            logging.info(f"  Flattened shape: {flat.shape}")
            logging.info(f"  Calling anonymize() with params: {params}")
            
            anon_call_start = time.time()
            y_flat = anonymize_fn(flat, fs, **params)
            anon_call_elapsed = time.time() - anon_call_start
            logging.info(f"✓ anonymize() completed in {anon_call_elapsed:.2f}s")
            logging.info(f"  Output shape: {np.array(y_flat).shape}")
            
            y = np.array(y_flat, dtype=np.float32).reshape(x.shape)
            logging.info(f"  Reshaped back to: {y.shape}")
        else:
            logging.info(f"Processing mono audio")
            logging.info(f"  Shape: {x.shape}")
            logging.info(f"  Calling anonymize() with params: {params}")
            
            anon_call_start = time.time()
            y = anonymize_fn(x, fs, **params)
            anon_call_elapsed = time.time() - anon_call_start
            logging.info(f"✓ anonymize() completed in {anon_call_elapsed:.2f}s")
            logging.info(f"  Output type: {type(y)}, shape/len: {np.array(y).shape if hasattr(y, 'shape') else len(y)}")
            
            y = np.array(y, dtype=np.float32)
            logging.info(f"  Converted to np.array: {y.shape}")
        
        anon_elapsed = time.time() - anon_start
        logging.info(f"✓ Voice modification completed in {anon_elapsed:.2f}s")
    except Exception as e:
        logging.error(f"✗ Error during voice modification: {e}", exc_info=True)
        raise

    # Write out as 16-bit PCM
    logging.info(f"\n--- Saving audio to {output_path} ---")
    save_start = time.time()
    try:
        logging.info(f"Audio shape before saving: {y.shape}, dtype: {y.dtype}")
        logging.info(f"Audio value range: [{y.min():.4f}, {y.max():.4f}]")
        sf.write(output_path, y, fs, subtype="PCM_16")
        save_elapsed = time.time() - save_start
        logging.info(f"✓ Audio saved successfully in {save_elapsed:.2f}s")
    except Exception as e:
        logging.error(f"✗ Error saving audio: {e}", exc_info=True)
        raise
    
    total_time = time.time() - load_start
    logging.info(f"\n===== PROCESSING COMPLETE =====")
    logging.info(f"Total processing time: {total_time:.2f}s")
    logging.info(f"Breakdown:")
    logging.info(f"  - Loading: {load_elapsed:.2f}s")
    logging.info(f"  - Processing: {anon_elapsed:.2f}s")
    logging.info(f"  - Saving: {save_elapsed:.2f}s")


def main():
    parser = argparse.ArgumentParser(description="Apply voice modification to audio files")
    parser.add_argument("--wav", help="Input WAV path (for single file processing)")
    parser.add_argument("--mp3", help="Input MP3 path (for single file processing)")
    parser.add_argument("--folder", help="Input folder path (for batch processing)")
    parser.add_argument("--params", required=True, help="Path to params JSON (e.g., params/mixed_medium_alt.json)")
    parser.add_argument("--out", help="Output WAV path (only for single file mode)")
    parser.add_argument("--skip-resamp", action="store_true", help="Skip resampling - fastest, no time-stretching")
    parser.add_argument("--librosa-pv", action="store_true", help="Use librosa phase vocoder - fast + pitch-preserving (RECOMMENDED)")
    parser.add_argument("--fast-resamp", action="store_true", help="Use fast scipy resampling - fastest but pitch changes")
    args = parser.parse_args()

    logging.info("========== AUDIO VOICE MODIFICATION SCRIPT ==========")
    logging.info(f"Arguments: --wav={args.wav}, --mp3={args.mp3}, --folder={args.folder}, --params={args.params}, --out={args.out}")
    logging.info(f"Options: --skip-resamp={args.skip_resamp}, --librosa-pv={args.librosa_pv}, --fast-resamp={args.fast_resamp}")

    if not args.wav and not args.mp3 and not args.folder:
        parser.error("Either --wav, --mp3, or --folder must be specified")
    
    num_options = sum([bool(args.skip_resamp), bool(args.librosa_pv), bool(args.fast_resamp)])
    if num_options > 1:
        parser.error("Specify only one of: --skip-resamp, --librosa-pv, or --fast-resamp")

    if not os.path.exists(args.params):
        raise FileNotFoundError(f"Params JSON not found: {args.params}")

    logging.info(f"Loading parameters from: {args.params}")
    params = json.load(open(args.params, "r"))
    logging.info(f"Original parameters: {params}")
    
    # Handle resampling method selection
    if args.skip_resamp:
        if "resamp" in params:
            logging.warning(f"⚠️  Skipping resampling - removing 'resamp' from parameters")
            del params["resamp"]
        logging.info(f"Modified parameters: {params}")
    elif args.librosa_pv:
        logging.info(f"Using librosa phase vocoder for resampling")
        logging.info(f"✓ This preserves pitch and original length while being ~5-10x faster than WSOLA")
        os.environ["USE_LIBROSA_PV"] = "1"
    elif args.fast_resamp:
        logging.info(f"Using fast scipy resampling")
        logging.warning(f"⚠️  WARNING: Pitch will be lowered (downsampling side effect)")
        os.environ["USE_FAST_RESAMP"] = "1"
    else:
        logging.info(f"Using default audiotsm WSOLA resampling (slow)")
        logging.warning(f"⚠️  WARNING: This may take 30+ minutes for long audio files")

    # Single file mode
    if args.wav or args.mp3:
        input_file = args.wav or args.mp3
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        output_path = args.out or "modified.wav"
        logging.info(f"Single file mode: {input_file} -> {output_path}")
        
        process_audio_file(input_file, output_path, anonymize, params)
        
    # Folder batch mode
    else:
        if not os.path.isdir(args.folder):
            raise FileNotFoundError(f"Input folder not found: {args.folder}")
        
        # Create output directory
        output_dir = os.path.join(args.folder, "anonymized")
        os.makedirs(output_dir, exist_ok=True)
        
        # Find all audio files
        audio_extensions = ['*.wav', '*.WAV', '*.mp3', '*.flac', '*.ogg', '*.m4a']
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(glob(os.path.join(args.folder, ext)))
        
        if not audio_files:
            logging.warning(f"No audio files found in {args.folder}")
            return
        
        logging.info(f"Batch mode: Found {len(audio_files)} audio file(s) in {args.folder}")
        logging.info(f"Output directory: {output_dir}")
        
        # Process each file
        for idx, input_path in enumerate(audio_files, 1):
            basename = os.path.basename(input_path)
            name_without_ext = os.path.splitext(basename)[0]
            output_filename = f"{name_without_ext}.wav"
            output_path = os.path.join(output_dir, output_filename)
            
            logging.info(f"\n[{idx}/{len(audio_files)}] Processing: {basename}")
            try:
                process_audio_file(input_path, output_path, anonymize, params)
            except Exception as e:
                logging.error(f"✗ Error processing {basename}: {e}", exc_info=True)
                continue
        
        logging.info(f"\n✓ Batch processing complete!")


if __name__ == "__main__":
    main()
