if __name__ == "__main__": # for debugging
    import os, sys
    _proj_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    sys.path.append(_proj_path)
    __package__ = 'playplaysyn.cli'

import os
import asyncio
import pyaudio

from aiossechat import aiosseclient, DefaultSSEType
from typing import Final, TypeAlias
from pydub import AudioSegment

from ..common_utils import logger
from ..data_types import Event, ChatStatus, Audio, Image, ChatMsgType, ChatMsg, AudioChunk

DEFAULT_BASE_URL: Final[str] = 'api.thinkthinksyn.com/aiw'
DEFAULT_CHAT_URL: Final[str] = 'chat'

def _get_url(url: str, base:str=DEFAULT_BASE_URL) -> str:
    if base in url:
        url = url.split(base)[-1]   # remove base url
    if url.startswith('http://') or url.startswith('https://'):
        return url  # unknown custom url
    url = url.lstrip('/').rstrip('/')
    return f'https://{base}/{url}'

_AvailableMsgType: TypeAlias = ChatMsg | str | tuple[str|bytes|Audio|Image, ChatMsgType] | Audio | Image



class PPSClient:
    '''Client for accessing PlayPlaySyn's AI-Character service.'''
    
    base_url: str
    chat_url: str
    access_token: str | None = None
    apikey: str | None = None
    
    # region events
    on_chat_status: Event
    '''
    Event[ChatStatus]
    When chat status is switched, this event will be triggered.
    '''
    
    on_chat_text: Event
    '''
    Event[str]
    When all chat texts is received from character, this event will be triggered.
    You can register both sync and async functions to this event.
    '''
    on_chat_text_chunk: Event
    '''
    Event[str]
    When chat text chunk is received from character, this event will be triggered.
    You can register both sync and async functions to this event.
    '''
    
    on_chat_audio: Event
    '''
    Event[Audio]
    When all chat audio chunks is received from character, this event will be triggered.
    You can register both sync and async functions to this event.
    '''
    on_chat_audio_chunk: Event
    '''
    Event[bytes]
    When chat audio chunks is received from character, this event will be triggered.
    You can register both sync and async functions to this event.
    Note: Each chunk is a wav chunk without header. Wav is in 24000Hz.
    '''
    
    on_emotion: Event
    '''
    Event[str]
    When emotion is switched, this event will be triggered.
    You can register both sync and async functions to this event.
    Default emotions: [idle, happy, sad, angry, surprised, disgusted, fearful].
    '''
    # endregion
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        chat_url: str = DEFAULT_CHAT_URL,
        access_token: str|None = None,
        apikey: str|None = None,
    ):
        '''
        Args:
            - base_url: The base url of the service. You could set your custom base url.
            - chat_url: the chat url. It could start with `http` or just the subpath 
            - access_token: The user access token, which can be gotten after login. It can also be set as an environment variable `PPS_ACCESS_TOKEN`.
                            If apikey is set, this field will be ignored. Note that you must set either `access_token` or `apikey`.
            - apikey: The api key for the service. If this field is set, `access_token` will be ignored. 
                      This field can also be set as an environment variable `PPS_APIKEY`. Note that you must set either `access_token` or `apikey`.
        '''
        # init client properties
        self.base_url = base_url
        self.chat_url = _get_url(chat_url, base_url)
        if not access_token:
            access_token =os.getenv('PPS_ACCESS_TOKEN', None)
        if not apikey:
            apikey = os.getenv('PPS_APIKEY', None)
        if apikey:
            access_token = None # ignore access_token if apikey is set
        if not apikey and not access_token:
            raise ValueError('You must set either access_token or apikey')
        self.access_token = access_token
        self.apikey = apikey
        
        # init events
        self.on_chat_status = Event(ChatStatus)
        self.on_chat_text = Event(str)
        self.on_chat_text_chunk = Event(str)
        self.on_chat_audio = Event(Audio)
        self.on_chat_audio_chunk = Event(bytes)
        self.on_emotion = Event(str)

    async def chat(
        self, 
        *msgs: _AvailableMsgType, 
        conversation_id: str|None=None,
        save_msg: bool = False,
        return_audio: bool = False,
        auto_tool: bool = False,
    ):
        '''
        Args:
            - msgs: The chat messages. It can be a string, a tuple of (str, ChatMsgType), an Audio, or an Image.
            - conversation_id: The conversation id. If not set, the default conversation id will be used.
            - save_msg: If True, chat history will be saved. Note, chat history != chat memory. 
            - return_audio: If True, both audio & text response will be returned.
            - auto_tool: (only available for internal developers through APIKey) If True, character will be able
                        to use internal tools(e.g. Wiki search) to enhance the conversation.
        '''
        if not conversation_id:
            if self.access_token:
                # TODO: get the default character of this user
                raise NotImplementedError('Not implemented yet')
            else:   # access by apikey, use the default conversation id `0`
                conversation_id = '0'
        if not self.apikey:
            auto_tool = False   # non-internal developers cannot use auto_tool
            auth_header = {'X-User-Token': self.access_token}
        else:
            auth_header = {'Authorization': f'Bearer {self.apikey}'}
        config = {
            'save_message': save_msg,
            'return_audio': return_audio,
            'auto_tool': auto_tool
        }
        inputs = []
        for msg in msgs:
            if isinstance(msg, ChatMsg):
                inputs.append(msg.build_req())
            else:
                inputs.append(ChatMsg.Create(msg).build_req())
        body = {
            'inputs': inputs,
            'config': config,
            'stream': True,
            'cache': False,
            'conversation_id': conversation_id
        }
        logger.debug('Start chatting with apikey...' if self.apikey else 'Start chatting with access token...')
        try:
            await self.on_chat_status.async_invoke(ChatStatus.START)
            full_text = ''
            full_audio = b''
            async for e in aiosseclient(self.chat_url, method='post', headers=auth_header, json=body):  # type: ignore
                event = e.event.lower()
                datas = [c.value for c in e.contents if c.value and c.content_type == DefaultSSEType.DATA]
                if datas:
                    if event in ('msg', 'message', 'text'):
                        for c in datas:
                            full_text += c
                            await self.on_chat_text_chunk.async_invoke(c)
                    elif event in ('audio', 'speech', 'sound', 'voice'):
                        for c in datas:
                            data = AudioChunk.model_validate_json(c)
                            data_bytes = data.data_bytes
                            full_audio += data_bytes
                            await self.on_chat_audio_chunk.async_invoke(data_bytes)
                    elif event in ('emotion', 'emo'):
                        for c in datas:    # actually there should be only one content
                            await self.on_emotion.async_invoke(c)
            tasks = []
            if full_text:
                tasks.append(self.on_chat_text.async_invoke(full_text))
            if full_audio:
                audio = AudioSegment(data=full_audio, sample_width=2, frame_rate=24000, channels=1)
                audio = Audio.Load(audio)
                tasks.append(self.on_chat_audio.async_invoke(audio))
            if tasks:
                await asyncio.gather(*tasks)
            await self.on_chat_status.async_invoke(ChatStatus.END)
            
        except (StopAsyncIteration, GeneratorExit):
            pass
        except Exception as e:
            logger.error(f'{type(e).__name__}: {e}')

        
__all__ = ['PPSClient']


if __name__ == '__main__':
    from functools import partial
    
    print_msg = partial(print, end='')
    
    def play_audio(audio: Audio):
        WIDTH, CHANNELS, RATE = 2, 1, 24000
        player = pyaudio.PyAudio()
        stream = player.open(format=player.get_format_from_width(WIDTH), 
                             channels=CHANNELS, 
                             rate=RATE, 
                             output=True)
        stream.write(audio.to_bytes())
        stream.stop_stream()
        stream.close()
        player.terminate()
    
    client = PPSClient(chat_url='https://api.thinkthinksyn.com/tts/ai/chat')
    client.on_chat_text_chunk.add_listener(print_msg)
    client.on_chat_audio.add_listener(play_audio)
    
    asyncio.run(client.chat('hi', return_audio=True))