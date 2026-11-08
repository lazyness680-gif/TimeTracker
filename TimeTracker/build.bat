@echo off
rem ============================================================
rem  Сборка portable-версии TimeTracker (PyInstaller, onedir)
rem  Требуется: pip install -r requirements.txt pyinstaller
rem ============================================================
pip install -r requirements.txt pyinstaller || goto :err

python -m PyInstaller --noconfirm --clean --onedir --windowed --name TimeTracker main.py
if errorlevel 1 goto :err

echo.
echo Готово: dist\TimeTracker\TimeTracker.exe
echo Скопируйте папку dist\TimeTracker целиком в место, доступное всем
echo пользователям ПК (например, C:\Users\Public\TimeTracker).
exit /b 0

:err
echo Сборка не удалась.
exit /b 1
