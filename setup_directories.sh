#!/bin/bash

# Setup script for Audio Anonymizer surrogate directories

echo "Creating surrogate directory structure..."

# Create language-based directories
mkdir -p data/surrogates/luganda/male/{person,user_id,location}
mkdir -p data/surrogates/luganda/female/{person,user_id,location}
mkdir -p data/surrogates/english/male/{person,user_id,location}
mkdir -p data/surrogates/english/female/{person,user_id,location}

# Create output directory
mkdir -p output

echo "✓ Directory structure created!"
echo ""
echo "Directory tree:"
tree data/surrogates/ -L 3 2>/dev/null || find data/surrogates/ -type d | sed 's|[^/]*/| |g'

echo ""
echo "Next steps:"
echo "1. Place your surrogate audio files in the appropriate directories"
echo "   Example: data/surrogates/luganda/male/person/surrogate1.wav"
echo "2. Supported formats: wav, mp3, flac, ogg, m4a"
echo "3. Run the app: python3 app/gradio_app.py"
