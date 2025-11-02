# Quick Start Guide

Get up and running with Message Extractor in 5 minutes!

## 1. Install

```bash
# Clone the repo
git clone <repository-url>
cd message-extractor

# Install dependencies
pip install -r requirements.txt
```

## 2. Choose Your Platform

### Option A: iMessage (easiest on macOS)

Just run:
```bash
python main.py --extract-imessage
```

⚠️ **Important**: Close the Messages app first!

### Option B: Gmail + Calendar

1. Download credentials from [Google Cloud Console](https://console.cloud.google.com/)
2. Save as `credentials.json` in this directory
3. Run:
```bash
python main.py --extract-gmail --extract-gcal
```
4. Authorize in browser on first run

### Option C: All Platforms

```bash
python main.py --extract-all
```

## 3. View Results

Your data is now in `output/unified/`:
- `unified_timeline.txt` - Read your life chronologically
- `unified_ledger.json` - Full data for analysis

## 4. Explore Cross-Platform Linking

Use the Python API:
```python
from schema import UnifiedLedger
from extractors import iMessageExtractor

# Extract
extractor = iMessageExtractor()
ledger = extractor.extract_all()

# Find all messages with someone
conversations = ledger.get_conversations_with_contact("friend@example.com")
```

## Common Issues

**"Database locked"** → Close Messages app

**"Credentials not found"** → Download from Google Cloud Console

**"Permission denied"** → Grant Full Disk Access to Terminal

## Next Steps

- 📖 Read the [full README](README.md) for features
- 🔧 Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup
- 💻 See [example_usage.py](example_usage.py) for code examples

## Questions?

- Check the README troubleshooting section
- Review SETUP_GUIDE.md for platform-specific help
- Open a GitHub issue

Happy extracting! 🎉

