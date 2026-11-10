import json
import subprocess
from pathlib import Path

from config import FPS_THRESHOLD

def _fraction_to_float(value):
    try:
        numerator, denominator = value.split("/", 1)
        denominator = float(denominator)
        return float(numerator) / denominator if denominator else 0.0
    except (ValueError, AttributeError, ZeroDivisionError):
        return 0.0

def _bitrate_to_int(value):
    try:
        bitrate = int(value)
    except (TypeError, ValueError):
        return None
    return bitrate if bitrate > 0 else None

def probe_video(path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,bit_rate:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json", str(path),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not inspect {path} with ffprobe:\n{result.stderr.strip()}"
        )

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise ValueError("No video stream found.")

    stream = streams[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("Invalid video dimensions.")

    # Account for phone footage carrying a 90/270-degree display rotation.
    rotation = 0.0
    for side_data in stream.get("side_data_list", []):
        if "rotation" in side_data:
            rotation = float(side_data["rotation"])
            break
    if not rotation:
        rotation = float(stream.get("tags", {}).get("rotate", 0) or 0)

    if int(round(rotation)) % 180 != 0:
        width, height = height, width

    fps = _fraction_to_float(stream.get("avg_frame_rate", "0/0"))
    if fps <= 0:
        fps = _fraction_to_float(stream.get("r_frame_rate", "0/0"))
    if fps <= 0:
        raise ValueError("Could not determine source FPS.")

    orientation = "vertical" if height > width else "horizontal"
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "bitrate": _bitrate_to_int(stream.get("bit_rate")),
        "orientation": orientation,
        "reduce_fps": fps > FPS_THRESHOLD,
    }
