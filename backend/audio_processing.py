import os
import sys
import random
import logging
import json
import importlib
from io import BytesIO
from typing import List, Optional

import numpy as np
from pydub import AudioSegment
from pydub.generators import Sine

from .models import Annotation, normalize_annotations

# Configure logging
log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

SUPPORTED_INPUT_FORMATS = {"wav", "mp3", "flac", "ogg", "m4a"}
DISABLE_VOICE_MOD = os.getenv("DISABLE_VOICE_MOD", "0") == "1"


def load_audio(file_path: str) -> AudioSegment:
    ext = os.path.splitext(file_path)[1].lower().strip(".")
    if ext not in SUPPORTED_INPUT_FORMATS:
        raise ValueError(f"Unsupported input format: {ext}")
    return AudioSegment.from_file(file_path)


def save_audio(audio: AudioSegment, out_path: str, format: str = "wav") -> None:
    audio.export(out_path, format=format)


def _list_audio_files(folder: str) -> List[str]:
    files: List[str] = []
    if not os.path.isdir(folder):
        return files
    for name in os.listdir(folder):
        if os.path.splitext(name)[1].lower().strip(".") in {"wav", "mp3", "flac", "ogg", "m4a"}:
            files.append(os.path.join(folder, name))
    return files


def _pick_surrogate_path(surrogates_root: str, gender: str, label: Optional[str], language: str = "english") -> Optional[str]:
    gender = (gender or "male").lower()  # Default to male if missing
    label = (label or "").strip().lower() or None
    language = (language or "english").lower()
    
    log.info(f"_pick_surrogate_path called: gender={gender}, label={label}, language={language}")

    search_order: List[str] = []
    # Prefer language + gender + label specific folders
    if label:
        search_order.append(os.path.join(surrogates_root, language, gender, label))
        search_order.append(os.path.join(surrogates_root, language, label, gender))
        search_order.append(os.path.join(surrogates_root, language, label))
    # Language + gender fallback
    search_order.append(os.path.join(surrogates_root, language, gender))
    # Language-neutral fallbacks (if language-specific not found)
    if label:
        search_order.append(os.path.join(surrogates_root, gender, label))
        search_order.append(os.path.join(surrogates_root, label, gender))
        search_order.append(os.path.join(surrogates_root, label))
    search_order.append(os.path.join(surrogates_root, gender))

    log.info(f"   Search order: {search_order}")

    candidates: List[str] = []
    for folder in search_order:
        folder_files = _list_audio_files(folder)
        if folder_files:
            log.info(f"   Found {len(folder_files)} files in {folder}: {[os.path.basename(f) for f in folder_files]}")
        
        # Filter by label if we're looking for a specific label
        # This handles cases where files are named PERSON.wav, USER_ID.wav etc. in a parent folder
        if label and folder_files:
            label_upper = label.upper()
            # Filter files that match the label in their filename
            filtered = [f for f in folder_files if label_upper in os.path.basename(f).upper()]
            if filtered:
                log.info(f"   Filtered to {len(filtered)} files matching label '{label_upper}': {[os.path.basename(f) for f in filtered]}")
                candidates.extend(filtered)
                break  # Stop at first folder with matching files
            else:
                log.info(f"   No files match label '{label_upper}' in {folder}")
        elif folder_files:
            # No label specified or we're in a label-specific folder already
            log.info(f"   Using all files from {folder}")
            candidates.extend(folder_files)
            break  # Stop at first folder with files
    
    if candidates:
        selected = random.choice(candidates)
        log.info(f"   Selected surrogate: {selected}")
        return selected
    
    log.warning(f"   No surrogate found for gender={gender}, label={label}, language={language}")
    return None


def _load_and_fit_surrogate(surrogates_root: str, gender: str, label: Optional[str], target_ms: int, sample_rate: int, language: str = "english") -> tuple[AudioSegment, str]:
    """Load and fit surrogate to target length. Returns (AudioSegment, file_path)."""
    path = _pick_surrogate_path(surrogates_root, gender, label, language)
    if path and os.path.exists(path):
        seg = AudioSegment.from_file(path)
    else:
        # No fallback: raise error if surrogate not found to ensure only real surrogates are used
        raise ValueError(f"No surrogate found for gender={gender}, label={label}, language={language}. Please add surrogate files to data/surrogates/{language}/{gender}/{label}/")

    # Fit surrogate to target length: trim or pad with silence
    if len(seg) > target_ms:
        seg = seg[:target_ms]
    elif len(seg) < target_ms:
        silence = AudioSegment.silent(duration=target_ms - len(seg), frame_rate=seg.frame_rate)
        seg = seg + silence

    # Match channels/sample rate later via set_frame_rate and set_channels
    return seg, path


