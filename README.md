# PLAYPLAYSYN 

This package provides a convenient interface (with runtime logic included) for accessing to PlayPlaySyn Ltd.'s AI-Character service. Hardware developers will only need to register proper interaction events(audio playing, emotion switch, etc) and the package will handle the rest.

## Install
```pip install playplaysyn```

## (For package developers) Build and upload
build cmd：
 ```python setup.py sdist bdist_wheel```

upload cmd:
 ```twine upload dist/*```

If fail：
 - 不要用powershell，可能複製token錯誤，用cmd
 - 大概率是"file exist", 因為忘了改版本號
