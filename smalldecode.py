#!/usr/bin/env python3
"""
Script para comprobar la decodificación AV1 de todos los videos en un directorio.
Muestra OK en verde si la decodificación es exitosa, o ERROR en rojo si falla.
"""
import argparse
import os
import subprocess
import sys

# Códigos ANSI para colores
GREEN = '\033[32m'
RED = '\033[31m'
RESET = '\033[0m'

VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.webm', '.mov', '.avi', '.m4v')


def is_video_file(filename: str) -> bool:
    """Devuelve True si el archivo tiene una extensión de video conocida."""
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def check_decode(path: str) -> bool:
    """
    Intenta decodificar el video con ffmpeg y envía la salida a null.
    Retorna True si la decodificación no reporta errores.
    """
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-loglevel', 'error',
        '-i', path,
        '-f', 'null',
        '-'  # salida a null
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except FileNotFoundError:
        print(f"{RED}Error: ffmpeg no está instalado o no se encuentra en el PATH{RESET}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Comprueba decodificación AV1 de videos en un directorio.'
    )
    parser.add_argument(
        'directory',
        help='Directorio raíz para escanear archivos de video'
    )
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"{RED}Error: '{args.directory}' no es un directorio válido{RESET}")
        sys.exit(1)

    for root, _, files in os.walk(args.directory):
        for filename in files:
            if is_video_file(filename):
                filepath = os.path.join(root, filename)
                ok = check_decode(filepath)
                status = f"{GREEN}OK{RESET}" if ok else f"{RED}ERROR{RESET}"
                print(f"{filepath}: {status}")


if __name__ == '__main__':
    main()
