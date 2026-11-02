from pathlib import Path
import argparse
import logging
import shutil
import sys

from config import INPUT_EXTENSIONS, OUTPUT_DIR, FPS_TARGET, MIN_BITRATE, RECURSIVE
from video_probe import probe_video
from compressor import compress_video

def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("logs/compressor.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

def main():
    parser = argparse.ArgumentParser(
        description="Batch compress videos to H.265 using CPU encoding."
    )
    parser.add_argument("folder", help="Folder containing source videos")
    parser.add_argument("--output", default=str(OUTPUT_DIR),
                        help="Output folder (default: output)")
    parser.add_argument("--fps", type=int, choices=(24, 30), default=FPS_TARGET,
                        help="FPS target for videos above 32 FPS (default: 30)")
    args = parser.parse_args()

    setup_logging()
    source_dir = Path(args.folder).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not source_dir.is_dir():
        logging.error("Input folder does not exist: %s", source_dir)
        raise SystemExit(1)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        logging.error("FFmpeg and ffprobe must be installed and available on PATH.")
        raise SystemExit(1)

    pattern = "**/*" if RECURSIVE else "*"
    videos = sorted(
        p for p in source_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )
    if not videos:
        logging.warning("No supported video files found in %s", source_dir)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info("Found %d video(s). Output: %s", len(videos), output_dir)

    success = 0
    skipped = 0
    for index, video in enumerate(videos, 1):
        try:
            info = probe_video(video)
            bitrate = info["bitrate"]
            if bitrate is None:
                logging.info("[%d/%d] %s | bitrate unavailable; skipping conversion.",
                             index, len(videos), video.name)
                skipped += 1
                continue
            if bitrate <= MIN_BITRATE:
                logging.info(
                    "[%d/%d] %s | bitrate %.2f Mbps is not above 10 Mbps; "
                    "skipping conversion.",
                    index, len(videos), video.name, bitrate / 1_000_000,
                )
                skipped += 1
                continue

            destination = output_dir / f"{video.stem}_compressed.mp4"
            # Avoid overwriting previous results, including same-stem input files.
            suffix = 2
            while destination.exists():
                destination = output_dir / f"{video.stem}_compressed_{suffix}.mp4"
                suffix += 1
            logging.info("[%d/%d] %s | %s | %.3f FPS",
                         index, len(videos), video.name,
                         info["orientation"], info["fps"])
            compress_video(video, destination, info, args.fps)
            success += 1
        except Exception:
            logging.exception("Failed to process: %s", video)

    logging.info("Finished: %d/%d videos compressed successfully; %d skipped.",
                 success, len(videos), skipped)

if __name__ == "__main__":
    main()
