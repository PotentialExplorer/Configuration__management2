@echo off
rem Run: run.bat [options]
cd /d "%~dp0"
set PYTHONPATH=src
python -m depviz %*
