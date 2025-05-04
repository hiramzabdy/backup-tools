import os
import sys
import subprocess
import argparse
from pathlib import Path
import re

def get_bitrate_mbps(path: Path) -> float:
    """Get or estimate video bitrate in Mbps."""
    # try metadata
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=bit_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        bits = float(res.stdout.strip())
        return bits / 1e6
    except:
        # estimate from size and duration
        size = path.stat().st_size
        # get duration
        cmd_dur = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path)
        ]
        res_d = subprocess.run(cmd_dur, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            dur = float(res_d.stdout.strip())
            return (size * 8 / dur) / 1e6
        except:
            return 0.0


def get_psnr(orig: Path, comp: Path) -> float:
    """Run ffmpeg PSNR filter and return average PSNR value."""
    cmd = [
        'ffmpeg', '-i', str(orig), '-i', str(comp),
        '-lavfi', '[0:v][1:v]psnr',
        '-f', 'null', '-'  # discard output
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # parse stderr for average PSNR
    # look for 'average:X' in PSNR line
    m = re.search(r'average:(\d+\.?\d*)', res.stderr)
    return float(m.group(1)) if m else 0.0


def get_ssim(orig: Path, comp: Path) -> float:
    """Run ffmpeg SSIM filter and return overall SSIM value."""
    cmd = [
        'ffmpeg', '-i', str(orig), '-i', str(comp),
        '-lavfi', '[0:v][1:v]ssim',
        '-f', 'null', '-'  # discard output
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # parse stderr for 'All:0.xxx' at last SSIM line
    m = re.search(r'All:(0\.?\d*)', res.stderr)
    return float(m.group(1)) if m else 0.0


def main():
    parser = argparse.ArgumentParser(description='Comparar bitrate, PSNR y SSIM entre dos directorios de video')
    parser.add_argument('dir1', help='Directorio original')
    parser.add_argument('dir2', help='Directorio codificado')
    args = parser.parse_args()

    d1 = Path(args.dir1)
    d2 = Path(args.dir2)
    if not d1.is_dir() or not d2.is_dir():
        print('Ambos argumentos deben ser directorios válidos.')
        sys.exit(1)

    # iterate original videos
    for orig in sorted(d1.iterdir()):
        if not orig.is_file():
            continue
        stem = orig.stem
        # find matching in dir2 (startswith stem)
        matches = [f for f in d2.iterdir() if f.is_file() and f.stem.startswith(stem)]
        if not matches:
            print(f'{orig.name}: no se encontró correspondencia en {d2.name}')
            continue
        comp = sorted(matches)[0]
        br1 = get_bitrate_mbps(orig)
        br2 = get_bitrate_mbps(comp)
        psnr = get_psnr(orig, comp)
        ssim = get_ssim(orig, comp)
        print(f"{orig.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, PSNR={psnr:.2f} dB, SSIM={ssim:.4f}")

if __name__ == '__main__':
    main()