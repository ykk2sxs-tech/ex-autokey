@echo off
rem สร้างไฟล์ EX-AutoKey.exe บน Windows (ต้องมี Python 3.10 ขึ้นไป)
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m PyInstaller --noconfirm --onefile --windowed --name EX-AutoKey ^
  --add-data "templates;templates" --add-data "samples;samples" EX-AutoKey.pyw || goto :error

if exist release rmdir /s /q release
mkdir release
copy dist\EX-AutoKey.exe release\ >nul
xcopy templates release\templates\ /e /i /q >nul
xcopy samples release\samples\ /e /i /q >nul
copy README.md release\ >nul
echo.
echo เสร็จแล้ว: โฟลเดอร์ release\
goto :eof

:error
echo.
echo build ไม่สำเร็จ
exit /b 1
