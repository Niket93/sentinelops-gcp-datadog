from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterator, Optional


@dataclass(frozen=True)
class ClipLocal:
    path: str
    clip_index: int
    start_ts: datetime
    end_ts: datetime


class VideoClipper:
    def __init__(self, clip_seconds: float = 2.0, sample_fps: int = 6) -> None:
        self.clip_seconds = float(clip_seconds)
        self.sample_fps = int(sample_fps)
        self._tmpdir: Optional[str] = None

    def _run_ffmpeg_segment(self, video_path: str, out_pattern: str) -> None:
        seg = float(self.clip_seconds)
        force_kf = f"expr:gte(t,n_forced*{seg})"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-force_key_frames", force_kf,
            "-r", str(self.sample_fps),
            "-an",
            "-f", "segment",
            "-segment_time", str(seg),
            "-reset_timestamps", "1",
            out_pattern,
        ]
        subprocess.run(cmd, check=True)

    def iter_clips(self, video_path: str) -> Iterator[ClipLocal]:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found. Install it or use Dockerfile.")
        if not os.path.exists(video_path):
            raise RuntimeError(f"Security video not found: {video_path}")

        self._tmpdir = tempfile.mkdtemp(prefix="clips_")
        out_pattern = os.path.join(self._tmpdir, "clip_%06d.mp4")
        self._run_ffmpeg_segment(video_path, out_pattern)

        files = sorted([f for f in os.listdir(self._tmpdir) if f.endswith(".mp4")])
        if not files:
            self.cleanup()
            raise RuntimeError("No clips produced by ffmpeg.")

        start0 = datetime.now(timezone.utc)
        clip_index = 0
        for fname in files:
            path = os.path.join(self._tmpdir, fname)
            if os.path.getsize(path) <= 0:
                continue
            start_ts = start0 + timedelta(seconds=clip_index * self.clip_seconds)
            end_ts = start_ts + timedelta(seconds=self.clip_seconds)
            yield ClipLocal(path=path, clip_index=clip_index, start_ts=start_ts, end_ts=end_ts)
            clip_index += 1

        self.cleanup()

    def cleanup(self) -> None:
        if self._tmpdir and os.path.isdir(self._tmpdir):
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        self._tmpdir = None