import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes
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

def validate_decode(output_path):
    """
    Tests video decoding to check integrity.
    """
    cmd = [
        'ffmpeg',
        '-v', 'error',
        '-c:v', "hevc",
        '-i', str(output_path),
        '-f', 'null',
        '-'
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode == 0:
        return True, None
    else:
        return False, proc.stderr.splitlines()

def delete_vids(vids):
    """
    Receives a list of videos, then iterates it and deletes them.
    Can be used to delete any files in a list, not only videos.
    """
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
        "-t",
        "--mode",
        choices=["time", "code", "both"],
        default="time",
        help="Type of test (default: time)"
    )
    parser.add_argument(
        "-d",
        "--delete",
        choices=["yes", "no"],
        default="no",
        help="Deletes videos that don't pass the integrity check (default: no)"
    )

    args = parser.parse_args()
    return args

def main():
    args = get_args()
    base_dir = Path(args.base)
    secondary_dir = Path(args.secondary)
    mode = args.mode
    margin = 0.5 # Time margin in seconds allowed between base and secondary videos. Default: 0.5
    delete = True if args.delete == "yes" else False

    if not secondary_dir.is_dir() or not base_dir.is_dir():
        print(f"One of the directories doesn't exist")
        sys.exit(1)

    coded_videos = sorted([f for f in secondary_dir.iterdir() if f.is_file()])    
    total = len(coded_videos)
    vids_To_Delete = []

    if total == 0:
        print("No videos were found in " + secondary_dir + ".")
        return

    for idx, vid in enumerate(coded_videos, start=1):
        print(f"[{idx}/{total}] ==> {vid.name}")

        # Time check
        if mode in ['time', 'both']:
            orig_stem = vid.stem
            orig = base_dir / (orig_stem + ".mp4")

            #Checks other extension in case .mp4 is not found.
            if not orig.exists():
                orig = base_dir / (orig_stem + ".3gp")
            if not orig.exists():
                orig = base_dir / (orig_stem + ".mkv")

            dur_secondary = get_duration(vid)
            dur_original = get_duration(orig)

            if dur_secondary is None:
                print(f"  {YELLOW}[WARN]{RESET} Couldn't get secondary video duration")
                vids_To_Delete.append(vid)
            elif dur_original is None:
                print(f"  {YELLOW}[WARN]{RESET} Original video not found.")
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

        # Decoding test
        if mode in ['code', 'both']:
            ok_decode, errors = validate_decode(vid)
            if ok_decode:
                print(f"  {GREEN}[OK]{RESET} Decoding successful.")
            else:
                print(f"  {RED}[ERROR]{RESET} Decoding failed:")
                for line in errors:
                    print(f"{line}")

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