import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

#Extensions
VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi', ".3gp"]

#Recomended values
"""
For Original Quality (Almost unnoticable compression):
libx265: -crf: 18, preset: slow
libsvt-av1: -crf: 24, preset: 4

For Storage Savings (Somewhat noticable difference)
libx265: -crf: 30, preset: slow
libsvt-av1: -crf: 36, preset: 2

1. For libx265 (hevc), going past slow (i.e. slower, veryslow) doesn't always increase compression efficiency.
2. Newer versions of libsvt-av1 are way faster to encode and provide better efficiency.
I tested this script using libsvt-av1 3.0.2. If your libsvt-av1 is in the 1.x.x version, I'd recommend
manually compiling ffmpeg with a newer libsvt-av1 version.
3. I'll include more references here once I test each encoder more thoroughly.
"""
def get_duration(path):
    """
    Given a video path, gets its duration and returns it as a float
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
        return 0.0

def seconds_to_mmss(seconds):
    """
    Receives a duration in seconds (possibly greater than 60) and returns it in mm:ss format.
    """
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def get_frame_rate(path):
    """
    Given a video path, gets its framerate and returns it as a float.
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    fr = result.stdout.strip()
    # Either '239737/1000', '240/1' or 'N/A'
    try:
        if '/' in fr:
            num, den = fr.split('/')
            fps_val = float(num) / float(den) if float(den) != 0 else 0.0
        else:
            fps_val = float(fr)
    except:
        fps_val = 0.0
    return fps_val

def print_scaled_resolution(path):
    """
    Given a video path, prints its original and downscaled resolutions.
    """
    # Run ffprobe to get width and height
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'stream=width,height',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    try:
        width_str, height_str = result.stdout.strip().split('\n')
        width, height = int(width_str), int(height_str)
    except ValueError:
        raise ValueError("Could not parse resolution from ffprobe output.")

    # Determine scale factor
    if width <= height:
        scale_factor = 1080 / width
    else:
        scale_factor = 1080 / height

    new_width = int(round(width * scale_factor))
    new_height = int(round(height * scale_factor))
    print(f"[Org. res] {width}x{height}")

    if min(width, height) > 1080:
        print(f"[New res] {RED} {new_width}x{new_height} {RESET}")

def encode_video(vid, out_file, library, crf, preset, downscale):
    duration = get_duration(vid)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(vid)

    # Builds ffmpeg command.
    cmd = ['ffmpeg', '-i', str(vid), '-c:v', str(library), '-crf', str(crf), '-preset', str(preset)]

    # Downscales to 1080p if set
    if downscale:
        vf = "scale='min(1080,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease,format=yuv420p"
        cmd += ["-vf", vf]
        print_scaled_resolution(vid)

    # Caps FPS at 240 since going above usually results in encoding error.
    if input_fps > 239:
        cmd += ['-r', str(240)]

    # Downsamples audio to 96kbps if set
    if downscale:
        cmd += ["-c:a", "libopus", "-b:a", "64k"] # Might be 64k, 96k or 128k
    else:
        cmd += ["-c:a", "copy"]

    cmd += ['-map_metadata', '0',
            '-y', '-progress', 'pipe:1', str(out_file)]

    #Runs the ffmpeg command.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    last_line_length = 0
    fps = 0
    bitrate = "0kbits/s"
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if '=' not in line:
                continue
            key, val = line.split('=', 1)

            if key == 'fps':
                try:
                    fps = round(float(val), 1)
                except:
                    fps = 0
            elif key == 'bitrate':
                try:
                    bitrate = val
                except:
                    bitrate = 0
            elif key == 'out_time_ms':
                try:
                    current_time_ms = int(val)
                except ValueError:
                    continue
                completed_sec = current_time_ms / 1_000_000
                pct = (completed_sec / duration) * 100 if duration else 0
                pct = min(pct, 100)
                mmss = seconds_to_mmss(completed_sec)
                msg = f"[{pct:.0f}%] {mmss}/{total_mmss} - Vel: {fps} FPS"
                msg = f"[{pct:.0f}%] {mmss}/{total_mmss} - Vel: {fps} FPS - BR: {bitrate}"
                print('\r' + msg + ' ' * max(0, last_line_length - len(msg)), end='', flush=True)
                last_line_length = len(msg)
            elif key == 'progress' and val == 'end':
                break

        proc.wait()
        print(f"\r[100%] {total_mmss}/{total_mmss} - Vel: {fps} FPS - BR: {bitrate}")

        if proc.returncode == 0:
            print(f"{GREEN}[OK]{RESET}")
        else:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    except Exception as e:
        print(f"{RED}[ERROR]{RESET}")
        print(e)

def get_args():
    parser = argparse.ArgumentParser(
        description="Video transcoder using ffmpeg with standardized options."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Directory to process"
    )
    parser.add_argument(
        "-l",
        "--library",
        choices=["libx264", "libx265", "libsvtav1"],
        default="libsvtav1",
        help="ffmpeg library to use (default: libsvtav1)"
    )
    parser.add_argument(
        "-q",
        "--crf",
        default="40",
        help="Codec quality preset (Recommended range: 18-40, default: 40)"
    )
    parser.add_argument(
        "-p",
        "--preset",
        default="4",
        help="Codec dependant (medium, slow... or 1,2,3..., default: 4)"
    )
    parser.add_argument(
        "-e",
        "--extension",
        choices=[".mp4", ".mkv"],
        default=".mkv",
        help="Extension to use (default: .mkv)"
    )
    parser.add_argument(
        "-d",
        "--downscale",
        choices=["yes", "no"],
        default="no",
        help="Downscale to 1080p (default: no)"
    )

    args = parser.parse_args()
    return args

def main():
    args = get_args()

    base_dir = Path(args.input)
    library = args.library
    crf = args.crf
    preset = args.preset
    extension = args.extension
    downscale = True if args.downscale == "yes" else False

    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)
        
    output_dir = base_dir / (library + "-" + crf + "-" + preset)
    output_dir.mkdir(exist_ok=True)

    videos = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos)
    total = len(videos)

    if total == 0:
        print("No videos were found")
        return

    for idx, vid in enumerate(videos, start=1):
        print(f"[{idx}/{total}] Processing: {vid.name}")

        out_file = output_dir / (vid.stem + extension)
        if out_file.exists():
            print(f"{YELLOW}[Skipping]{RESET}")
            continue

        encode_video(vid, out_file, library, crf, preset, downscale)

if __name__ == '__main__':
    main()