import sys
import os
import math
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageOps

# ANSI color codes.
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# Extensions.
IMAGE_EXTS = [".jpg", ".jpeg", ".heic", ".heif", ".webp", ".avif", ".png"]

# Notes:
"""
For Orignal Quality (Pretty much unnoticeable compression):
--quality 24 --preset 2 --megapixels 48

For Storage Savings (Somewhat noticeable difference):
--quality 32 --preset 2 --megapixels 20

For EXTREME Storage Savings (Noticeable difference, still not radio-like photos):
--quality 40 --preset 1 --megapixels 12

1. Running multiple instances of the script with the same params (running on the same output directory)
might result in encoding errors.
"""

# Auxiliary Functions.

def resize_image(path: Path, megapixels: str) -> Path:
    """
    Resizes an image to fit within the given megapixel count, preserving aspect ratio.
    Returns the path of the resized temp image.
    """
    try:
        with Image.open(path) as img:

            # Stores metadata.
            exif = img.info.get("exif")

            # Parses megapixels as int for calculations.
            megapixels = int(megapixels)

            # Converts target megapixels to pixels.
            target_pixels = megapixels * 1_000_000

            # Gets original size (w, h, pixels).
            w, h = img.size
            pixels = (int(w) * int(h))

            # Prints original resolution.
            megapixels = pixels / 1_000_000
            print(f"[Org Res] {w}x{h} [{megapixels:.1f}MP]")

            # Returns if no need for resizing.
            if pixels <= target_pixels and max(w, h) <= 8704:
                return path

            # Scales width and heigth to match target MP.
            scale = math.sqrt(target_pixels / pixels)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Only used in case new_w or new_h is bigger than max w,h supported by ffmpeg.
            if max(new_w, new_h) > 8704:
                max_scale = 8704 / max(new_w, new_h)
                new_w = int(new_w * max_scale)
                new_h = int(new_h * max_scale)

            # Forces even width and height.
            new_w = new_w - 1 if new_w % 2 != 0 else new_w
            new_h = new_h - 1 if new_h % 2 != 0 else new_h

            # Prints new resolution.
            new_megapixels = (new_w * new_h) / 1_000_000
            print(f"[New Res] {RED}{new_w}x{new_h}{RESET} [{new_megapixels:.1f}MP]")

            # Saves downscaled img to temp file, then returns it.
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            tmp_path = path.stem + "_" + str(new_megapixels)[:3] + "MP_temp.jpg"

            # Writes temp file.
            try:
                resized.save(tmp_path, format="JPEG", quality=100, subsampling=0, exif=exif) # Normal write.
            except:
                resized = resized.convert("RGB")
                resized.save(tmp_path, format="JPEG", quality=100, subsampling=0, exif=exif) # Drops alpha channel.

            return tmp_path
    # If process fails, returns path to the original image, no downscaling.
    except (IOError, OSError) as e:
        print(f"{YELLOW}[WARN]{RESET} Could not downscale image: {e}")
        return path

def run_command(cmd: list) -> bool:
    "Runs a command provided as argument. Returns True if sucess, else False"
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,    # Silence stdout.
            stderr=subprocess.PIPE        # Capture stderr.
        )
        return True
    except subprocess.CalledProcessError as e: # Handles error.
        print(e.stderr.decode())
        return False

# Main Functions.

def process_image(path: Path, out_file: Path, megapixels: str, quality: str, preset: str):
    """
    Resizes and encodes a single image into AVIF format using libsvtav1.
    """

    # Returns if output file exists.
    if out_file.exists():
        print(f"{YELLOW}[Skipping]{RESET} Output file exists.")
        return

    # Creates temp img for resizing to max megapixels if needed.
    tmp = resize_image(path, megapixels)

    # Builds ffmpeg command to encode image.
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp),
        "-map", "0",                      # Copy metadata.
        "-frames:v", "1",                 # Single frame (treat as image).
        "-c:v", "libsvtav1",              # AV1 encoder.
        "-crf", str(quality),             # Quality.
        "-preset", str(preset),           # Speed/compression tradeoff.
        "-pix_fmt", "yuv420p",            # yuv420p 8bits depth.
        str(out_file)
    ]

    # Builds exiftool command to copy metadata.
    exiftool_cmd = [
        "exiftool",
        "-tagsFromFile", str(path),       # Original file metadata.
        "-Orientation=",                  # Prevents rotation issue.
        "-overwrite_original",            # Suppresses creation of a backup file.
        str(out_file)
    ]

    # Executes commands.
    encode_OK = run_command(ffmpeg_cmd)
    metadata_OK = run_command(exiftool_cmd)

    # Prints result.
    msg = f"{GREEN}[OK]{RESET}" if encode_OK and metadata_OK else f"{YELLOW}[WARN]{RESET} One step failed!"
    print(msg)

    # cleanup temp resize file if it was created.
    if str(tmp) != str(path) and os.path.exists(tmp):
        os.remove(tmp)

