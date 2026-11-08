"""Cooperative heavy-task admission and automatic macOS cooldowns."""
import json
from pathlib import Path
import platform
import subprocess
import time

from . import runtime


class ResourcePause(RuntimeError):
    pass


class Governor:
    def __init__(self, studio, job):
        self.studio, self.job = studio, job
        self.last_sample = -100.0
        self.last_reason = None
        self.baseline_swap = None
        self.available = platform.system() == 'Darwin'
        self.probe = studio.data / 'bin' / 'resource-probe'
        if self.available:
            source = studio.root / 'native' / 'ResourceProbe.swift'
            if not self.probe.exists() or self.probe.stat().st_mtime < source.stat().st_mtime:
                self.probe.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['/usr/bin/swiftc', str(source), '-O', '-module-cache-path',
                                str(studio.data / 'cache' / 'swift'), '-o', str(self.probe)],
                               check=True, capture_output=True, timeout=90)

    def sample(self):
        sample = runtime.memory_sample()
        if self.available:
            sample.update(json.loads(subprocess.check_output([str(self.probe)], text=True, timeout=5)))
        if self.baseline_swap is None:
            self.baseline_swap = sample.get('swap_bytes') or 0
        sample['swap_growth_bytes'] = max(0, (sample.get('swap_bytes') or 0) - self.baseline_swap)
        return sample

    @staticmethod
    def reason(sample):
        if sample.get('thermal_state', 0) >= 2:
            return 'Your Mac needs a cooling break'
        footprint = max(sample.get('physical_footprint_bytes') or 0, sample.get('rss_bytes') or 0)
        if sample.get('pressure') == 4 or footprint > 19 * 1024 ** 3:
            return 'Waiting for available memory'
        return None

    def check(self):
        if not self.available or time.monotonic() - self.last_sample < 2:
            return
        self.last_sample = time.monotonic()
        sample = self.sample()
        self.last_reason = self.reason(sample)
        old = self.job.get('resource_metrics', {})
        self.job['resource_metrics'] = {
            'thermal_state': sample.get('thermal_name'),
            'peak_model_bytes': max(old.get('peak_model_bytes', 0), sample.get('physical_footprint_bytes') or sample.get('rss_bytes') or 0),
            'peak_swap_growth_bytes': max(old.get('peak_swap_growth_bytes', 0), sample['swap_growth_bytes']),
            'cooldowns': old.get('cooldowns', 0)}
        if self.last_reason:
            raise ResourcePause(self.last_reason)

    def cool_down(self):
        runtime.unload()
        self.job.setdefault('resource_metrics', {})['cooldowns'] = self.job.get('resource_metrics', {}).get('cooldowns', 0) + 1
        self.studio.update(self.job, resource_pause=self.last_reason or 'Waiting for your Mac to cool down')
        self.studio.event(self.job, 'Heavy work paused. Saved tasks and completed videos are safe; processing will resume automatically.')
        stable = None
        try:
            while True:
                self.studio.check_cancel(self.job['id'], resources=False)
                reason = self.reason(self.sample())
                if reason:
                    stable = None
                elif stable is None:
                    stable = time.monotonic()
                elif time.monotonic() - stable >= 30:
                    return
                self.studio.cancel_flags[self.job['id']].wait(2)
        finally:
            self.last_sample = time.monotonic()
            self.studio.update(self.job, resource_pause=None)


def retry_after_cooldown(studio, job, operation):
    while True:
        try:
            return operation()
        except ResourcePause:
            studio.governors[job['id']].cool_down()
