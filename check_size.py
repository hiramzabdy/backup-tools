import sys
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'


def bytes_to_mb(b):
    return b / (1024 * 1024)

def format_signed(value, unit=''):
    sign = '+' if value >= 0 else '-'
    return f"{sign}{abs(value):.1f}{unit}"

def delete_vids(vids):
    for file_path in vids:
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
        choices=["yes", "no"],
        default="no",
        help="Delete videos bigger than margin (default: no)"
    )

    args = parser.parse_args()
    return args

def main():
    args = get_args()
    base_dir = Path(args.base)
    second_dir = Path(args.secondary)
    margin = int(args.margin)
    delete = True if args.delete == "yes" else False

    if not base_dir.is_dir() or not second_dir.is_dir():
        print(f"One of the directories doesn't exist")
        sys.exit(1)

    second_dir_vids = sorted([f for f in second_dir.iterdir() if f.is_file()])
    total = len(second_dir_vids)
    if total == 0:
        print("No videos were found")
        return

    all_original_size = 0
    all_coded_size = 0
    vids_To_Delete = []

    for idx, vid in enumerate(second_dir_vids, start=1):

        orig_stem = vid.stem
        orig = base_dir / (orig_stem + ".mp4")

        # Checks other extension in case .mp4 is not found.
        if not orig.exists():
            orig = base_dir / (orig_stem + ".3gp")
        if not orig.exists():
            orig = base_dir / (orig_stem + ".mkv")

        size_orig = orig.stat().st_size if orig.exists() else None
        size_sec = vid.stat().st_size

        if size_orig is None:
            print(f"  {YELLOW}[WARN]{RESET} Original video not found.")
            continue

        mb_orig = bytes_to_mb(size_orig)
        mb_sec = bytes_to_mb(size_sec)
        diff_mb = mb_sec - mb_orig
        pct = (diff_mb / mb_orig * 100) if mb_orig > 0 else 0
        bigger_Than_Margin = pct >= margin

        status = f"{GREEN}[OK]{RESET}" if not bigger_Than_Margin else f"{YELLOW}[WARN]{RESET}"


        # Formats output
        print(
            f"[{idx}/{total}] - {orig_stem} - {mb_orig:.1f} MB => {mb_sec:.1f} MB, Δ {format_signed(diff_mb, ' MB')} ({format_signed(pct, '%')}), {status}"
        )
        all_original_size += mb_orig
        all_coded_size += mb_sec
        all_diff_percentage = (all_coded_size/all_original_size-1)*100

        if bigger_Than_Margin:
            vids_To_Delete.append(vid)

    print(f"\nOriginal size: {all_original_size:.1f} MB\nNew size: {all_coded_size:.1f} MB\nDiference: {(all_original_size-all_coded_size):.1f} MB ({all_diff_percentage:.1f}%)\n")
    print(f"Videos bigger than margin ({margin}%): {len(vids_To_Delete)}")

    # Deleting logic
    if delete:
        if vids_To_Delete:
            print(f"{RED}\nDeleting the following videos:{RESET}")
            for video in vids_To_Delete:
                print(video.name)
            confirm = input("\nDo you want to delete them? (y/N): ").strip().lower()
            if confirm == "y":
                delete_vids(vids_To_Delete)
            else:
                print("Deletion cancelled")

if __name__ == '__main__':
    main()