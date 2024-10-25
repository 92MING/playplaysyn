import base64

from enum import Enum
from typing import Literal, TypeAlias, NamedTuple
from typing_extensions import Self

from .audio import Audio
from .image import Image


# region chat
class ChatStatus(str, Enum):
    '''Chat status for AI character'''
    START = 'start'
    END = 'end'

ChatMsgType: TypeAlias = Literal['text', 'audio', 'img']

class ChatMsg(NamedTuple):
    
    raw: str | bytes | Audio | Image
    type: ChatMsgType = 'text'

    @property
    def raw_str(self)->str:
        '''
        build the raw data to string.
        For text data, nothing will be changed. Other media formats will be
        converted to base64 string.
        '''
        if isinstance(self.raw, str):
            return self.raw
        if isinstance(self.raw, Audio):
            return self.raw.to_base64()
        if isinstance(self.raw, Image):
            return self.raw.to_base64()
        if isinstance(self.raw, bytes):
            return base64.b64encode(self.raw).decode()
        else:
            raise ValueError('Invalid raw data type.')

    def build_req(self)->dict:
        '''build for sending request to server.'''
        return {
            'content': self.raw_str,
            'type': self.type
        }
    
    @classmethod
    def Create(cls, content: str | tuple[str|bytes|Audio|Image, ChatMsgType] | Audio | Image)->Self:
        if isinstance(content, (list, tuple)):
            assert len(content) == 2, 'content should be a tuple of (bytes, ChatMsgType)'
            if not isinstance(content[0], str) and content[1] == 'text':
                raise ValueError('content should be a tuple of (str, ChatMsgType) if the content is bytes')     
            if not isinstance(content[0], (bytes, str, Image)) and content[1] == 'img':
                raise ValueError(f'Invalid content type, got: {content[0]}, which should be bytes, base64 or Image')
            if not isinstance(content[0], (bytes, str, Audio)) and content[1] == 'audio':
                raise ValueError(f'Invalid content type, got: {content[0]}, which should be bytes, base64 or Audio')
            return cls(content[0], content[1])
        if isinstance(content, str):
            return cls(content)
        if isinstance(content, Audio):
            return cls(content, 'audio')
        if isinstance(content, Image):
            return cls(content, 'img')
        raise ValueError(f'Invalid content type, got: {content}')


__all__ = ['ChatStatus', 'ChatMsgType', 'ChatMsg']
# endregion


