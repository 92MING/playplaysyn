import os

if __name__ == "__main__": # for debugging
    import sys
    _proj_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    sys.path.append(_proj_path)
    __package__ = 'playplaysyn.common_utils'

import asyncio
import nest_asyncio

from asyncio import _get_running_loop
from dataclasses import dataclass
from types import FunctionType, MethodType
from typing import (Callable, Awaitable, TypeGuard, Any, Iterable, overload, TypeAlias,
                    TypeVar, ParamSpec)
from concurrent.futures import Future, ThreadPoolExecutor

from .type_utils import check_val_type

# region helper functions
AsyncFuncType: TypeAlias = Callable[..., Awaitable[Any]]
'''Type hints for async functions'''

def is_async_callable(func:Callable)->TypeGuard[Callable[..., Awaitable]]:
    '''Check if a callable is async'''
    if not isinstance(func, (FunctionType, MethodType)):
        if hasattr(func, '__call__') and not type(func.__call__).__qualname__ == 'method-wrapper':
            func = func.__call__
    return asyncio.iscoroutinefunction(func)

__all__ = ['AsyncFuncType', 'is_async_callable']
# endregion


# region runners
_cpu_count = os.cpu_count() or 1
_thread_pool = ThreadPoolExecutor(max_workers=_cpu_count + 1)

@dataclass
class AsyncTask:
    func: AsyncFuncType
    args: tuple
    kwargs: dict
    result: Any = None

_R = TypeVar('_R')
_P = ParamSpec('_P')

def run_async_in_sync(async_func: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs:_P.kwargs)->_R:
    '''
    Get the return value of an async function. The simple version of `run_async_funcs`.
    
    Note: for async function, it will be submitted to another thread to run,
         thus it can be a solution to run async function in parallel. But please
         ensure the function is thread-safe.
    '''
    def runner(task: AsyncTask):
        if not (loop := _get_running_loop()):
            loop = asyncio.new_event_loop()
            nest_asyncio.apply(loop)
            asyncio.set_event_loop(loop)
        r = loop.run_until_complete(task.func(*task.args, **task.kwargs))
        task.result = r
        loop.close()
    task = AsyncTask(func=async_func, args=args, kwargs=kwargs)
    fut = _thread_pool.submit(runner, task)
    return fut.result() # type: ignore

def run_async_funcs(async_funcs:AsyncFuncType|Iterable[AsyncFuncType], 
                    args:tuple[tuple]|None=None, 
                    kwargs:tuple[dict]|dict|None=None,
                    timeout: int|None=None): # type: ignore
    '''
    Run async functions and get return. 
    
    This function is the multi version of `get_async_func_return`, i.e., it can run multiple 
    async functions at the same time, but args/kwargs should be passed in the same
    length as async_funcs.
    '''
    if not isinstance(async_funcs, Iterable):
        async_funcs = [async_funcs]
    if args is None:
        args = [tuple()] * len(async_funcs) # type: ignore
    elif not check_val_type(args, tuple[tuple]):
        args = [args,] * len(async_funcs) # type: ignore
    if kwargs is None:
        kwargs = [dict()] * len(async_funcs) # type: ignore
    elif kwargs is not None and isinstance(kwargs, dict):
        kwargs = [kwargs,] * len(async_funcs) # type: ignore
    
    if not timeout or timeout<=0:
        async def run():
            return await asyncio.gather(*[async_func(*arg, **kwarg) for async_func, arg, kwarg in zip(async_funcs, args, kwargs)]) # type: ignore
        return run_async_in_sync(run)
    else:
        async def run():
            f = asyncio.gather(*[async_func(*arg, **kwarg) for async_func, arg, kwarg in zip(async_funcs, args, kwargs)]) # type: ignore
            await asyncio.wait_for(f, timeout)
            return f.result()
        return run_async_in_sync(run)

@overload
def run_any_func(func: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs: _P.kwargs)->_R:...
@overload
def run_any_func(func: Callable[_P, _R],  *args: _P.args, **kwargs: _P.kwargs)->_R:...

def run_any_func(func, *args, **kwargs):
    '''
    Wrapper of `run_async_in_sync`, i.e. detect the function type,
    and call `run_async_in_sync` in case of async function.
    
    Note: for async function, it will be submitted to another thread to run,
         thus it can be a solution to run async function in parallel.
    '''
    if is_async_callable(func):
        return run_async_in_sync(func, *args, **kwargs)
    else:
        return func(*args, **kwargs)    # type: ignore


@overload
async def async_run_any_func(func: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs: _P.kwargs)->_R:...
@overload
async def async_run_any_func(func: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs)->_R:...

async def async_run_any_func(func, *args, **kwargs):
    '''
    async version of `run_any_func`.
     
    If the function is async, `await` will be called automatically, otherwise, 
    the function will be called directly.
    '''
    if is_async_callable(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)

@overload
def run_in_background(func:Callable[..., Awaitable[_R]], args:tuple|None=None, kwargs: dict|None=None, timeout: int|None=120)->Future[_R]:...
@overload
def run_in_background(func:Callable[..., _R], args:tuple|None=None, kwargs: dict|None=None, timeout: int|None=120)->Future[_R]:...

def run_in_background(func:Callable[..., Awaitable[_R]], args:tuple|None=None, kwargs: dict|None=None, timeout: int|None=120):  # type: ignore
    '''
    Run a function in background, i.e., submit the function to another thread to run.
    The function can be both sync and async.
    If `timeout` is set, the function will be cancelled after `timeout` seconds.
    '''
    args = args or tuple()
    kwargs = kwargs or dict()
    if is_async_callable(func):
        def wrapper(f, *args, **kwargs):
            if not (loop:=_get_running_loop()):
                loop = asyncio.new_event_loop()
                nest_asyncio.apply(loop)
                asyncio.set_event_loop(loop)
            if timeout:
                coro = asyncio.wait_for(f(*args, **kwargs), timeout)
            else:
                coro = f(*args, **kwargs) 
            return loop.run_until_complete(coro)
        return _thread_pool.submit(wrapper, func, *args, **kwargs)
    else:
        f = _thread_pool.submit(func, *args, **kwargs)
        if timeout:
            return _thread_pool.submit(f.result, timeout)
        return f


__all__.extend(['run_async_in_sync', 'run_async_funcs', 'run_any_func', 'async_run_any_func', 'run_in_background'])
# endregion


if __name__ == '__main__':
    async def test():
        for i in range(10):
            print(i)
            await asyncio.sleep(0.25)
    
    run_async_in_sync(test)