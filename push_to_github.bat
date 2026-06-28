@echo off
cd /d "C:\Users\USUARIO\Desktop\Tidal-Media-Downloader-PRO-1.2.1.10"

git init
git config user.email "jeanvitola@gmail.com"
git config user.name "Jean Vitola"
git branch -m main 2>nul
git checkout -b main 2>nul
git remote remove origin 2>nul
git remote add origin https://github.com/jeanvitola/Tidal-Downloader-Project.git
git add .
git commit -m "Initial commit: AetherMusic + Tidal Downloader PRO"
git push -u origin main

echo.
echo === LISTO ===
pause
