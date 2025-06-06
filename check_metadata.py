import sys
import os
import tempfile
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
    Extrae DateTimeOriginal de la imagen usando exiftool en formato YYYYMMDD_HHMMSS
    """
    cmd = [
        'exiftool',
        '-DateTimeOriginal',
        '-d', '%Y%m%d_%H%M%S',
        '-S', '-s',
        str(path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    out = proc.stdout.strip()
    return out or None

def get_video_creation(path: Path):
    """
    Extracts creation_time from a video using ffprobe and converts it from UTC to CDMX time (UTC-6).
    Returns the result in the format YYYYMMDD_HHMMSS.
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'format_tags=creation_time',
        '-of', 'default=noprint_wrappers=1:nokey=1',
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

def get_video_duration_seconds(path: Path) -> int:
    """
    Returns the duration of a video file in whole seconds using ffprobe.
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    output = proc.stdout.strip()
    try:
        duration = float(output)
        return int(round(duration))
    except (ValueError, TypeError):
        return 0  # Return 0 if duration can't be parsed

def is_within_margin(filename_ts: str, metadata_ts: str, max_seconds: int = None, max_hours: int = None) -> bool:
    """
    Comprueba si la diferencia entre filename_ts y metadata_ts
    está dentro de los márgenes dados (segundos y/o horas).
    
    Params:
      - filename_ts: 'yyyymmdd_HHMMSS' (e.g. '20210525_153020')
      - metadata_ts: idem
      - max_seconds: si se especifica, margen máximo en segundos
      - max_hours: si se especifica, margen máximo en horas
      
    Devuelve True si la diferencia está dentro de ambos márgenes (los que hayas pasado).
    """
    # 1) Convertir strings a datetime
    fmt = "%Y%m%d_%H%M%S"
    dt_file = datetime.strptime(filename_ts, fmt)
    dt_meta = datetime.strptime(metadata_ts, fmt)
    
    # 2) Calcular diferencia absoluta
    delta = abs(dt_file - dt_meta)
    
    # 3) Construir timedelta con tus márgenes
    if max_seconds is not None:
        if delta > timedelta(seconds=max_seconds):
            return False
    if max_hours is not None:
        if delta > timedelta(hours=max_hours):
            return False
    
    return True

def set_video_creation_time(path: Path, local_ts: str) -> bool:
    """
    Overwrites the 'creation_time' metadata of a video file so that
    it matches `local_ts` interpreted as CDMX time (UTC-6).

    Args:
        path: Path to the input video (will be replaced in-place).
        local_ts: Timestamp in 'YYYYMMDD_HHMMSS' format, in CDMX time.

    Returns:
        True on success, False on failure.
    """
    # 1) Parse the incoming local timestamp
    try:
        dt_local = datetime.strptime(local_ts, "%Y%m%d_%H%M%S")
    except ValueError:
        raise ValueError(f"Timestamp {local_ts!r} not in YYYYMMDD_HHMMSS")
    
    # 2) Convert from CDMX (UTC-6) to UTC
    tz_cdmx = timezone(timedelta(hours=-6))
    dt_utc  = dt_local.replace(tzinfo=tz_cdmx).astimezone(timezone.utc)
    utc_str = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 3) Build a temp filename in the same folder
    tmp_name = f".{path.stem}.tmp{path.suffix}"
    tmp_path = path.parent / tmp_name
    
    # 4) Remux with FFmpeg, injecting new creation_time
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
    
    # 5) Atomically replace original
    os.replace(str(tmp_path), str(path))
    set_file_modified_time(path, local_ts)
    return True

def set_image_all_dates(path: Path, local_ts: str, adjust_file_mtime: bool = False, overwrite: bool = False) -> bool:
    """
    Sets all the important EXIF date tags of an image (CreateDate, DateTimeOriginal, ModifyDate)
    to `local_ts` (CDMX local time).
    Optionally also updates the file's modification time to match.

    Args:
        path: Path to the image file.
        local_ts: Timestamp in 'YYYYMMDD_HHMMSS' format (CDMX local time).
        adjust_file_mtime: If True, also sets the filesystem mtime to the same timestamp.

    Returns:
        True if ExifTool (and utime, if requested) succeed, False otherwise.
    """
    # 1) Parse incoming timestamp
    try:
        dt = datetime.strptime(local_ts, "%Y%m%d_%H%M%S")
    except ValueError:
        raise ValueError(f"Timestamp {local_ts!r} not in YYYYMMDD_HHMMSS format")

    # 2) Reformat to EXIF’s "YYYY:MM:DD HH:MM:SS"
    exif_ts = dt.strftime("%Y:%m:%d %H:%M:%S")

    # 3) Build ExifTool command
    cmd = [
        "exiftool",
        "-overwrite_original",
        f"-AllDates={exif_ts}",
    ]
    if adjust_file_mtime:
        # Also set the file’s modify timestamp
        cmd.append(f"-FileModifyDate={exif_ts}")
    cmd.append(str(path))

    # 4) Run ExifTool
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if overwrite:
        original = path
        new_path = original.with_name(f"{local_ts}{original.suffix}")
        original.rename(new_path)
    return res.returncode == 0

def set_file_modified_time(path: Path, local_ts: str) -> bool:
    """
    Sets the file's mtime (and atime) to `local_ts`, interpreted as CDMX time (UTC-6).

    Args:
        path: Path to the file.
        local_ts: Timestamp in 'YYYYMMDD_HHMMSS' format (CDMX time).

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

