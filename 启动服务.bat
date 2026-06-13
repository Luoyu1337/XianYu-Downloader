@echo off
chcp 65001 >nul
title 🎨 闲鱼图片下载器 - Web服务
cd /d "%~dp0"

echo ╔═══════════════════════════════════════╗
echo ║    🎨 闲鱼图片下载器 Web 服务         ║
║                                       ║
echo ║   🌐 http://127.0.0.1:5000         ║
echo ║   💡 浏览器打开上面地址即可使用      ║
echo ║                                       ║
echo ║   📁 下载目录: downloads\            ║
echo ║   ❌ 按 Ctrl+C 停止服务              ║
echo ╚═══════════════════════════════════════╝
echo.

python app.py
pause
