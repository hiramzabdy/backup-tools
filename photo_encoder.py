import sys
import os
import math
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageOps
from tempfile import NamedTemporaryFile
Image.MAX_IMAGE_PIXELS = 200_000_000

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

def resize_image(path: Path, megapixels: str, max_dim: int) -> Path:
    """
    Resizes an image to fit within the given megapixel count, preserving aspect ratio.
    Returns the path of the img temp image.
    """
    try:
        with Image.open(path) as img:
            # Rotates image.
            img = ImageOps.exif_transpose(img)

            # Parses megapixels as int for calculations.
            target_megapixels = int(megapixels)
            target_pixels = target_megapixels * 1_000_000

            # Gets original size (w, h, pixels).
            w, h = img.size
            orig_pixels = (int(w) * int(h))
            orig_megapixels = orig_pixels / 1_000_000

            # Scales width and heigth to match target MP.
            scale = 1 
            if orig_pixels > target_pixels:
                scale = math.sqrt(target_pixels / orig_pixels)

            # Constraint: Max dimensions for some encoders
            if max_dim != 0 and max(w * scale, h * scale) > max_dim:
                scale = min(scale, max_dim / max(w, h))

            new_w = int(w * scale)
            new_h = int(h * scale)

            # Forces Even Dimensions (Critical for FFmpeg/yuv420p)
            if new_w % 2 != 0: new_w -= 1
            if new_h % 2 != 0: new_h -= 1
            
            if (new_w, new_h) != img.size:
                img = img.resize((new_w, new_h), Image.LANCZOS)

            # Prints new resolution.
            new_megapixels = (new_w * new_h) / 1_000_000
            if scale != 1:
                print(f"[Res] {w}x{h} [{orig_megapixels:.1f}MP] => {YELLOW}{new_w}x{new_h}{RESET} [{new_megapixels:.1f}MP]")
            else:
                print(f"[Res] {w}x{h} [{orig_megapixels:.1f}MP]")

            # Alpha-safe format selection and temp save.
            has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)

            # Ensure a PNG-compatible mode
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if has_alpha else "RGB")

            # Create temp file NEXT TO ORIGINAL (same filesystem)
            with NamedTemporaryFile(
                suffix=".png",
                dir=path.parent / ("temp"),
                delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)


            # Lossless temp save
            img.save(
                tmp_path,
                format="PNG",
                optimize=False  # Faster, avoids extra CPU
            )

            return Path(tmp_path)
        
    # If process fails, returns the original Path.
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

def process_image(path: Path, out_file: Path, megapixels: str, quality: str, preset: str, max_dim: int):
    """
    Resizes and encodes a single image into AVIF or WEBP format.
    """

    # Returns if output file exists.
    if out_file.exists():
        print(f"{YELLOW}[Skipping]{RESET} Output file exists.")
        return

    # Creates temp img for resizing to max megapixels if needed.
    tmp = resize_image(path, megapixels, max_dim)

    # Create a temp output file IN THE SAME DIRECTORY
    with NamedTemporaryFile(
        suffix=out_file.suffix,
        dir=path.parent / ("temp"),
        delete=False
    ) as tmp_out:
        tmp_out_path = Path(tmp_out.name)

    # Builds cwebp command.
    cwebp_cmd = [
        "cwebp",
        "-q", str(quality),
        "-m", str(preset),
        "-pass", "10",
        "-mt",
        "-metadata", "all",
        str(tmp),
        "-o", str(tmp_out_path)
    ]

    # Builds ffmpeg command to encode image.
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp),
        "-map", "0",                      # Copy metadata.
        "-frames:v", "1",                 # Single frame (treat as image).
        "-c:v", "libsvtav1",              # AV1 encoder.
        "-crf", str(quality),             # Quality.
        "-preset", str(preset),           # Speed/compression tradeoff.
        str(tmp_out_path)
    ]

    # Builds exiftool command to copy metadata (in case image is img).
    exiftool_cmd = [
            "exiftool",
            "-tagsFromFile", str(path),
            "-overwrite_original",
            "-Orientation=",     # DELETE orientation tag from output
            "-ThumbnailImage=",  # Remove embedded thumbnails (save space)
            str(out_file)
    ]

    # Executes commands.
    encode_OK = run_command(cwebp_cmd) if out_file.suffix == ".webp" else run_command(ffmpeg_cmd)
    encode_msg = f"{GREEN}[OK]{RESET} Encode" if encode_OK else f"{RED}[ERROR]{RESET} Encode failed"
    print(encode_msg)

    # Delete first temp file.
    if tmp != path and tmp.exists():
        tmp.unlink(missing_ok=True)

    # Delete second temp file on error.
    if not encode_OK:
        tmp_out_path.unlink(missing_ok=True)
        return
    
    # Write second temp file to output dir.
    tmp_out_path.replace(out_file)
    tmp_out_path.unlink(missing_ok=True)

    # Copy metadata to final file.
    metadata_OK = run_command(exiftool_cmd)
    metadata_msg = f"{GREEN}[OK]{RESET} Metadata" if metadata_OK else f"{RED}[ERROR]{RESET} Metadata copy failed"
    print(metadata_msg + "\n")

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
        choices=["avif", "webp"],
        default="avif",
        help="Library (format) to use"
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
        default="12",
        help="Downscale to x megapixels (default: 12)."
    )
    parser.add_argument(
        "-r",
        "--reverse",
        choices=["true", "false"],
        default="false",
        help="true: newer to older. Default: false"
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
    max_dim = 8704 if library == "avif" else 16382

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
    
    # Creates temp dir.
    output_dir = base_dir / "temp"
    output_dir.mkdir(exist_ok=True)

    # Processing branch for AVIF.
    if library == "avif":
        # Creates output directory.
        output_dir = base_dir / ("avif-" + quality + "q-" + preset + "p-" + megapixels + "mp")
        output_dir.mkdir(exist_ok=True)
        
        # Processes each image, printing current/remaining items to console.
        for idx, img in enumerate(images, start=1):
            print(f"[{idx}/{total}] Processing: {img.name}")
            out_file = output_dir / (img.stem + ".avif")
            process_image(img, out_file, megapixels, quality, preset, max_dim)
    
    # Processing branch for WEBP
    if library == "webp":
        # Creates output directory.
        output_dir = base_dir / ("webp-" + quality + "q-" + preset + "p-" + megapixels + "mp")
        output_dir.mkdir(exist_ok=True)
        
        # Processes each image, printing current/remaining items to console.
        for idx, img in enumerate(images, start=1):
            print(f"[{idx}/{total}] Processing: {img.name}")
            out_file = output_dir / (img.stem + ".webp")
            process_image(img, out_file, megapixels, quality, preset, max_dim)

if __name__ == "__main__":
    main()