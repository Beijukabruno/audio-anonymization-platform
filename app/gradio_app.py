import os
import logging
from typing import List, Dict, Any
from datetime import datetime

import gradio as gr

# Configure logging
log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ensure project root is on sys.path so sibling package 'backend' can be imported
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models import Annotation
from backend.audio_processing import anonymize_to_bytes

SURROGATES_ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "surrogates")

PREDEFINED_LABELS = ["PERSON", "USER_ID", "LOCATION"]
SUPPORTED_LANGUAGES = ["luganda", "english"]


def process(audio: tuple, table: List[Dict[str, Any]], output_format: str = "wav"):
    if audio is None:
        return None
    # Gradio audio tuple: (sr, np.ndarray) or filepath depending on source
    # Use filepath when provided (microphone yields array)
    input_format = "wav"

    if isinstance(audio, str) and os.path.exists(audio):
        # filepath
        with open(audio, "rb") as f:
            audio_bytes = f.read()
        input_format = os.path.splitext(audio)[1].lstrip(".").lower() or "wav"
    else:
        # (sr, samples) array -> export to wav bytes via pydub
        sr, samples = audio
        from pydub import AudioSegment
        from io import BytesIO
        seg = AudioSegment(
            samples.tobytes(),
            frame_rate=sr,
            sample_width=samples.dtype.itemsize,
            channels=1 if len(samples.shape) == 1 else samples.shape[1],
        )
        buf = BytesIO()
        seg.export(buf, format="wav")
        audio_bytes = buf.getvalue()
        input_format = "wav"

    annotations: List[Annotation] = []
    for r in (table or []):
        try:
            start = float(r.get("start_sec", 0))
            end = float(r.get("end_sec", 0))
            gender = str(r.get("gender", "male")).lower()
            label = r.get("label")
            if end > start:
                annotations.append(Annotation(start_sec=start, end_sec=end, gender=gender, label=label))
        except Exception:
            pass

    if not annotations:
        return None

    out_bytes = anonymize_to_bytes(audio_bytes, annotations, SURROGATES_ROOT, input_format=input_format, output_format=output_format)
    return (output_format, out_bytes)


def extract_path(audio: Any):
    """Return the filepath for the uploaded/recorded audio (empty if none)."""
    if audio is None:
        return ""
    if isinstance(audio, str):
        return audio
    if isinstance(audio, (list, tuple)) and audio:
        # Some gradio backends may return (sr, samples); ignore for filepath mode
        return ""
    return ""


