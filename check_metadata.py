import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

# Extensiones a procesar
IMAGE_EXTS = ['.jpg', '.jpeg', '.png']
VIDEO_EXTS = ['.mp4', '.mov', '.mkv', '.avi']


def get_image_datetime(path: Path):
    """
    Extrae DateTimeOriginal de la imagen usando exiftool en formato YYYYMMDD_HHMMSS
    """
    cmd = [
        'exiftool',
        '-DateTimeOriginal',
        '-d', '%Y%m%d_%H%M%S',
        '-S', '-s',
        str(path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    out = proc.stdout.strip()
    return out or None


def get_video_creation(path: Path):
    """
    Extrae creation_time de video con ffprobe en formato YYYYMMDD_HHMMSS
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'format_tags=creation_time',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    ts = proc.stdout.strip()
    if not ts:
        return None
    # ffprobe retorna algo como 2024-10-18T21:52:16.000000Z
    try:
        date, time = ts.split('T')
        time = time.split('.')[0]
        return date.replace('-', '') + '_' + time.replace(':', '')
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Comprueba que el metadata de fecha/hora coincida con el nombre de archivo yyyymmdd_HHMMSS.ext'
    )
    parser.add_argument('dir', help='Directorio con archivos estandarizados')
    args = parser.parse_args()

    base = Path(args.dir)
    if not base.is_dir():
        print(f"El directorio {base} no existe o no es válido.")
        sys.exit(1)

    files = sorted([f for f in base.iterdir() if f.suffix.lower() in IMAGE_EXTS + VIDEO_EXTS])
    total = len(files)
    if total == 0:
        print("No se encontraron archivos para validar metadatos.")
        return

    for idx, path in enumerate(files, start=1):
        print(f"[{idx}/{total}] {path.name}")
        stem = path.stem  # formato yyyymmdd_HHMMSS

        # Seleccionar modo según extensión
        if path.suffix.lower() in IMAGE_EXTS:
            meta = get_image_datetime(path)
        else:
            meta = get_video_creation(path)

        if not meta:
            print(f"  {YELLOW}[WARN]{RESET} No se encontró metadata de fecha/hora.")
            continue

        if meta == stem:
            print(f"  {GREEN}[OK]{RESET} Metadata coincide: {meta}")
        else:
            print(f"  {RED}[ERROR]{RESET} Metadata difiere. Nombre: {stem}, Metadata: {meta}")

if __name__ == '__main__':
    main()