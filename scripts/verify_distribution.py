"""Select and inspect public source files without reading local runtime configuration."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    "mcp.json",
    "mcp.example.json",
}
SOURCE_TREES = {"app", "docs", "examples", "licenses", "scripts", "skills", "tests"}
WEB_FILES = {"package.json", "package-lock.json", "tsconfig.json", "vite.config.ts", "index.html"}
IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "data",
    "backups",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite", ".db", ".pem", ".key"}
CHECKS = {
    "private-key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "api-key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "bearer-value": r"Bearer\s+[A-Za-z0-9_./+-]{24,}",
    "personal-path": r"/(?:Users|home)/[A-Za-z][^\s\"']*/",
    "private-address": (
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
}
BINARY_ASSETS = {"web/public/covers/earthrise.jpg"}


def selected_files(root=ROOT):
    selected, errors = [], []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            errors.append(f"{relative}: symbolic links cannot be distributed")
            continue
        if not path.is_file():
            continue
        if path.name in (".DS_Store", "SOURCE_MANIFEST.json") or path.suffix in IGNORED_SUFFIXES:
            continue
        if path.name.startswith(".env") and relative.as_posix() != ".env.example":
            continue
        if path.name.endswith((".sqlite-wal", ".sqlite-shm")):
            continue
        name = relative.as_posix()
        allowed = name in ROOT_FILES or relative.parts[0] in SOURCE_TREES
        if relative.parts[0] == "web" and len(relative.parts) > 1:
            allowed = name.removeprefix("web/") in WEB_FILES or relative.parts[1] in {
                "src",
                "public",
                "tests",
            }
        if not allowed:
            errors.append(f"{relative}: file is outside the source allowlist")
            continue
        if path.name.lower().startswith(("dockerfile", "docker-compose")):
            errors.append(f"{relative}: deployment files are excluded")
            continue
        selected.append(path)
    return selected, errors


def verify(root=ROOT):
    paths, errors = selected_files(root)
    manifest = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        content = path.read_bytes()
        manifest.append(
            {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        )
        if name in BINARY_ASSETS:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeError:
            errors.append(f"{name}: unexpected binary file")
            continue
        for label, pattern in CHECKS.items():
            if re.search(pattern, text):
                errors.append(f"{name}: possible {label}; inspect locally")
        if name == ".env.example":
            values = dict(
                line.split("=", 1)
                for line in text.splitlines()
                if "=" in line and not line.startswith("#")
            )
            for key in (
                "AGENT_MODEL",
                "AGENT_BASE_URL",
                "AGENT_API_KEY",
                "AGENT_SEARCH_API_KEY",
                "AGENT_SEARCH_BASE_URL",
            ):
                if values.get(key, "").strip():
                    errors.append(f"{name}: {key} must be blank")
        if name == "mcp.json" and json.loads(text) != {"mcpServers": {}}:
            errors.append("mcp.json: clear runtime connectors before distribution")
    return manifest, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, help="Optional JSON manifest outside the source tree"
    )
    args = parser.parse_args()
    manifest, errors = verify()
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    if args.manifest:
        args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"PASS: {len(manifest)} source files; local secrets and runtime data excluded")


if __name__ == "__main__":
    main()
