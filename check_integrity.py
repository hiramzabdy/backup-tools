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


def validate_decode(output_path):
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
        '-c:v', 'hevc',
        '-i', str(output_path),
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
        description='Valida integridad de videos codificados HEVC'
    )
    parser.add_argument('base_dir', help='Directorio raíz con videos originales/')
    parser.add_argument('output_dir', help='Directorio raíz con videos codificados/')
    parser.add_argument(
        'mode',
        choices=['time', 'code', 'both'],
        help='Tipo de comprobación: time, code o both'
    )
    parser.add_argument(
        '--margin', type=float, default=0.5,
        help='Margen de diferencia de duración en segundos (default: 0.5s)'
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    output_dir = Path(args.output_dir)

    if not output_dir.is_dir() or not base_dir.is_dir():
        print(f"Uno de los dos directorios no existe.")
        sys.exit(1)

    coded_videos = sorted([f for f in output_dir.iterdir() if f.is_file()])    
    total = len(coded_videos)

    if total == 0:
        print("No se encontraron archivos en " + output_dir + ".")
        return

    for idx, vid in enumerate(coded_videos, start=1):
        print(f"[{idx}/{total}] ==> {vid.name}")

        # Comprobación de tiempo
        if args.mode in ['time', 'both']:
            orig_stem = vid.stem[:-5] if vid.stem.endswith('_hevc') else vid.stem[:-4]
            orig = base_dir / (orig_stem + ".mp4")

            dur_vid = get_duration(vid)
            dur_orig = get_duration(orig)

            if dur_vid is None:
                print(f"  {YELLOW}[WARN]{RESET} No se pudo leer duración del archivo resultante.")
            elif dur_orig is None:
                print(f"  {YELLOW}[WARN]{RESET} Original no encontrado para comparar duración.")
            else:
                diff = abs(dur_vid - dur_orig)
                mmss_orig = seconds_to_mmss(dur_orig)
                mmss_av1 = seconds_to_mmss(dur_vid)
                if diff <= args.margin:
                    print(f"  {GREEN}[OK]{RESET} Duración OK (orig: {mmss_orig}, av1: {mmss_av1}).")
                else:
                    print(
                        f"  {RED}[ERROR]{RESET} Duración difiere más de {args.margin}s: "
                        f"orig {mmss_orig}, av1 {mmss_av1}."
                    )

        # Comprobación de decodificación
        if args.mode in ['code', 'both']:
            ok_decode, errors = validate_decode(vid)
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

if __name__ == '__main__':
    main()