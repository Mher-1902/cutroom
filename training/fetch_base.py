#!/usr/bin/env python3
"""Future explicit download of a pinned free MLX snapshot. Does not load weights."""
import argparse
import json
from pathlib import Path
import sys

from common import ROOT, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Actually download about 8.32 GB; otherwise refuse")
    args = parser.parse_args()
    require(args.download, "Use --download explicitly after dataset readiness; nothing was fetched")
    destination = ROOT / "base-qwen3-14b-4bit"
    require(not destination.exists(), "Refusing to change an existing base snapshot")
    from huggingface_hub import HfApi, snapshot_download
    repo = "mlx-community/Qwen3-14B-4bit"
    revision = HfApi().model_info(repo).sha
    require(isinstance(revision, str) and len(revision) == 40, "Cannot resolve immutable model revision")
    snapshot_download(repo, revision=revision, local_dir=str(destination), cache_dir=str(ROOT / "hf-cache"),
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "README.md", "LICENSE*"])
    (ROOT / "base-snapshot.json").write_text(json.dumps(
        {"repo": repo, "revision": revision, "path": str(destination), "weights_loaded": False}, indent=2) + "\n")
    print(f"Downloaded {repo}@{revision}; no model was loaded")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ImportError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
