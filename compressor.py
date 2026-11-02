import logging
import os
import subprocess
import tempfile
from pathlib import Path

from config import (
    LANDSCAPE_MAX, PORTRAIT_MAX, VIDEO_BITRATE, MAX_BITRATE,
    BUFFER_SIZE, AUDIO_BITRATE, AUDIO_CODEC, VIDEO_CODEC,
    X265_PRESET,
)

def _scale_filter(orientation):
    max_width, max_height = (
        PORTRAIT_MAX if orientation == "vertical" else LANDSCAPE_MAX
    )
    # Fit within the orientation's 1080p bounds, preserve aspect ratio,
    # avoid upscaling, and keep dimensions divisible by 2 for 4:2:0 encoding.
    return (
        f"scale=w='min(iw,{max_width})':h='min(ih,{max_height})':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )

def _run_ffmpeg(command, source: Path, pass_number: int):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg pass {pass_number} failed for {source.name}:\n"
            f"{result.stderr[-4000:]}"
        )

def compress_video(source: Path, destination: Path, info: dict, fps_target: int):
    orientation = info["orientation"]
    bitrate = VIDEO_BITRATE[orientation]
    maxrate = MAX_BITRATE[orientation]
    bufsize = BUFFER_SIZE[orientation]

    filters = [_scale_filter(orientation)]
    if info["reduce_fps"]:
        filters.append(f"fps={fps_target}")

    video_options = [
        "-vf", ",".join(filters),
        "-c:v", VIDEO_CODEC,
        "-preset", X265_PRESET,
        "-b:v", bitrate,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-fps_mode", "passthrough",
        "-tag:v", "hvc1",
    ]

    logging.info("Encoding %s -> %s | HEVC 2-pass | %s | target %s",
                 source.name, destination.name, orientation, bitrate)

    with tempfile.TemporaryDirectory(prefix="video-compress-") as stats_dir:
        stats_file = str(Path(stats_dir) / "x265-stats.log")
        try:
            first_pass = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(source),
                "-map", "0:v:0",
                *video_options,
                "-x265-params", "pass=1",
                "-x265-stats", stats_file,
                "-an",
                "-f", "null", os.devnull,
            ]
            _run_ffmpeg(first_pass, source, 1)

            second_pass = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(source),
                "-map", "0:v:0",
                *video_options,
                "-x265-params", "pass=2",
                "-x265-stats", stats_file,
                "-map", "0:a?",
                "-map_metadata", "0",
                "-c:a", AUDIO_CODEC,
                "-b:a", AUDIO_BITRATE,
                "-movflags", "+faststart",
                str(destination),
            ]
            _run_ffmpeg(second_pass, source, 2)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    logging.info("Created: %s", destination)
