# Voice Modification Script - Quick Usage Guide

## TL;DR - Quick Start

**For 38s audio processing:**
- ⏱ **0.67 seconds** with `--fast-resamp` RECOMMENDED
- ⏱ **0.12 seconds** with `--skip-resamp`
- ⏱ **30+ MINUTES** with default (AVOID)

---

## Examples

### Example 1: Fast Resampling (Recommended)
```bash
python3 scripts/apply_voice_mod.py \
  --mp3 "WhatsApp Audio 2026-01-13 at 11.39.55 AM.mp3" \
  --params params/mixed_medium_alt.json \
  --out output.wav \
  --fast-resamp
```

**Output:**
```
 Audio loading completed in 0.10s
 Voice modification completed in 0.56s
 Audio saved successfully in 0.02s
Total processing time: 0.67s
```

---

### Example 2: Skip Resampling (Fastest)
```bash
python3 scripts/apply_voice_mod.py \
  --mp3 "audio.mp3" \
  --params params/mixed_medium_alt.json \
  --out output.wav \
  --skip-resamp
```

**Use when:**
- You don't need the resampling effect
- Maximum speed is critical
- Other voice modifications are needed (vtln, modspec_smoothing, etc.)

---

### Example 3: Batch Processing with Fast Resampling
```bash
python3 scripts/apply_voice_mod.py \
  --folder data/audio_files \
  --params params/mixed_medium_alt.json \
  --fast-resamp
```

**Output locations:** `data/audio_files/anonymized/*.wav`

---

### Example 4: WAV Input
```bash
python3 scripts/apply_voice_mod.py \
  --wav audio.wav \
  --params params/mixed_medium_alt.json \
  --out output.wav \
  --fast-resamp
```

---

## Command-Line Arguments

```
usage: apply_voice_mod.py [-h] [--wav WAV] [--mp3 MP3] [--folder FOLDER] 
                          --params PARAMS [--out OUT] 
                          [--skip-resamp] [--fast-resamp]

Apply voice modification to audio files

optional arguments:
  -h, --help            Show this help message
  
  --wav WAV             Input WAV file path
  --mp3 MP3             Input MP3 file path
  --folder FOLDER       Input folder with multiple audio files
  
  --params PARAMS       Path to parameters JSON file (REQUIRED)
                        Example: params/mixed_medium_alt.json
  
  --out OUT             Output WAV file path (default: modified.wav)
  
  --skip-resamp         Skip resampling (fastest, but no resampling effect)
  --fast-resamp         Use fast scipy resampling (recommended for speed)
```

---

## Supported Audio Formats

### Input
- MP3 (via ffmpeg)
- WAV
- FLAC
- OGG
- M4A

### Output
- WAV (16-bit PCM, same sample rate as input)

---

## Performance Benchmarks

**Test Audio: 38.42 seconds @ 48kHz**

| Mode | Command | Time | Notes |
|------|---------|------|-------|
| Skip | `--skip-resamp` | **0.12s** | No resampling |
| Fast | `--fast-resamp` | **0.67s** |  Recommended |
| Default | (no flags) | **Hangs** | Don't use |

---

## Parameters File Format

Example: `params/mixed_medium_alt.json`

```json
{
  "resamp": 0.85
}
```

All parameters are cascaded together. Available parameters:
- `resamp`: Resampling factor (0.85 = 85% speed)
- `vtln`: Vocal tract length normalization coefficient
- `mcadams`: McAdams coefficient for spectrum modification
- `modspec`: Modulation spectrum smoothing
- `clip`: Clipping threshold (0-1)
- `chorus`: Chorus effect coefficient

Example with multiple effects:
```json
{
  "vtln": 0.05,
  "resamp": 0.85,
  "mcadams": 0.8,
  "clip": 0.5
}
```

---

## Typical Use Cases

### 1. WhatsApp Audio Anonymization
```bash
python3 scripts/apply_voice_mod.py \
  --mp3 "WhatsApp Audio 2026-01-13 at 11.39.55 AM.mp3" \
  --params params/mixed_medium_alt.json \
  --out anonymized_audio.wav \
  --fast-resamp
```

### 2. Batch Process Directory
```bash
python3 scripts/apply_voice_mod.py \
  --folder recordings/ \
  --params params/mixed_medium_alt.json \
  --fast-resamp
```

Output: `recordings/anonymized/*.wav`

### 3. Quick Audio Check (No Resampling)
```bash
python3 scripts/apply_voice_mod.py \
  --mp3 "test.mp3" \
  --params params/sample.json \
  --out test_out.wav \
  --skip-resamp
```

---

## Troubleshooting

### Q: Script still hangs?
**A:** Make sure you're using one of the fast options:
```bash
# DO THIS
python3 scripts/apply_voice_mod.py ... --fast-resamp

# ❌ NOT THIS (will hang)
python3 scripts/apply_voice_mod.py ...  # no flags
```

### Q: What does "resamp: 0.85" do?
**A:** Slows down audio playback to 85% speed (pitch down). With `--fast-resamp`, this runs in 0.56s instead of 30+ minutes.

### Q: Can I mix `--skip-resamp` and `--fast-resamp`?
**A:** No, pick one:
- Use `--skip-resamp` if parameters include resamp but you want no resampling
- Use `--fast-resamp` if you want to keep resampling but speed it up

### Q: Output audio quality is bad?
**A:** Try default WSOLA for higher quality (but much slower):
```bash
# Remove both flags to use original WSOLA method
# Warning: Will take 30+ minutes for 38s audio
python3 scripts/apply_voice_mod.py --mp3 "audio.mp3" ...
```

---

## Related Files

- `scripts/apply_voice_mod.py` - Main script
- `scripts/voice_modification.py` - Audio processing modules
- `scripts/optimize.py` - Parameter management and cascading
- `params/mixed_medium_alt.json` - Example parameters
- `DEBUG_REPORT.md` - Detailed analysis of the bottleneck

---

## Credits

Comprehensive debug logging and performance optimization by GitHub Copilot.

Issue tracking: WSOLA bottleneck in audiotsm library (known limitation for long audio files).
