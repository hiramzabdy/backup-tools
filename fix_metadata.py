import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

# Extensiones a procesar
IMAGE_EXTS = ['.jpg', '.jpeg', '.png', ".heic"]
VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi', ".3gp"]


def get_image_datetime(path: Path):
    """
    Gets DateTimeOriginal of image using exiftool, then returns it in YYYYMMDD_HHMMSS format.
    """
    cmd = [
        "exiftool",
        "-DateTimeOriginal",
        "-d", "%Y%m%d_%H%M%S",
        "-S", "-s",
        str(path)
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        out = proc.stdout.strip()
    except:
        pass
    return out or None

def get_video_creation(path: Path):
    """
    Extracts creation_time from a video using ffprobe and converts it from UTC to CDMX time (UTC-6).
    Returns the result in the format YYYYMMDD_HHMMSS.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format_tags=creation_time",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    ts = proc.stdout.strip()
    if not ts:
        return None

    try:
        # Example ffprobe timestamp: 2024-10-18T21:52:16.000000Z
        dt_utc = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        dt_cdmx = dt_utc.astimezone(timezone(timedelta(hours=-6)))
        return dt_cdmx.strftime("%Y%m%d_%H%M%S")
    except ValueError:
        return None

def is_within_margin(filename_ts: str, metadata_ts: str, max_seconds: int) -> bool:
    """
    Checks if difference between filename_ts and metadata_ts is within margin.
    Returns True if within margin, else False
    """
    # String to datetime.
    fmt = "%Y%m%d_%H%M%S"
    dt_file = datetime.strptime(filename_ts, fmt)
    dt_meta = datetime.strptime(metadata_ts, fmt)
    
    # Calculates absolute difference.
    delta = abs(dt_file - dt_meta)
    
    # Checks if longer than margin.
    if delta > timedelta(seconds=max_seconds):
        return False
    
    return True

def set_file_modified_time(path: Path, local_ts: str) -> bool:
    """
    Sets the file's mtime (and atime) to `local_ts`, interpreted as CDMX time (UTC-6).
    Returns:
        True if successful, False otherwise.
    """
    # 1) Parse the incoming local timestamp
    try:
        dt_local = datetime.strptime(local_ts, "%Y%m%d_%H%M%S")
    except ValueError:
        raise ValueError(f"Timestamp {local_ts!r} not in YYYYMMDD_HHMMSS format")

    # 2) Attach CDMX timezone (UTC-6) and convert to UTC
    tz_cdmx = timezone(timedelta(hours=-6))
    dt_aware = dt_local.replace(tzinfo=tz_cdmx)
    
    # 3) Get POSIX timestamp (seconds since epoch)
    #    .timestamp() on an aware datetime gives the correct UTC-based epoch
    ts = dt_aware.timestamp()

    # 4) Apply to both atime and mtime
    try:
        os.utime(path, (ts, ts))
        return True
    except Exception:
        return False

def set_video_date(path: Path, local_ts: str) -> bool:
    """
    Overwrite the "creation_time" metadata of a video file to match "local_ts" in CDMX time (UTC-6).
    Returns True on success, False on failure.
    """

    # Parses local timestamp.
    try:
        dt_local = datetime.strptime(local_ts, "%Y%m%d_%H%M%S")
    except ValueError:
        raise ValueError(f"Timestamp {local_ts!r} not in YYYYMMDD_HHMMSS")
    
    # Converts from CDMX (UTC-6) to UTC.
    tz_cdmx = timezone(timedelta(hours=-6))
    dt_utc  = dt_local.replace(tzinfo=tz_cdmx).astimezone(timezone.utc)
    utc_str = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Build a temp filename in the same folder.
    tmp_name = f".{path.stem}.tmp{path.suffix}"
    tmp_path = path.parent / tmp_name
    
    # Remux with FFmpeg, injecting new creation_time.
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(path),
        "-c", "copy",
        "-map_metadata", "0",
        "-metadata", f"creation_time={utc_str}",
        str(tmp_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not tmp_path.exists():
        if tmp_path.exists():
            tmp_path.unlink()
        return False
    
    # Atomically replaces original
    os.replace(str(tmp_path), str(path))
    set_file_modified_time(path, local_ts)
    return True

def set_image_date(path: Path, local_ts: str) -> bool:
    """
    Sets all the important EXIF date tags of an image (CreateDate, DateTimeOriginal, ModifyDate)
    to `local_ts` (CDMX local time).
    Optionally also updates the file's modification time to match.

    Returns:
        True if ExifTool (and utime, if requested) succeed, False otherwise.
    """
    # Parses incoming timestamp
    try:
        dt = datetime.strptime(local_ts, "%Y%m%d_%H%M%S")
    except ValueError:
        raise ValueError(f"Timestamp {local_ts!r} not in YYYYMMDD_HHMMSS format")

    # Reformats to EXIF’s "YYYY:MM:DD HH:MM:SS"
    exif_ts = dt.strftime("%Y:%m:%d %H:%M:%S")

    # 3) Builds ExifTool command
    cmd = [
        "exiftool",
        "-overwrite_original",
        f"-AllDates={exif_ts}",
    ]

    # Also sets the file’s modify timestamp.
    cmd.append(f"-FileModifyDate={exif_ts}")
    cmd.append(str(path))

    # 4) Runs ExifTool.
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode == 0

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
        "-t",
        "--metadata",
        default="name",
        choices=["name", "exif"],
        help="Metadata to keep (default: name)."
    )
    parser.add_argument(
        "-f",
        "--fix",
        default="false",
        choices=["true", "false"],
        help="Fix metadata or naming date (default False)."
    )

    args = parser.parse_args()
    return args

def main():
    # Assing ars to variables.
    args = get_args()
    base_dir = Path(args.input)
    date_to_keep = args.metadata
    fix = False if args.fix == "false" else True

    # Lists containing unique dates for names and exif, used to avoid overwriting files.
    pathUniqueDates = []
    metaUniqueDates = []

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

        # Print current index, total files and current file name.
        print(f"[{idx}/{total}] {item.name}")

        # Extracts date from name and metadata in YYYYMMDD_HHMMSS format.
        name_date = item.stem[:15]
        meta_date = get_image_datetime(item) if item.suffix.lower() in IMAGE_EXTS else get_video_creation(item)
        margin_in_seconds = 30 # Used to compare both dates.

        # Checks if there is a mismatch between name and metadata dates.
        try:
            is_Ok = is_within_margin(name_date, meta_date, max_seconds=margin_in_seconds)
        except:
            is_Ok = False

        # Case 1: No metadata at all => Appends name date.
        if not meta_date:
            print(f"{YELLOW}[WARN]{RESET} No metadata was found")
            if fix:
                print(f"Fixing... {item} => {name_date}")
                if item.suffix.lower() in IMAGE_EXTS:
                    set_image_date(item, name_date)
                else:
                    set_video_date(item, name_date)
            continue

        # Used to avoid overwriting a file that already exists.
        pathUniqueDates.append(name_date)

        # Case 1: Dates differ => Keeps only selected date.
        if not is_Ok:
            print(f"{RED}[ERROR]{RESET} Metadata differs.\n-Name: {name_date}\n-Meta: {meta_date}\n")
            if fix:
                print(f"Fixing... {item.name}")
                if item.suffix.lower() in IMAGE_EXTS:
                    if date_to_keep == "name":
                        set_image_date(item, name_date)
                    elif meta_date not in pathUniqueDates and meta_date not in metaUniqueDates:
                        metaUniqueDates.append(meta_date)
                        set_image_date(item, meta_date)
                    else:
                        print(f"Ya hay un archivo con el nombre {meta_date}")
                else:
                    if date_to_keep == "name":
                        set_video_date(item, name_date)
                    elif meta_date not in pathUniqueDates and meta_date not in metaUniqueDates:
                        set_video_date(item, meta_date)


if __name__ == '__main__':
    main()