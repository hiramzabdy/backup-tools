import sys
import os
import math
import subprocess
import argparse
from pathlib import Path
from PIL import Image

# ANSI color codes.
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# Extensions.
IMAGE_EXTS = ['.jpg', '.jpeg', '.heic', ".heif", ".webp", ".avif"] # Avoided .png as it can affect script dowscaling.

# Notes:
"""
For Orignal Quality (Pretty much unnoticeable compression):
--quality 24 --preset 2 --megapixels 48

For Storage Savings (Somewhat noticeable difference):
--quality 32 --preset 2 --megapixels 20

For EXTREME Storage Savings (Noticeable difference, still not radio-like photos):
--quality 40 --preset 2 --megapixels 12

1. Running multiple instances of the script with the same params(running on the same output directory)
might result in encoding errors.
"""

def resize_image(path: Path, megapixels: str) -> str:
    """
    Resizes an image to fit within the given megapixel count, preserving aspect ratio.
    Returns the path of the resized temp image.
    """
    with Image.open(path) as img:
        # Parses megapixels as int for calculations, and path to str.
        megapixels = int(megapixels)
        path = str(path)

        # Converts target megapixels to pixels.
        target_pixels = megapixels * 1_000_000

        # Gets original size (w, h, pixels).
        w, h = img.size
        pixels = (int(w) * int(h))

        # Prints original resolution.
        megapixels = pixels / 1_000_000
        print(f"[Org Res] {w}x{h} [{megapixels:.1f}MP]")

        # Returns if no need for resizing.
        if pixels <= target_pixels:
            return path

        # Scales width and heigth to match target MP.
        scale = math.sqrt(target_pixels / pixels)
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Prints new resolution.
        new_megapixels = (new_w * new_h) / 1_000_000
        print(f"[New Res] {RED}{new_w}x{new_h}{RESET}, [{new_megapixels:.1f}MP]")

        # Saves downscaled img to temp file, then returns it.
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        tmp_path = path + ".resized.png"
        resized.save(tmp_path, format="PNG")
        return tmp_path

def process_image(path: Path, out_file: Path, megapixels: str, quality: str, preset: str):
    """
    Resize and encode a single image into AVIF format using libsvtav1.
    Args:
        path (Path or str): Input image path.
        out_file (Path or str): Output file path (e.g. picture.avif).
        megapixels (int): Target megapixel cap (e.g. 12).
        quality (int): AVIF quantizer (lower = higher quality).
        preset (int): AVIF speed preset (0 = slowest, best compression).
    """

    # Returns if output file exists.
    if out_file.exists():
        print(f"{YELLOW}[Skipping]{RESET}")
        return

    # Creates temp img for resizing to max megapixels if needed.
    tmp = resize_image(path, megapixels)

    # Builds ffmpeg command.
    cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp),
        "-map_metadata", "0",             # Copy metadata.
        "-frames:v", "1",                 # Single frame (treat as image).
        "-c:v", "libsvtav1",              # AV1 encoder.
        "-crf", str(quality),             # Quality.
        "-preset", str(preset),           # Speed/compression tradeoff.
        "-pix_fmt", "yuv420p",            # yuv420p 8bits depth.
        str(out_file)
    ]

    # Runs ffmpeg command.
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,    # Silence stdout.
            stderr=subprocess.PIPE        # Capture stderr.
        )
        print(f"{GREEN}[OK]{RESET}")      # Success.
    except subprocess.CalledProcessError as e: # Handles error.
        print(f"{RED}[ERROR]{RESET} during ffmpeg execution:")
        print(e.stderr.decode())

    # cleanup temp resize file if it was created.
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
        "-x",
        "--megapixels",
        default="48",
        help="Maximun size in MegaPixels per image (default: 48)."
    )

    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.input)
    megapixels = args.megapixels
    quality = args.quality
    preset = args.preset

    # Checks if input directory exists.
    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)

    # Creates output directory.
    output_dir = base_dir / (megapixels + "mp-" + quality + "q-" + preset + "p")
    output_dir.mkdir(exist_ok=True)

    # Selects all images in input files, sorts and then counts them.
    images = [f for f in base_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS and f.is_file()]
    images = sorted(images)
    total = len(images)

    # Stops if no images were found.
    if total == 0:
        print("No pictures were found")
        return
    
    # Processes each image, printing current/remaining items to console.
    for idx, img in enumerate(images, start=1):
        print(f"[{idx}/{total}] Processing: {img.name}")
        out_file = output_dir / (img.stem + ".avif")
        process_image(img, out_file, megapixels, quality, preset)

if __name__ == "__main__":
    main()