# Output sizing: maximum 1920x1080 landscape or 1080x1920 portrait.
# Aspect ratio is preserved and smaller videos are not upscaled.
LANDSCAPE_MAX = (1920, 1080)
PORTRAIT_MAX = (1080, 1920)

# Applied only when the source frame rate is greater than 32 FPS.
FPS_THRESHOLD = 32
FPS_TARGET = 30  # Change to 24, or use: python main.py FOLDER --fps 24
MIN_BITRATE = 10_000_000

# Target and peak bitrates for 1080p HEVC.
VIDEO_BITRATE = {
    "horizontal": "8M",
    "vertical": "6M",
}
# Slightly higher targets for NVENC; libx265 continues using VIDEO_BITRATE.
NVENC_VIDEO_BITRATE = {
    "horizontal": "9M",
    "vertical": "7M",
}
MAX_BITRATE = {
    "horizontal": "12M",
    "vertical": "10M",
}
BUFFER_SIZE = {
    "horizontal": "16M",
    "vertical": "12M",
}

AUDIO_BITRATE = "256k"
AUDIO_CODEC = "aac"
VIDEO_CODEC = "hevc_nvenc"  # Choose "libx265" (CPU) or "hevc_nvenc" (NVIDIA GPU).
X265_PRESET = "medium"
NVENC_PRESET = "p5"
NVENC_MULTIPASS = "fullres"

INPUT_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".mts"
}
RECURSIVE = False  # Set True to include videos in subfolders.