with gr.Blocks(title="Audio Anonymizer (Gradio)") as demo:
    gr.Markdown("# Audio Anonymizer (Gradio)")
    gr.Markdown("Upload or record audio, add annotations with precise time slots, and anonymize PII regions.")
    with gr.Row():
        audio_in = gr.Audio(type="filepath", label="Upload or Record Audio")
    # Waveform section removed as requested
    
    with gr.Row():
        language = gr.Dropdown(
            choices=["Luganda", "English"],
            value="Luganda",
            label="Surrogate Language",
            info="Language of replacement audio",
            scale=1
        )
        output_format = gr.Dropdown(
            choices=["wav", "mp3", "flac"],
            value="wav",
            label="Output Format",
            scale=1
        )

    gr.Markdown("## Add Annotations")
    with gr.Row():
        start_sec = gr.Number(label="Start (sec)", value=None, step=0.001, precision=3, elem_id="start_sec_input")
        end_sec = gr.Number(label="End (sec)", value=None, step=0.001, precision=3, elem_id="end_sec_input")
        gender = gr.Dropdown(
            choices=["male", "female"],
            value="male",
            label="Gender",
        )
        label = gr.Dropdown(
            choices=PREDEFINED_LABELS,
            value="PERSON",
            label="PII Type",
        )

    with gr.Row():
        add_btn = gr.Button("➕ Add Annotation", scale=1)
        status_msg = gr.Textbox(label="Messages", interactive=False, value="")

    gr.Markdown("## Annotations Table")
    table = gr.Dataframe(
        headers=["start_sec", "end_sec", "gender", "label", "language"],
        datatype=["number", "number", "str", "str", "str"],
        row_count=(0, "dynamic"),
        col_count=(5, "fixed"),
        value=[],
        interactive=True,
        label="Edit annotations (delete rows by clearing all fields)",
    )

    anonymize_btn = gr.Button("🎵 Anonymize Audio", variant="primary", size="lg")
    audio_out = gr.Audio(label="Anonymized Output", type="filepath")

    def _normalize_rows(current_table):
        if current_table is None:
            return []
        if isinstance(current_table, list):
            return current_table
        # Try pandas.DataFrame-like
        try:
            values = getattr(current_table, "values", None)
            if values is not None and hasattr(values, "tolist"):
                return values.tolist()
        except Exception:
            pass
        # Try list of dict-like rows
        try:
            return [
                [
                    float(r.get("start_sec", 0)) if hasattr(r, "get") else None,
                    float(r.get("end_sec", 0)) if hasattr(r, "get") else None,
                    (r.get("gender") if hasattr(r, "get") else None),
                    (r.get("label") if hasattr(r, "get") else None),
                ]
                for r in (list(current_table) if not isinstance(current_table, list) else current_table)
            ]
        except Exception:
            return []

    def add_annotation(start, end, gend, lbl, lang, current_table):
        """Add a new row to the annotations table."""
        if start is None or end is None:
            return current_table, "⚠️ Provide both start and end times"
        if end <= start:
            return current_table, "⚠️ End time must be > start time"

        current = _normalize_rows(current_table)
        lang_lower = lang.lower()
        new_row = [float(start), float(end), gend, lbl, lang_lower]
        current.append(new_row)
        return current, f"✓ Added {lbl} ({gend}, {lang}) [{float(start):.3f}s - {float(end):.3f}s]"

    add_btn.click(
        add_annotation,
        inputs=[start_sec, end_sec, gender, label, language, table],
        outputs=[table, status_msg],
    )

    def run(audio, table_data, fmt):
        """Process audio with annotations."""
        log.info("=== Starting anonymization process ===")
        log.info(f"Output format: {fmt}")
        
        if audio is None:
            log.warning("No audio provided")
            return None
        
        if isinstance(audio, str) and os.path.exists(audio):
            with open(audio, "rb") as f:
                audio_bytes = f.read()
            input_format_local = os.path.splitext(audio)[1].lstrip(".").lower() or "wav"
            log.info(f"Loaded audio from file: {audio}, format: {input_format_local}, size: {len(audio_bytes)} bytes")
        else:
            sr, samples = audio
            from pydub import AudioSegment
            from io import BytesIO
            seg = AudioSegment(
                samples.tobytes(),
                frame_rate=sr,
                sample_width=samples.dtype.itemsize,
                channels=1 if len(samples.shape) == 1 else samples.shape[1],
            )
            buf = BytesIO()
            seg.export(buf, format="wav")
            audio_bytes = buf.getvalue()
            input_format_local = "wav"
            log.info(f"Converted audio from array: sr={sr}, size={len(audio_bytes)} bytes")

        log.info(f"Table data received: {table_data}")
        rows = _normalize_rows(table_data)
        log.info(f"Normalized to {len(rows)} rows")
        
        annotations_local: List[Annotation] = []
        for idx, r in enumerate(rows):
            try:
                start = float(r[0]) if len(r) > 0 and r[0] is not None else 0.0
                end = float(r[1]) if len(r) > 1 and r[1] is not None else 0.0
                gender = str(r[2]).lower() if len(r) > 2 and r[2] is not None else "male"
                label = str(r[3]).upper().strip() if len(r) > 3 and r[3] is not None else "PERSON"
                lang = str(r[4]).lower() if len(r) > 4 and r[4] is not None else "luganda"
                
                log.info(f"   Row {idx+1}: start={start}, end={end}, gender={gender}, label={label}, language={lang}")
                
                if label not in PREDEFINED_LABELS:
                    log.warning(f"   Label '{label}' not in predefined labels, defaulting to 'PERSON'")
                    label = "PERSON"
                if end > start:
                    ann = Annotation(start_sec=start, end_sec=end, gender=gender, label=label, language=lang)
                    annotations_local.append(ann)
                    log.info(f"   Added annotation: {ann}")
                else:
                    log.warning(f"   Skipped row {idx+1}: end ({end}) <= start ({start})")
            except Exception as e:
                log.error(f"   Error processing row {idx+1}: {e}")
                pass

        if not annotations_local:
            log.warning("No valid annotations to process")
            return None

        log.info(f"Calling anonymize_to_bytes with {len(annotations_local)} annotations")
        
        # Load default voice modification parameters
        default_params_path = os.path.join(os.path.dirname(__file__), "..", "params", "mixed_medium_alt.json")

        out_bytes_local = anonymize_to_bytes(
            audio_bytes,
            annotations_local,
            SURROGATES_ROOT,
            input_format=input_format_local,
            output_format=fmt,
            strategy="direct",
            params_file=default_params_path,
        )
        
        log.info(f"Anonymization complete, output size: {len(out_bytes_local)} bytes")
        
        # Save to output directory with unique timestamp
        output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        out_name = f"anonymized_{timestamp}.{fmt}"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "wb") as f:
            f.write(out_bytes_local)
        log.info(f"Saved anonymized audio to: {out_path}")
        log.info("=== Anonymization process complete ===")
        return out_path

    anonymize_btn.click(
        run,
        inputs=[audio_in, table, output_format],
        outputs=audio_out,
    )

    gr.Markdown("""
    ### Tips
    - Use precise time ranges for better anonymization
    - Select the correct gender and label for each region
    - Output files are saved in the `output/` directory
    """)

if __name__ == "__main__":
    demo.launch()
