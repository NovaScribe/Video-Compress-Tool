from pathlib import Path

# Output sizing: maximum 1920x1080 landscape or 1080x1920 portrait.
# Aspect ratio is preserved and smaller videos are not upscaled.
LANDSCAPE_MAX = (1920, 1080)
PORTRAIT_MAX = (1080, 1920)

# Applied only when the source frame rate is greater than 32 FPS.
FPS_THRESHOLD = 32.0
FPS_TARGET = 30  # Change to 24, or use: python main.py FOLDER --fps 24
MIN_BITRATE = 10_000_000

# Conservative starting bitrates for low-bitrate 1080p HEVC.
# Increase these if fine detail or fast motion looks too soft.
VIDEO_BITRATE = {
    "horizontal": "2M",
    "vertical": "1.5M",
}
MAX_BITRATE = {
    "horizontal": "3M",
    "vertical": "2.25M",
}
BUFFER_SIZE = {
    "horizontal": "4M",
    "vertical": "3M",
}

AUDIO_BITRATE = "256k"
AUDIO_CODEC = "aac"
VIDEO_CODEC = "libx265"
X265_PRESET = "medium"

INPUT_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".mts"
}
OUTPUT_DIR = Path("output")
RECURSIVE = False  # Set True to include videos in subfolders.
