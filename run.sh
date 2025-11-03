#!/bin/bash
# Run message extractor

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run main script
python scripts/extract.py "$@"