def process_image_webp(path: Path, out_file: Path, megapixels: str, quality: str, preset: str):
    """
    Resizes and encodes a single image into WebP format using cwebp (lossy).
    """

    # Skip if output exists.
    if out_file.exists():
        print(f"{YELLOW}[Skipping]{RESET} Output file exists.")
        return

    # Resize step (creates temp file if need be)
    tmp = resize_image(path, megapixels)

    # Build cwebp command.
    # IMPORTANT: If resize_image already resized for us, we don't pass -resize to cwebp.
    cwebp_cmd = [
        "cwebp",
        "-q", str(quality),
        "-m", str(preset),
        "-pass", "10",
        "-mt",
        "-metadata", "all",
        str(tmp),
        "-o", str(out_file)
    ]

    # Copy metadata with exiftool (optional but recommended)
    exiftool_cmd = [
        "exiftool",
        "-tagsFromFile", str(path),
        "-overwrite_original",
        str(out_file)
    ]

    # Execute commands
    encode_OK = run_command(cwebp_cmd)
    metadata_OK = run_command(exiftool_cmd)

    # Print result
    msg = f"{GREEN}[OK]{RESET}" if encode_OK and metadata_OK else f"{YELLOW}[WARN]{RESET} One step failed!"
    print(msg)

    # Cleanup temp resized file — but don't delete the original image
    if str(tmp) != str(path) and os.path.exists(tmp):
        os.remove(tmp)

def get_args():
    parser = argparse.ArgumentParser(
        description="Image compressor using ffmpeg and libsvtav1 with standardized options."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Directory to process."
    )
    parser.add_argument(
        "-l",
        "--library",
        choices=["av1", "webp"],
        default="av1",
        help="Codec to use, some args may differ."
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="24",
        help="Compression quality (default: 24)."
    )
    parser.add_argument(
        "-p",
        "--preset",
        default="2",
        help="Compression efficiency level (default: 2)."
    )
    parser.add_argument(
        "-d",
        "--downscale",
        default="48",
        help="Downscale to x megapixels (default: 48)."
    )
    parser.add_argument(
        "-r",
        "--reverse",
        choices=["true", "false"],
        default="false",
        help="false: older to newer. Default: false"
    )

    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.input)
    library = args.library
    megapixels = args.downscale
    quality = args.quality
    preset = args.preset
    reverse_Order = False if args.reverse == "false" else True

    # Checks if input directory exists.
    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)

    # Selects all images in input files, sorts and then counts them.
    images = [f for f in base_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS and f.is_file()]
    images = sorted(images, reverse=reverse_Order)
    total = len(images)

    # Stops if no images were found.
    if total == 0:
        print("No pictures were found")
        return

    if library == "av1":
        # Creates output directory.
        output_dir = base_dir / ("libsvtav1-" + quality + "-" + preset + "-" + megapixels + "mp")
        output_dir.mkdir(exist_ok=True)
        
        # Processes each image, printing current/remaining items to console.
        for idx, img in enumerate(images, start=1):
            print(f"[{idx}/{total}] Processing: {img.name}")
            out_file = output_dir / (img.stem + ".avif")
            process_image(img, out_file, megapixels, quality, preset)
    
    if library == "webp":
        # Creates output directory.
        output_dir = base_dir / ("cwepb-" + quality + "-" + preset + "-" + megapixels + "mp")
        output_dir.mkdir(exist_ok=True)
        
        # Processes each image, printing current/remaining items to console.
        for idx, img in enumerate(images, start=1):
            print(f"[{idx}/{total}] Processing: {img.name}")
            out_file = output_dir / (img.stem + ".webp")
            process_image_webp(img, out_file, megapixels, quality, preset)

if __name__ == "__main__":
    main()