def main():
    parser = argparse.ArgumentParser(
        description='Comprueba que el metadata de fecha/hora coincida con el nombre de archivo yyyymmdd_HHMMSS.ext'
    )
    parser.add_argument('dir', help='Directorio con archivos estandarizados')
    parser.add_argument(
        "fix",
        nargs="?",
        default="no",
        help="Borrar archivos más grandes que el archivo original. [yes, no] (Default: no)"
    )
    args = parser.parse_args()

    fix = True if args.fix == "fix" else False
    fix_type = "VID" # VID, IMG, BOTH
    data_to_keep = "NAME" #NAME or META

    #Checks dir, gets and sorts all item in it.
    base = Path(args.dir)
    if not base.is_dir():
        print(f"El directorio {base} no existe o no es válido.")
        sys.exit(1)
    if fix_type == "IMG":
        files = sorted([f for f in base.iterdir() if f.suffix.lower() in IMAGE_EXTS])
    elif fix_type == "VID":
        files = sorted([f for f in base.iterdir() if f.suffix.lower() in VIDEO_EXTS])
    elif fix_type == "BOTH":
        files = sorted([f for f in base.iterdir() if f.suffix.lower() in IMAGE_EXTS + VIDEO_EXTS])
    total = len(files)
    if total == 0:
        print("No se encontraron archivos para validar metadatos.")
        return

    for idx, path in enumerate(files, start=1):
        print(f"[{idx}/{total}] {path.name}")
        stem = path.stem  # yyyymmdd_HHMMSS format
        # Gets metadata and adjusts margin
        if path.suffix.lower() in IMAGE_EXTS:
            meta = get_image_datetime(path)
            margin_secs = 60
        else:
            meta = get_video_creation(path)
            margin_secs = get_video_duration_seconds(path)
            margin_secs += margin_secs

        if not meta:
            print(f"  {YELLOW}[WARN]{RESET} No se encontró metadata de fecha/hora.")
            if fix:
                print(f"Fixing... {path}, {stem}")
                if fix_type == "IMG":
                    set_image_all_dates(path, stem, True, True)
                else:
                    set_video_creation_time(path, stem)
            continue

        is_Ok = is_within_margin(stem, meta, max_seconds=margin_secs)

        if not is_Ok:
            print(f"  {RED}[ERROR]{RESET} Metadata difiere. Nombre: {stem}, Metadata: {meta}")
            if fix:
                print(f"Fixing... {path}, {stem}")
                if fix_type == "IMG":
                    if data_to_keep == "NAME":
                        set_image_all_dates(path, stem, True)
                    else:
                        set_image_all_dates(path, meta, True)
                elif fix_type == "VID":
                    if data_to_keep == "NAME":
                        set_video_creation_time(path, stem)
                    else:
                        set_video_creation_time(path, meta)


if __name__ == '__main__':
    main()