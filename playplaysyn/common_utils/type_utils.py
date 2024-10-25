if __name__ == "__main__": # for debugging
    import os, sys
    _proj_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    sys.path.append(_proj_path)
    __package__ = 'playplaysyn.common_utils'
    
import inspect
import builtins

from pathlib import Path
from types import UnionType, GenericAlias
from typing_extensions import Self
from inspect import getmro as _get_mro
from typeguard import check_type as tg_check_type
from typing import (Any, Sequence, Union, ForwardRef, Iterable, Mapping, Literal, ClassVar, TypeVar, 
                    overload, TypedDict, get_origin as tp_get_origin, get_args as tp_get_args,
                    TypeGuard, TypeVar)

_T = TypeVar('_T')

# region helper functions
def get_module_name(t: Any):
    """
    Get the proper module name of the type.
    This is useful when running scripts directly for debugging,

    e.g. you define a class in `utils.xxx....`, but the module will shows '__main__' when running the script directly.
    Class will be redefined by python as '__main__.A', which is different from 'utils.xxx....A'.
    By using this function, you could get the proper module name `utils.xxx....` instead of `__main__`
    """

    if not isinstance(t, str):
        if hasattr(t, "__module__"):
            module = t.__module__
        elif not isinstance(t, type) and hasattr(type(t), "__module__"):
            module = type(t).__module__
        else:
            raise ValueError(f"Cannot get module name of {t}.")
    else:
        module = t

    if module == "__main__":
        import __main__ as _main
        source_path = Path(__file__).resolve().parent.parent
        main_path = Path(_main.__file__).resolve()
        try:
            module = main_path.relative_to(source_path).with_suffix("").as_posix().replace("/", ".")
        except ValueError:
            module = "__main__"  # not in source dir, use __main__ instead
    return module

def is_builtin(obj: Any) -> bool:
    """check if an object is a builtin function or type."""
    if not (r := inspect.isbuiltin(obj)):
        cls_name = get_cls_name(obj)
        r = hasattr(builtins, cls_name)
    return r

def get_cls_name(cls: Any, 
                 with_module_name=False,
                 with_generic=True):
    """
    Return the pure class name, without module name. e.g. 'A' instead of 'utils.xxx....A
    If `__qualname__` is not available, it will use `__name__` instead.
    For generic class, it will return the class with its type arguments, e.g. `List[int]`.
    
    Args:
        cls: the class to be get name.
        with_module_name: if True, will return the class name with module name, e.g. 'utils.xxx....A'
                         This is only available for non-builtin classes.
        with_generic: if True, will return the class name with its type arguments, e.g. `List[int]`,
                        otherwise, will return the class name without type arguments, e.g. `List`. 
    Note: if `cls` is a string, it will return the string itself, instead of `str`.
    """
    if with_generic and isinstance(cls, GenericAlias):
        main_cls_name = get_cls_name(cls.__origin__, with_module_name, False)
        arg_names = []
        for arg in cls.__args__:
            arg_name = get_cls_name(arg, with_module_name, with_generic)
            if arg_name.lower() == 'ellipsis':
                arg_name = '...'
            arg_names.append(arg_name)
        return f"{main_cls_name}[{', '.join(arg_names)}]"
    
    if isinstance(cls, str):
        return cls
    if not isinstance(cls, type):
        cls = type(cls)
    if hasattr(cls, "__qualname__"):
        n = cls.__qualname__
    elif hasattr(cls, "__name__"):
        n = cls.__name__.split(".")[-1]
    elif hasattr(cls, "__repr__"):
        n = cls.__repr__().split(".")[-1].split("<")[0].split("[")[0].split("(")[0].split("{")[0]
    else:
        n = str(cls).split(".")[-1].split("<")[0].split("[")[0].split("(")[0].split("{")[0]
    
    if not with_generic and '[' in n:
        n = n.split('[')[0]
    if with_module_name and not is_builtin(cls):
        return f"{get_module_name(cls)}.{n}"
    return n

def get_sub_clses(cls_or_ins):
    """
    Get all sub classes of a class, recursively.
    The class itself will also be included as the first element.
    """
    if not isinstance(cls_or_ins, type):
        cls_or_ins = type(cls_or_ins)
    if not hasattr(cls_or_ins, "__subclasses__"):
        return (cls_or_ins,)
    else:
        sub_clses = cls_or_ins.__subclasses__()
        all_subclses = [
            cls_or_ins,
        ]
        for sub_cls in sub_clses:
            sub_sub_clses = get_sub_clses(sub_cls)
            for sub_sub_cls in sub_sub_clses:
                if sub_sub_cls not in all_subclses:
                    all_subclses.append(sub_sub_cls)
        return tuple(all_subclses)

