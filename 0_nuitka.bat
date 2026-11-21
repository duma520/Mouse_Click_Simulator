cls
if exist *.build rmdir /s /q *.build
if exist *.dist rmdir /s /q *.dist
if exist dist rmdir /s /q dist

nuitka --standalone ^
    --enable-plugin=pyqt5 ^
    --windows-console-mode=disable ^
    --include-package-data=pypinyin ^
    --windows-icon-from-ico=icon.ico ^
    --jobs=4 ^
    --output-dir=dist ^
    Mouse_Click_Simulator.py