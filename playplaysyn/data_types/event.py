# -*- coding: utf-8 -*-
'''
Event is a class that is used to implement the event mechanism, 
i.e. a listener can listen to an event and be notified when the event is invoked.
'''

if __name__ == "__main__": # for debugging
    import os, sys
    _proj_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    sys.path.append(_proj_path)
    __package__ = 'playplaysyn.data_types'

import asyncio

from functools import partial
from types import UnionType, FunctionType
from inspect import signature, Signature, isabstract
from typing import Callable, Generic, ForwardRef, Iterable, get_type_hints as tp_get_type_hints, Any, Literal

from ..common_utils.concurrent_utils import is_async_callable, run_async_funcs
from ..common_utils.type_utils import check_super_cls


class ListenerNotFoundError(Exception):...
class NoneTypeNotSupportedError(Exception):...

def _get_func_type_hints(func, func_sig: Signature):
    try:
        return tp_get_type_hints(func)
    except NameError:
        d = {}
        for key, param in func_sig.parameters.items():
            if param.annotation == Signature.empty:
                d[key] = Any
            else:
                d[key] = param.annotation
        return d
    
def _func_param_type_check(func:Callable, *args, **kwargs):
    '''check if the args and kwargs of func are valid for a event'''
    # pack all args and kwargs into a dict
    sig = signature(func)
    try:
        bound_args = sig.bind(*args, **kwargs)
    except TypeError:
        return False # unexpected args or kwargs
    
    bound_args.apply_defaults()
    
    args_dict = bound_args.arguments
    if isinstance(func, partial):
        func_type_hints = _get_func_type_hints(func.func, sig)
        func_type_hints.update({k: Any for k in args_dict.keys() if k not in func_type_hints})
        for key in func.keywords:
            del func_type_hints[key]
    else:
        func_type_hints = _get_func_type_hints(func, sig)
        func_type_hints.update({k: Any for k in args_dict.keys() if k not in func_type_hints})
        
    for arg_name, arg_val in args_dict.items():
        if arg_name not in func_type_hints:
            return False
        if not check_super_cls(arg_val, func_type_hints[arg_name]):
            return False
    return True

def _get_func_arg_count(func:Callable):
    '''get the count of args of a function'''
    try:
        return len(signature(func).parameters)
    except ValueError as e:
        if 'no signature' in str(e):
            return -1   # fail to get signature
        raise e

def _cls_is_abs(cls):
    r = isabstract(cls)
    if not r:
        if hasattr(cls, 'IsAbstract'):
            r = cls.IsAbstract
            if not isinstance(r, bool) and callable(r):
                try:
                    r = r()
                except Exception:
                    return False
    return r

