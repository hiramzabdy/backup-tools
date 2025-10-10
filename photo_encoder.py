import sys
import os
import math
import subprocess
import argparse
from pathlib import Path
from PIL import Image

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

#Extensions
IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.heic', ".heif", ".webp", ".avif"]

def get_megapixels(path: str) -> float:
    """
    Returns the megapixel count of the image.
    """
    with Image.open(path) as img:
        w, h = img.size
    return (w * h) / 1_000_000

def resize_image(path: str, megapixels: int) -> str:
    """
    Resizes an image to fit within the given megapixel count, preserving aspect ratio.
    Returns the path of the resized temp image.
    """
    with Image.open(path) as img:
        w, h = img.size
        current_mp = (int(w) * int(h))
        target_pixels = megapixels * 1_000_000

        # Prints current resolution
        xmp = current_mp / 1_000_000
        print(f"[Org Res] {w}x{h} [{xmp:.1f}MP]")

        # Returns if no need for resizing
        if current_mp <= target_pixels:
            return path

        # Scale factor to match target MP
        scale = math.sqrt(target_pixels / current_mp)
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Saves downscaled img to temp file
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        tmp_path = path + ".resized.png"
        resized.save(tmp_path, format="PNG")

        # Prints new resolution, returns downscaled img
        nmp = (new_w * new_h) / 1_000_000
        print(f"[New Res] {RED}{new_w}x{new_h}{RESET}, [{nmp:.1f}MP]")
        return tmp_path

def encode_image(path: str, out_file: str, megapixels: int, quality: int = 40, preset: int = 2) -> None:
    """
    Resizes image to target megapixels and encodes it as AVIF using avifenc.
    """
    tmp = resize_image(path, megapixels)

    # Build avifenc command
    cmd = [
        "avifenc",
        "--min", "0",
        "--max", str(quality),
        "--speed", str(preset),
        "--yuv", "420",            # change to 444 if you want better color
        tmp, out_file
    ]

    subprocess.run(cmd, check=True)

    # cleanup if we created a temp file
    if tmp != path and os.path.exists(tmp):
        os.remove(tmp)

def process_image(path, out_file, megapixels: int, quality=40, preset=2):
    """
    Resize and encode a single image into AVIF format using libsvtav1.
    Args:
        path (Path or str): Input image path.
        out_file (Path or str): Output file path (e.g. picture.avif).
        megapixels (int): Target megapixel cap (e.g. 12).
        quality (int): AVIF quantizer (lower = higher quality).
        preset (int): AVIF speed preset (0 = slowest, best compression).
    """

    # Returns if output file exists
    if out_file.exists():
        print(f"{YELLOW}[Skipping]{RESET}")
        return

    # Creates temp img for resizing to max MegaPixels if needed
    tmp = resize_image(str(path), megapixels)

    # Builds ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp),
        "-map_metadata", "0",             # copy metadata
        "-frames:v", "1",                 # single frame (treat as image)
        "-c:v", "libsvtav1",              # AV1 encoder
        "-crf", str(quality),             # quality
        "-preset", str(preset),           # speed/compression tradeoff
        "-pix_fmt", "yuv420p",            # yuv420p 8bits depth
        str(out_file)
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,    # silence stdout
            stderr=subprocess.PIPE        # capture stderr
        )
        print(f"{GREEN}[OK]{RESET}")      # success
    except subprocess.CalledProcessError as e:
        print(f"{RED}[ERROR]{RESET} during ffmpeg execution:")
        print(e.stderr.decode())

    # cleanup temp resize file if it was created
    if tmp != str(path) and os.path.exists(tmp):
        os.remove(tmp)

def get_args():
    parser = argparse.ArgumentParser(
        description="Image compressor using [] with standardized options."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Directory to process"
    )
    parser.add_argument(
        "-x",
        "--megapixels",
        default="12",
        help="Maximun size in MegaPixels per image (default: 12)"
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="40",
        help="Compression quality (default: 40)"
    )
    parser.add_argument(
        "-p",
        "--preset",
        default="2",
        help="Compression efficiency level (default: 2)"
    )

    args = parser.parse_args()
    return args

def main():
    args = get_args()
    base_dir = Path(args.input)
    megapixels = args.megapixels
    quality = args.quality
    preset = args.preset

    # Checks if input directory exists
    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)

    # Creates output directory
    output_dir = base_dir / (megapixels + "mp-" + quality + "q-" + preset + "p")
    output_dir.mkdir(exist_ok=True)

    # Selects all images in input files, sorts and then counts them
    images = [f for f in base_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS and f.is_file()]
    images = sorted(images)
    total = len(images)

    # Stops if no images were found
    if total == 0:
        print("No pictures were found")
        return
    
    # Processes each image, printing current/remaining items to console.
    for idx, img in enumerate(images, start=1):
        print(f"[{idx}/{total}] Processing: {img.name}")
        out_file = output_dir / (img.stem + ".avif")
        process_image(img, out_file, int(megapixels), quality, preset)

if __name__ == "__main__":
    main()