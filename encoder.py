import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes.
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# Extensions.
VIDEO_EXTS = [".mp4", ".mkv", ".mov", ".avi", ".3gp"]

# Recomended values.
"""
For Original Quality (Pretty much unnoticeable compression):
--library libx265 --crf 18 --preset slow
--library libsvtav1 --crf 24 --preset 2

For Storage Savings (Somewhat noticable difference, not thoroughly tested):
--library libsvtav1 --crf 36, --preset 2

For EXTREME Storage Savings (Noticable difference, still not potato-like videos):
--library libsvtav1 --crf 44 --preset 1 --downscale 1080

This option turned a 350GB smartphones videos backup into a lite 9.3GB backup (2.6% of the original size).

1. For libx265 (hevc), going past slow (i.e. slower, veryslow) doesn't always increase compression efficiency.
2. Newer versions of libsvtav1 are way faster to encode and provide better efficiency.
I tested this script using libsvtav1 3.x.x. If your libsvtav1 is in the 1.x.x version, I'd recommend
manually compiling ffmpeg with a newer libsvtav1 version.
3. I'll include more references here once I test each encoder more thoroughly.
"""

# Auxiliary Functions.

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
    # Either '239737/1000', '240/1' or 'N/A'.
    try:
        if '/' in fr:
            num, den = fr.split('/')
            fps_val = float(num) / float(den) if float(den) != 0 else 0.0
        else:
            fps_val = float(fr)
    except:
        fps_val = 0.0
    return fps_val

def print_scaled_resolution(path, new_res):
    """
    Given a video path, prints its original and downscaled resolutions.
    """
    # Run ffprobe to get width and height.
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

    # Determine scale factor.
    new_res = int(new_res)
    if width <= height:
        scale_factor = new_res / width
    else:
        scale_factor = new_res / height

    new_width = int(round(width * scale_factor))
    new_height = int(round(height * scale_factor))
    print(f"[Org res] {width}x{height}")

    if min(width, height) > new_res:
        print(f"[New res] {RED}{new_width}x{new_height}{RESET}")

def get_video_audio_info(path: Path):
    """
    Returns the audio codec and bitrate (in kbps) of a video file.
    Returns ("Undefined", 0) if no audio codec found.
    """
    try:
        # ffprobe command to extract codec name and bitrate from the audio stream.
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=0",
            str(path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res.returncode != 0 or not res.stdout.strip():
            return ("Undefined", 0)

        codec_name = None
        bitrate = None

        for line in res.stdout.splitlines():
            if line.startswith("codec_name="):
                codec_name = line.split("=", 1)[1].strip()
            elif line.startswith("bit_rate="):
                try:
                    bitrate = int(line.split("=", 1)[1].strip())
                    bitrate = int(bitrate/1000)
                except ValueError:
                    bitrate = None

        return (codec_name, bitrate)

    except FileNotFoundError:
        print("Error: ffprobe not found. Please install FFmpeg.")
        return ("Undefined", 0)
    except Exception as e:
        print(f"Error reading audio info: {e}")
        return ("Undefined", 0)

# Main Functions.

def encode_video(vid, out_file, library, crf, preset, downscale):
    # Assigns args to variables.
    duration = get_duration(vid)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(vid)
    orig_audio_props = get_video_audio_info(vid)

    # Builds ffmpeg command.
    cmd = ['ffmpeg', '-i', str(vid), '-c:v', str(library), '-crf', str(crf), '-preset', str(preset)]

    # Downscales to resolution if set.
    if downscale:
        vf = f"scale='min({downscale},iw)':'min({downscale},ih)':force_original_aspect_ratio=decrease,format=yuv420p"
        cmd += ["-vf", vf]
        print_scaled_resolution(vid, downscale)

    # Caps FPS range, since going above 240 or below 24 usually results in encoding error.
    if input_fps > 239:
        cmd += ['-r', str(240)]
    elif input_fps < 24:
        cmd += ['-r', str(24)]

    # Used to determine audio stream bitrate.
    orig_bitrate = orig_audio_props[1]

    # Caps max audio bitrate to 256kbps aac for H264 and H265.
    if library == "libx264" or library == "libx265":
        if orig_bitrate == 0:
            cmd += ["-c:a", "copy"] # In case audio exists but script wasn't able to detect it.
        elif orig_bitrate <= 256:
            out_bitrate = str(orig_bitrate) + "k"
            cmd += ["-c:a", "libfdk_aac", "-b:a", out_bitrate]
        elif orig_bitrate > 256:
            cmd += ["-c:a", "libfdk_aac", "-b:a", "256k"]
    
    # Caps max audio bitrate to 128kbps or 64kbps opus for AV1.
    if library == "libsvtav1":
        if orig_bitrate <= 64:
            out_bitrate = str(orig_bitrate) + "k"
            cmd += ["-c:a", "libopus", "-b:a", out_bitrate]
        else:
            cmd += ["-c:a", "libopus", "-b:a", "64k"]

    # Copies metadata and completes command.
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
        help="Codec quality level (default: 40)"
    )
    parser.add_argument(
        "-p",
        "--preset",
        default="4",
        help="Codec efficiency level (Codec dependant) (default: 4)"
    )
    parser.add_argument(
        "-d",
        "--downscale",
        choices=["480", "720", "1080", "1440", "2160", "false"],
        default="false",
        help="Downscale to specific resolution (default: false)"
    )
    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.input)
    library = args.library
    crf = args.crf
    preset = args.preset
    extension = ".mkv" if library == "libsvtav1" else ".mp4"
    downscale = False if args.downscale == "false" else args.downscale

    # Checks if input directory exists.
    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)

    # Selects all videos in input directory, sorts them and counts them.
    videos = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos)
    total = len(videos)

    # Returns if there are no videos.
    if total == 0:
        print("No videos were found")
        return
    
    # Creates output folder with arguments data.
    output_dir = base_dir / (library + "-" + crf + "-" + preset)
    output_dir.mkdir(exist_ok=True)

    # Iterates each video.
    for idx, vid in enumerate(videos, start=1):
        print(f"[{idx}/{total}] Processing: {vid.name}")

        out_file = output_dir / (vid.stem + extension) # Output video name.

        # Skips if video already exists.
        if out_file.exists():
            print(f"{YELLOW}[Skipping]{RESET}")
            continue

        encode_video(vid, out_file, library, crf, preset, downscale)

if __name__ == '__main__':
    main()