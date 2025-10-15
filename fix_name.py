import os
import re
import sys
from pathlib import Path

def estandarizar_nombres(directorio):
    """
    Renombra archivos de imagen y video en un directorio a un formato de fecha y hora
    estandarizado (YYYYMMDD_HHMMSS), manejando múltiples formatos de nombre de archivo.

    Args:
        directorio (str): La ruta al directorio que contiene los archivos.
    """
    # Patrón 1: Captura formatos comunes como 'YYYYMMDD_HHMMSS' o 'IMG_YYYYMMDD_HHMMSS...'.
    # Busca 8 dígitos (fecha), un separador opcional, y 6 dígitos (hora).
    patron_principal = re.compile(r'(\d{8})[_-]?(\d{6})')
    
    # Patrón 2: Para usarse sobre un nombre de archivo sin separadores.
    # Busca una secuencia directa de 'YYYYMMDDHHMMSS'.
    patron_secundario = re.compile(r'(\d{8})(\d{6})')

    if not os.path.isdir(directorio):
        print(f"Error: El directorio '{directorio}' no existe.")
        return

    print(f"Analizando el directorio: {directorio}\n")

    for archivo in os.listdir(directorio):
        ruta_original = os.path.join(directorio, archivo)

        if not os.path.isfile(ruta_original):
            continue

        nombre, extension = os.path.splitext(archivo)
        extension = extension.lower()

        # Filtrar solo los formatos de archivo de interés
        if extension not in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.mkv', '.avi', '.3gp']:
            continue

        fecha, hora = None, None
        
        # --- Inicio de la lógica de extracción mejorada ---

        # Intento 1: Usar el patrón principal
        match = patron_principal.search(nombre)
        if match:
            fecha = match.group(1)
            hora = match.group(2)
        else:
            # Intento 2: Limpiar el nombre de separadores y usar el patrón secundario
            nombre_limpio = re.sub(r'[-. _]', '', nombre)
            match_sec = patron_secundario.search(nombre_limpio)
            if match_sec:
                fecha = match_sec.group(1)
                hora = match_sec.group(2)

        # --- Fin de la lógica de extracción ---

        # Si se encontró una fecha y hora, proceder a renombrar
        if fecha and hora:
            nuevo_nombre = f"{fecha}_{hora}{extension}"
            nueva_ruta = os.path.join(directorio, nuevo_nombre)

            # Renombrar solo si el nombre es diferente
            if ruta_original != nueva_ruta:
                # Y si no existe ya un archivo con el nuevo nombre para evitar sobrescribir
                if not os.path.exists(nueva_ruta):
                    print(f"✅ Renombrando: {archivo}  =>  {nuevo_nombre}")
                    os.rename(ruta_original, nueva_ruta)
                else:
                    print(f"⚠️  Omitiendo (ya existe): {archivo}  (destino: {nuevo_nombre})")
            # else:
            #     print(f"ℹ️  Omitiendo (nombre sin cambios): {archivo}")
        # else:
        #     print(f"❌ Omitiendo (patrón no encontrado): {archivo}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python renombrar.py /ruta/del/directorio")
        sys.exit(1)

    carpeta = sys.argv[1]
    estandarizar_nombres(carpeta)