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

def seconds_to_mmss(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def get_duration(path):
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

def get_frame_rate(path):
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

def log_status(summary_path, video_name, status, error_lines=None):
    with open(summary_path, 'a', encoding='utf-8') as f:
        if status == 'OK':
            f.write(f"{video_name} => [OK]\n")
        else:
            f.write(f"{video_name} => [ERROR]:\n")
            if error_lines:
                for line in error_lines:
                    f.write(f"//{line}\n")

def print_scaled_resolution(video_path):
    """
    Given a video path, prints its resolution (width, height).
    Also prints new downscaled resolution.
    """
    # Run ffprobe to get width and height
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'stream=width,height',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
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
    print(f"[New res] {RED} {new_width}x{new_height} {RESET}")

def encode_video(vid, out_file, library, crf, preset, downscale):
    duration = get_duration(vid)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(vid)
    
    # Builds ffmpeg command.
    cmd = ['ffmpeg', '-i', str(vid), '-c:v', str(library), '-crf', str(crf), '-preset', str(preset)]

    # Downscales it to 1080p if codec set to av1 (for storage savings).
    if downscale:
        cmd += ["-vf", "scale='if(gt(a,1),-2,1080)':'if(gt(a,1),1080,-2)'"] #scale='if(gt(a,1),-2,1080)':'if(gt(a,1),1080,-2)'.
        print_scaled_resolution(vid)

    #Caps FPS at 240 since going above usually results in encoding error.
    if input_fps > 239:
        cmd += ['-r', str(240)]

    cmd += ['-pix_fmt', 'yuv420p']  # Widely compatible format, may be omitted.

    cmd += ['-c:a', 'copy', '-map_metadata', '0',
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
            #log_status(summary_path, input_path.name, 'OK')
        else:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    except Exception as e:
        print(f"{RED}[ERROR]{RESET}")
        #log_status(summary_path, input_path.name, 'ERROR', [str(e)])

def get_presets(codec: str, quality: str, speed: str):
    """
    Maps codec, quality, and speed to ffmpeg parameters.
    """

    codec = codec.lower()
    quality = quality.lower()
    speed = speed.lower()

    # Codec library mapping
    codec_map = {
        "avc": "libx264",
        "hevc": "libx265",
        "av1": "libsvtav1",
    }

    # Quality presets mapping
    crf_map = {
        "storage": {"avc": 28, "hevc": 28, "av1": 36},
        "medium": {"avc": 24, "hevc": 24, "av1": 30},
        "high": {"avc": 20, "hevc": 20, "av1": 24},
    }

    # Codec speed presets
    if codec == "av1":
        preset_map = {
            "fast": "6",
            "medium": "4",
            "slow": "2",
        }
    else:
        preset_map = {
            "fast": "fast",
            "medium": "medium",
            "slow": "slow",
        }
    
    library = codec_map[codec]
    crf = crf_map[quality][codec]
    preset = preset_map[speed]
    return library, crf, preset

def get_args():

    parser = argparse.ArgumentParser(
        description="Video transcoder using ffmpeg with standardized options."
    )

    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        required=True,
        help="Directory to process"
    )
    parser.add_argument(
        "-c",
        "--codec",
        choices=["avc", "hevc", "av1"],
        default="hevc",
        help="Codec to use (default: hevc)"
    )
    parser.add_argument(
        "-q",
        "--quality",
        choices=["storage", "medium", "high"],
        default="medium",
        help="Codec quality preset (default: medium)"
    )
    parser.add_argument(
        "-s",
        "--speed",
        choices=["fast", "medium", "slow"],
        default="slow",
        help="Codec speed preset (default: slow)"
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

    base_dir = Path(args.input_dir)
    codec = args.codec
    quality = args.quality
    speed = args.speed
    extension = args.extension
    downscale = True if args.downscale.lower == "yes" else False

    library, crf, preset = get_presets(codec, quality, speed)

    if not base_dir.is_dir():
        print("Directory does not exist")
        sys.exit(1)
        
    output_dir = base_dir / (codec + "-" + quality + "-" + speed)
    output_dir.mkdir(exist_ok=True)

    videos = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos)
    total = len(videos)

    if total == 0:
        print("No videos were found")
        return

    for idx, vid in enumerate(videos, start=1):
        print(f"[{idx}/{total}] Processing: {vid.name}")

        out_file = output_dir / (vid.stem + "_" + codec + extension)
        if out_file.exists():
            print(f"{YELLOW}[Skipping]{RESET}")
            continue

        encode_video(vid, out_file, library, crf, preset, downscale)

if __name__ == '__main__':
    main()