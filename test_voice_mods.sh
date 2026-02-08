#!/bin/bash
# Test script to run all voice modification parameter files
# Usage: ./test_voice_mods.sh input.wav output_dir

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_audio.wav> <output_directory>"
    echo "Example: ./test_voice_mods.sh input.wav test_outputs"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_DIR="$2"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Testing Voice Modification Parameters"
echo "=========================================="
echo "Input: $INPUT_FILE"
echo "Output: $OUTPUT_DIR"
echo ""

# Test each parameter file
for params_file in params/test_*.json; do
    if [ -f "$params_file" ]; then
        # Extract test name from filename
        test_name=$(basename "$params_file" .json)
        output_file="$OUTPUT_DIR/${test_name}.wav"
        
        echo "----------------------------------------"
        echo "Testing: $test_name"
        echo "Params: $params_file"
        echo "Output: $output_file"
        echo "----------------------------------------"
        
        # Run voice modification
        python3 scripts/apply_voice_mod.py \
            --wav "$INPUT_FILE" \
            --params "$params_file" \
            --out "$output_file"
        
        if [ $? -eq 0 ]; then
            echo "✓ Success: $test_name"
        else
            echo "✗ Failed: $test_name"
        fi
        echo ""
    fi
done

# Special test for librosa phase vocoder (test_04)
echo "----------------------------------------"
echo "Testing: test_04_resamp_librosa (with USE_LIBROSA_PV=1)"
echo "----------------------------------------"
USE_LIBROSA_PV=1 python3 scripts/apply_voice_mod.py \
    --wav "$INPUT_FILE" \
    --params params/test_04_resamp_librosa.json \
    --out "$OUTPUT_DIR/test_04_resamp_librosa_pv.wav"

if [ $? -eq 0 ]; then
    echo "✓ Success: test_04_resamp_librosa with phase vocoder"
else
    echo "✗ Failed: test_04_resamp_librosa with phase vocoder"
fi

echo ""
echo "=========================================="
echo "All tests completed!"
echo "Listen to files in: $OUTPUT_DIR"
echo "=========================================="
