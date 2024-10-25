import os
import base64
import aiohttp

from io import BytesIO
from pathlib import Path
from pydub import AudioSegment
from typing_extensions import Self
from pydantic import BaseModel
from pydantic_core import core_schema
from typing import TYPE_CHECKING, TypeAlias, Literal, overload

from ..common_utils import hash_md5, run_any_func


AudioFormat: TypeAlias = Literal["wav", "mp3", "aac", "flac", "opus", "pcm", "ogg"]


@overload
async def get_audio(audio: str | bytes | Path | None) -> bytes: ...
@overload
async def get_audio(
    audio: str | bytes | Path | None, return_mode: Literal["bytes", "audio"] = "audio"
) -> AudioSegment: ...

async def get_audio(audio: str | bytes | Path | None, return_mode: Literal["bytes", "audio"] = "bytes"):
    """
    Get audio bytes from audio source.
    Args:
        - audio: the audio source. It can be a url, base64 string or bytes.
        - return_mode: the return mode. It can be 'bytes' or 'audio'(AudioSegment object).
    """

    format_byte_audio_for_return = lambda audio: (
        audio if return_mode == "bytes" else AudioSegment.from_file(BytesIO(audio))
    )
    if isinstance(audio, str):
        if len(audio) < 2048 and ('/' in audio or '\\' in audio) and '.' in audio:
            if os.name == 'nt':
                if not audio.startswith('http'):
                    audio = Path(audio)
            elif ':' not in audio:
                audio = Path(audio)
    
    if not audio:
        return None
    if isinstance(audio, bytes):
        return format_byte_audio_for_return(audio)
    elif isinstance(audio, str):
        if audio.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(audio) as response:
                    data = await response.read()
                    if return_mode == "bytes":
                        return data
                    else:
                        return AudioSegment.from_file(BytesIO(data))
        elif audio.startswith("data:"):
            audio = audio.split("base64,")[-1]

        data = base64.b64decode(audio)
        return format_byte_audio_for_return(data)
    elif isinstance(audio, Path):
        with open(audio, "rb") as f:
            data = f.read()
            return format_byte_audio_for_return(data)
    else:
        raise ValueError("Unexpected audio data type. It should be a url, base64 string or bytes.")


class Audio(AudioSegment):
    '''advance audio model for easy validation in pydantic.'''
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        def validator(data):
            if isinstance(data, dict):
                if ('voice' in data) or ('sound' in data) or ('audio' in data) or ('data' in data) or ('source' in data) or ('url' in data):
                    audio = data.get('voice', data.get('sound', data.get('audio', data.get('data', data.get('source', data.get('url'))))))
                    if audio and isinstance(audio, (Path, str, bytes, AudioSegment)):
                        data = audio # continue to the next step
                        
            if isinstance(data, (Path, str, bytes, AudioSegment)):
                data = cls.Load(data)
            return data
        
        def serializer(audio: 'Audio'):
            return audio.to_base64()    # will be dump as wav base64 string in pydantic

        validate_schema = core_schema.no_info_after_validator_function(validator, core_schema.any_schema())
        serialize_schema = core_schema.plain_serializer_function_ser_schema(serializer)
        return core_schema.json_or_python_schema(
            json_schema=validate_schema,
            python_schema=validate_schema,
            serialization=serialize_schema
        )
    
    def to_bytes(self, format: AudioFormat='wav'):
        '''
        Get the data of this audio in bytes format.
        You can specify the output format of the audio bytes.
        '''
        buffer = BytesIO()
        self.export(buffer, format=format)
        return buffer.getvalue()
    
    def to_base64(self, format: AudioFormat='wav')->str:
        '''
        Get the data of this audio in base64 format.
        You can specify the output format of the audio bytes.
        '''
        return base64.b64encode((self.to_bytes(format=format))).decode()

    def to_md5_hash(self, format: AudioFormat='wav')->str:
        return hash_md5(self.to_bytes(format=format))
    
    @classmethod
    def Load(cls, data: str|bytes|AudioSegment|Path)->Self:
        '''Load audio from data. If the data is already an AudioSegment, it will be casted to this class.'''
        if isinstance(data, (str, bytes, Path)):
            data = run_any_func(get_audio, data, return_mode='audio')
            if data is None:
                raise ValueError('Invalid audio data')
        if not isinstance(data, cls) and isinstance(data, AudioSegment):
            data = cls.CastAudio(data)
        return data # type: ignore
        
    @classmethod
    def CastAudio(cls, audio: AudioSegment)->Self:   
        '''change origin audio type(AudioSegment) to this advance audio type'''
        if isinstance(audio, cls):
            return audio
        setattr(audio, '__class__', cls)
        return audio  # type: ignore
    
    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} duration={self.duration_seconds}s>'
    
    if not TYPE_CHECKING:
        def __getattribute__(self, name: str):
            attr = super().__getattribute__(name)
            if not (name.startswith('__') and name.endswith('__')):
                if not isinstance(attr, type) and callable(attr):
                    return _AudioRetWrapper(attr)
            return attr

class _AudioRetWrapper:
    def __init__(self, f):
        self.f = f
        if hasattr(self.f, '__doc__'):
            self.__doc__ = self.f.__doc__
        
    def __getattr__(self, name: str):
        return getattr(self.f, name)
        
    def __call__(self, *args, **kwargs):
        r = self.f(*args, **kwargs)
        if isinstance(r, AudioSegment):
            return Audio.CastAudio(r)
        return r

class AudioChunk(BaseModel):
    '''CLass for receiving chunk audio data from server'''
    data: str
    '''base64 encoded audio data'''
    end: bool
    '''whether the audio is the last chunk'''
    stage: int
    '''stage of the audio generation process, for internal debug only.'''

    @property
    def data_bytes(self):
        '''get the audio data in bytes format'''
        return base64.b64decode(self.data)


__all__ = ['Audio', 'get_audio', 'AudioChunk']