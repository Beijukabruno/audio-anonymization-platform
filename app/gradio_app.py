import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from io import BytesIO
import uuid

import gradio as gr
import pandas as pd

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

# Try to import database functionality (graceful degradation if DB not available)
try:
    from backend.database import init_db, ProcessingStatus
    from backend.db_logger import ProcessingJobLogger, init_surrogate_voices, get_db_session
    DB_ENABLED = True
    log.info("Database support enabled")
except Exception as e:
    log.warning(f"Database support disabled: {e}")
    DB_ENABLED = False
    ProcessingJobLogger = None

SURROGATES_ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "surrogates")

PREDEFINED_LABELS = ["PERSON", "USER_ID", "LOCATION"]
SUPPORTED_LANGUAGES = ["english"]

# Generate a session ID for this instance
SESSION_ID = str(uuid.uuid4())


# Database query functions for history and statistics
def query_processing_history(
    status_filter: str = "all",
    days_back: int = 7,
    limit: int = 100
) -> pd.DataFrame:
    """Query processing history from database."""
    if not DB_ENABLED:
        return pd.DataFrame({"message": ["Database not available"]})
    
    try:
        from backend.database import ProcessingJob
        db = get_db_session()
        
        # Base query
        query = db.query(ProcessingJob)
        
        # Filter by status
        if status_filter != "all":
            status_map = {
                "completed": ProcessingStatus.COMPLETED,
                "failed": ProcessingStatus.FAILED,
                "processing": ProcessingStatus.PROCESSING,
            }
            if status_filter in status_map:
                query = query.filter(ProcessingJob.status == status_map[status_filter])
        
        # Filter by date range
        if days_back > 0:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            query = query.filter(ProcessingJob.created_at >= cutoff_date)
        
        # Order and limit
        query = query.order_by(ProcessingJob.created_at.desc()).limit(limit)
        
        jobs = query.all()
        db.close()
        
        if not jobs:
            return pd.DataFrame({"message": ["No processing jobs found"]})
        
        # Convert to DataFrame
        data = []
        for job in jobs:
            data.append({
                "ID": job.id,
                "Filename": job.original_filename,
                "Output File": job.output_filename or "",
                "Status": job.status.value,
                "Method": job.processing_method.value,
                "Created": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else "",
                "Duration (s)": f"{job.processing_duration_seconds:.2f}" if job.processing_duration_seconds else "",
                "Size (KB)": f"{job.original_file_size/1024:.1f}" if job.original_file_size else "",
                "Gender": job.gender_detected.value if job.gender_detected else "",
                "Language": job.language_detected or "",
                "Surrogate": job.surrogate_voice_used or "",
                "Error": job.error_message or "",
            })
        
        return pd.DataFrame(data)
    
    except Exception as e:
        log.error(f"Failed to query processing history: {e}")
        return pd.DataFrame({"error": [str(e)]})


def get_statistics_summary() -> Dict[str, Any]:
    """Get summary statistics from database."""
    if not DB_ENABLED:
        return {"message": "Database not available"}
    
    try:
        from backend.database import ProcessingJob
        db = get_db_session()
        
        # Overall stats
        total_jobs = db.query(ProcessingJob).count()
        completed = db.query(ProcessingJob).filter(ProcessingJob.status == ProcessingStatus.COMPLETED).count()
        failed = db.query(ProcessingJob).filter(ProcessingJob.status == ProcessingStatus.FAILED).count()
        
        # Recent stats (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_jobs = db.query(ProcessingJob).filter(ProcessingJob.created_at >= week_ago).count()
        
        # Average processing time
        avg_time_result = db.query(ProcessingJob.processing_duration_seconds).filter(
            ProcessingJob.processing_duration_seconds.isnot(None)
        ).all()
        avg_time = sum(t[0] for t in avg_time_result) / len(avg_time_result) if avg_time_result else 0
        
        db.close()
        
        success_rate = (completed / total_jobs * 100) if total_jobs > 0 else 0
        
        return {
            "Total Jobs": total_jobs,
            "Completed": completed,
            "Failed": failed,
            "Success Rate": f"{success_rate:.1f}%",
            "Recent (7 days)": recent_jobs,
            "Avg Processing Time": f"{avg_time:.2f}s",
        }
    
    except Exception as e:
        log.error(f"Failed to get statistics: {e}")
        return {"error": str(e)}


