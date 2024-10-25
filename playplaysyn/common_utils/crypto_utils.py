import uuid
import hashlib
import secrets

from io import BytesIO
from pathlib import Path
from typing import Union, Literal, overload

# region random
def gen_alphanum_string(len: int):
    return ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(len))

def gen_alphanum_string_with_special_chars(len: int):
    return ''.join(secrets.choice(r'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789;:[]{}()<>.,/?!@#$%^&*_-+=`') for _ in range(len))

def gen_digits(len: int):
    return ''.join(secrets.choice('0123456789') for _ in range(len))

def gen_apikey(len=64):
    return gen_alphanum_string(len)

def gen_pw(len=16):
    return gen_alphanum_string(len)

def gen_salt(len=32):
    return gen_alphanum_string_with_special_chars(len)

def gen_verify_code(len=6):
    '''return 6 digits (phone) verification code'''
    return gen_digits(len)

def gen_uuid4(with_bar=False) -> str:
    '''
    Return a random uuid4 string.
    If with_bar is True, return uuid4 with `-`, else they will be removed.
    
    Final Length:
        - with_bar=True: 36
        - with_bar=False: 32
    '''
    if with_bar:
        return str(uuid.uuid4())
    return uuid.uuid4().hex
# endregion

# region hash
@overload
def hash_sha256(data: str|bytes, encode: str='utf-8')->str: ...
@overload
def hash_sha256(data: str|bytes, encode: str='utf-8', mode: Literal['hex', 'bytes']='bytes')->Union[str, bytes]: ...

def hash_sha256(data: Union[str, bytes], encode: str = 'utf-8', mode: Literal['hex', 'bytes'] = 'hex'):
    '''
    Return the SHA256 hash of the text (len=64)
    Param:
        data: str or bytes
        encode: encoding of the data(only used when data is str)
        mode: 'hex' or 'bytes' (default='hex') for digest mode
    '''
    mode = mode.lower() # type: ignore
    if mode not in ('hex', 'bytes'):
        raise ValueError(f'Invalid mode: {mode}')
    if isinstance(data, str):
        hashed = hashlib.sha256(data.encode(encode))
    else:
        hashed = hashlib.sha256(data)
    if mode == 'hex':
        return hashed.hexdigest()
    else:
        return hashed.digest()

@overload
def hash_md5(data: str|bytes, encode: str='utf-8')->str: ...
@overload
def hash_md5(data: str|bytes, encode: str='utf-8', mode: Literal['hex', 'bytes']='bytes')->Union[str, bytes]: ...

def hash_md5(data: Union[str, bytes], encode: str = 'utf-8', mode: Literal['hex', 'bytes'] = 'hex'):
    '''
    Return the MD5 hash of the text (len=32)
    Param:
        data: str or bytes
        encode: encoding of the data(only used when data is str)
        mode: 'hex' or 'bytes' (default='hex') for digest mode
    '''
    mode = mode.lower() # type: ignore
    if mode not in ('hex', 'bytes'):
        raise ValueError(f'Invalid mode: {mode}')
    if isinstance(data, str):
        hashed = hashlib.md5(data.encode(encode))
    else:
        hashed = hashlib.md5(data)
    if mode == 'hex':
        return hashed.hexdigest()
    else:
        return hashed.digest()

@overload
def hash_sha1(data: str|bytes, encode: str='utf-8')->str: ...
@overload
def hash_sha1(data: str|bytes, encode: str='utf-8', mode: Literal['hex', 'bytes']='bytes')->Union[str, bytes]: ...

def hash_sha1(data: Union[str, bytes], encode: str = 'utf-8', mode: Literal['hex', 'bytes'] = 'hex'):
    '''
    Return the SHA1 hash of the text (len=40)
    Param:
        data: str or bytes
        encode: encoding of the data(only used when data is str)
        mode: 'hex' or 'bytes' (default='hex') for digest mode
    '''
    mode = mode.lower() # type: ignore
    if mode not in ('hex', 'bytes'):
        raise ValueError(f'Invalid mode: {mode}')
    if isinstance(data, str):
        hashed = hashlib.sha1(data.encode(encode))
    else:
        hashed = hashlib.sha1(data)
    if mode == 'hex':
        return hashed.hexdigest()
    else:
        return hashed.digest()


def hash_file_sha256(filePath: str | Path | bytes, 
                     mode: Literal['hex', 'bytes'] = 'hex',
                     chunk:int=4096):
    '''
    Hash the file data and return 64 hex string or 32 bytes
    Args:
        filePath: str | Path | bytes
        mode: 'hex' or 'bytes' (default='hex') for digest mode
        chunk: int, default=4096 (chunk size for hashing)
    '''
    h = hashlib.sha256()
    reader = BytesIO(filePath) if isinstance(filePath, bytes) else open(filePath, 'rb')
    while True:
        data = reader.read(4096)
        if not data:
            break
        h.update(data)
    reader.close()
    return h.hexdigest() if mode == 'hex' else h.digest()

def hash_file_md5(file: str | Path | bytes, 
                  mode: Literal['hex', 'bytes'] = 'hex',
                  chunk:int=4096):
    '''
    Hash the file data and return 32 hex string or 16 bytes.
    Args:
        file: str | Path | bytes
        mode: 'hex' or 'bytes' (default='hex') for digest mode
        chunk: int, default=4096 (chunk size for hashing)
    '''
    h = hashlib.md5()
    if isinstance(file, bytes):
        reader = BytesIO(file)
    else:
        reader = open(file, 'rb')
    while True:
        data = reader.read(chunk)
        if not data:
            break
        h.update(data)
    reader.close()
    return h.hexdigest() if mode == 'hex' else h.digest()

def hash_file_sha1(file: str | Path | bytes, 
                   mode: Literal['hex', 'bytes'] = 'hex',
                   chunk:int=4096):
    '''
    Hash the file data and return 40 hex string or 20 bytes
    Args:
        file: str | Path | bytes
        mode: 'hex' or 'bytes' (default='hex') for digest mode
        chunk: int, default=4096 (chunk size for hashing)
    '''
    h = hashlib.sha1()
    if isinstance(file, bytes):
        reader = BytesIO(file)
    else:
        reader = open(file, 'rb')
    while True:
        data = reader.read(chunk)
        if not data:
            break
        h.update(data)
    reader.close()
    return h.hexdigest() if mode == 'hex' else h.digest()
# endregion


if __name__ == '__main__':
    print(gen_alphanum_string(16))
    print(hash_md5('123'))