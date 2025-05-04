import os
import sys
import subprocess
import argparse
from pathlib import Path

VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi', '.flv', '.wmv', '.webm']

def get_duration(path: Path) -> float:
    """Returns duration in seconds using ffprobe."""
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
    except (ValueError, TypeError):
        return 0.0

def get_bitrate_mbps(path: Path) -> float:
    """
    Attempts to get bitrate in Mbps. If not available via ffprobe, it estimates from file size and duration.
    """
    # Try reading bitrate metadata
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=bit_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        bits_per_sec = float(result.stdout.strip())
        return bits_per_sec / 1_000_000
    except (ValueError, TypeError):
        # Estimate bitrate manually
        file_size_bytes = path.stat().st_size
        duration_sec = get_duration(path)
        if duration_sec > 0:
            bits_per_sec = (file_size_bytes * 8) / duration_sec
            return bits_per_sec / 1_000_000
        return 0.0

def main():
    parser = argparse.ArgumentParser(description='Calcular bitrate promedio de videos en un directorio')
    parser.add_argument('input_dir', help='Directorio con videos (no se incluyen subdirectorios)')
    args = parser.parse_args()

    base_dir = Path(args.input_dir)
    if not base_dir.is_dir():
        print(f"El directorio {base_dir} no existe.")
        sys.exit(1)

    videos = [f for f in base_dir.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    if not videos:
        print("No se encontraron archivos de video en el directorio especificado.")
        return

    total_bitrate = 0.0
    count = 0

    for vid in sorted(videos):
        bitrate = get_bitrate_mbps(vid)
        if bitrate > 0:
            print(f"{vid.name}: {bitrate:.2f} Mbps")
            total_bitrate += bitrate
            count += 1
        else:
            print(f"{vid.name}: no se pudo obtener o estimar bitrate")

    if count > 0:
        avg = total_bitrate / count
        print(f"\nBitrate promedio: {avg:.2f} Mbps")
    else:
        print("No se pudo calcular bitrate promedio para ningún video.")

if __name__ == '__main__':
    main()