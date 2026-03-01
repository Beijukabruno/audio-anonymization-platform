# Audio Anonymizer (Streamlit)

A minimal prototype to anonymize audio segments via manual annotations in a Streamlit UI. Users upload an audio file, enter time slots (start/end in seconds) and gender metadata, and the backend replaces those segments with predetermined surrogate clips.

## Concept

Frontend (Streamlit)
- Audio player
- Annotation table (start, end, gender, label)
- Submit to process

Backend (Python)
- Store annotations (JSON-like rows)
- Audio slicing and stitching (pydub)
- Surrogate selection by gender (`data/surrogates/<male|female|neutral>`)
- Export anonymized audio

## Getting Started

### Prerequisites
- Python 3.9+
- `ffmpeg` recommended if you need to read/write mp3/m4a/ogg (for Linux: `sudo apt install ffmpeg`). WAV works without ffmpeg.

### Setup
```bash
# create and activate venv (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# create surrogate folders and add your clips
mkdir -p data/surrogates/male data/surrogates/female data/surrogates/neutral
# Place .wav/.mp3 etc. clips inside these folders
```

### Run the Streamlit app
```bash
streamlit run app/streamlit_app.py
```

Upload an audio file, add annotations (rows with start/end/gender), click "Anonymize". The app will produce an anonymized output and let you listen/download.

### Run the Gradio app
```bash
python app/gradio_app.py
```
In the Gradio UI, upload or record audio, edit the annotations table, and click Anonymize to preview the output.

## How it Works
- Annotations are normalized (sorted, overlapping merged).
- Predefined label options: `PERSON` (names), `USER_ID` (phone/ID numbers), `LOCATION` (places).
- Surrogate selection uses `gender` and optional `label` (folders like `data/surrogates/<gender>/<label>` are supported; falls back to `gender` or `neutral`).
- Two replacement strategies:
  - Direct swap: inserts the full surrogate clip without trimming/padding/fades. Output duration may change.
  - Fit to duration: trims/pads the surrogate to exactly match the annotated slot (no audible gaps), with gentle fade-in/out.
- The result is stitched as: original up to the start → surrogate → remaining original.

## Extending
- Waveform UI: integrate Wavesurfer.js via `streamlit-components` for visual selection.
- Gradio: mirror the Streamlit flow with `gr.Dataframe` + `gr.Audio` for an alternative UI.
- Metadata: add more labels/types to guide surrogate selection.
- DSP: replace tone fallback with TTS/voice conversion to match duration/gender.

## File Structure
```
backend/
  models.py            # Annotation dataclass and normalization
  audio_processing.py  # Slice/replace/stitch functions (pydub)
app/
  streamlit_app.py     # Streamlit UI
  gradio_app.py        # Gradio UI
data/surrogates/
  male/                # Put male surrogate clips here
  female/              # Put female surrogate clips here
  neutral/             # Optional neutral surrogate clips
uploads/               # Saved uploads
output/                # Anonymized outputs
requirements.txt
README.md
```

## Notes
- Ensure annotations do not overlap excessively; basic merging is applied.
- For consistent output, supply surrogate clips with similar loudness.
- MP3 export requires ffmpeg; otherwise use WAV.
- Direct swap will change total duration if surrogate length differs; choose Fit mode to keep duration unchanged.

## Inter-Operator Agreement (IOA) Database

To support fine-grained inter-operator agreement analysis, a new dedicated SQLite database (`inter_operator_agreement.db`) is used. This database is separate from the main processing database to avoid mixing annotation and processing data.

### What was added
- A new database schema (see `backend/ioa_models.py`) with tables for:
  - Operators (names/IDs)
  - Entities (audio files)
  - Annotations (operator, entity, start/stop timestamps, label, comments)
- The Gradio UI now requires an operator name for each annotation session.
- All annotation details (including operator name, audio file, timestamps, and labels) are logged to the IOA database for every session.
- Analysis scripts can query this database to compare annotations across operators and generate agreement reports.

### Deployment
- No changes to Docker Compose are required for SQLite (the default). The database file is created automatically in the project root.
- If you wish to use a different database backend, update `backend/ioa_database.py` accordingly and add the service to your `docker-compose.yml`.

### Usage
- On startup, the platform initializes both the main and IOA databases.
- When annotating audio, enter your operator name in the UI. All annotations will be saved for agreement analysis.
- Use the provided analysis script (`scripts/inter_operator_agreement.py`) to extract and compare annotation data.

For more details, see `backend/ioa_models.py` and `backend/ioa_database.py`.
