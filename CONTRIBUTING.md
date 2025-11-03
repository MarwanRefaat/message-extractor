# Contributing

Thanks for wanting to contribute!

## Development Setup

```bash
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

1. Add extractor to `src/extractors/` folder
2. Implement `extract_all()` and `export_raw()` methods
3. Add to `src/extractors/__init__.py`
4. Update `scripts/extract.py` to include it
5. Update README

## Questions?

Open an issue and ask!