def get_origin(t: Any, self=None, return_t_if_no_origin=False) -> type | None:  # type: ignore
    """
    Return the origin type of the type hint.
    Different to typing.get_origin, this function will convert some special types to their real origin type,
    
    Args:
        `self`: if provided, for type = `Self`, it will return the `self`.
        `return_t_if_no_origin`: if True, will return the type itself if no origin is found.

    e.g.
        * int|str -> Union                  (the origin typing.get_origin will return UnionType, which is not easy to do comparison)
        * ForwardRef('A') -> ForwardRef     (the origin typing.get_origin will return None, which is not correct)
        * _empty -> Any
    """
    if t == inspect._empty:
        return Any  # type: ignore
    if isinstance(t, ForwardRef):
        return ForwardRef
    if t == Self:
        if self is not None:
            if isinstance(self, type):
                return type(self)
            else:
                return self
        else:
            return Self

    origin = tp_get_origin(t)
    if origin in (UnionType, Union):
        return Union    # type: ignore
    
    if return_t_if_no_origin and origin is None:
        return t
    return origin

def get_args(t) -> tuple[Any, ...]:
    """
    Return the args of the type hint.
    Different to typing.get_args, this function will convert some special types to their real args,

    e.g.
        * ForwardRef('A') -> ('A',)     (the origin typing.get_args will return (), which is not correct)
    """
    if isinstance(t, ForwardRef):
        return (t.__forward_arg__,)
    return tp_get_args(t)

def getmro(cls: type) -> tuple[type, ...]:
    try:
        return _get_mro(cls)
    except Exception:   # some special types may fail to get mro
        return (cls, )


__all__ = ['get_module_name', 'is_builtin', 'get_cls_name', 'get_sub_clses', 'get_origin', 'get_args',
           'getmro']
# endregion

# region type checking
def _get_real_types(t):
    tt = type(t)
    if tt == TypeVar:
        r = []
        for bound in t.__constraints__:
            r.extend(_get_real_types(bound))
        return r
    elif tt == Literal:
        r = []
        for arg in t.__args__:
            r.extend(_get_real_types(arg))
        return r
    elif tt in (Union, UnionType):
        r = []
        for arg in t.__args__:
            r.extend(_get_real_types(arg))
        return r
    else:
        return [tt, ]
    
def _direct_check_sub_cls(sub_cls:type|str, super_cls:type|str):
    if super_cls in (Any, any):
        return True
    
    if type(sub_cls) == TypeVar:
        sub_type_bounds = sub_cls.__constraints__   # type: ignore
        for bound in sub_type_bounds:   # type: ignore
            if not _direct_check_sub_cls(bound, super_cls):
                return False
        return True # no bound or all bounds are valid
    
    sub_cls_origin = get_origin(sub_cls)
    super_cls_origin = get_origin(super_cls)
    
    if sub_cls_origin == ClassVar:
        return _direct_check_sub_cls(get_args(sub_cls)[0], super_cls)

    elif sub_cls_origin == type and get_args(sub_cls):
        real_tps = _get_real_types(get_args(sub_cls)[0])
        for tp in real_tps:
            if _direct_check_sub_cls(tp, super_cls):
                return True
        return False
    
    elif sub_cls_origin == Literal:
        if super_cls_origin == Literal:
            sub_args = get_args(sub_cls)
            for arg in get_args(super_cls):
                if arg not in sub_args:
                    return False
            return True
        else:
            lit_arg_types = [type(arg) for arg in get_args(sub_cls)]
            if not lit_arg_types:
                return False
            for t in lit_arg_types:
                if not _direct_check_sub_cls(t, super_cls):
                    return False
            return True
        
    elif sub_cls_origin == Union and not super_cls_origin == Union:
        return all([_direct_check_sub_cls(arg, super_cls) for arg in get_args(sub_cls)])
    
    elif super_cls_origin == Union and not sub_cls_origin == Union:
        return any([_direct_check_sub_cls(sub_cls, arg) for arg in get_args(super_cls)])
    
    elif isinstance(sub_cls, ForwardRef):
        return _direct_check_sub_cls(sub_cls.__forward_arg__, super_cls)
    elif isinstance(super_cls, ForwardRef):
        return _direct_check_sub_cls(sub_cls, super_cls.__forward_arg__)
    
    if isinstance(sub_cls, str) and not isinstance(super_cls, str):
        return sub_cls in [get_cls_name(cls) for cls in get_sub_clses(super_cls)]
    if not isinstance(sub_cls, str) and isinstance(super_cls, str):
        ret = super_cls in [get_cls_name(cls) for cls in getmro(sub_cls)]
        return ret
    
    elif isinstance(sub_cls, type) and isinstance(super_cls, type):
        if '__main__' in (sub_cls.__name__, super_cls.__name__):
            if sub_cls.__name__.split('.')[-1] == super_cls.__name__.split('.')[-1]:
                return True
        return issubclass(sub_cls, super_cls)
    
    elif isinstance(sub_cls, str) and isinstance(super_cls, str):
        raise TypeError(f'Sub cls and super cls cannot both be str: sub_cls: {sub_cls}, super_cls: {super_cls}. There should be at least one type.')
    
    else:
        try:
            return issubclass(sub_cls, super_cls)   # type: ignore
        except TypeError as e:
            if str(e).startswith('issubclass() arg 1 must be a class'):
                raise TypeError(f'Invalid sub class type: `{sub_cls}`(type of sub cls input={type(sub_cls)}).') from e
            elif str(e).startswith('issubclass() arg 2 must be'):
                raise TypeError(f'Invalid super class type: `{super_cls}`(type of super cls input={type(super_cls)}).') from e
            else:
                raise TypeError(f'Error when checking sub class: {sub_cls} and super class: {super_cls}.') from e
        except Exception as e:
            raise e
        
