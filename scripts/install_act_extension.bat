@echo off
setlocal EnableExtensions

rem ==========================================================================
rem  install_act_extension.bat - install the ansys_automation ACT extension.
rem
rem  Copies src\act\ansys_automation\ into the user ACT directory:
rem      %APPDATA%\Ansys\v211\ACT\extensions\ansys_automation.xml
rem      %APPDATA%\Ansys\v211\ACT\extensions\ansys_automation\*.py
rem  (override the version directory with: set ANSYS_ACT_VER=211).
rem
rem  Then restart Workbench/Mechanical and, if needed, enable the extension in
rem  Extensions -> Manage Extensions. ACT requires an ACT licence - see
rem  docs\act-extension.md.
rem
rem  Exit codes:
rem      0 - extension installed
rem      1 - copy failed
rem      3 - extension source not found
rem ==========================================================================

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "SRC=%ROOT%\src\act\ansys_automation"

if not defined ANSYS_ACT_VER set "ANSYS_ACT_VER=211"
set "VER=%ANSYS_ACT_VER%"

if not defined APPDATA set "APPDATA=%USERPROFILE%\AppData\Roaming"
set "DEST=%APPDATA%\Ansys\v%VER%\ACT\extensions"

if not exist "%SRC%\ansys_automation.xml" (
    echo ERROR: extension source not found: "%SRC%\ansys_automation.xml"
    exit /b 3
)

if not exist "%DEST%" mkdir "%DEST%"
if not exist "%DEST%\ansys_automation" mkdir "%DEST%\ansys_automation"

copy /Y "%SRC%\ansys_automation.xml" "%DEST%\ansys_automation.xml" >nul
if errorlevel 1 (
    echo ERROR: cannot copy manifest to "%DEST%"
    exit /b 1
)
copy /Y "%SRC%\*.py" "%DEST%\ansys_automation\" >nul
if errorlevel 1 (
    echo ERROR: cannot copy modules to "%DEST%\ansys_automation"
    exit /b 1
)

echo INSTALLED: %DEST%\ansys_automation.xml
echo INSTALLED: %DEST%\ansys_automation\
echo.
echo Next: restart Workbench/Mechanical; if the extension is not picked up,
echo       enable it in Mechanical -^> Extensions -^> Manage Extensions.
echo       ACT licence is required (docs\act-extension.md).
exit /b 0
