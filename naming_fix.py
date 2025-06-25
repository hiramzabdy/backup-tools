import os
import re
import sys
from pathlib import Path

def estandarizar_nombres(directorio):
    patron_fecha_hora = re.compile(r'(\d{8})[_\-]?(\d{6})')  # Ej: 20240104_162823 o 20240104-162823

    for archivo in os.listdir(directorio):
        ruta_original = os.path.join(directorio, archivo)
        if not os.path.isfile(ruta_original):
            continue

        nombre, extension = os.path.splitext(archivo)
        extension = extension.lower()

        # Solo interesan estos formatos
        if extension not in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.mkv', '.avi', '.3gp']:
            continue

        m = patron_fecha_hora.search(nombre)
        # Verificamos que el patrón llegue hasta el final del nombre original
        if m and m.end() == len(nombre):
            fecha = m.group(1)
            hora = m.group(2)[:6]  # descartamos posibles milisegundos
            nuevo_nombre = f"{fecha}_{hora}{extension}"
            nueva_ruta = os.path.join(directorio, nuevo_nombre)

            # Renombrar solo si no existe ya un archivo con ese nombre
            if ruta_original != nueva_ruta and not os.path.exists(nueva_ruta):
                print(f"Renombrando: {archivo} → {nuevo_nombre}")
                os.rename(ruta_original, nueva_ruta)
            else:
                # Si existe, dejamos el archivo con su nombre original
                print(f"Omitiendo (ya existe o sin cambios): {archivo}")

def estandarizar_screenshots(directorio):
    patrones = [
        # Captura de pantalla_2017-01-04-03-24-19.png
        re.compile(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_]?[- ]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})'),
        # _20170802_140411.JPG, SAVE_20190729_041118.jpg, IMG_20170807_225549.jpg
        re.compile(r'(\d{8})[_\-](\d{6})'),
    ]

    app_extra = re.compile(r'[_-]([a-zA-Z0-9\.]+)\.(jpg|jpeg|png|mp4|mov|mkv|avi)$')

    for archivo in os.listdir(directorio):
        ruta_original = os.path.join(directorio, archivo)
        if not os.path.isfile(ruta_original):
            continue

        nombre, extension = os.path.splitext(archivo)
        extension = extension.lower()

        if extension not in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.mkv', '.avi', '.3gp']:
            continue

        fecha = hora = app = None

        for patron in patrones:
            coincidencia = patron.search(nombre)
            if coincidencia:
                if len(coincidencia.groups()) == 6:
                    # yyyy-mm-dd-hh-mm-ss separado
                    yyyy, mm, dd, hh, mi, ss = coincidencia.groups()
                    fecha = f"{yyyy}{mm}{dd}"
                    hora = f"{hh}{mi}{ss}"
                elif len(coincidencia.groups()) == 2:
                    # yyyymmdd_hhmmss
                    fecha = coincidencia.group(1)
                    hora = coincidencia.group(2)[:6]
                break

        if not fecha or not hora:
            continue  # Si no se puede extraer la fecha/hora, saltar

        # Intentamos extraer el nombre de la app (opcional)
        app_match = app_extra.search(archivo)
        if app_match:
            app = app_match.group(1)

        nuevo_nombre = f"{fecha}_{hora}"
        if app:
            nuevo_nombre += f"_{app}"
        nuevo_nombre += extension

        nueva_ruta = os.path.join(directorio, nuevo_nombre)

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