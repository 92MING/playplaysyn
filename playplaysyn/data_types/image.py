import os
import base64
import aiohttp
import requests
import numpy as np

from io import BytesIO
from pathlib import Path
from PIL import Image as PILImage, UnidentifiedImageError
from pydantic_core import core_schema
from typing import Literal, TYPE_CHECKING, overload
from typing_extensions import override, Self

from ..common_utils import hash_md5, run_any_func
from .box2d import Box2D

@overload
async def get_image(img: str | bytes | Path | None) -> bytes: ...
@overload
async def get_image(
    img: str | bytes | Path | None, return_mode: Literal["bytes", "image"] = "image"
) -> PILImage.Image: ...

async def get_image(img: str | bytes | Path | None, return_mode: Literal["bytes", "image"] = "bytes"):
    """
    Get image bytes from image source.
    Args:
        - img: the image source. It can be a url, base64 string or bytes.
        - return_mode: the return mode. It can be 'bytes' or 'image'(PIL PILImage Obj).
    """
    if not img:
        return None
    if isinstance(img, bytes):
        if return_mode == "bytes":
            return img
        else:
            return PILImage.open(BytesIO(img))

    elif isinstance(img, PILImage.Image):
        if return_mode == "bytes":
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        else:
            return img

    elif isinstance(img, str):
        if img.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(img) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to get image from url: `{img}`.")
                    data = await response.read()
                    if return_mode != "bytes":
                        ret = PILImage.open(BytesIO(data))
                    else:
                        ret = data
                    return ret

        elif img.startswith("data:"):
            img = img.split("base64,")[-1]

        data = base64.b64decode(img)
        if return_mode == "bytes":
            return data
        else:
            try:
                return PILImage.open(BytesIO(data))
            except UnidentifiedImageError:
                if len(data) < 256:
                    raise ValueError("Invalid image data. Got: ", data)
                raise ValueError("Invalid image data.")

    elif isinstance(img, Path):
        with open(img, "rb") as f:
            data = f.read()
            if return_mode == "bytes":
                return data
            else:
                return PILImage.open(BytesIO(data))
    else:
        raise ValueError("Unexpected image type. It should be a url, base64 string or bytes.")


def crop_img(
    img: bytes | str | Path | np.ndarray | PILImage.Image,
    region: Box2D,
    return_mode: Literal["bytes", "base64", "image"] = "image",
    color_mode: Literal["unchange", "L", "RGB", "RGBA"] = "unchange",
):
    """
    Cut the image with a given region.

    Args:
        - img: the target image. It can be a url (http/https), base64 string, bytes, path or numpy array.
        - region: the target region to crop.
        - return_mode: the return mode. It can be 'bytes', 'base64'(str) or 'image'(PIL PILImage Obj).
    """
    if isinstance(img, bytes):
        img_obj = PILImage.open(BytesIO(img))
    elif isinstance(img, str):
        if img.startswith("http://") or img.startswith("https://"):
            img_obj = PILImage.open(BytesIO(requests.get(img).content))
        elif os.path.exists(img):
            img_obj = PILImage.open(img)
        else:
            img_obj = PILImage.open(base64.b64decode(img))
    elif isinstance(img, Path):
        img_obj = PILImage.open(img)
    elif isinstance(img, np.ndarray):
        img_obj = PILImage.fromarray(img)
    elif isinstance(img, PILImage.Image):
        img_obj = img
    else:
        raise ValueError("Unexpected image type. It should be a url, base64 string, bytes, path or numpy array.")

    if region.mode == "relative":
        region = region.to_absolute(img_obj.size)
    img_obj = img_obj.crop((region.left_top.x, region.left_top.y, region.right_bottom.x, region.right_bottom.y))  # type: ignore
    if color_mode != "unchange":
        img_obj = img_obj.convert(color_mode)

    if return_mode == "bytes":
        buf = BytesIO()
        img_obj.save(buf, format="PNG")
        return buf.getvalue()
    elif return_mode == "base64":
        buf = BytesIO()
        img_obj.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    else:
        return img_obj


