@echo off
rem Copyright (C) 2026 Gato
rem SPDX-License-Identifier: GPL-3.0-only
rem Licensed under the GNU General Public License v3.0; see LICENSE.
setlocal
cd /d "%~dp0"
python build_release.py > build_log.txt 2>&1
set "BUILD_RESULT=%ERRORLEVEL%"
powershell -NoProfile -Command "Get-Content build_log.txt -Tail 25"
if not "%BUILD_RESULT%"=="0" echo Build failed. See build_log.txt.
pause
exit /b %BUILD_RESULT%