class Event:
    
    def __init__(self, *args, accept_none=False, no_check=False):
        '''
        :param args: 事件的参数类型（1個或多個），可以是 类型 或 类型名稱 。支持所有utils.TypeUtils.simpleTypeCheck的類型。
        :param accept_none: 是否接受None作為參數。如果args中有None，則accept_none會強制設置為True(僅限useQtSignal模式)。
        :param no_check: addListener/invoke 時不檢查參數數量/類型是否正確
        
        e.g.:
        ```
        e = Event(int,)
        
        @e.register # register a normal func
        def f(x):
            print(x)
        
        class A:
            @e.register # register a static method
            @staticmethod
            def f(x):
                print(x)
                
            @e.register
            def f2(self, x):   # register a instance method. All instance will call this method when invoke
                print(x)
                
            @e.register
            @classmethod    # register a class method
            def f3(cls, x):
                print(x)
                
        a = A()
        e.invoke(1)     # invoke all listeners
        ```
        '''
        args = list(args)
        for arg in args:
            if arg is None:
                if not accept_none:
                    accept_none = True # force accept_none to True
            elif not isinstance(arg, (str, type, Generic, ForwardRef, UnionType)):
                raise Exception("Event's arg must be type or type name, but got " + str(type(arg)))
        self._args = tuple(args)
        self._accept_none = accept_none
        self._events:set = set()
        self._async_events:set = set()
        self._temp_events:set = set()
        self._async_temp_events:set = set()
        self._no_check = no_check
        self._add_listener_decorator = self._get_event_decorator(False)
        self._add_temp_listener_decorator = self._get_event_decorator(True)
        
    def __iadd__(self, other):
        self.add_listener(other)
        return self
    
    def __isub__(self, other):
        self.remove_listener(other)
        return self
    
    def __bool__(self):
        return self.event_count() > 0 or self.temp_event_count() > 0
    
    def _get_event_decorator(self_event, temp_listener:bool):   # type: ignore
        class _event_decorator:
            def __init__(self, fn):
                self.fn = fn
                self.fn_type: Literal['normal', 'static', 'class', 'instance'] = 'normal'
                if isinstance(fn, FunctionType):
                    if '.' not in fn.__qualname__:
                        self_event.add_listener(self.fn) if not temp_listener else self_event.add_temp_listener(self.fn)
                    else: # instance method
                        self.fn_type = 'instance'
                elif isinstance(fn, staticmethod):
                    self.fn_type = 'static'
                elif isinstance(fn, classmethod):
                    self.fn_type = 'class'
                    
            def __set_name__(self, owner, name):
                setattr(owner, name, self.fn)
                
                if self.fn_type == 'instance':
                    origin_init = owner.__init__ if hasattr(owner, '__init__') else lambda *args, **kwargs: None
                    def new_init(*args, **kwargs):
                        origin_init(*args, **kwargs)
                        self_event.add_listener(partial(getattr(owner, name), args[0])) if not temp_listener else self_event.add_temp_listener(partial(getattr(owner, name), args[0]))
                    owner.__init__ = new_init
                    
                    origin_del = owner.__del__ if hasattr(owner, '__del__') else lambda *args, **kwargs: None
                    def new_del(*args, **kwargs):
                        self_event.remove_listener(partial(getattr(owner, name), args[0]), throwError=False) if not temp_listener else self_event.remove_temp_listener(partial(getattr(owner, name), args[0]), throwError=False)
                        origin_del(*args, **kwargs)
                    owner.__del__ = new_del
                    
                elif self.fn_type == 'class':
                    origin_init_sub_class = owner.__init_subclass__ if hasattr(owner, '__init_subclass__') else lambda *args, **kwargs: None
                    if hasattr(owner, '__pydantic_init_subclass__'):
                        origin_init_sub_class = owner.__dict__['__pydantic_init_subclass__']
                    def new_init_sub_class(cls, *args, **kwargs):
                        origin_init_sub_class(cls, *args, **kwargs)
                        if not _cls_is_abs(cls):
                            self_event.add_listener(getattr(cls, name)) if not temp_listener else self_event.add_temp_listener(getattr(owner, name))
                    owner.__init_subclass__ = classmethod(new_init_sub_class)
                    if not _cls_is_abs(owner):
                        self_event.add_listener(getattr(owner, name)) if not temp_listener else self_event.add_temp_listener(getattr(owner, name))
                                        
                else:
                    self_event.add_listener(getattr(owner, name)) if not temp_listener else self_event.add_temp_listener(getattr(owner, name))

            def __call__(self, *args: Any, **kwds: Any) -> Any:
                '''call the origin function'''
                return self.fn(*args, **kwds)
        return _event_decorator
        
    @property
    def register(self)->Callable:
        return self._add_listener_decorator
    
    @property
    def temp_register(self)->Callable:
        return self._add_temp_listener_decorator

    @property
    def args(self):
        return self._args
    
    @property
    def arg_count(self):
        return len(self._args)
    
    @property
    def events(self)->tuple[Callable]:
        '''return a tuple of events'''
        return tuple(self._events)
    
    @property
    def arg_length(self)->int:
        '''return the length of args'''
        return len(self.args)
    
    @property
    def temp_events(self)->tuple:
        '''return a tuple of temp events'''
        return tuple(self._temp_events)
    
    @property
    def accept_none(self)->bool:
        return self._accept_none

    def _checkListener(self, listener:Callable):
        if self._no_check:
            return
        arg_count = _get_func_arg_count(listener)  
        if arg_count == 0:    # 0 args can always be accepted
            return
        if arg_count !=-1 and not _func_param_type_check(listener, *self.args): # when -1, means fail to get signature
            raise Exception("Invalid type of listener's args. Expected: " + str(self.args))
        
    def add_listener(self, listener:Callable | Iterable[Callable]):
        '''add a listener to event'''
        if isinstance(listener, Iterable):
            for l in listener:
                self.add_listener(l)
        elif isinstance(listener, Callable):
            self._checkListener(listener)
            if not is_async_callable(listener):
                self._events.add(listener)
            else:
                self._async_events.add(listener)
        else:
            raise TypeError("Listener must be callable, or iterable of callable")
    
    def add_temp_listener(self, listener:Callable | Iterable[Callable]):
        '''add a temp listener to event'''
        if isinstance(listener, Iterable):
            for l in listener:
                self.add_temp_listener(l)
        elif isinstance(listener, Callable):
            self._checkListener(listener)
            if not is_async_callable(listener):
                self._temp_events.add(listener)
            else:
                self._async_temp_events.add(listener)
    
    def remove_listener(self, listener:Callable, throwError=True):
        '''remove a listener from event'''
        try:
            if not is_async_callable(listener):
                self._events.remove(listener)
            else:
                self._async_events.remove(listener)
        except KeyError:
            if throwError:
                raise ListenerNotFoundError
            else:
                return
    
    def remove_temp_listener(self, listener:Callable, throwError=True):
        '''remove a temp listener from event'''
        try:
            if not is_async_callable(listener):
                self._temp_events.remove(listener)
            else:
                self._async_temp_events.remove(listener)
        except KeyError:
            if throwError:
                raise ListenerNotFoundError

    def _invoke_event(self, event, raise_error, *args):
        try:
            if _get_func_arg_count(event) == 0:
                event()
            else:
                event(*args)
        except Exception as e:
            if raise_error:
                raise e
    
    async def _async_invoke_event(self, event, raise_error, *args):
        try:
            if _get_func_arg_count(event) == 0:
                await event()
            else:
                await event(*args)
        except Exception as e:
            if raise_error:
                raise e
    
    def invoke(self, *args, raise_error=True, invoke_asyncs=True):
        for event in self.events:
            self._invoke_event(event, raise_error, *args)

        for event in self.temp_events:
            self._invoke_event(event, raise_error, *args)
            
        if invoke_asyncs:
            async_args = []
            for event in self._async_events:
                async_args.append((event, raise_error, *args))
            temp_async_args = []
            for event in self._async_temp_events:
                temp_async_args.append((event, raise_error, *args))
            if len(async_args) > 0:
                run_async_funcs([self._async_invoke_event,]*len(self._async_events), async_args)    # type: ignore
            if len(self._async_temp_events) > 0:
                run_async_funcs([self._async_invoke_event,]*len(self._async_temp_events), temp_async_args)  # type: ignore
            
        self.clear_temp_event()
    
    async def async_invoke(self, *args, raise_error=True, invoke_non_asyncs=True):
        tasks = []
        for event in self._async_events:
            tasks.append(self._async_invoke_event(event, raise_error, *args))
        for event in self._async_temp_events:
            tasks.append(self._async_invoke_event(event, raise_error, *args))
        try:
            await asyncio.gather(*tasks)
        except RuntimeError as e:
            if raise_error:
                raise e
            
        if invoke_non_asyncs:
            for event in self.events:
                self._invoke_event(event, raise_error, *args)
            for event in self.temp_events:
                self._invoke_event(event, raise_error, *args)
        self.clear_temp_event()

    def event_count(self):
        '''return the count of normal events'''
        return len(self._events)
    
    def temp_event_count(self):
        '''return the count of temp events'''
        return len(self._temp_events)

    def clear(self):
        '''clear all events(both temp and normal)'''
        self.clear_normal_event()
        self.clear_temp_event()

    def clear_normal_event(self):
        '''clear normal event only'''
        self._events.clear()
        self._async_events.clear()

    def clear_temp_event(self):
        '''clear temp event only'''
        self._temp_events.clear()
        self._async_temp_events.clear()


__all__ = ["Event", "ListenerNotFoundError", "NoneTypeNotSupportedError"]


if __name__ == '__main__':  # for debugging
    e = Event(int,)
    @e.register
    def f(x):
        print(x)
    
    class A:
        @e.register
        @staticmethod
        def f(x):
            print(x)
        @e.register
        def f2(self, x):
            print(x)
        @e.register
        @classmethod
        def f3(cls, x):
            print(x)
            
    a = A()
    e.invoke(1)