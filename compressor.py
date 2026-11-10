import logging
import os
import subprocess
import tempfile
from pathlib import Path

from config import (
    LANDSCAPE_MAX, PORTRAIT_MAX, VIDEO_BITRATE, NVENC_VIDEO_BITRATE, MAX_BITRATE,
    BUFFER_SIZE, AUDIO_BITRATE, AUDIO_CODEC, VIDEO_CODEC,
    X265_PRESET, NVENC_PRESET, NVENC_MULTIPASS,
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

def _run_ffmpeg(command, source: Path, stage: str):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg {stage} failed for {source.name}:\n"
            f"{result.stderr[-4000:]}"
        )

def compress_video(source: Path, destination: Path, info: dict, fps_target: int):
    if VIDEO_CODEC == "libx265":
        preset = X265_PRESET
        two_pass = True
        workflow = "2-pass"
    elif VIDEO_CODEC == "hevc_nvenc":
        preset = NVENC_PRESET
        two_pass = False
        workflow = f"single encode, NVENC multipass={NVENC_MULTIPASS}"
    else:
        raise ValueError(
            f"Unsupported video codec {VIDEO_CODEC!r}; "
            "choose 'libx265' or 'hevc_nvenc'."
        )

    orientation = info["orientation"]
    bitrate = (
        NVENC_VIDEO_BITRATE[orientation]
        if VIDEO_CODEC == "hevc_nvenc"
        else VIDEO_BITRATE[orientation]
    )
    maxrate = MAX_BITRATE[orientation]
    bufsize = BUFFER_SIZE[orientation]

    filters = [_scale_filter(orientation)]
    if info["reduce_fps"]:
        filters.append(f"fps={fps_target}")

    video_options = [
        "-vf", ",".join(filters),
        "-c:v", VIDEO_CODEC,
        "-preset", preset,
        "-b:v", bitrate,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        *(["-multipass", NVENC_MULTIPASS] if VIDEO_CODEC == "hevc_nvenc" else []),
        *(
            [
                "-rc-lookahead", "20",
                "-spatial-aq", "1",
                "-bf", "0",
            ]
            if VIDEO_CODEC == "hevc_nvenc"
            else []
        ),
        "-pix_fmt", "yuv420p",
        "-fps_mode", "passthrough",
        "-tag:v", "hvc1",
    ]

    max_width, max_height = (
        PORTRAIT_MAX if orientation == "vertical" else LANDSCAPE_MAX
    )
    input_bitrate = info.get("bitrate")
    input_bitrate_text = (
        f"{input_bitrate / 1_000_000:.2f} Mbps"
        if input_bitrate is not None
        else "unknown"
    )
    output_fps = fps_target if info["reduce_fps"] else info["fps"]

    #logging.info("Encoding: %s -> %s", source, destination)
    logging.info(
        "Settings: input %dx%d @ %.3f FPS, %s -> output up to %dx%d @ %.3f FPS, "
        "%s (%s), %s, video %s target / %s max, %s buffer, audio %s %s",
        info["width"], info["height"], info["fps"], input_bitrate_text,
        max_width, max_height, output_fps,
        VIDEO_CODEC, preset, workflow, bitrate, maxrate, bufsize,
        AUDIO_CODEC, AUDIO_BITRATE,
    )

    try:
        if two_pass:
            with tempfile.TemporaryDirectory(prefix="video-compress-") as stats_dir:
                stats_file = str(Path(stats_dir) / "x265-stats.log")
                first_pass = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-i", str(source),
                    "-map", "0:v:0",
                    *video_options,
                    "-x265-params", "pass=1",
                    "-passlogfile", stats_file,
                    "-an",
                    "-f", "null", os.devnull,
                ]
                _run_ffmpeg(first_pass, source, "pass 1")

                second_pass = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-i", str(source),
                    "-map", "0:v:0",
                    *video_options,
                    "-x265-params", "pass=2",
                    "-passlogfile", stats_file,
                    "-map", "0:a?",
                    "-map_metadata", "0",
                    "-c:a", AUDIO_CODEC,
                    "-b:a", AUDIO_BITRATE,
                    "-movflags", "+faststart",
                    str(destination),
                ]
                _run_ffmpeg(second_pass, source, "pass 2")
        else:
            command = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(source),
                "-map", "0:v:0",
                *video_options,
                "-map", "0:a?",
                "-map_metadata", "0",
                "-c:a", AUDIO_CODEC,
                "-b:a", AUDIO_BITRATE,
                "-movflags", "+faststart",
                str(destination),
            ]
            _run_ffmpeg(command, source, "encoding")
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    #logging.info("Created: %s", destination)
