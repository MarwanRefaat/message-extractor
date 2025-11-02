# Contributing

Thanks for wanting to contribute! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd message-extractor

# Install
./install.sh

# Run tests
./run.sh --extract-imessage
```

## Code Style

- Use type hints
- Follow PEP 8
- Write docstrings
- Keep it simple!

## Adding a Platform

1. Add extractor to `extractors/` folder
2. Implement `extract_all()` and `export_raw()` methods
3. Add to `extractors/__init__.py`
4. Update `main.py` to include it
5. Update README

## Questions?

Open an issue and ask!

