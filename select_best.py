import sys
import argparse
import shutil
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def bytes_to_mb(b):
    return b / (1024 * 1024)


def main():
    parser = argparse.ArgumentParser(
        description='Selecciona el archivo de menor tamaño entre original y AV1 y lo mueve a final_vid/'
    )
    parser.add_argument('base_dir', help='Directorio raíz con videos originales y vid_av1/')
    args = parser.parse_args()

    base = Path(args.base_dir)
    vid_dir = base / 'vid_av1'
    final_dir = base / 'final_vid'
    if not vid_dir.is_dir():
        print(f"La carpeta {vid_dir} no existe o no es un directorio.")
        sys.exit(1)
    final_dir.mkdir(exist_ok=True)

    av1_files = sorted([f for f in vid_dir.iterdir() if f.is_file()])
    total = len(av1_files)
    if total == 0:
        print("No se encontraron archivos en vid_av1/.")
        return

    for idx, av1 in enumerate(av1_files, start=1):
        # nombre base sin sufijo _av1
        stem = av1.stem
        basename = stem[:-4] if stem.endswith('_av1') else stem
        orig = base / (basename + av1.suffix)

        size_av1 = av1.stat().st_size
        size_orig = orig.stat().st_size if orig.exists() else None
        mb_av1 = bytes_to_mb(size_av1)
        mb_orig = bytes_to_mb(size_orig) if size_orig is not None else None

        # Encabezado
        print(f"[{idx}/{total}] ==> {basename}")

        # Si no existe original
        if size_orig is None:
            print(f"  {YELLOW}[WARN]{RESET} Original no encontrado; moviendo codificado ({mb_av1:.1f} MB)")
            shutil.move(str(av1), str(final_dir / av1.name))
            continue

        # Comparar tamaños
        if size_av1 < size_orig:
            print(
                f"  {GREEN}[OK]{RESET} Codificado más pequeño: "
                f"{mb_av1:.1f} MB < {mb_orig:.1f} MB; moviendo codificado"
            )
            shutil.move(str(av1), str(final_dir / av1.name))
        else:
            print(
                f"  {YELLOW}[WARN]{RESET} Original más pequeño: "
                f"{mb_orig:.1f} MB <= {mb_av1:.1f} MB; moviendo original"
            )
            shutil.move(str(orig), str(final_dir / orig.name))

    print(f"\nProceso completado: archivos movidos a {final_dir}")

if __name__ == '__main__':
    main()