import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes.
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def seconds_to_mmss(seconds):
    """
    Receives a duration in seconds (possibly greater than 60) and returns it in mm:ss format.
    """
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def get_duration(path):
    """
    Returns video duration in seconds as a float.
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return None

def validate_decode(path):
    """
    Tests video decoding to check integrity of all streams.
    Returns (True, None) if decodable, otherwise (False, list_of_errors)
    """
    cmd = [
        "ffmpeg",
        "-v", "error",      # Show only errors
        "-xerror",          # Stop on first error and set nonzero exit code
        "-i", str(path),    # Input file
        "-map", "0",        # Include all streams (video, audio, subtitles)
        "-f", "null", "-",  # Decode everything but discard output
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )

    if proc.returncode == 0:
        return (True, None)
    else:
        # Split stderr into lines, removing empty ones
        errors = [line for line in proc.stderr.splitlines() if line.strip()]
        return (False, errors)

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
        description="Checks integrity of videos in a directory, taking originals as reference"
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
        help="Secondary directory, integrity checks"
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["time", "decode", "both"],
        default="time",
        help="Type of test (default: time)"
    )
    parser.add_argument(
        "-d",
        "--delete",
        choices=["true", "false"],
        default="false",
        help="Deletes videos that don't pass the integrity check (default: no)"
    )

    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.base)
    secondary_dir = Path(args.secondary)
    mode = args.mode
    margin = 0.5 # Time margin in seconds allowed between base and secondary videos.
    delete = True if args.delete == "true" else False

    # Checks if both directories exist.
    if not secondary_dir.is_dir() or not base_dir.is_dir():
        print(f"One of the directories doesn't exist")
        sys.exit(1)

    # Gets all videos in secondary directory and sorts them.
    coded_videos = sorted([f for f in secondary_dir.iterdir() if f.is_file()])    
    total = len(coded_videos)

    # Returns if no videos were found.
    if total == 0:
        print("No videos were found in " + secondary_dir + ".")
        return
    
    # List with videos that don't pass the test, used to delete them.
    vids_To_Delete = []

    # Iterates each video.
    for idx, vid in enumerate(coded_videos, start=1):
        print(f"[{idx}/{total}] ==> {vid.name}")

        # Time check.
        if mode in ['time', 'both']:
            orig_stem = vid.stem
            orig = base_dir / (orig_stem + ".mp4")

            # Checks other extension in case .mp4 is not found.
            if not orig.exists():
                orig = base_dir / (orig_stem + ".3gp")
            if not orig.exists():
                orig = base_dir / (orig_stem + ".mkv")

            # Exact duration of both videos.
            dur_secondary = get_duration(vid)
            dur_original = get_duration(orig)

            # Case 1: Couldn't get secondary video duration => Delete.
            if dur_secondary is None:
                print(f"  {YELLOW}[WARN]{RESET} Couldn't get secondary video duration")
                vids_To_Delete.append(vid)
            # Case 2: Original wasn't found => Prints alert.
            elif dur_original is None:
                print(f"  {YELLOW}[WARN]{RESET} Original video not found.")
            # Case 3: Compares videos duration => If mismatch, delete.
            else:
                diff = abs(dur_secondary - dur_original)
                mmss_original = seconds_to_mmss(dur_original)
                mmss_secondary = seconds_to_mmss(dur_secondary)
                if diff <= margin:
                    print(f"  {GREEN}[OK]{RESET} Duraction OK (Original: {mmss_original}, Secondary: {mmss_secondary}).")
                else:
                    print(
                        f"{RED}[ERROR]{RESET} Duration differs in more than {margin}s."
                        f"Original: {mmss_original}, Secondary: {mmss_secondary}."
                    )
                    vids_To_Delete.append(vid)

        # Decoding test.
        if mode in ['code', 'both']:
            ok_decode, errors = validate_decode(vid)
            if ok_decode:
                print(f"  {GREEN}[OK]{RESET} Decoding successful.")
            else:
                print(f"  {RED}[ERROR]{RESET} Decoding failed:")
                for line in errors:
                    print(f"{line}")
                # Appends video to vids_To_Delete only if it hasn't been appended in the time check.
                if vid not in vids_To_Delete:
                    vids_To_Delete.append(vid)

    # Deleting logic.
    if delete:
        if vids_To_Delete:
            print(f"{RED}\nDeleting the following videos:{RESET}")
            for video in vids_To_Delete:
                print(video.name)
            confirm = input("\nDo you want to delete them? (y/N): ").strip().lower()
            if confirm == "y":
                delete_files(vids_To_Delete)
            else:
                print("Deletion cancelled.")

if __name__ == '__main__':
    main()