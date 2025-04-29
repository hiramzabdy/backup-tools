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
        description='Compara tamaños originales y AV1 en vid_av1/'
    )
    parser.add_argument('base_dir', help='Directorio raíz con videos originales y subcarpeta vid_av1/')
    args = parser.parse_args()

    base = Path(args.base_dir)
    av1_dir = base / 'vid_av1'
    if not av1_dir.is_dir():
        print(f"La carpeta {av1_dir} no existe o no es un directorio.")
        sys.exit(1)

    av1_files = sorted([f for f in av1_dir.iterdir() if f.is_file()])
    total = len(av1_files)
    if total == 0:
        print("No se encontraron archivos en vid_av1/.")
        return

    for idx, av1 in enumerate(av1_files, start=1):
        # Derivar archivo original
        stem = av1.stem
        if stem.endswith('_av1'):
            orig_stem = stem[:-4]
        else:
            orig_stem = stem
        orig = base / (orig_stem + '.mp4') #av1.suffix

        print(f"[{idx}/{total}] ==> {orig_stem}")

        size_orig = orig.stat().st_size if orig.exists() else None
        size_av1 = av1.stat().st_size

        if size_orig is None:
            print(f"  {YELLOW}[WARN]{RESET} Original no encontrado para comparar tamaño.")
            continue

        mb_orig = bytes_to_mb(size_orig)
        mb_av1 = bytes_to_mb(size_av1)
        diff_mb = mb_av1 - mb_orig
        pct = (diff_mb / mb_orig * 100) if mb_orig > 0 else 0

        status = f"{GREEN}[OK]{RESET}" if diff_mb < 0 else f"{YELLOW}[WARN]{RESET}"

        # Formatear salida
        print(
            f"  {mb_orig:.1f} MB -> {mb_av1:.1f} MB, Δ {format_signed(diff_mb, ' MB')} ({format_signed(pct, '%')}), {status}"
        )

if __name__ == '__main__':
    main()