def export_to_csv() -> str:
    """Export processing history to CSV file."""
    if not DB_ENABLED:
        return None
    
    try:
        df = query_processing_history(status_filter="all", days_back=30, limit=1000)
        
        if df.empty or "message" in df.columns or "error" in df.columns:
            log.warning("No data to export")
            return None
        
        # Save to output directory
        output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(output_dir, f"processing_history_{timestamp}.csv")
        
        df.to_csv(csv_path, index=False)
        log.info(f"Exported {len(df)} records to {csv_path}")
        
        return csv_path
    
    except Exception as e:
        log.error(f"Failed to export CSV: {e}")
        return None


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

    out_bytes, surrogate_usage = anonymize_to_bytes(audio_bytes, annotations, SURROGATES_ROOT, input_format=input_format, output_format=output_format)
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
        add_btn = gr.Button("Add Annotation", scale=1)
        status_msg = gr.Textbox(label="Messages", interactive=False, value="")

    gr.Markdown("## Annotations Table")
    table = gr.Dataframe(
        headers=["start_sec", "end_sec", "gender", "label"],
        datatype=["number", "number", "str", "str"],
        row_count=(0, "dynamic"),
        col_count=(4, "fixed"),
        value=[],
        interactive=True,
        label="Edit annotations (delete rows by clearing all fields)",
    )

    anonymize_btn = gr.Button("Anonymize Audio", variant="primary", size="lg")
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

    def add_annotation(start, end, gend, lbl, current_table):
        """Add a new row to the annotations table."""
        if start is None or end is None:
            return current_table, "Provide both start and end times"
        if end <= start:
            return current_table, "End time must be > start time"

        current = _normalize_rows(current_table)
        # Language is always english (hardcoded)
        new_row = [float(start), float(end), gend, lbl]
        current.append(new_row)
        return current, f"Added {lbl} ({gend}) [{float(start):.3f}s - {float(end):.3f}s]"

    add_btn.click(
        add_annotation,
        inputs=[start_sec, end_sec, gender, label, table],
        outputs=[table, status_msg],
    )

    def run(audio, table_data, fmt):
        """Process audio with annotations (with database logging)."""
        log.info("=== Starting anonymization process ===")
        log.info(f"Output format: {fmt}")
        
        if audio is None:
            log.warning("No audio provided")
            return None
        
        # Determine input filename
        if isinstance(audio, str) and os.path.exists(audio):
            input_filename = os.path.basename(audio)
            with open(audio, "rb") as f:
                audio_bytes = f.read()
            input_format_local = os.path.splitext(audio)[1].lstrip(".").lower() or "wav"
            log.info(f"Loaded audio from file: {audio}, format: {input_format_local}, size: {len(audio_bytes)} bytes")
        else:
            input_filename = f"recorded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            sr, samples = audio
            from pydub import AudioSegment
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
        detected_gender = None
        detected_language = None
        
        for idx, r in enumerate(rows):
            try:
                start = float(r[0]) if len(r) > 0 and r[0] is not None else 0.0
                end = float(r[1]) if len(r) > 1 and r[1] is not None else 0.0
                gender = str(r[2]).lower() if len(r) > 2 and r[2] is not None else "male"
                label = str(r[3]).upper().strip() if len(r) > 3 and r[3] is not None else "PERSON"
                # Language is always english (hardcoded)
                lang = "english"
                
                # Capture first gender/language for DB logging
                if detected_gender is None:
                    detected_gender = gender
                if detected_language is None:
                    detected_language = lang
                
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

        def _process_and_save(db_logger=None):
            log.info(f"Calling anonymize_to_bytes with {len(annotations_local)} annotations")
            default_params_path = os.path.join(os.path.dirname(__file__), "..", "params", "mixed_medium_alt.json")

            out_bytes_local, surrogate_usage = anonymize_to_bytes(
                audio_bytes,
                annotations_local,
                SURROGATES_ROOT,
                input_format=input_format_local,
                output_format=fmt,
                strategy="direct",
                params_file=default_params_path,
            )

            log.info(f"Anonymization complete, output size: {len(out_bytes_local)} bytes")
            log.info(f"Surrogate usage: {len(surrogate_usage)} annotations processed")

            # Save to output directory with unique timestamp
            output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            out_name = f"anonymized_{timestamp}.{fmt}"
            out_path = os.path.join(output_dir, out_name)
            with open(out_path, "wb") as f:
                f.write(out_bytes_local)
            log.info(f"Saved anonymized audio to: {out_path}")

            # Log output metadata and surrogate usage
            if db_logger and db_logger.job:
                from pydub import AudioSegment as AS
                out_audio = AS.from_file(BytesIO(out_bytes_local), format=fmt)
                db_logger.update_output_metadata(
                    filename=out_name,
                    file_size=len(out_bytes_local),
                    duration=len(out_audio) / 1000.0,
                )
                
                # Log each annotation's surrogate usage
                db_logger.log_annotation_surrogates(surrogate_usage)

            return out_path

        if DB_ENABLED and ProcessingJobLogger:
            try:
                with ProcessingJobLogger(
                    original_filename=input_filename,
                    processing_method="both",
                    parameters={"format": fmt, "strategy": "direct", "annotations": len(annotations_local)},
                    user_session_id=SESSION_ID,
                ) as db_logger:
                    if db_logger and db_logger.job:
                        from pydub import AudioSegment as AS
                        temp_audio = AS.from_file(BytesIO(audio_bytes), format=input_format_local)
                        db_logger.update_input_metadata(
                            file_size=len(audio_bytes),
                            duration=len(temp_audio) / 1000.0,
                            sample_rate=temp_audio.frame_rate,
                            channels=temp_audio.channels,
                        )
                        db_logger.update_detection_metadata(
                            gender=detected_gender,
                            language=detected_language,
                        )
                    return _process_and_save(db_logger)
            except Exception as e:
                log.error(f"Anonymization failed (db logging): {e}")
                raise
        else:
            # No DB logging
            return _process_and_save(None)

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

