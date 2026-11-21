nuitka --standalone ^
    --enable-plugin=pyside6 ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=icon.ico ^
    --include-data-files=icon.ico=icon.ico ^
    --include-module=pynput ^
    --include-module=pynput.mouse ^
    --include-module=pygame ^
    --include-package-data=pygame ^
    --include-module=threading ^
    --include-module=queue ^
    --follow-imports ^
    --jobs=4 ^
    --clang ^
    --remove-output ^
    --output-dir=build_output ^
    MouseClick.py

