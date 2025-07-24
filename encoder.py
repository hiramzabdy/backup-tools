import os
import sys
import subprocess
import argparse
import time
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

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
    # Puede venir como '239737/1000' o '240/1' o 'N/A'
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

def get_scaled_resolution(video_path: str) -> tuple[int, int]:
    """
    Given a video path, returns the scaled resolution (width, height).
    If the video is already <=1080p (in both dimensions), returns the original resolution.
    If larger, it scales it down to max 1080 in the larger dimension, preserving aspect ratio.
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

    # Check if scaling is needed
    if min(width, height) <= 1088:
        return False  # No scaling needed

    # Determine scale factor
    if width <= height:
        scale_factor = 1080 / width
    else:
        scale_factor = 1080 / height

    new_width = int(round(width * scale_factor))
    new_height = int(round(height * scale_factor))
    print(f"[Org. res] {width}x{height}")
    print(f"[New res] {RED} {new_width}x{new_height} {RESET}")
    return True

def encode_video(input_path, output_path, codec, summary_path, ccd=2):
    duration = get_duration(input_path)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(input_path)

    #if 28 < input_fps < 32:
    #    output_fps = 30
    #elif 58 < input_fps < 62:
    #    output_fps = 60
    
    if input_fps > 239:
        output_fps = 240
    else:
        output_fps = None

    # Builds ffmpeg command
    cmd = ['ffmpeg', '-i', str(input_path)]
           
    # Select codec, HEVC or AV1
    if codec == "hevc":
        cmd += ['-c:v', 'libx265', '-crf', '18', '-preset', 'slower'] # Default: 18, slower (or veryslow)
    elif codec == "av1": 
        cmd += ['-c:v', 'libsvtav1', '-crf', '36', '-preset', '1'] # Default: 36, 3

    # Downscales it to 1080p if codec set to av1 (for storage savings)
    toDownscale = get_scaled_resolution(str(input_path))
    if codec == "av1" and toDownscale:
        cmd += ["-vf", "scale='if(gt(a,1),-2,1080)':'if(gt(a,1),1080,-2)'"] #scale='if(gt(a,1),-2,1080)':'if(gt(a,1),1080,-2)'

    # Caps FPS at 240
    if output_fps:
        cmd += ['-r', str(output_fps)]

    cmd += ['-pix_fmt', 'yuv420p']  # Widely compatible, especially for web/streaming

    cmd += ['-c:a', 'copy', '-map_metadata', '0',
            '-y', '-progress', 'pipe:1', str(output_path)]

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
        if output_path.exists():
            output_path.unlink()
        print(f"{RED}[ERROR]{RESET}")
        #log_status(summary_path, input_path.name, 'ERROR', [str(e)])

def main():
    parser = argparse.ArgumentParser(description='Codifica videos usando libx265 o libsvt-av1')
    parser.add_argument('input_dir', help='Directorio con videos a procesar')
    parser.add_argument('codec', help='Codec a utilizar (hevc, av1)')
    parser.add_argument(
        "ccd",
        nargs="?",
        default=2,
        help="CCD a utilizar. [0 = CC0, 1 = CCD1, 2 = No afinity]"
    )
    args = parser.parse_args()

    base_dir = Path(args.input_dir)
    if not base_dir.is_dir():
        print("El directorio especificado no existe.")
        sys.exit(1)
        
    codec = args.codec if args.codec else "hevc"
    summary_log = base_dir / (codec + "_summary.log")
    output_dir = base_dir / (codec)
    output_dir.mkdir(exist_ok=True)

    videos = [f for f in base_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos)
    total = len(videos)
    if total == 0:
        print("No se encontraron archivos de video para procesar.")
        return

    for idx, vid in enumerate(videos, start=1):
        print(f"[{idx}/{total}] Procesando: {vid.name}")

        name = vid.stem + "_" + codec
        out_file = output_dir / (name + '.mkv' if codec=="av1" else name + ".mp4") # or vid.suffix

        if out_file.exists():
            print(f"{YELLOW}[Saltando]{RESET}")
            continue
        encode_video(vid, out_file, codec, summary_log, args.ccd)

if __name__ == '__main__':
    main()