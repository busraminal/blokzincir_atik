@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ATIK — dev başlatıcı
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-atik-dev.ps1"
if errorlevel 1 pause
