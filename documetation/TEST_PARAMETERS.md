# Voice Modification Test Parameters

Created 10 test configurations to evaluate different voice modification approaches.

## Quick Test Command

```bash
# Test all parameters on a single audio file
./test_voice_mods.sh input.wav test_outputs

# Or test individually
python scripts/apply_voice_mod.py --wav input.wav --params params/test_01_vtln_mcadams_clean.json --out output.wav
```

---

## Test Configurations

### test_01_vtln_mcadams_clean.json
```json
{"vtln": 0.15, "mcadams": 0.85}
```
**Purpose**: Natural-sounding combo without artifacts  
**Expected**: Clean audio, moderate pitch shift, warmer timbre  
**Artifacts**: None  
**Processing**: Fast (~2-3 seconds)

---

### test_02_mcadams_only.json
```json
{"mcadams": 0.8}
```
**Purpose**: Safest single-method approach  
**Expected**: Warmer/fuller voice, no timing changes  
**Artifacts**: None  
**Processing**: Medium (~3-4 seconds)

---

### test_03_vtln_modspec_fixed.json
```json
{"vtln": 0.12, "modspec": 0.25}
```
**Purpose**: Fixed version of your original parameters  
**Expected**: Subtle pitch shift, less reverb than your 0.1 modspec  
**Artifacts**: Slight temporal smoothing (much less than before)  
**Processing**: Fast (~2-3 seconds)

---

### test_04_resamp_librosa.json
```json
{"resamp": 0.88}
```
**Purpose**: Resampling with reduced lingering  
**Expected**: Faster playback, higher pitch  
**Artifacts**: Some lingering (less if using USE_LIBROSA_PV=1)  
**Processing**: Slow with WSOLA (~10-15 seconds), fast with librosa PV (~3 seconds)

**Note**: Run with `USE_LIBROSA_PV=1 python scripts/apply_voice_mod.py ...` for better performance

---

### test_05_multi_strong.json
```json
{"vtln": -0.12, "mcadams": 1.15, "clip": 0.6}
```
**Purpose**: Strong anonymization with 3 methods  
**Expected**: Deeper voice with brighter timbre and slight distortion  
**Artifacts**: Harmonic distortion from clipping  
**Processing**: Medium (~4-5 seconds)

---

### test_06_vtln_only.json
```json
{"vtln": 0.15}
```
**Purpose**: Minimal modification, just formant shifting  
**Expected**: Slightly higher-pitched voice  
**Artifacts**: None  
**Processing**: Very fast (~1-2 seconds)

---

### test_07_mcadams_high.json
```json
{"mcadams": 1.2}
```
**Purpose**: Brighter/thinner voice (opposite of test_02)  
**Expected**: More metallic, brighter timbre  
**Artifacts**: None if 1.2 is not too extreme  
**Processing**: Medium (~3-4 seconds)

---

### test_08_vtln_clip.json
```json
{"vtln": 0.13, "clip": 0.65}
```
**Purpose**: Clean pitch shift with subtle distortion  
**Expected**: Higher voice with slight grit  
**Artifacts**: Mild harmonic distortion  
**Processing**: Fast (~2 seconds)

---

### test_09_chorus.json
```json
{"chorus": 0.1}
```
**Purpose**: Multiple-voice effect  
**Expected**: Phasey/flanged sound, like multiple speakers  
**Artifacts**: Slight phasing  
**Processing**: Slow (~5-6 seconds) - runs VTLN 3 times

---

### test_10_balanced.json
```json
{"vtln": 0.08, "mcadams": 0.9, "modspec": 0.28}
```
**Purpose**: Conservative multi-method approach  
**Expected**: Subtle changes across pitch, timbre, and dynamics  
**Artifacts**: Minimal temporal smoothing  
**Processing**: Medium (~4 seconds)

---

## Recommendations by Priority

### If avoiding reverb/echo:
1. **test_02_mcadams_only** - Cleanest
2. **test_01_vtln_mcadams_clean** - Natural combo
3. **test_06_vtln_only** - Fastest

### If avoiding lingering:
1. **test_02_mcadams_only** - No temporal processing
2. **test_08_vtln_clip** - No resampling
3. **test_07_mcadams_high** - Single method

### If maximum anonymization:
1. **test_05_multi_strong** - Three methods combined
2. **test_04_resamp_librosa** - Strong pitch change
3. **test_01_vtln_mcadams_clean** - Good balance

### If fastest processing:
1. **test_06_vtln_only** - Single lightweight method
2. **test_08_vtln_clip** - Two fast methods
3. **test_01_vtln_mcadams_clean** - Two medium methods

---

## Artifact Comparison

| Test | Reverb | Lingering | Distortion | Phasing |
|------|--------|-----------|------------|---------|
| 01   | ❌     | ❌         | ❌          | ❌       |
| 02   | ❌     | ❌         | ❌          | ❌       |
| 03   | 🟡     | 🟡         | ❌          | ❌       |
| 04   | ❌     | ✅         | ❌          | ❌       |
| 05   | ❌     | ❌         | ✅          | ❌       |
| 06   | ❌     | ❌         | ❌          | ❌       |
| 07   | ❌     | ❌         | ❌          | ❌       |
| 08   | ❌     | ❌         | 🟡          | ❌       |
| 09   | ❌     | ❌         | ❌          | ✅       |
| 10   | 🟡     | 🟡         | ❌          | ❌       |

**Legend**: ❌ None | 🟡 Minimal | ✅ Present

---

## After Testing - Feedback Template

For each output, note:
- **Intelligibility**: Can you understand the speech clearly?
- **Naturalness**: Does it sound like a human voice?
- **Anonymization**: Is the original speaker unrecognizable?
- **Artifacts**: Any reverb, echo, distortion, or other issues?
- **Preference**: Rate 1-10

This will help identify the best parameters for your use case.
