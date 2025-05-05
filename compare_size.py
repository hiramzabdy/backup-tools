import sys
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def bytes_to_mb(b):
    return b / (1024 * 1024)


def format_signed(value, unit=''):
    sign = '+' if value >= 0 else '-'
    return f"{sign}{abs(value):.1f}{unit}"


def main():
    parser = argparse.ArgumentParser(
        description='Compara tamaños de los videos entre dos directorios distintos'
    )
    parser.add_argument('first_dir', help='Directorio tomado como base')
    parser.add_argument('second_dir', help='Directorio a comparar con directorio base')
    args = parser.parse_args()

    first_dir = Path(args.first_dir)
    second_dir = Path(args.second_dir)

    if not first_dir.is_dir() or not second_dir.is_dir():
        print(f"Alguna carpeta no existe o no es un directorio.")
        sys.exit(1)

    second_dir_vids = sorted([f for f in second_dir.iterdir() if f.is_file()])
    total = len(second_dir_vids)
    if total == 0:
        print("No se encontraron videos para comparar")
        return

    for idx, vid in enumerate(second_dir_vids, start=1):
        # Derivar archivo original
        stem = vid.stem
        if stem.endswith('_hevc'):
            orig_stem = stem[:-5]
        else:
            orig_stem = stem
        orig = first_dir / (orig_stem + '.mp4') # or _hevc.mkv if comparing two outputs

        print(f"[{idx}/{total}] ==> {orig_stem}")

        size_orig = orig.stat().st_size if orig.exists() else None
        size_sec = vid.stat().st_size

        if size_orig is None:
            print(f"  {YELLOW}[WARN]{RESET} Original no encontrado para comparar tamaño.")
            continue

        mb_orig = bytes_to_mb(size_orig)
        mb_sec = bytes_to_mb(size_sec)
        diff_mb = mb_sec - mb_orig
        pct = (diff_mb / mb_orig * 100) if mb_orig > 0 else 0

        status = f"{GREEN}[OK]{RESET}" if diff_mb < 0 else f"{YELLOW}[WARN]{RESET}"

        # Formatear salida
        print(
            f"  {mb_orig:.1f} MB -> {mb_sec:.1f} MB, Δ {format_signed(diff_mb, ' MB')} ({format_signed(pct, '%')}), {status}"
        )

if __name__ == '__main__':
    main()