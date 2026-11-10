"""
Batch VMAF: compare every video in the ORIGINAL folder with the file of the
same name in the COMPRESSED folder. Needs vmaf_tool.py in the same directory.

Outputs:
  log.log            - full run log (also printed on screen)
  vmaf_results.csv   - one row per file
  vmaf_logs/*.json   - per-frame VMAF data for each file
"""
import argparse
import csv
import logging
import os
import sys
import time

from VMAF_tool import calculate_vmaf, check_ffmpeg, fmt, quality_label

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".ts", ".mts", ".m2ts", ".wmv", ".flv", ".3gp"}


def setup_logging(log_file):
    logger = logging.getLogger("vmaf_batch")
    logger.setLevel(logging.INFO)
    fmt_ = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    fh.setFormatter(fmt_)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt_)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def find_pairs(orig_dir, comp_dir, recursive):
    """Return (pairs, missing). Match by relative path; fall back to same stem, any extension."""
    pairs, missing = [], []
    walker = os.walk(orig_dir) if recursive else [(orig_dir, [], os.listdir(orig_dir))]
    for root, _, files in walker:
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() not in VIDEO_EXT:
                continue
            rel_dir = os.path.relpath(root, orig_dir)
            comp_root = comp_dir if rel_dir == "." else os.path.join(comp_dir, rel_dir)
            ref_path = os.path.join(root, name)
            dist_path = os.path.join(comp_root, name)

            if not os.path.exists(dist_path) and os.path.isdir(comp_root):
                stem = os.path.splitext(name)[0].lower()
                for c in os.listdir(comp_root):
                    if os.path.splitext(c)[0].lower() == stem and os.path.splitext(c)[1].lower() in VIDEO_EXT:
                        dist_path = os.path.join(comp_root, c)
                        break

            if os.path.exists(dist_path):
                pairs.append((os.path.normpath(os.path.join(rel_dir, name)), ref_path, dist_path))
            else:
                missing.append(ref_path)
    return pairs, missing


def main():
    p = argparse.ArgumentParser(description="Batch VMAF: original folder vs compressed folder")
    p.add_argument("--orig", required=True, help="Folder with original videos")
    p.add_argument("--comp", required=True, help="Folder with compressed videos (same file names)")
    p.add_argument("--log", default="log.log", help="Log file (default: log.log)")
    p.add_argument("--csv", default="vmaf_results.csv", help="CSV summary file")
    p.add_argument("--json-dir", default="vmaf_logs", help="Folder for per-file VMAF JSON")
    p.add_argument("--recursive", action="store_true", help="Include sub-folders")
    p.add_argument("--subsample", type=int, default=1, help="Score every Nth frame (faster)")
    p.add_argument("--model", default=None, help="e.g. vmaf_v0.6.1 or vmaf_4k_v0.6.1")
    p.add_argument("--threads", type=int, default=None)
    p.add_argument("--skip-existing", action="store_true",
                   help="Skip files that already have a JSON result in --json-dir")
    a = p.parse_args()

    log = setup_logging(a.log)
    log.info("=" * 70)
    log.info("Batch VMAF started")
    log.info(f"Original  : {a.orig}")
    log.info(f"Compressed: {a.comp}")

    for d in (a.orig, a.comp):
        if not os.path.isdir(d):
            log.error(f"Folder not found: {d}")
            sys.exit(1)

    check_ffmpeg()
    os.makedirs(a.json_dir, exist_ok=True)

    pairs, missing = find_pairs(a.orig, a.comp, a.recursive)
    for m in missing:
        log.warning(f"No compressed match for: {m}")
    log.info(f"Found {len(pairs)} pair(s) to compare, {len(missing)} original(s) without match")

    rows, failed = [], []
    t_all = time.time()

    for i, (rel, ref, dist) in enumerate(pairs, 1):
        log.info("-" * 70)
        log.info(f"[{i}/{len(pairs)}] {rel}")
        json_path = os.path.join(a.json_dir, rel.replace(os.sep, "_") + ".json")

        if a.skip_existing and os.path.exists(json_path):
            log.info("Skipped (result JSON already exists)")
            continue

        t0 = time.time()
        try:
            r = calculate_vmaf(dist, ref, log_path=json_path, model=a.model,
                               n_threads=a.threads, subsample=a.subsample)
        except Exception as e:
            log.error(f"FAILED: {rel}: {e}")
            failed.append(rel)
            continue

        size_ref, size_dist = os.path.getsize(ref), os.path.getsize(dist)
        ratio = size_dist / size_ref * 100 if size_ref else 0
        log.info(f"Target: {r['target_resolution']} @ {r['target_fps']:.3f} fps | frames: {r['frames']} | model: {r['model']}")
        log.info(f"VMAF mean={fmt(r['mean'])} ({quality_label(r['mean'])}) | "
                 f"harmonic={fmt(r['harmonic_mean'])} | min={fmt(r['min'])} | max={fmt(r['max'])}")
        log.info(f"Size: {size_ref/1e6:.1f} MB -> {size_dist/1e6:.1f} MB ({ratio:.1f}% of original) | "
                 f"time {time.time()-t0:.0f}s")
        log.info("Worst frames: " + ", ".join(f"#{n}={s:.1f}" for n, s in r["worst_frames"]))

        rows.append({
            "file": rel, "mean": r["mean"], "harmonic_mean": r["harmonic_mean"],
            "min": r["min"], "max": r["max"], "frames": r["frames"],
            "resolution": r["target_resolution"], "fps": round(r["target_fps"], 3),
            "orig_mb": round(size_ref / 1e6, 2), "comp_mb": round(size_dist / 1e6, 2),
            "size_percent": round(ratio, 1), "quality": quality_label(r["mean"]),
        })

    # CSV
    if rows:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Summary
    log.info("=" * 70)
    log.info("SUMMARY")
    ok = [r for r in rows if isinstance(r["mean"], (int, float))]
    if ok:
        avg = sum(r["mean"] for r in ok) / len(ok)
        worst = min(ok, key=lambda r: r["mean"])
        best = max(ok, key=lambda r: r["mean"])
        log.info(f"Files compared : {len(ok)}")
        log.info(f"Average VMAF   : {avg:.3f} ({quality_label(avg)})")
        log.info(f"Best file      : {best['file']} ({best['mean']:.3f})")
        log.info(f"Worst file     : {worst['file']} ({worst['mean']:.3f})")
        for r in sorted(ok, key=lambda r: r["mean"]):
            log.info(f"  {r['mean']:7.3f}  min {r['min']:7.3f}  {r['size_percent']:5.1f}% size  {r['file']}")
        log.info(f"CSV saved      : {os.path.abspath(a.csv)}")
    if failed:
        log.warning(f"Failed ({len(failed)}): " + ", ".join(failed))
    if missing:
        log.warning(f"Unmatched originals: {len(missing)} (listed above)")
    log.info(f"Total time     : {(time.time()-t_all)/60:.1f} min")
    log.info("Batch VMAF finished")


if __name__ == "__main__":
    main()
