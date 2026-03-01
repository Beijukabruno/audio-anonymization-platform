#!/bin/bash
# Batch anonymization script for all audios in NO_PII with all test_*.json params
# Output goes to a folder per test, with anonymised_<originalname>.wav naming

NO_PII_DIR="NO_PII"
PARAMS_DIR="params"
SCRIPT="scripts/apply_voice_mod.py"

# Find all wav files in NO_PII (non-recursive)
find "$NO_PII_DIR" -maxdepth 1 -type f -name '*.wav' | while read -r audio_file; do
    audio_base=$(basename "$audio_file")
    audio_name="${audio_base%.wav}"

    # For each test_*.json param file
    for params_file in $PARAMS_DIR/mixed_medium_*.json; do
        if [ -f "$params_file" ]; then
            test_name=$(basename "$params_file" .json)
            out_dir="$test_name"
            mkdir -p "$out_dir"
            out_file="$out_dir/anonymised_${audio_base}"
            echo "Processing $audio_file with $params_file -> $out_file"
            python3 "$SCRIPT" --wav "$audio_file" --params "$params_file" --out "$out_file"
        fi
    done
done

echo "All files processed."
