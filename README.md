# VideoCompressor

Batch compress videos in a folder to H.265/HEVC using either CPU (`libx265`) or NVIDIA NVENC (`hevc_nvenc`) encoding.

## Requirements

- Windows or Linux
- Python 3.9+
- FFmpeg and ffprobe available on PATH
- An FFmpeg build that includes `libx265`; `hevc_nvenc` is also needed to use an
  NVIDIA GPU.
- An FFmpeg build that includes the `libvmaf` filter to run quality comparisons.

## 1. Create and activate a virtual environment

### Windows (PowerShell)
```powershell
cd VideoCompressor
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux
```bash
cd VideoCompressor
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Install/check FFmpeg

Install FFmpeg from a trusted distribution and make sure both `ffmpeg` and
`ffprobe` are on PATH. The build must include `libx265`. To use NVIDIA encoding,
it must also include `hevc_nvenc`, and the NVIDIA driver must support the
NVENC API required by that FFmpeg build.

Check:
```bash
ffmpeg -hide_banner -encoders
ffmpeg -hide_banner -h encoder=libx265
ffmpeg -hide_banner -h encoder=hevc_nvenc
ffmpeg -hide_banner -filters
ffprobe -version
```

The encoder list should contain `libx265`; it must also contain `hevc_nvenc`
when using NVIDIA encoding. The filters list should contain `libvmaf` to use
the quality comparison module.

## 3. Run

```bash
python main.py "D:/Videos"
```

By default, converted videos are saved in a `compressed` folder inside the
source folder. To choose another output folder:
```bash
python main.py "D:/Videos" --output "D:/Compressed"
```

Choose 24 FPS for source videos above 32 FPS:
```bash
python main.py "D:/Videos" --fps 24
```

Converted files keep the original filename and extension. Files already present
in the output folder are skipped, and the output folder must differ from the
source folder. Original files are not modified. Logs are saved in
`logs/compressor.log`.

## Encoding behavior

- Landscape: fit within 1920x1080.
- Portrait: fit within 1080x1920.
- Aspect ratio is preserved; smaller sources are not upscaled.
- Source FPS at or below 32 is retained.
- Source FPS above 32 is converted to the selected 30 or 24 FPS.
- Set `VIDEO_CODEC` in `config.py` to `libx265` for CPU-based x265 encoding,
  or `hevc_nvenc` for NVIDIA GPU encoding. The NVENC path requires a compatible
  NVIDIA GPU, driver, and FFmpeg build.
- `X265_PRESET` applies to `libx265`; `NVENC_PRESET` and `NVENC_MULTIPASS`
  apply to `hevc_nvenc`. Their quality and speed characteristics differ, so
  compare output quality and file size when switching encoders.
- `NVENC_VIDEO_BITRATE` controls only NVENC's target bitrate. It is slightly
  higher than `VIDEO_BITRATE` by default; changing it does not affect `libx265`.
- Audio is converted to AAC at 256 kbps.
- `VIDEO_CODEC` is set in `config.py`: use `libx265` for CPU-based x265 encoding,
  or `hevc_nvenc` for NVIDIA GPU encoding. The NVENC path enables NVENC's
  multipass rate-control option, but it still uses a single FFmpeg encode pass.

Bitrate and quality are a trade-off. If the output looks too soft, increase
the values in `config.py`. For smaller files, lower them gradually and test.

## Notes

- The program processes files in the selected folder (not subfolders by
  default). Set `RECURSIVE = True` in `config.py` to include subfolders.
- Rotation metadata from common phone videos is considered when detecting
  orientation. FFmpeg's automatic rotation is left enabled.
- You can adjust the encoder-specific preset in `config.py` to trade encoding
  speed for compression efficiency.
- Some unusual variable-frame-rate files may report an approximate FPS.

## Compare quality with VMAF

Compare a compressed video against its original reference:

```bash
python scorecheck.py "D:/Videos/original.mp4" "D:/Videos/compressed/original.mp4"
```

The module reports the mean VMAF score, the minimum and maximum frame scores,
and the number of frames compared. It scales the compressed video to the
original's display dimensions, aligns both videos' start timestamps, and stops
at the end of the shorter video. VMAF measures video similarity only; it does
not compare audio.