def _load_surrogate_direct(surrogates_root: str, gender: str, label: Optional[str], sample_rate: int, language: str = "english") -> tuple[AudioSegment, str]:
    """Load surrogate without modifications. Returns (AudioSegment, file_path)."""
    path = _pick_surrogate_path(surrogates_root, gender, label, language)
    if path and os.path.exists(path):
        seg = AudioSegment.from_file(path)
    else:
        # No fallback: raise error if surrogate not found to ensure only real surrogates are used
        raise ValueError(f"No surrogate found for gender={gender}, label={label}, language={language}. Please add surrogate files to data/surrogates/{language}/{gender}/{label}/")
    # Normalize format to input sample rate/channels later; do not pad/trim/fade.
    return seg, path


def anonymize_with_surrogates(
    input_audio: AudioSegment,
    annotations: List[Annotation],
    surrogates_root: str,
    strategy: str = "direct",  # 'direct' (no trim/pad/fade) or 'fit'
) -> tuple[AudioSegment, List[dict]]:
    """
    Replace annotated time ranges with surrogate clips selected by gender.
    Assumes annotations are in seconds; handles overlap by merging first.
    Returns (processed_audio, surrogate_usage_list)
    """
    log.info(f"anonymize_with_surrogates called with {len(annotations)} annotations")
    for i, ann in enumerate(annotations):
        log.info(f"   Annotation {i+1}: {ann.start_sec:.3f}s-{ann.end_sec:.3f}s, gender={ann.gender}, label={ann.label}, language={ann.language}")
    
    annots = normalize_annotations(annotations)
    if not annots:
        log.info("   No valid annotations after normalization")
        return input_audio, []
    
    log.info(f"   After normalization: {len(annots)} annotations")

    sr = input_audio.frame_rate
    ch = input_audio.channels

    # Build output by stitching original segments + surrogate replacements
    output = AudioSegment.empty()
    cursor_ms = 0
    surrogate_usage = []  # Track surrogate usage for each annotation

    for i, ann in enumerate(annots):
        start_ms = int(ann.start_sec * 1000)
        end_ms = int(ann.end_sec * 1000)
        target_ms = max(0, end_ms - start_ms)
        
        log.info(f"   Processing annotation {i+1}/{len(annots)}: {start_ms}ms-{end_ms}ms (duration={target_ms}ms)")
        log.info(f"      gender={ann.gender}, label={ann.label}, language={ann.language}")

        # Append original up to start
        if start_ms > cursor_ms:
            original_part = input_audio[cursor_ms:start_ms]
            output += original_part
            log.info(f"      Added {len(original_part)}ms of original audio")

        # Append surrogate according to strategy
        if strategy == "fit":
            surrogate, surrogate_path = _load_and_fit_surrogate(surrogates_root, ann.gender, ann.label, target_ms, sr, ann.language)
        else:
            surrogate, surrogate_path = _load_surrogate_direct(surrogates_root, ann.gender, ann.label, sr, ann.language)
        
        surrogate = surrogate.set_frame_rate(sr).set_channels(ch)
        log.info(f"      Loaded surrogate: {len(surrogate)}ms from {surrogate_path}")
        output += surrogate
        
        # Track surrogate usage
        # Generate database-compatible surrogate name: language_gender_label_filename
        # Note: label must be lowercase to match database initialization logic
        filename_without_ext = os.path.splitext(os.path.basename(surrogate_path))[0]
        db_surrogate_name = f"{ann.language}_{ann.gender}_{ann.label.lower()}_{filename_without_ext}"
        
        surrogate_usage.append({
            'start_sec': ann.start_sec,
            'end_sec': ann.end_sec,
            'duration_sec': ann.end_sec - ann.start_sec,
            'gender': ann.gender,
            'label': ann.label,
            'language': ann.language,
            'surrogate_path': surrogate_path,
            'surrogate_name': db_surrogate_name,
            'surrogate_duration_ms': len(surrogate),
            'processing_strategy': strategy
        })

        cursor_ms = end_ms

    # Append the tail of the original
    if cursor_ms < len(input_audio):
        output += input_audio[cursor_ms:]

    return output, surrogate_usage


def anonymize_file(
    input_path: str,
    annotations: List[Annotation],
    surrogates_root: str,
    output_path: Optional[str] = None,
    output_format: str = "wav",
    strategy: str = "direct",
) -> tuple[str, List[dict]]:
    """Anonymize audio file and return (output_path, surrogate_usage_list)."""
    audio = load_audio(input_path)
    output, surrogate_usage = anonymize_with_surrogates(audio, annotations, surrogates_root, strategy=strategy)
    if not output_path:
        base, _ = os.path.splitext(os.path.basename(input_path))
        output_path = os.path.join(os.path.dirname(input_path), f"{base}.anonymized.{output_format}")
    save_audio(output, output_path, format=output_format)
    return output_path, surrogate_usage


