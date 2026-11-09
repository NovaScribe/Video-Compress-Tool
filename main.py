from pathlib import Path
import argparse
import logging
import shutil
import sys

from config import INPUT_EXTENSIONS, FPS_TARGET, MIN_BITRATE, RECURSIVE
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
    parser.add_argument(
        "--output",
        help="Output folder (default: compressed subfolder inside the source folder)",
    )
    parser.add_argument("--fps", type=int, choices=(24, 30), default=FPS_TARGET,
                        help="FPS target for videos above 32 FPS (default: 30)")
    args = parser.parse_args()

    setup_logging()
    source_dir = Path(args.folder).expanduser().resolve()
    output_dir = (
        Path(args.output).expanduser().resolve()
        if args.output
        else source_dir / "compressed"
    )

    if not source_dir.is_dir():
        logging.error("Input folder does not exist: %s", source_dir)
        raise SystemExit(1)
    if source_dir == output_dir:
        logging.error("The output folder must be different from the source folder.")
        raise SystemExit(1)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        logging.error("FFmpeg and ffprobe must be installed and available on PATH.")
        raise SystemExit(1)

    pattern = "**/*" if RECURSIVE else "*"
    output_is_source_subfolder = source_dir in output_dir.parents
    videos = sorted(
        p for p in source_dir.glob(pattern)
        if p.is_file()
        and p.suffix.lower() in INPUT_EXTENSIONS
        and not (output_is_source_subfolder and output_dir in p.parents)
    )
    if not videos:
        logging.warning("No supported video files found in %s", source_dir)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info("Found %d video(s). Output: %s", len(videos), output_dir)

    success = 0
    skipped = 0
    for index, video in enumerate(videos, 1):
        if is_already_converted(video, output_dir):
            logging.info(
                "[%d/%d] %s | already exists in output folder; skipping.",
                index, len(videos), video.name,
            )
            skipped += 1
            continue
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

            destination = output_dir / video.name
            logging.info("[%d/%d] %s | %s | %.3f FPS",
                         index, len(videos), video.name,
                         info["orientation"], info["fps"])
            compress_video(video, destination, info, args.fps)
            success += 1
        except Exception:
            logging.exception("Failed to process: %s", video)

    logging.info("Finished: %d/%d videos compressed successfully; %d skipped.",
                 success, len(videos), skipped)


def is_already_converted(video: Path, output_dir: Path) -> bool:
    """Return whether this video's same-name output already exists."""
    return (output_dir / video.name).is_file()


if __name__ == "__main__":
    main()
