import sys
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def format_signed(value, unit=''):
    sign = '+' if value >= 0 else '-'
    return f"{sign}{abs(value):.1f}{unit}"

def delete_files(files):
    """
    Receives a list of videos, then iterates it and deletes them.
    Can be used to delete any files in a list, not only videos.
    """
    for file_path in files:
        path = Path(file_path)
        try:
            path.unlink()
            print(f"Deleted: {file_path}")
        except FileNotFoundError:
            print(f"Not found: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

def get_args():
    parser = argparse.ArgumentParser(
        description="Compares file size of videos in two directories"
    )

    parser.add_argument(
        "-b",
        "--base",
        type=Path,
        required=True,
        help="Base directory, taken as reference"
    )
    parser.add_argument(
        "-s",
        "--secondary",
        type=Path,
        required=True,
        help="Secondary directory, quality checks"
    )
    parser.add_argument(
        "-m",
        "--margin",
        default="-50",
        help="File size reduction target percentage (default: -50)"
    )
    parser.add_argument(
        "-d",
        "--delete",
        choices=["true", "false"],
        default="false",
        help="Delete videos bigger than margin (default: false)"
    )

    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.base)
    second_dir = Path(args.secondary)
    margin = int(args.margin)
    delete = True if args.delete == "true" else False

    # Checks if both directories exist.
    if not base_dir.is_dir() or not second_dir.is_dir():
        print(f"One of the directories doesn't exist")
        sys.exit(1)

    # Gets all videos in secondary directory and sorts them.
    second_dir_vids = sorted([f for f in second_dir.iterdir() if f.is_file()])
    total = len(second_dir_vids)

    # Returns if no videos were found.
    if total == 0:
        print("No videos were found")
        return

    # Total size in MB of videos in both directories.
    all_original_size = 0
    all_coded_size = 0

    # List of videos to delete.
    vids_To_Delete = []

    # Iterates each video.
    for idx, vid in enumerate(second_dir_vids, start=1):
        orig_stem = vid.stem
        orig = base_dir / (orig_stem + ".mp4")

        # Checks other extension in case .mp4 is not found.
        if not orig.exists():
            orig = base_dir / (orig_stem + ".3gp")
        if not orig.exists():
            orig = base_dir / (orig_stem + ".mkv")

        # Gets video size in bytes.
        size_orig = orig.stat().st_size if orig.exists() else None
        size_sec = vid.stat().st_size

        # Returns if original video wasn't found.
        if size_orig is None:
            print(f"{YELLOW}[WARN]{RESET} Original video not found.")
            continue

        # Converts Bytes to Megabytes
        mb_orig = size_orig/(1000 * 1000)
        mb_sec = size_sec/(1000 * 1000)

        # Compares both videos sizes.
        diff_mb = mb_sec - mb_orig
        pct = (diff_mb / mb_orig * 100) if mb_orig > 0 else 0
        bigger_Than_Margin = pct >= margin

        # Green [OK] if not bigger, else yellow [WARN].
        status = f"{GREEN}[OK]{RESET}" if not bigger_Than_Margin else f"{YELLOW}[WARN]{RESET}"

        # Formats output
        print(
            f"[{idx}/{total}] {orig_stem} - {mb_orig:.1f} MB => {mb_sec:.1f} MB, Δ {format_signed(diff_mb, ' MB')} ({format_signed(pct, '%')}) {status}"
        )

        # Adds up the size of all videos so far.
        all_original_size += mb_orig
        all_coded_size += mb_sec

        # Appends video to vids_To_Delete if bigger than margin.
        if bigger_Than_Margin:
            vids_To_Delete.append(vid)

    # Total difference in percentage.
    all_diff_percentage = (all_coded_size/all_original_size-1)*100

    # Print summary.
    print(f"\nOrg size: {all_original_size:.1f} MB\nNew size: {all_coded_size:.1f} MB\nDifference: {(all_original_size-all_coded_size):.1f} MB ({all_diff_percentage:.1f}%)\n")
    print(f"Videos bigger than margin ({margin}%): {len(vids_To_Delete)}")

    # Deleting logic
    if delete:
        if vids_To_Delete:
            print(f"{RED}\nDeleting the following videos:{RESET}")
            for video in vids_To_Delete:
                print(video.name)
            confirm = input("\nDo you want to delete them? (y/N): ").strip().lower()
            if confirm == "y":
                delete_files(vids_To_Delete)
            else:
                print("Deletion cancelled")

if __name__ == '__main__':
    main()