def apply_voice_modifications(audio: AudioSegment, params: dict) -> AudioSegment:
    """
    Apply voice modifications (anonymization) to audio using parameters from JSON.
    Converts AudioSegment to numpy array, applies vclm modifications, and converts back.
    
    Args:
        audio: AudioSegment to modify
        params: Dictionary of parameters from params JSON file
    
    Returns:
        Modified AudioSegment
    """
    if not params:
        log.info("No voice modification parameters provided")
        return audio
    
    # Import anonymize function from scripts/optimize.py
    # Try multiple paths to handle different execution contexts (dev, docker, etc.)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    scripts_dir = os.path.join(project_root, "scripts")
    
    log.info(f"Attempting to import from scripts directory: {scripts_dir}")
    
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from optimize import anonymize as anonymize_fn
        log.info("Successfully imported anonymize function from scripts/optimize.py")
    except ImportError as e:
        log.warning(f"Failed to import anonymize function: {e}")
        log.warning(f"Scripts directory: {scripts_dir}, exists: {os.path.exists(scripts_dir)}")
        log.warning(f"sys.path: {sys.path[:5]}")  # Show first 5 entries
        log.warning("Returning original audio without voice modifications.")
        return audio

    try:
        fs = audio.frame_rate
        sample_width_bytes = audio.sample_width or 2
        full_scale = float(2 ** (8 * sample_width_bytes - 1))

        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

        # Normalize to [-1, 1] using actual bit depth
        if audio.channels == 1:
            samples = samples / full_scale
        else:
            samples = samples.reshape((-1, audio.channels)) / full_scale

        log.info(
            "Voice mod input stats: channels=%s, fs=%s, dtype=%s, max=%.4f, min=%.4f",
            audio.channels,
            fs,
            samples.dtype,
            float(np.max(samples)) if samples.size else 0.0,
            float(np.min(samples)) if samples.size else 0.0,
        )

        log.info(f"Applying voice modifications with params: {params}")

        modified = anonymize_fn(samples if audio.channels == 1 else samples.flatten(), fs, **params)

        modified = np.int16(np.clip(modified * (2 ** 15), -32768, 32767))
        output_audio = AudioSegment(
            modified.tobytes(),
            frame_rate=fs,
            sample_width=2,
            channels=audio.channels,
        )

        log.info(
            "Voice mod output stats: channels=%s, fs=%s, max=%d, min=%d",
            output_audio.channels,
            output_audio.frame_rate,
            int(np.max(modified)) if modified.size else 0,
            int(np.min(modified)) if modified.size else 0,
        )

        log.info("Voice modifications applied successfully")
        return output_audio
    except Exception as e:
        log.warning(f"Failed to apply voice modifications: {e}. Returning original audio.")
        return audio


def load_voice_modification_params(params_file: str) -> dict:
    """
    Load voice modification parameters from JSON file.
    
    Args:
        params_file: Path to JSON parameters file
    
    Returns:
        Dictionary of parameters
    """
    if not os.path.exists(params_file):
        log.warning(f"Parameters file not found: {params_file}")
        return {}
    
    try:
        with open(params_file, 'r') as f:
            params = json.load(f)
        log.info(f"Loaded voice modification parameters from {params_file}: {params}")
        return params
    except Exception as e:
        log.error(f"Failed to load parameters from {params_file}: {e}")
        return {}


def anonymize_to_bytes(
    input_bytes: bytes,
    annotations: List[Annotation],
    surrogates_root: str,
    input_format: str = "wav",
    output_format: str = "wav",
    strategy: str = "direct",
    params_file: str = None,
) -> tuple[bytes, List[dict]]:
    """Anonymize audio from bytes and return (output_bytes, surrogate_usage_list)."""
    buf = BytesIO(input_bytes)
    audio = AudioSegment.from_file(buf, format=input_format)
    
    # Step 1: Surrogate replacement
    output, surrogate_usage = anonymize_with_surrogates(audio, annotations, surrogates_root, strategy=strategy)
    
    # Step 2: Apply voice modifications
    # Temporarily disabled for troubleshooting per request.
    if params_file:
        log.info("Voice modification is commented out for troubleshooting; skipping.")
        # params = load_voice_modification_params(params_file)
        # output = apply_voice_modifications(output, params)
    
    out_buf = BytesIO()
    output.export(out_buf, format=output_format)
    return out_buf.getvalue(), surrogate_usage