@overload
def check_val_type(value: Any, types: type[_T]) -> TypeGuard[_T]:...
@overload
def check_val_type(value: Any, types: str | Sequence[type|str]| UnionType) ->bool:...

def check_val_type(value:Any, types):
    '''
    Check value with given types. Advance version of `isinstance`.
    support passing special types in `typing` module, e.g. Union, Literal, TypedDict, etc.
    
    Example 1:
    ```
    check_val_type([1,2,'abc',1.23], list[int|str|float])
    check_val_type([1,2], Any)
    check_val_type(1, Literal[1, 2])
    check_val_type(1, Union[int, str])
    check_val_type(1, int | str)
    ```
    
    Example 2:
    ```
    class A:
        pass
    a = A()
    check_val_type(a, 'A') # True, accept class name
    ```
    '''
    
    if not isinstance(types, str) and isinstance(types, Sequence):
        return any(check_val_type(value, t) for t in types)
    
    elif isinstance(types, str):
        return _direct_check_sub_cls(type(value), types)
    
    elif (origin:=get_origin(types)) and origin not in (None, Union, Iterable, Literal):   
        # None: means no origin, e.g. list 
        # Union/UnionType: means union, e.g.: Union[int, str], int | str
        # Iterable: checking inner type of Iterable is meaningless, since it will destroy the structure of Iterable
        if issubclass(origin, Sequence):
            if not issubclass(origin, tuple):
                args = get_args(types)
                if len(args) == 0:  # no args, e.g. check_val_type([1,2], list)
                    return isinstance(value, origin)
                else:
                    return isinstance(value, origin) and all(check_val_type(v, args[0]) for v in value)
            else:
                args = get_args(types)
                if len(args) == 0:
                    return isinstance(value, origin)
                elif len(args) == 2 and args[-1] == Ellipsis:
                    return isinstance(value, origin) and all(check_val_type(v, args[0]) for v in value)
                else:
                    return (isinstance(value, origin)
                        and len(value) == len(get_args(types))
                        and all(check_val_type(v, t) for v, t in zip(value, get_args(types))))  # type: ignore
        elif issubclass(origin, Mapping):
            return (isinstance(value, origin) 
                    and all(check_val_type(v, get_args(types)[1]) for v in value.values())
                    and all(check_val_type(k, get_args(types)[0]) for k in value.keys()))
        else:
            try:
                tg_check_type(value, types) # type: ignore
                return True
            except Exception:
                return False
    else:
        try:
            tg_check_type(value, types) # type: ignore
            return True
        except Exception:
            return False

def check_super_cls(sub_cls:Any, super_cls: Any|Sequence[Any])->bool:
    '''
    Check if sub_cls is a subclass of super_cls.
    You could use `|` to represent Union, e.g.: `check_super_cls(sub_cls, int | str)`
    You could also use list to represent Union, e.g.: `check_super_cls(sub_cls, [int, str])`
    Class name is also supported, e.g.: `check_super_cls(sub_cls, 'A')`
    '''
    if isinstance(sub_cls, str):
        if isinstance(super_cls, str):
            return sub_cls.split('.')[-1] == super_cls.split('.')[-1]
        else:
            all_super_cls_names = []
            if isinstance(super_cls, Sequence):
                for c in super_cls:
                    if hasattr(c, '__subclasses__'):
                        all_super_cls_names.extend([get_cls_name(cls) for cls in get_sub_clses(c)])   # type: ignore
                    else:
                        all_super_cls_names.append(get_cls_name(c))
            else:
                if hasattr(super_cls, '__subclasses__'):
                    all_super_cls_names = [get_cls_name(cls) for cls in get_sub_clses(super_cls)] # type: ignore
                else:
                    all_super_cls_names = [get_cls_name(super_cls),]
            
            return sub_cls.split('.')[-1] in all_super_cls_names
        
    if not isinstance(super_cls, str) and isinstance(super_cls, Sequence):
        return any(_direct_check_sub_cls(sub_cls, t) for t in super_cls)
    try:
        return _direct_check_sub_cls(sub_cls, super_cls)
    except TypeError:
        return False

def is_convertible_to_number(x: Any)->bool:
    try:
        _ = float(x)
        return True
    except:
        return False

__all__.extend(['check_val_type', 'check_super_cls', 'is_convertible_to_number'])
# endregion


if __name__ == '__main__':
    class A(TypedDict):
        x: int
        y: int
    print(check_val_type({}, A))
    print(check_val_type({'x': 1, 'y': 2}, A))