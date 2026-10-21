"""Build an inspected source ZIP without credentials, runtime data or dependencies."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from verify_distribution import ROOT, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New ZIP path outside this project")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error("Choose a new output file outside the project")
    manifest, errors = verify()
    if errors:
        parser.error("Source validation failed: " + "; ".join(errors))
    manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in manifest:
                content = (ROOT / item["path"]).read_bytes()
                if hashlib.sha256(content).hexdigest() != item["sha256"]:
                    raise ValueError("Source changed while packaging; run again")
                archive.writestr("agent-framework/" + item["path"], content)
            archive.writestr("agent-framework/SOURCE_MANIFEST.json", manifest_content)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive integrity check failed")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print(f"Created {output.name}: {len(manifest)} inspected source files")


if __name__ == "__main__":
    main()