with gr.Blocks(title="Logs & Stats") as logs_tab:
    gr.Markdown("# Logs & Stats")
    gr.Markdown("Minimal view: recent jobs, export CSV, and quick stats.")

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Row():
                status_filter = gr.Dropdown(
                    choices=["all", "completed", "failed", "processing"],
                    value="all",
                    label="Status",
                )
                days_filter = gr.Number(label="Days", value=7, minimum=1, maximum=365)
                limit_filter = gr.Number(label="Limit", value=100, minimum=10, maximum=1000)
                refresh_btn = gr.Button("Refresh", variant="secondary")
                export_btn = gr.Button("Export CSV", variant="primary")

            history_table = gr.Dataframe(
                label="Processing Jobs",
                interactive=False,
                wrap=True,
            )

            export_status = gr.Textbox(label="Export Status", interactive=False)
            download_file = gr.File(label="Download CSV", interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("### Quick Stats")
            stats_json = gr.JSON(label="Stats Summary")
            stats_text = gr.Markdown()
            refresh_stats_btn = gr.Button("Refresh Stats", variant="secondary")

    def load_history(status, days, limit):
        df = query_processing_history(status, int(days), int(limit))
        return df

    def export_history():
        csv_path = export_to_csv()
        if csv_path:
            return f"Exported: {os.path.basename(csv_path)}", csv_path
        else:
            return "Export failed or no data", None

    def load_stats():
        stats = get_statistics_summary()
        if "error" in stats or "message" in stats:
            markdown = f"**{stats.get('error', stats.get('message', 'N/A'))}**"
        else:
            markdown = (
                f"- **Total Jobs**: {stats.get('Total Jobs', 0)}\n"
                f"- **Success Rate**: {stats.get('Success Rate', '0%')}\n"
                f"- **Recent (7d)**: {stats.get('Recent (7 days)', 0)}\n"
                f"- **Avg Time**: {stats.get('Avg Processing Time', 'N/A')}"
            )
        return stats, markdown

    refresh_btn.click(
        load_history,
        inputs=[status_filter, days_filter, limit_filter],
        outputs=history_table,
    )

    export_btn.click(
        export_history,
        inputs=[],
        outputs=[export_status, download_file],
    )

    refresh_stats_btn.click(
        load_stats,
        inputs=[],
        outputs=[stats_json, stats_text],
    )

    # Initial load
    logs_tab.load(
        load_history,
        inputs=[status_filter, days_filter, limit_filter],
        outputs=history_table,
    )
    logs_tab.load(
        load_stats,
        inputs=[],
        outputs=[stats_json, stats_text],
    )

# Combine minimal tabs
with gr.TabbedInterface(
    [demo, logs_tab],
    ["Anonymize", "Logs"],
    title="Audio Anonymization Platform"
) as app:
    pass

if __name__ == "__main__":
    # Initialize database on startup
    if DB_ENABLED:
        try:
            init_db()
            init_surrogate_voices(SURROGATES_ROOT)
            log.info("Database initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize database: {e}")
    
    app.launch()
