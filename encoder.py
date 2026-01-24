import sys
import subprocess
import argparse
import math
from pathlib import Path
from typing import Tuple, Optional, Union

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
--library libx265   --crf 18 --preset medium/slow
--library libsvtav1 --crf 24 --preset 2/4

1. For libx265 (hevc), going past slow (i.e. slower, veryslow) doesn't always increase compression efficiency.
2. Newer versions of libsvtav1 are way faster to encode and provide better efficiency.
I tested this script using libsvtav1 3.x.x. If your libsvtav1 is in the 1.x.x version, I'd recommend
manually compiling ffmpeg with a newer libsvtav1 version.
3. I'll include more references here once I test each encoder more thoroughly.
"""

# Pixel count (in 9:16 aspect ratio), comparison vs 1080p.
"""
Resolution -  Pixel Count  - Description
  180p =>    57,600 (  3%) - 
  360p =>   230,400 ( 11%) -
  540p =>   518,400 ( 25%) - 
  720p =>   921,600 ( 45%) - HD
  900p => 1,440,000 ( 70%) - HD+ (Recommended)
 1080p => 2,073,600 (100%) - Full-HD
 1440p => 3,686,400 (177%) - Quad-HD
 2160p => 8,294,400 (400%) - 4K UHD
"""

# Auxiliary Functions.

def get_duration(path: Union[Path, str]) -> float:
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
    except Exception:
        return 0.0

def seconds_to_mmss(seconds: Union[int, float]) -> str:
    """
    Receives a duration in seconds (possibly greater than 60) and returns it in mm:ss format.
    """
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def get_frame_rate(path: Union[Path, str]) -> float:
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
    except Exception:
        fps_val = 0.0
    return fps_val

def get_new_resolution(path: Union[Path, str], new_res: Union[int, str]) -> int:
    """
    Given a video path, prints its original and downscaled resolutions.
    """
    # Run ffprobe to get width and height.
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'stream=width,height',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
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

    new_width = math.floor(width * scale_factor)
    new_height = math.floor(height * scale_factor)
    new_width = new_width + 1 if new_width % 2 != 0 else new_width
    new_height = new_height + 1 if new_height % 2 != 0 else new_height
    print(f"[Org res] {width}x{height}")

    if min(width, height) > new_res:
        print(f"[New res] {RED}{new_width}x{new_height}{RESET}")
        res = min(new_height, new_width)
        return res

    res = min(width, height)
    return res

def get_video_audio_info(path: Path) -> Tuple[str, int]:
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

        codec_name: Optional[str] = None
        bitrate: Optional[int] = None

        for line in res.stdout.splitlines():
            if line.startswith("codec_name="):
                codec_name = line.split("=", 1)[1].strip()
            elif line.startswith("bit_rate="):
                try:
                    bitrate = int(line.split("=", 1)[1].strip())
                    bitrate = int(bitrate / 1000)
                except ValueError:
                    bitrate = None

        # Normalize return types to (str, int)
        codec_name_final = codec_name if codec_name else "Undefined"
        bitrate_final = int(bitrate) if bitrate else 0
        return (codec_name_final, bitrate_final)

    except FileNotFoundError:
        print("Error: ffprobe not found. Please install FFmpeg.")
        return ("Undefined", 0)
    except Exception as e:
        print(f"Error reading audio info: {e}")
        return ("Undefined", 0)

# Main Functions.

def encode_video(
    vid: Path,
    out_file: Path,
    library: str,
    crf: Union[str, int],
    preset: Union[str, int],
    downscale: Union[bool, str, int],
    audio_bitrate: Union[str, int]
) -> None:
    # Assigns args to variables.
    duration = get_duration(vid)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(vid)
    orig_audio_props = get_video_audio_info(vid)

    # Builds ffmpeg command.
    cmd = ['ffmpeg', '-i', str(vid), '-c:v', str(library), '-crf', str(crf), '-preset', str(preset)]

    # Downscales to resolution if set.
    if downscale:
        res = get_new_resolution(vid, downscale)
        vf = f"scale='if(gt(a,1),-2,{res})':'if(gt(a,1),{res},-2)',format=yuv420p" #yuv420p10le
        cmd += ["-vf", vf]

    # Caps FPS range, since going above 240 or below 24 usually results in encoding error.
    if input_fps > 239:
        cmd += ['-r', str(240)]
    elif input_fps < 24:
        cmd += ['-r', str(24)]

    # Used to determine audio stream bitrate.
    orig_bitrate = int(orig_audio_props[1])

    # Normalize audio_bitrate to int for comparisons
    try:
        audio_bitrate_int = int(audio_bitrate)
    except Exception:
        audio_bitrate_int = 128

    # Caps max audio bitrate to provided max (in kbps).
    if orig_bitrate != 0 and orig_bitrate <= audio_bitrate_int:
        ab = f"{orig_bitrate}k"
    else:
        ab = f"{audio_bitrate_int}k"
    cmd += ["-c:a", "libopus", "-b:a", ab]

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
            print(f"{GREEN}[OK]{RESET}\n")
        else:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    except Exception as e:
        print(f"{RED}[ERROR]{RESET}")
        print(e + "\n")

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
        default="32",
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
        choices=["180", "360", "540", "720", "900", "1080", "1440", "2160"],
        default="2160",
        help="Downscale to specific resolution (default: 2160)"
    )
    parser.add_argument(
        "-a",
        "--audiobitrate",
        choices=["32", "64", "96", "128", "160", "192", "256"],
        default="128",
        help="Set max audio bitrate (default: 128)"
    )
    parser.add_argument(
        "-r",
        "--reverse",
        choices=["true", "false"],
        default="false",
        help="false: older to newer. Default: false"
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
    audio_bitrate = args.audiobitrate
    extension = ".mkv" if library == "libsvtav1" else ".mp4"
    downscale = False if args.downscale == "false" else args.downscale
    reverse_Order = False if args.reverse == "false" else True

    # Checks if input directory exists.
    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)

    # Selects all videos in input directory, sorts them and counts them.
    videos = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos, reverse=reverse_Order)
    total = len(videos)

    # Returns if there are no videos.
    if total == 0:
        print("No videos were found")
        return
    
    # Creates output folder with arguments data.
    output_dir = base_dir / (library + "-" + crf + "-" + preset + "-" + downscale + "p-" + audio_bitrate + "k")
    output_dir.mkdir(exist_ok=True)

    # Iterates each video.
    for idx, vid in enumerate(videos, start=1):
        print(f"[{idx}/{total}] Processing: {vid.name}")

        out_file = output_dir / (vid.stem + extension) # Output video name.

        # Skips if video already exists.
        if out_file.exists():
            print(f"{YELLOW}[Skipping]{RESET}")
            continue

        encode_video(vid, out_file, library, crf, preset, downscale, audio_bitrate)

if __name__ == '__main__':
    main()