@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo 用法：把要体检的合同母本 .docx 文件拖到本文件图标上
  pause
  exit /b
)
python -m contract_compose.health_check "%~1"
echo.
echo 报告在 new_types 文件夹里对应的子文件夹中（体检报告.md）
pause
