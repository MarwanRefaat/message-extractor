#!/bin/bash
# One-click install script for message extractor

set -e  # Exit on error

echo "=================================="
echo "Message Extractor - Installation"
echo "=================================="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# Install package in development mode
echo "📦 Installing message extractor..."
pip install -e . -q

echo ""
echo "✅ Installation complete!"
echo ""
echo "To use:"
echo "  source .venv/bin/activate"
echo "  python main.py --help"
echo ""

