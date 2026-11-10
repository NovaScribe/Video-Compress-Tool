"""
VMAF comparison tool: original (reference) vs converted/compressed (distorted).

Handles: FPS mismatch, resolution mismatch, phone rotation metadata,
VFR video, 10-bit sources, timestamp offsets, Windows paths.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from fractions import Fraction


def run(cmd):
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def check_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        try:
            run([tool, "-version"])
        except FileNotFoundError:
            sys.exit(f"ERROR: '{tool}' not found in PATH.")
    r = run(["ffmpeg", "-hide_banner", "-filters"])
    if "libvmaf" not in r.stdout:
        sys.exit("ERROR: this ffmpeg build has no libvmaf. Use a 'full' build "
                 "(e.g. gyan.dev full build or BtbN builds).")


def parse_fps(s):
    try:
        f = Fraction(s)
        return f if 0 < f <= 240 else None
    except Exception:
        return None


def get_rotation(stream):
    rot = 0
    try:
        rot = int(float(stream.get("tags", {}).get("rotate", 0)))
    except Exception:
        pass
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                rot = int(float(sd["rotation"]))
            except Exception:
                pass
    return rot


def get_video_info(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    r = run(["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", path])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {r.stderr}")

    data = json.loads(r.stdout)
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if vs is None:
        raise ValueError(f"No video stream found in {path}")

    # avg_frame_rate is more reliable than r_frame_rate for VFR phone video
    fps = parse_fps(vs.get("avg_frame_rate", "0/0")) or parse_fps(vs.get("r_frame_rate", "0/0"))
    if fps is None:
        raise ValueError(f"Could not determine FPS of {path}")
    fps = fps.limit_denominator(1001)

    w, h = int(vs.get("width", 0)), int(vs.get("height", 0))
    rot = get_rotation(vs)
    if abs(rot) % 180 == 90:  # ffmpeg auto-rotates, so use displayed size
        w, h = h, w

    pix_fmt = vs.get("pix_fmt", "") or ""
    try:
        duration = float(vs.get("duration") or data.get("format", {}).get("duration", 0))
    except Exception:
        duration = 0.0

    return {
        "path": path,
        "width": w,
        "height": h,
        "rotation": rot,
        "fps": fps,
        "duration": duration,
        "codec": vs.get("codec_name"),
        "pix_fmt": pix_fmt,
        "is_10bit": "10" in pix_fmt or "12" in pix_fmt,
        "nb_frames": vs.get("nb_frames"),
    }


def calculate_vmaf(distorted_path, reference_path, log_path="vmaf.json",
                   model=None, n_threads=None, subsample=1):
    dist = get_video_info(distorted_path)
    ref = get_video_info(reference_path)

    def show(tag, i):
        print(f"{tag}: {i['width']}x{i['height']} @ {float(i['fps']):.3f} fps, "
              f"{i['codec']} {i['pix_fmt']}, {i['duration']:.2f}s, rot={i['rotation']}  {i['path']}")

    show("Reference", ref)
    show("Distorted", dist)

    # Same orientation sanity check (after rotation handling)
    ref_ar = ref["width"] / ref["height"]
    dist_ar = dist["width"] / dist["height"]
    if abs(ref_ar - dist_ar) / ref_ar > 0.02:
        print(f"\nWARNING: aspect ratios differ ({ref_ar:.3f} vs {dist_ar:.3f}). "
              "The distorted video will be stretched/squashed to match; "
              "the score may be unreliable (cropped or letterboxed file?).")

    target_fps = min(ref["fps"], dist["fps"])  # never invent frames
    tw, th = ref["width"], ref["height"]
    # keep 10-bit precision if either source is 10-bit
    pix = "yuv420p10le" if (ref["is_10bit"] or dist["is_10bit"]) else "yuv420p"

    # Auto-pick model: 4K model for 4K-ish reference
    if model is None and max(tw, th) >= 3840:
        model = "vmaf_4k_v0.6.1"

    def chain(info, in_idx, label):
        f = ["setpts=PTS-STARTPTS"]                     # align start timestamps
        if info["fps"] != target_fps:
            f.append(f"fps={target_fps.numerator}/{target_fps.denominator}")
        if (info["width"], info["height"]) != (tw, th):
            f.append(f"scale={tw}:{th}:flags=bicubic")
        f += [f"format={pix}", "setsar=1"]
        return f"[{in_idx}:v]{','.join(f)}[{label}]"

    # libvmaf: log_path must be a bare filename (Windows 'C:' breaks filtergraph)
    log_abs = os.path.abspath(log_path)
    log_dir, log_name = os.path.split(log_abs)

    opts = [f"log_path={log_name}", "log_fmt=json",
            f"n_threads={n_threads or os.cpu_count() or 4}"]
    if model:
        opts.append(f"model=version={model}")
    if subsample > 1:
        opts.append(f"n_subsample={subsample}")

    fc = (f"{chain(dist, 0, 'dist')};{chain(ref, 1, 'ref')};"
          f"[dist][ref]libvmaf={':'.join(opts)}")

    cmd = ["ffmpeg", "-hide_banner", "-y",
           "-i", os.path.abspath(distorted_path),
           "-i", os.path.abspath(reference_path),
           "-filter_complex", fc, "-f", "null", "-"]

    print(f"\nRunning: {' '.join(shlex.quote(c) for c in cmd)}\n")
    if os.path.exists(log_abs):
        os.remove(log_abs)
    r = run_in(cmd, log_dir)
    if r.returncode != 0:
        print(r.stderr[-2500:])
        raise RuntimeError("ffmpeg libvmaf failed (see output above).")
    if not os.path.exists(log_abs):
        raise RuntimeError("VMAF log not created")

    with open(log_abs, "r", encoding="utf-8") as f:
        data = json.load(f)

    pooled = data.get("pooled_metrics", {}).get("vmaf", {})
    frames = data.get("frames", [])

    # Frame count sanity check
    expected = min(ref["duration"], dist["duration"]) * float(target_fps)
    if expected and subsample == 1 and abs(len(frames) - expected) / expected > 0.05:
        print(f"WARNING: compared {len(frames)} frames, expected ~{expected:.0f}. "
              "Files may differ in length or have sync problems.")

    scores = [fr["metrics"]["vmaf"] for fr in frames if "vmaf" in fr.get("metrics", {})]
    low = sorted(range(len(scores)), key=lambda i: scores[i])[:5]

    return {
        "target_fps": float(target_fps),
        "target_resolution": f"{tw}x{th}",
        "model": model or "default (vmaf_v0.6.1)",
        "mean": pooled.get("mean"),
        "harmonic_mean": pooled.get("harmonic_mean"),
        "min": pooled.get("min"),
        "max": pooled.get("max"),
        "frames": len(frames),
        "worst_frames": [(frames[i].get("frameNum", i), scores[i]) for i in low],
        "log_path": log_abs,
    }


def run_in(cmd, cwd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd or None)


def fmt(v):
    return f"{v:.3f}" if isinstance(v, (int, float)) else "n/a"


def quality_label(m):
    if m is None:
        return ""
    if m >= 95: return "visually identical"
    if m >= 90: return "excellent"
    if m >= 80: return "good"
    if m >= 70: return "fair"
    return "noticeable quality loss"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="VMAF calculator (original vs converted)")
    p.add_argument("--ref", required=True, help="Original video")
    p.add_argument("--dist", required=True, help="Converted/compressed video")
    p.add_argument("--log", default="vmaf.json", help="Output JSON log")
    p.add_argument("--model", default=None, help="e.g. vmaf_v0.6.1 or vmaf_4k_v0.6.1")
    p.add_argument("--threads", type=int, default=None)
    p.add_argument("--subsample", type=int, default=1,
                   help="Score every Nth frame (faster, e.g. 5)")
    a = p.parse_args()

    check_ffmpeg()
    res = calculate_vmaf(a.dist, a.ref, a.log, a.model, a.threads, a.subsample)

    print("\n--- VMAF RESULT ---")
    print(f"Model             : {res['model']}")
    print(f"Target FPS used   : {res['target_fps']:.3f}")
    print(f"Target Resolution : {res['target_resolution']}")
    print(f"Frames compared   : {res['frames']}")
    print(f"Mean              : {fmt(res['mean'])}  ({quality_label(res['mean'])})")
    print(f"Harmonic Mean     : {fmt(res['harmonic_mean'])}")
    print(f"Min (worst frame) : {fmt(res['min'])}")
    print(f"Max (best frame)  : {fmt(res['max'])}")
    print("Worst 5 frames    : " + ", ".join(f"#{n}={s:.1f}" for n, s in res["worst_frames"]))
    print(f"Log               : {res['log_path']}")
