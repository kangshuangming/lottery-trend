@echo off
chcp 65001 >nul 2>&1
title 彩票走势分析系统
cd /d "C:\Users\edwin\WorkBuddy\2026-06-10-15-09-40\lottery-trend"
set PYTHONIOENCODING=utf-8
start "" "http://localhost:5088"
"C:\Users\edwin\.workbuddy\binaries\python\envs\default\Scripts\python.exe" app.py
pause
