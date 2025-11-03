#!/usr/bin/env python3
"""
Test Gmail authentication and do a small export
"""
import sys
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractors.gmail_extractor import GmailExtractor

print("=" * 70)
print("Gmail Extractor - Authentication Test")
print("=" * 70)
print()

# Initialize extractor
extractor = GmailExtractor(export_dir="gmail_export_test")
print(f"✓ Extractor initialized")
print(f"  Binary: {extractor.gmail_exporter_path}")
print(f"  Export dir: {extractor.export_dir}")
print()

# Test authentication by listing labels
print("Step 1: Testing authentication (will open browser if needed)...")
print()

cmd = [
    extractor.gmail_exporter_path,
    "labels"
]

print(f"Running: {' '.join(cmd)}")
print("(If this is first run, a browser will open for authentication)")
print()

try:
    result = subprocess.run(cmd, cwd=str(Path(extractor.gmail_exporter_path).parent))
    
    if result.returncode == 0:
        print("\n✓ Authentication successful!")
        print()
        
        # Now do a small test export
        print("Step 2: Running small test export (1 page from SENT folder)...")
        print()
        
        export_cmd = [
            extractor.gmail_exporter_path,
            "export",
            "--save-eml",
            "--eml-dir", str(extractor.eml_dir),
            "--out-file", str(extractor.spreadsheet_path),
            "--no-attachments",
            "--pages-limit", "1",
            "--page-size", "25",
            "SENT"
        ]
        
        print(f"Running: {' '.join(export_cmd)}")
        print()
        
        export_result = subprocess.run(export_cmd, cwd=str(Path(extractor.gmail_exporter_path).parent))
        
        if export_result.returncode == 0:
            print("\n✓ Test export completed!")
            print(f"  EML files: {extractor.eml_dir}")
            print(f"  Spreadsheet: {extractor.spreadsheet_path}")
        else:
            print(f"\n⚠ Export returned code: {export_result.returncode}")
    else:
        print(f"\n⚠ Authentication test returned code: {result.returncode}")
        print("  Make sure you completed authentication in the browser")
        
except KeyboardInterrupt:
    print("\n⚠ Interrupted by user")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

