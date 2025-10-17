import sys
import subprocess
import argparse
from pathlib import Path
import re
from datetime import datetime

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

#Extensions
VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi', ".3gp"]

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
        '-lavfi', (
            '[0:v]fps=30,scale=1920:1080,format=yuv420p[ref];'
            '[1:v]fps=30,scale=1920:1080,format=yuv420p[dist];'
            '[ref][dist]psnr'
        ),
        '-f', 'null', '-'
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
        '-lavfi', (
            '[0:v]fps=30,scale=1920:1080,format=yuv420p[ref];'
            '[1:v]fps=30,scale=1920:1080,format=yuv420p[dist];'
            '[ref][dist]ssim'
        ),
        '-f', 'null', '-'
    ]

    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # parse stderr for 'All:0.xxx' at last SSIM line
    m = re.search(r'All:(0\.?\d*)', res.stderr)
    return float(m.group(1)) if m else 0.0

def get_vmaf(orig: Path, comp: Path) -> float:
    """Run ffmpeg libvmaf filter and return overall VMAF score."""
    cmd = [
        'ffmpeg', '-i', str(orig), '-i', str(comp),
        '-lavfi', (
            '[0:v]fps=30,scale=1920:1080,format=yuv420p[ref];'
            '[1:v]fps=30,scale=1920:1080,format=yuv420p[dist];'
            '[ref][dist]libvmaf'
        ),
        '-f', 'null', '-'
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # looks for something like "VMAF score: 95.432100"
    m = re.search(r'(?i)VMAF score: *([\d\.]+)', res.stderr)
    return float(m.group(1)) if m else 0.0

def get_args():
    parser = argparse.ArgumentParser(
        description="Gets and compares PSNR, SSIM and VMAF between original and transcoded videos"
    )

    parser.add_argument(
        "-b",
        "--base",
        type=Path,
        required=True,
        help="Base directory, taken as reference"
    )
    parser.add_argument(
        "-s",
        "--secondary",
        type=Path,
        required=True,
        help="Secondary directory, quality checks"
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["psnr", "ssim", "vmaf"],
        default="ssim",
        help="Type of test (default: ssim)"
    )

    args = parser.parse_args()
    return args

def main():
    # Assigns args to variables.
    args = get_args()
    base_dir = Path(args.base)
    secondary_dir = Path(args.secondary)
    mode = args.mode

    # Checks that both directories exist.
    if not base_dir.is_dir() or not secondary_dir.is_dir():
        print(f"One of the directories doesn't exist")
        sys.exit(1)

    # List with each result, used to calculate average result.
    all_results = []

    # Gets all videos in secondary directory, sorts and counts them.
    videos = [f for f in secondary_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS and f.is_file()]
    videos = sorted(videos)
    total = len(videos)

    # Iterates base videos.
    for idx, vid in enumerate(videos, start=1):
        # Finds matching in secondary directory
        print(f"[{idx}/{total}] Processing: {vid.name}")
        matches = [f for f in base_dir.iterdir() if f.is_file() and f.stem.startswith(vid.stem)]

        # No matches => Continues to next video.
        if not matches:
            print(f'{vid.name}: No video equivalent found in base directory: {base_dir.name}')
            continue

        # Gets original video with same stem.
        orig_video = sorted(matches)[0]

        # Original and compressed video bitrates.
        br1 = get_bitrate_mbps(orig_video)
        br2 = get_bitrate_mbps(vid)

        # Runs test input in the arguments.
        if mode == "psnr":
            psnr = get_psnr(orig_video, vid)
            all_results.append(psnr)
            result = (f"{orig_video.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, {GREEN}PSNR: {psnr:.2f} dB{RESET}")
        elif mode == "ssim":
            ssim = get_ssim(orig_video, vid)
            all_results.append(ssim)
            result = (f"{orig_video.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, {GREEN}SSIM: {ssim:.4f}{RESET}")
        else:
            vmaf = get_vmaf(orig_video, vid)
            all_results.append(vmaf)
            result = (f"{orig_video.name}: {br1:.2f} Mbps => {br2:.2f} Mbps, {GREEN}VMAF: {vmaf:.4f}{RESET}")

        print(f"Result: {result}")
    
    average_result = sum(all_results) / len(all_results)
    decimals = 2 if mode == "psnr" else 4
    average_result = round(average_result, decimals)
    print(f"Average {mode}: {average_result}.")

if __name__ == '__main__':
    main()