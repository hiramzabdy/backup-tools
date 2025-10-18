import os
import re
import sys
import argparse
from pathlib import Path

# ANSI color codes.
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

# Extensions to process.
IMAGE_EXTS = [".jpg", ".jpeg", ".heic", ".heif", ".webp", ".avif", ".png"]
VIDEO_EXTS = [".mp4", ".mov", ".mkv", ".avi", ".3gp"]

def standardize_filename(path: Path, keep_app_name: bool = False) -> Path:
    """
    Renames an image or video file to the format:
        YYYYMMDD_HHMMSS[_optional].ext

    - Extracts the first 14-digit sequence starting with '2' (year 2000+)
    - Optionally keeps app name (text right after the date)
    - Returns the new Path (doesn't modify file on disk)
    """

    name = path.stem
    ext = path.suffix.lower()

    # Extract digits, ignoring separators (e.g., '-' or '_')
    digits = re.sub(r'\D', '', name)

    # Find first 14-digit sequence starting with 2
    match = re.search(r'2\d{13}', digits)
    if not match:
        raise ValueError(f"No valid date found in filename: {path.name}")

    date_digits = match.group()
    date_str = f"{date_digits[:8]}_{date_digits[8:]}"  # YYYYMMDD_HHMMSS

    # Extract optional app name (text after date)
    optional = ""
    if keep_app_name:
        # Reconstruct simplified version of the "tail" after the date
        post_date = name[name.find(date_digits[-6:]) + len(date_digits[-6:]):]
        post_date = re.sub(r"[^A-Za-z]+", "", post_date)  # keep only letters
        if post_date:
            optional = f"_{post_date[:20]}"  # limit length

    new_name = f"{date_str}{optional}{ext}"
    return path.with_name(new_name)

def get_args():
    parser = argparse.ArgumentParser(
        description="Metadata fix using filename or exif info."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Directory to process."
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["simple", "full"],
        default="simple",
        help="Keeps only date or date plus app name if available (default: simple)"
    )
    args = parser.parse_args()
    return args

def main():
    # Assing args to variables.
    args = get_args()
    base_dir = Path(args.input)
    mode = False if args.mode == "simple" else True

    # Checks if dir exists.
    if not base_dir.is_dir():
        print(f"Input directory doesn't exist.")
        sys.exit(1)

    # Sorts photos and videos by name.
    files = sorted([f for f in base_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS + VIDEO_EXTS])
    total = len(files)

    # Checks if there are compatible files in dir.
    if total == 0:
        print("No compatible files in selected directory.")
        return
    
    # Iterates each file and display total files count.
    for idx, item in enumerate(files, start=1):
        print(f"[{idx}/{total}] {item.name}")

        try:
            new_path = standardize_filename(item, mode)
        except ValueError as e:
            print(f"{RED}[ERROR]{RESET} Couldn't get standarized name.")
            continue

        # Skips if already renamed or same name.
        if new_path.name == item.name:
            print(f"{YELLOW}[Skipping]{RESET} Already standardized.")
            continue

        # If file with same name exists on disk, append counter (_1, _2, etc.)
        counter = 1
        final_path = new_path
        while final_path.exists():
            final_path = new_path.with_stem(f"{new_path.stem}_{counter}")
            counter += 1

        # Perform rename safely
        try:
            item.rename(final_path)
            print(f"{GREEN}[OK]{RESET} Renamed to {final_path.name}.")
        except Exception as e:
            print(f"{RED}[ERROR]{RESET} Failed to rename {item.name}: {e}")

if __name__ == "__main__":
    main()