# Video Transcoder (FFmpeg Wrapper)

This Python script is a command-line tool for batch video transcoding using **FFmpeg**.  
It standardizes options for popular codecs (H.264, H.265, AV1), supports CRF/preset tuning, downscaling, and real-time progress display.

---

## Features

- 🎥 **Batch processing**: Encodes all videos in a given folder.
- ⚡ **Supported codecs**:
  - `libx264` (H.264)
  - `libx265` (H.265/HEVC)
  - `libsvtav1` (AV1)
- 🔧 **Configurable quality & speed**:
  - CRF values (`-q`)
  - Preset values (`-p`)
- 📉 **Optional downscaling** to 1080p.
- 🖼️ **Preserves metadata** and copies original audio streams.
- ⏱️ **Progress display**: Shows percentage, elapsed time, FPS, and bitrate.
- 🗂️ Creates an output folder named after codec, CRF, and preset.

---

## Requirements

- Python **3.7+**
- [FFmpeg](https://ffmpeg.org/download.html) compiled with:
  - `libx264`
  - `libx265`
  - `libsvt-av1` (recommended: v3.0.2+ for speed and efficiency)

## Usage

Run the script with:

python3 encoder.py -i <input_directory> [options]

| Flag | Name          | Description                                      | Default      |
| ---- | ------------- | ------------------------------------------------ | ------------ |
| `-i` | `--input`     | Directory containing videos to encode            | **required** |
| `-l` | `--library`   | Codec library: `libx264`, `libx265`, `libsvtav1` | `libsvt-av1` |
| `-q` | `--crf`       | Quality (lower = higher quality, bigger files)   | `32`         |
| `-p` | `--preset`    | Codec preset (speed vs compression)              | `4`          |
| `-e` | `--extension` | Output extension: `.mp4` or `.mkv`               | `.mkv`       |
| `-d` | `--downscale` | Downscale to 1080p: `yes` / `no`                 | `no`         |

## Example Commands

Encode all videos in ./videos/ with AV1:
```
python3 encoder.py -i ./testing/ -l libsvtav1 -q 32 -p 4
```
Encode with H.265 to MP4, high quality, slow preset:
```
python3 encoder.py -i ./movies/ -l libx265 -q 18 -p slow -e .mp4
```
Encode with H.264 to MKV, downscaled to 1080p:
```
python3 encoder.py -i ./clips/ -l libx264 -q 20 -p medium -e .mkv -d yes
```