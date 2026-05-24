"""
Módulo para el manejo de canales de señales estéreo en ficheros WAVE.

Autor: Pere Villaronga Folguera
Descripción: Funciones para extraer, combinar y codificar canales 
de audio (izquierdo y derecho) en ficheros WAVE utilizando 
exclusivamente la biblioteca estándar 'struct'.
"""

import struct

def leer_cabecera(f):
    """
    Lee y valida la cabecera de un fichero WAVE abierto en modo binario.
    Devuelve los parámetros clave: (num_channels, sample_rate, bits_per_sample, num_samples).
    """
    datos = f.read(44)
    if len(datos) < 44:
        raise ValueError("El fichero es demasiado corto para ser un WAVE válido.")
    
    # Desempaquetamos los 44 bytes de la cabecera estándar de PCM
    cabecera = struct.unpack('<4sI4s4sIHHIIHH4sI', datos)
    
    if cabecera[0] != b'RIFF' or cabecera[2] != b'WAVE' or cabecera[3] != b'fmt ':
        raise ValueError("Formato de fichero no soportado (debe ser WAVE PCM lineal).")
        
    num_channels = cabecera[6]
    sample_rate = cabecera[7]
    bits_per_sample = cabecera[10]
    data_size = cabecera[12]
    
    # Calculamos el número total de muestras por canal
    num_samples = data_size // (num_channels * (bits_per_sample // 8))
    
    return num_channels, sample_rate, bits_per_sample, num_samples

def escribir_cabecera(f, num_channels, sample_rate, bits_per_sample, num_samples):
    """
    Genera y escribe la cabecera de un fichero WAVE.
    """
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = num_samples * block_align
    chunk_size = 36 + data_size
    
    cabecera = struct.pack('<4sI4s4sIHHIIHH4sI',
                           b'RIFF', chunk_size, b'WAVE',
                           b'fmt ', 16, 1, num_channels,
                           sample_rate, byte_rate, block_align, bits_per_sample,
                           b'data', data_size)
    f.write(cabecera)


def estereo2mono(ficEste, ficMono, canal=2):
    """
    Lee un fichero WAVE estéreo y escribe un fichero WAVE monofónico.
    canal=0: L, canal=1: R, canal=2: (L+R)/2, canal=3: (L-R)/2.
    """
    with open(ficEste, 'rb') as f_in, open(ficMono, 'wb') as f_out:
        num_channels, sample_rate, bits, num_samples = leer_cabecera(f_in)
        
        if num_channels != 2:
            raise ValueError("El fichero de entrada debe ser estéreo.")
            
        # Leemos todas las muestras de golpe
        datos_crudos = f_in.read()
        muestras = struct.unpack(f"<{num_samples * 2}h", datos_crudos)
        
        # Separamos los canales usando rebanados (slicing)
        canal_l = muestras[0::2]
        canal_r = muestras[1::2]
        
        # Operamos con comprensiones según el canal solicitado
        if canal == 0:
            mono_muestras = canal_l
        elif canal == 1:
            mono_muestras = canal_r
        elif canal == 2:
            mono_muestras = [(l + r) // 2 for l, r in zip(canal_l, canal_r)]
        elif canal == 3:
            mono_muestras = [(l - r) // 2 for l, r in zip(canal_l, canal_r)]
        else:
            raise ValueError("Argumento 'canal' no válido (debe ser 0, 1, 2 o 3).")
            
        # Escribimos cabecera y datos
        escribir_cabecera(f_out, 1, sample_rate, 16, num_samples)
        f_out.write(struct.pack(f"<{num_samples}h", *mono_muestras))

        
def mono2estereo(ficIzq, ficDer, ficEste):
    """
    Lee dos ficheros WAVE monofónicos y los combina en uno estéreo.
    """
    with open(ficIzq, 'rb') as f_l, open(ficDer, 'rb') as f_r, open(ficEste, 'wb') as f_out:
        ch_l, sr_l, bits_l, samples_l = leer_cabecera(f_l)
        ch_r, sr_r, bits_r, samples_r = leer_cabecera(f_r)
        
        if ch_l != 1 or ch_r != 1:
            raise ValueError("Los ficheros de entrada deben ser monofónicos.")
        if sr_l != sr_r or samples_l != samples_r:
            raise ValueError("Los ficheros de entrada deben tener la misma duración y frecuencia.")
            
        datos_l = struct.unpack(f"<{samples_l}h", f_l.read())
        datos_r = struct.unpack(f"<{samples_r}h", f_r.read())
        
        # Intercalamos las muestras usando comprensión plana
        muestras_estereo = [muestra for par in zip(datos_l, datos_r) for muestra in par]
        
        escribir_cabecera(f_out, 2, sr_l, 16, samples_l)
        f_out.write(struct.pack(f"<{samples_l * 2}h", *muestras_estereo))

def codEstereo(ficEste, ficCod):
    """
    Codifica un fichero estéreo (16 bits) a un fichero mono (32 bits),
    almacenando la semisuma en los 16 bits superiores y la semidiferencia
    en los 16 bits inferiores.
    """
    with open(ficEste, 'rb') as f_in, open(ficCod, 'wb') as f_out:
        num_channels, sample_rate, bits, num_samples = leer_cabecera(f_in)
        
        if num_channels != 2 or bits != 16:
            raise ValueError("El fichero de entrada debe ser estéreo a 16 bits.")
            
        muestras = struct.unpack(f"<{num_samples * 2}h", f_in.read())
        canal_l = muestras[0::2]
        canal_r = muestras[1::2]
        
        # Calculamos y combinamos con bits: (suma desplazada 16 bits) OR (diferencia sin extensión de signo)
        muestras_32 = [
            (((l + r) // 2) << 16) | (((l - r) // 2) & 0xFFFF)
            for l, r in zip(canal_l, canal_r)
        ]
        
        # Guardamos como un archivo mono, pero de 32 bits (formato 'i' en struct)
        escribir_cabecera(f_out, 1, sample_rate, 32, num_samples)
        f_out.write(struct.pack(f"<{num_samples}i", *muestras_32))


def decEstereo(ficCod, ficEste):
    """
    Decodifica un fichero mono de 32 bits en uno estéreo de 16 bits,
    recuperando los canales izquierdo y derecho a partir de la semisuma y semidiferencia.
    """
    with open(ficCod, 'rb') as f_in, open(ficEste, 'wb') as f_out:
        num_channels, sample_rate, bits, num_samples = leer_cabecera(f_in)
        
        if num_channels != 1 or bits != 32:
            raise ValueError("El fichero codificado debe ser monofónico a 32 bits.")
            
        muestras_32 = struct.unpack(f"<{num_samples}i", f_in.read())
        
        # Reconstruimos usando comprensión. Convertimos el complemento a 2 de 16 bits si es necesario.
        # Desempaquetar la semidiferencia: (val & 0xFFFF) y si es > 32767 restar 65536
        reconstruccion = [
            (
                (val >> 16) + (val & 0xFFFF if (val & 0xFFFF) <= 32767 else (val & 0xFFFF) - 65536), # L = Suma + Dif
                (val >> 16) - (val & 0xFFFF if (val & 0xFFFF) <= 32767 else (val & 0xFFFF) - 65536)  # R = Suma - Dif
            )
            for val in muestras_32
        ]
        
        muestras_estereo = [muestra for par in reconstruccion for muestra in par]
        
        escribir_cabecera(f_out, 2, sample_rate, 16, num_samples)
        f_out.write(struct.pack(f"<{num_samples * 2}h", *muestras_estereo))