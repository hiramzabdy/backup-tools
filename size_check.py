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

def delete_vids(vids):
    for file_path in vids:
        path = Path(file_path)
        try:
            path.unlink()
            print(f"Deleted: {file_path}")
        except FileNotFoundError:
            print(f"Not found: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Compara tamaños de los videos entre dos directorios distintos'
    )
    parser.add_argument('first_dir', help='Directorio tomado como base')
    parser.add_argument('second_dir', help='Directorio a comparar con directorio base')
    parser.add_argument(
        "margin_pct",
        nargs="?",
        type=int,
        default=0,
        help="Porcentaje de margen para borrar (Default: 0)"
    )
    parser.add_argument(
        "delete",
        nargs="?",
        default="no",
        help="Borrar archivos más grandes que el archivo original. [del, no] (Default: no)"
    )

    args = parser.parse_args()
    first_dir = Path(args.first_dir)
    second_dir = Path(args.second_dir)
    delete = True if args.delete == "del" else False
    margin_pct = int(args.margin_pct)

    if not first_dir.is_dir() or not second_dir.is_dir():
        print(f"Alguna carpeta no existe o no es un directorio.")
        sys.exit(1)

    second_dir_vids = sorted([f for f in second_dir.iterdir() if f.is_file()])
    total = len(second_dir_vids)
    if total == 0:
        print("No se encontraron videos para comparar")
        return

    all_original_size = 0
    all_coded_size = 0
    vids_To_Delete = []

    for idx, vid in enumerate(second_dir_vids, start=1):
        # Derivar archivo original
        stem = vid.stem

        if stem.endswith('_hevc'):
            orig_stem = stem[:-5]
        elif stem.endswith('_av1'):
            orig_stem = stem[:-4]

        orig = first_dir / (orig_stem + ".mp4")
        orig3gp = first_dir / (orig_stem + ".3gp")
        
        if orig.exists():
            size_orig = orig.stat().st_size or None
        elif orig3gp.exists():
            size_orig = orig3gp.stat().st_size or None
            orig = orig3gp
        else:
            size_orig = None

        size_orig = orig.stat().st_size if orig.exists() else None
        size_sec = vid.stat().st_size

        if size_orig is None:
            print(f"  {YELLOW}[WARN]{RESET} Original no encontrado para comparar tamaño.")
            continue

        mb_orig = bytes_to_mb(size_orig)
        mb_sec = bytes_to_mb(size_sec)
        diff_mb = mb_sec - mb_orig
        pct = (diff_mb / mb_orig * 100) if mb_orig > 0 else 0
        bigger_Than_Margin = pct >= margin_pct

        status = f"{GREEN}[OK]{RESET}" if not bigger_Than_Margin else f"{YELLOW}[WARN]{RESET}"


        # Formatear salida
        print(
            f"[{idx}/{total}] - {orig_stem} - {mb_orig:.1f} MB => {mb_sec:.1f} MB, Δ {format_signed(diff_mb, ' MB')} ({format_signed(pct, '%')}), {status}"
        )
        all_original_size += mb_orig
        all_coded_size += mb_sec
        diff_percentage = (all_coded_size/all_original_size-1)*100

        if bigger_Than_Margin:
            vids_To_Delete.append(vid)

    print(f"\nTamaño Original: {all_original_size:.1f} MB\nTamaño Codificados: {all_coded_size:.1f} MB\nDiferencia: {(all_original_size-all_coded_size):.1f} MB ({diff_percentage:.1f}%)\n")
    print(f"Videos más grandes que el margen: {len(vids_To_Delete)}")

    if delete:
        delete_vids(vids_To_Delete)

if __name__ == '__main__':
    main()