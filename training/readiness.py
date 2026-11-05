#!/usr/bin/env python3
"""Read-only, CPU-only inventory. Never loads weights or certifies training fit."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from common import parse_json


def command(argv):
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=10, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("training/base-qwen3-14b-4bit"))
    parser.add_argument("--data", type=Path, default=Path("training/prepared"))
    args = parser.parse_args()
    versions = {}
    for package in ("mlx", "mlx-lm", "transformers", "huggingface-hub"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    ram = command(["sysctl", "-n", "hw.memsize"]) if platform.system() == "Darwin" else None
    process_list = command(["/bin/ps", "-axo", "pid=,comm="])
    model_processes = [line.strip() for line in (process_list or "").splitlines()
                       if any(name in line.lower() for name in ("ollama", "whisper", "ffmpeg", "mlx_lm"))]
    config = None
    if (args.base / "config.json").exists():
        config = parse_json((args.base / "config.json").read_text())
    manifest = None
    if (args.data / "manifest.json").exists():
        manifest = parse_json((args.data / "manifest.json").read_text())
    blockers = []
    if ram is None or process_list is None:
        blockers.append("Sandbox hides system/process telemetry; inventory cannot establish an idle GPU or memory headroom")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        blockers.append("The prepared pilot targets an arm64 Mac")
    if not ((3, 11) <= sys.version_info[:2] <= (3, 13)):
        blockers.append("Use an isolated Python 3.11–3.13 environment; inspected release lists these versions")
    if versions["mlx-lm"] != "0.32.2":
        blockers.append("Inspected MLX-LM 0.32.2 training environment is not installed here")
    if not config or config.get("model_type") != "qwen3" or config.get("quantization", {}).get("bits") != 4:
        blockers.append("Pinned local Qwen3 MLX 4-bit snapshot is missing or has a different config")
    if not manifest or manifest.get("fixture_only"):
        blockers.append("Licensed human dataset with source-grouped train/valid/test is missing")
    if model_processes:
        blockers.append("Potential app/model/media workloads exist; parent must explicitly release the GPU first")
    report = {"training_ready": False,
              "reason": "Inventory only. Exact token checks and a monitored 4-step training memory gate remain mandatory",
              "python": platform.python_version(), "machine": platform.machine(), "platform": platform.platform(),
              "ram_gib": round(int(ram) / 2**30, 2) if ram else None,
              "swap": command(["sysctl", "vm.swapusage"]) if ram else None,
              "disk_free_gib": round(shutil.disk_usage(Path.cwd()).free / 2**30, 2),
              "packages": versions, "potential_competing_processes": model_processes,
              "process_telemetry_available": process_list is not None,
              "base_present": config is not None, "dataset_present": manifest is not None,
              "blockers": blockers}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
