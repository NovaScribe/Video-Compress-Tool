import logging
import subprocess
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

def compress_video(source: Path, destination: Path, info: dict, fps_target: int):
    orientation = info["orientation"]
    bitrate = VIDEO_BITRATE[orientation]
    maxrate = MAX_BITRATE[orientation]
    bufsize = BUFFER_SIZE[orientation]

    filters = [_scale_filter(orientation)]
    if info["reduce_fps"]:
        filters.append(f"fps={fps_target}")

    command = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(source),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-map_metadata", "0",
        "-vf", ",".join(filters),
        "-c:v", VIDEO_CODEC,
        "-preset", X265_PRESET,
        "-b:v", bitrate,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-fps_mode", "passthrough",
        "-tag:v", "hvc1",
        "-c:a", AUDIO_CODEC,
        "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",
        str(destination),
    ]

    logging.info("Encoding %s -> %s | HEVC CPU | %s | target %s",
                 source.name, destination.name, orientation, bitrate)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"FFmpeg failed for {source.name}:\n{result.stderr[-4000:]}"
        )
    logging.info("Created: %s", destination)
