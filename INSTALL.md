# Installation Guide

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd message-extractor
```

### 2. Set Up Virtual Environment (Recommended)
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
# .venv\Scripts\activate
```

### 3. Install the Package
```bash
# Install in development mode (recommended for development)
pip install -e .

# Or install production version
pip install .
```

### 4. Install Dependencies Only (Alternative)
```bash
pip install -r requirements.txt
```

### 5. Verify Installation
```bash
# Test imports
python -c "from extractors import iMessageExtractor; print('✓ Success')"

# Run the main script
python main.py --help
```

## Platform-Specific Setup

### macOS (iMessage)
- No additional setup required
- Make sure Messages app has proper permissions

### Gmail / Google Calendar
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API and Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download as `credentials.json` and place in project root

### WhatsApp
- Extract database from device backup
- Provide path to database file during extraction

## Troubleshooting

### Import Errors
If you see `ModuleNotFoundError: No module named 'schema'`:

**Solution 1: Install in development mode**
```bash
pip install -e .
```

**Solution 2: Use virtual environment**
```bash
source .venv/bin/activate  # On macOS/Linux
pip install -e .
```

**Solution 3: Add to PYTHONPATH**
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/message-extractor"
```

### Permission Errors
If you see permission errors during installation:
- Use a virtual environment (recommended)
- Use `--user` flag: `pip install -e . --user`
- Or use `sudo` (not recommended)

### PATH Issues
If scripts aren't found:
```bash
# Add virtual environment bin to PATH
export PATH="${PATH}:${PWD}/.venv/bin"

# Or use full path
./.venv/bin/python main.py
```

## Development Setup

For contributors:

```bash
# Clone repository
git clone <repository-url>
cd message-extractor

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .

# Verify installation
python main.py --help
```

## Production Deployment

For production:

```bash
# Build wheel
python -m build

# Install from wheel
pip install dist/message-extractor-1.0.0-py3-none-any.whl

# Or install directly
pip install .
```

## Uninstall

To uninstall:

```bash
pip uninstall message-extractor
```

## Need Help?

- Check the [README.md](README.md) for usage
- See [QUICKSTART.md](QUICKSTART.md) for quick examples
- Review [SETUP_GUIDE.md](SETUP_GUIDE.md) for platform-specific setup

