# VideoCompressor

Batch compress videos in a folder to H.265/HEVC using CPU encoding.

## Requirements

- Windows or Linux
- Python 3.9+
- FFmpeg and ffprobe available on PATH
- An FFmpeg build that includes `libx265`

The GTX 1050 is a Pascal-generation GPU and supports hardware HEVC encoding.
Actual availability depends on the installed driver and FFmpeg build.

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
`ffprobe` are on PATH. The FFmpeg build must include the `libx265` encoder.

Check:
```bash
ffmpeg -hide_banner -encoders
ffmpeg -hide_banner -h encoder=libx265
ffprobe -version
```

The encoder list should contain `libx265`.

## 3. Run

```bash
python main.py "D:/Videos"
```

Choose 24 FPS for source videos above 32 FPS:
```bash
python main.py "D:/Videos" --fps 24
```

Choose a custom output folder:
```bash
python main.py "D:/Videos" --output "D:/Compressed"
```

Output files are written as `<original_name>_compressed.mp4`.
Original files are not modified. Logs are saved in `logs/compressor.log`.

## Encoding behavior

- Landscape: fit within 1920x1080.
- Portrait: fit within 1080x1920.
- Aspect ratio is preserved; smaller sources are not upscaled.
- Source FPS at or below 32 is retained.
- Source FPS above 32 is converted to the selected 30 or 24 FPS.
- Video uses the CPU-based `libx265` encoder with VBR and a medium preset.
- CPU encoding can take longer and use more system resources than GPU encoding.
- Audio is converted to AAC at 128 kbps.

Bitrate and quality are a trade-off. If the output looks too soft, increase
the values in `config.py`. For smaller files, lower them gradually and test.

## Notes

- The program processes files in the selected folder (not subfolders by
  default). Set `RECURSIVE = True` in `config.py` to include subfolders.
- Rotation metadata from common phone videos is considered when detecting
  orientation. FFmpeg's automatic rotation is left enabled.
- You can adjust `X265_PRESET` in `config.py` to trade encoding speed for
  compression efficiency.
- Some unusual variable-frame-rate files may report an approximate FPS.
