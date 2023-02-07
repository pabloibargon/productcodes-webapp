from PIL import Image  # pillow
import numpy as np
import galois
from scipy import sparse

import math
import os

default_rsCode = galois.ReedSolomon(255,223)
FILENAME_FOR_ENCODED = 'encoded.png'
FILENAME_FOR_CORRECTED = 'corrected.png'
FILENAME_FOR_TEMP = 'tmp.png'

# Formato PNG:
# Internamente se trabaja con formato PNG porque se comprime sin perdida
# 'lossless'. Necesitamos que los bytes sean exactamente iguales para que el
# codigo funcione.

##################  E N C O D I N G  ###################

def encode_row(row,image_size,rsCode : galois.ReedSolomon):
    nChunks = image_size[1] // rsCode.k
    GF = rsCode.field
    if image_size[1] % rsCode.k == 0:
        nChunks = nChunks - 1
    parity_bits = []
    for i in range(nChunks):
        parity_bits.append(
            rsCode.encode(GF(row[i * rsCode.k : (i + 1) * rsCode.k]), output="parity")
        )
    # Bloque posiblemente incompleto
    parity_bits.append(rsCode.encode(GF(row[rsCode.k * nChunks :]), output="parity"))

    parity_bits = [np.array(arr) for arr in parity_bits]
    return np.concatenate(parity_bits)

def encode_image_rows(data,rsCode : galois.ReedSolomon) :
    image_size = data.shape

    rs = data[:, :, 0]
    gs = data[:, :, 1]
    bs = data[:, :, 2]
    # Codigo comunmente utilizado, simbolos en F_2^8, perfecto para bytes
    # Codficacion por filas (sup. <223 px de ancho)

    rsCode = galois.ReedSolomon(255, 223)
    GF = rsCode.field

    encoded_rs = np.array([encode_row(row,image_size,rsCode) for row in rs])
    encoded_gs = np.array([encode_row(row,image_size,rsCode) for row in gs])
    encoded_bs = np.array([encode_row(row,image_size,rsCode) for row in bs])

    # Out:
    encoded_data = np.zeros(
        shape=(
            image_size[0],
            encoded_rs.shape[1] + image_size[1],
            3,
        ),
        dtype="uint8",
    )
    encoded_data[:, : image_size[1], :] = data
    encoded_data[:, image_size[1] :, 0] = encoded_rs
    encoded_data[:, image_size[1] :, 2] = encoded_bs
    encoded_data[:, image_size[1] :, 1] = encoded_gs

    return encoded_data

def encode_image(data,rsCode : galois.ReedSolomon=default_rsCode):
    return encode_image_rows(encode_image_rows(data,rsCode).transpose((1,0,2)),rsCode).transpose((1,0,2))

def encode_image_from_path(in_path,out_dir,rsCode=default_rsCode):
    print('encode in: ' + in_path)
    im = Image.open(in_path).convert('RGB')
    data = np.array(im)
    encoded_data = encode_image(data,rsCode)
    Image.fromarray(encoded_data).save(os.path.join(out_dir,FILENAME_FOR_ENCODED))


##################  D E C O D I N G  ###################

def decode_row(row,image_size,rsCode : galois.ReedSolomon):
    chunk = np.zeros((rsCode.n), dtype="uint8")
    nChunks = image_size[1] // rsCode.k
    decoded_row = []
    if image_size[1] % rsCode.k == 0:
        nChunks = nChunks - 1
    for i in range(nChunks):
        chunk[: rsCode.k] = row[rsCode.k * i : rsCode.k * (i + 1)]
        chunk[rsCode.k :] = row[
            image_size[1]
            + i * (rsCode.n - rsCode.k) : image_size[1]
            + (i + 1) * (rsCode.n - rsCode.k)
        ]
        decoded_chunk = rsCode.decode(chunk)
        decoded_row.append(rsCode.decode(chunk))
    # Bloque posiblemente incompleto
    last_chunk = np.zeros(
        image_size[1] - rsCode.k * nChunks + (rsCode.n - rsCode.k), dtype="uint8"
    )
    last_chunk[: image_size[1] - rsCode.k * nChunks] = row[
        rsCode.k * nChunks : image_size[1]
    ]
    last_chunk[image_size[1] - rsCode.k * nChunks :] = row[
        image_size[1] + nChunks * (rsCode.n - rsCode.k) :
    ]
    decoded_row.append(rsCode.decode(last_chunk))

    return np.concatenate(decoded_row)

def decode_image_rows(data,original_size,extra_size,rsCode : galois.ReedSolomon):
    image_size = (original_size[0]+extra_size[0],original_size[1])

    decoded_rows = np.zeros((image_size[0], image_size[1], 3), dtype="uint8")
    for i in range(3):
        for j in range(image_size[0]):
            decoded_rows[j, :, i] = decode_row(data[j, :, i],image_size,rsCode)

    return decoded_rows

def decode_image_cols(data,original_size,extra_size,rsCode : galois.ReedSolomon):
    image_size = (original_size[1],original_size[0])

    data = data.transpose((1,0,2))

    decoded_rows = np.zeros((image_size[0], image_size[1], 3), dtype="uint8")
    for i in range(3):
        for j in range(image_size[0]):
            decoded_rows[j, :, i] = decode_row(data[j, :, i],image_size,rsCode)

    return decoded_rows.transpose((1,0,2))

def naive_decode_image(data,original_size,extra_size,rsCode : galois.ReedSolomon):
    decoded_rows = decode_image_rows(data,original_size,extra_size,rsCode)
    decoded_data = decode_image_cols(decoded_rows,original_size,extra_size,rsCode)
    return decoded_data

#Decoding images from path will save multiple images showing possible intermediate steps
def naive_decode_image_from_path(in_path,out_dir,rsCode : galois.ReedSolomon=default_rsCode):
    print('decode in :' + in_path)
    corrupted_data = np.array(Image.open(in_path).convert('RGB'))
    print('corrupted data shape:')
    print(corrupted_data.shape)
    #Compute original size from extended size and rsCode message length
    original_size = (
        corrupted_data.shape[0]-(math.ceil(corrupted_data.shape[0]/rsCode.n))*(rsCode.n-rsCode.k),
        corrupted_data.shape[1]-(math.ceil(corrupted_data.shape[1]/rsCode.n))*(rsCode.n-rsCode.k),
    )
    extra_size=(corrupted_data.shape[0]- original_size[0],corrupted_data[1] - original_size[1])

    decoded_rows = decode_image_rows(corrupted_data,original_size,extra_size,rsCode)
    Image.fromarray(decoded_rows).save(os.path.join(out_dir,'corrected_rows.png'))

    decoded_data = decode_image_cols(decoded_rows,original_size,extra_size,rsCode)
    Image.fromarray(decoded_data).save(os.path.join(out_dir,FILENAME_FOR_CORRECTED))

##################  C O R R U P T I N G ###################
def add_random_noise_from_path(in_path,out_dir,density=0.02):
    print('random in : ' +in_path)
    data = np.array(Image.open(in_path).convert('RGB'))
    corrupted_data = np.zeros_like(data)
    for i in range(3):
        corrupted_data[:, :, i] = data[:, :, i] + sparse.random(
            data.shape[0], data.shape[1], density=density, dtype="uint8"
        )
    im = Image.fromarray(corrupted_data)
    im.save(os.path.join(out_dir,FILENAME_FOR_TEMP))