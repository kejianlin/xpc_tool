@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Generating ICO from logo.png...
python -c "from PIL import Image; img=Image.open('logo.png').convert('RGBA'); s=max(img.size); canvas=Image.new('RGBA',(s,s),(0,0,0,0)); canvas.paste(img,((s-img.size[0])//2,(s-img.size[1])//2)); canvas.save('logo.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if errorlevel 1 (
  echo ICO generation failed.
  exit /b 1
)

echo [2/3] Building EXE with PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --hidden-import PyQt5.sip ^
  --icon "logo.ico" ^
  --name CPSY_Config_Tool ^
  --add-data "logo.png;." ^
  main.py

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo [3/3] Done.
echo EXE: %~dp0dist\CPSY_Config_Tool.exe
exit /b 0
