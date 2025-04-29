import os
import re
import sys
from pathlib import Path

def estandarizar_nombres(directorio):
    patron_fecha_hora = re.compile(r'(\d{8})[_\-]?(\d{6})')  # Busca algo como 20240104_162823 o 20240104-162823

    for archivo in os.listdir(directorio):
        ruta_original = os.path.join(directorio, archivo)
        if not os.path.isfile(ruta_original):
            continue

        nombre, extension = os.path.splitext(archivo)
        extension = extension.lower()

        if extension not in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.mkv', '.avi', '.3gp']:
            continue

        coincidencia = patron_fecha_hora.search(nombre)
        if coincidencia:
            fecha = coincidencia.group(1)
            hora = coincidencia.group(2)[:6]  # En caso de que haya milisegundos o más
            nuevo_nombre = f"{fecha}_{hora}{extension}"
            nueva_ruta = os.path.join(directorio, nuevo_nombre)

            # Evita sobreescribir archivos existentes
            if ruta_original != nueva_ruta:
                contador = 1
                while os.path.exists(nueva_ruta):
                    nueva_ruta = os.path.join(
                        directorio,
                        f"{fecha}_{hora}_{contador}{extension}"
                    )
                    contador += 1

                print(f"Renombrando: {archivo} => {os.path.basename(nueva_ruta)}")
                os.rename(ruta_original, nueva_ruta)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python renombrar.py /ruta/del/directorio")
        sys.exit(1)

    carpeta = sys.argv[1]
    estandarizar_nombres(carpeta)
