@echo off
cd /d "%~dp0"
echo Building HyruleGuardianEye executable...
pyinstaller --noconfirm --onefile --windowed --add-data "..\UI\hylia-serif\Hylia Serif Beta v0-009\HyliaSerifBeta-Regular.otf;UI\hylia-serif\Hylia Serif Beta v0-009" --name "HyruleGuardianEye" webcam_gui.py
echo.
echo Build finished. Find the executable in the dist folder.
pause