class Image(PILImage.Image):
    '''Advanced Image class with pydantic support'''
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        def validator(data):
            if isinstance(data, dict):
                if ('img' in data) or ('image' in data) or ('source' in data) or ('url' in data):
                    img = data.get('img') or data.get('image') or data.get('source') or data.get('url')
                    if img and isinstance(img, (str, bytes, Path)):
                        data = img # continue to the next step
                        
            if isinstance(data, (str, bytes, Path)):
                data = cls.Load(data)
            return data
        
        def serializer(img: 'Image'):
            if len(img.mode) <= 3:
                mode = 'jpg'
            else:
                mode = 'png'
            return img.to_base64(mode=mode)

        validate_schema = core_schema.no_info_after_validator_function(validator, core_schema.any_schema())
        serialize_schema = core_schema.plain_serializer_function_ser_schema(serializer)
        return core_schema.json_or_python_schema(
            json_schema=validate_schema,
            python_schema=validate_schema,
            serialization=serialize_schema
        )
        
    @classmethod
    def Load(cls, img: str|bytes|Path)->Self:
        '''load image from file bytes, path or url'''
        img_data = run_any_func(get_image, img, return_mode='image')
        if img_data is None:
            raise ValueError('Invalid image data')
        if not img_data.im:
            img_data = img_data.convert(img_data.mode)  # this is required for some image types, e.g. WEBP
        return cls.CastPILImage(img_data)
    
    @property
    def channel_count(self):
        return len(self.getbands())    
    
    @property
    def size_in_bytes(self):
        out = BytesIO()
        if self.format:
            self.save(out, format=self.format)
        else:
            self.save(out, format='PNG')
        last = out.tell()
        out.seek(0)
        return last
    
    @override
    def tobytes(self, encoder_name="raw", mode: Literal['pil', 'jpg', 'png']='pil', *args):
        '''
        get the data of this image in bytes format
        
        Args:
            mode: 'pil', 'jpg', 'png'. 'pil' means the original PIL image format.
        '''
        mode = mode.lower() # type: ignore
        if mode =='pil':
            return super().tobytes(encoder_name, *args)
        else:
            bytes_io = BytesIO()
            format = {'jpg': 'JPEG', 'png': 'PNG'}[mode]
            if format == 'JPEG' and self.channel_count != 3:
                new_img = self.convert('RGB')
                new_img.save(bytes_io, format=format)
            elif format == 'PNG' and self.channel_count != 4:
                new_img = self.convert('RGBA')
                new_img.save(bytes_io, format=format)
            else:
                self.save(bytes_io, format=format)
            return bytes_io.getvalue()
    
    def to_base64(self, mode: Literal['pil', 'jpg', 'png']='pil')->str:
        '''get the data of this image in base64 format'''
        return base64.b64encode(self.tobytes(mode=mode)).decode()

    def to_md5_hash(self, mode: Literal['pil', 'jpg', 'png']='pil')->str:
        return hash_md5(self.tobytes(mode=mode))
        
    @override
    def crop(self, region: Box2D):
        if not isinstance(region, Box2D):
            return super().crop(region)
        img = crop_img(self, region, return_mode='image')
        return self.CastPILImage(img)   # type: ignore
     
    @classmethod
    def CastPILImage(cls, img: PILImage.Image)->Self:   
        '''change origin PIL Image type to this Image type'''
        if isinstance(img, cls):
            return img
        setattr(img, '__class__', cls)
        return img  # type: ignore

    if not TYPE_CHECKING:
        def __getattribute__(self, name: str):
            attr = super().__getattribute__(name)
            if not (name.startswith('__') and name.endswith('__')):
                if not isinstance(attr, type) and callable(attr):
                    return _ImgRetWrapper(attr)
            return attr

class _ImgRetWrapper:
    def __init__(self, f):
        self.f = f
        if hasattr(self.f, '__doc__'):
            self.__doc__ = self.f.__doc__
        
    def __getattr__(self, name: str):
        return getattr(self.f, name)
        
    def __call__(self, *args, **kwargs):
        r = self.f(*args, **kwargs)
        if isinstance(r, PILImage.Image):
            return Image.CastPILImage(r)
        return r


    
__all__ = ['Image']