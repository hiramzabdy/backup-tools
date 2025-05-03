import sys
import subprocess
import argparse
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'


def seconds_to_mmss(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def get_duration(path):
    """
    Devuelve la duración en segundos del archivo de video usando ffprobe.
    """
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
        return None


def validate_decode(av1_path):
    """
    Prueba de decodificación usando el decoder interno de FFmpeg para AV1.
    Forzamos el codec de decodificación software con '-c:v av1'.
    Comando:
        ffmpeg -v error -c:v av1 -i archivo -f null -
    Devuelve (True, None) si pasa, o (False, [líneas de error]) si falla.
    """
    cmd = [
        'ffmpeg',
        '-v', 'error',
        '-c:v', 'av1',    # forzar decoder interno AV1 en software
        '-i', str(av1_path),
        '-f', 'null',
        '-'
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode == 0:
        return True, None
    else:
        return False, proc.stderr.splitlines()


def main():
    parser = argparse.ArgumentParser(
        description='Valida integridad de videos AV1 en vid_av1/'
    )
    parser.add_argument('base_dir', help='Directorio raíz con vid_av1/')
    parser.add_argument(
        'mode',
        choices=['time', 'code', 'both'],
        help='Tipo de comprobación: time, code o both'
    )
    parser.add_argument(
        '--margin', type=float, default=1.0,
        help='Margen de diferencia de duración en segundos (default: 1s)'
    )
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
        print(f"[{idx}/{total}] ==> {av1.name}")

        # Comprobación de decodificación
        if args.mode in ['code', 'both']:
            ok_decode, errors = validate_decode(av1)
            if ok_decode:
                print(f"  {GREEN}[OK]{RESET} Decodificación correcta.")
            else:
                print(f"  {RED}[ERROR]{RESET} Falló decodificación:")
                for line in errors:
                    print(f"    {line}")
                if args.mode == 'code':
                    continue
                if args.mode == 'both':
                    continue

        # Comprobación de tiempo
        if args.mode in ['time', 'both']:
            orig_stem = av1.stem[:-4] if av1.stem.endswith('_av1') else av1.stem
            orig = base / (orig_stem + '.mp4') #av1.suffix

            dur_av1 = get_duration(av1)
            dur_orig = get_duration(orig) if orig.exists() else None

            if dur_av1 is None:
                print(f"  {YELLOW}[WARN]{RESET} No se pudo leer duración de AV1.")
            elif dur_orig is None:
                print(f"  {YELLOW}[WARN]{RESET} Original no encontrado para comparar duración.")
            else:
                diff = abs(dur_av1 - dur_orig)
                mmss_orig = seconds_to_mmss(dur_orig)
                mmss_av1 = seconds_to_mmss(dur_av1)
                if diff <= args.margin:
                    print(f"  {GREEN}[OK]{RESET} Duración OK (orig: {mmss_orig}, av1: {mmss_av1}).")
                else:
                    print(
                        f"  {RED}[ERROR]{RESET} Duración difiere más de {args.margin}s: "
                        f"orig {mmss_orig}, av1 {mmss_av1}."
                    )

if __name__ == '__main__':
    main()