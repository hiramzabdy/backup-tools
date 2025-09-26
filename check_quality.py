import sys
import subprocess
import argparse
from pathlib import Path
import re
from datetime import datetime

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
    # looks for 'average:X' in PSNR line
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

def get_vmaf(orig: Path, comp: Path) -> float:
    """Run ffmpeg libvmaf filter and return overall VMAF score."""
    cmd = [
        'ffmpeg', '-i', str(orig), '-i', str(comp),
        '-lavfi', '[0:v][1:v]libvmaf',
        '-f', 'null', '-' # discard output
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # looks for something like "VMAF score: 95.432100"
    m = re.search(r'(?i)VMAF score: *([\d\.]+)', res.stderr)
    return float(m.group(1)) if m else 0.0

def log_result(logfile, result):
    with open(logfile, 'a', encoding='utf-8') as f:
        if result:
            f.write(f"{result}\n")

def get_args():
    parser = argparse.ArgumentParser(
        description="Gets and compares PSNR, SSIM and VMAF between original and transcoded videos"
    )

    parser.add_argument(
        "-b",
        "--base",
        type=Path,
        required=True,
        help="Base directory"
    )
    parser.add_argument(
        "-s",
        "--secondary",
        type=Path,
        required=True,
        help="Secondary directory"
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=["psnr", "ssim", "vmaf"],
        default="vmaf",
        help="Type of test (default: vmaf)"
    )

    args = parser.parse_args()
    return args

def main():
    args = get_args()
    d1 = Path(args.base)
    d2 = Path(args.secondary)
    test_type = args.type

    # Creates log file
    date_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile_name = Path(d2).name
    log_result(f"./{logfile_name}.log", date_time)

    if not d1.is_dir() or not d2.is_dir():
        print('Both arguments need to be a valid directory')
        sys.exit(1)

    # iterate base videos
    for orig in sorted(d1.iterdir()):
        if not orig.is_file():
            continue
        stem = orig.stem
        # find matching in dir2 (startswith stem)
        matches = [f for f in d2.iterdir() if f.is_file() and f.stem.startswith(stem)]
        if not matches:
            print(f'{orig.name}: No video equivalent found in second directory: {d2.name}')
            continue
        comp = sorted(matches)[0]
        br1 = get_bitrate_mbps(orig)
        br2 = get_bitrate_mbps(comp)

        if test_type == "psnr":
            psnr = get_psnr(orig, comp)
            result = (f"{orig.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, PSNR={psnr:.2f} dB")
        elif test_type == "ssim":
            ssim = get_ssim(orig, comp)
            result = (f"{orig.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, SSIM={ssim:.4f}")
        else:
            vmaf = get_vmaf(orig, comp)
            result = (f"{orig.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, VMAF={vmaf:.4f}")

        log_result(f"./{logfile_name}.log", result)
        print(result)

if __name__ == '__main__':
    main()