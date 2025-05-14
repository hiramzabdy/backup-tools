import os
import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi']


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


def encode_video(input_path, output_path, codec, summary_path):
    duration = get_duration(input_path)
    total_mmss = seconds_to_mmss(duration)
    input_fps = get_frame_rate(input_path)
    # limitar fps a 240 si supera
    output_fps = 240 if input_fps > 239 else None

    # Construir comando ffmpeg
    cmd = ['ffmpeg', '-i', str(input_path)]
           
    # Select codec, HEVC or AV1
    if codec == "hevc":
        cmd += ['-c:v', 'libx265', '-crf', '22', '-preset', 'medium'] # default: crf 20 preset slow
    elif codec == "av1": 
        cmd += ['-c:v', 'libsvtav1', '-crf', '28', '-preset', '8'] # default: crf 28 preset 6

    # Caps FPS at 240
    if output_fps:
        cmd += ['-r', str(output_fps)]

    cmd += ['-c:a', 'copy', '-map_metadata', '0',
            '-y', '-progress', 'pipe:1', str(output_path)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    last_line_length = 0
    fps = 0
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
                    fps = int(float(val))
                except:
                    fps = 0
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
                print('\r' + msg + ' ' * max(0, last_line_length - len(msg)), end='', flush=True)
                last_line_length = len(msg)
            elif key == 'progress' and val == 'end':
                break

        proc.wait()
        print(f"\r[100%] {total_mmss}/{total_mmss} - Vel: {fps} FPS")
        if proc.returncode == 0:
            print(f"{GREEN}[OK]{RESET}")
            #log_status(summary_path, input_path.name, 'OK')
        else:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    except Exception as e:
        if output_path.exists():
            output_path.unlink()
        print(f"{RED}[ERROR]{RESET}")
        log_status(summary_path, input_path.name, 'ERROR', [str(e)])


def main():
    parser = argparse.ArgumentParser(description='Codifica videos usando libx265 o libsvt-av1')
    parser.add_argument('input_dir', help='Directorio con videos a procesar')
    parser.add_argument('codec', help='Codec a utilizar (hevc, av1)')
    args = parser.parse_args()

    base_dir = Path(args.input_dir)
    if not base_dir.is_dir():
        print("El directorio especificado no existe.")
        sys.exit(1)
        
    codec = args.codec if args.codec else "hevc"
    summary_log = base_dir / (codec + "_summary.log")
    output_dir = base_dir / (codec + '_output')
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
        encode_video(vid, out_file, codec, summary_log)

if __name__ == '__main__':
    main()
