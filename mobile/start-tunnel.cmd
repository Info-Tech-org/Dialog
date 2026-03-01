@echo off
set HTTP_PROXY=http://127.0.0.1:7897
set HTTPS_PROXY=http://127.0.0.1:7897
set npm_config_proxy=http://127.0.0.1:7897
set npm_config_https_proxy=http://127.0.0.1:7897

REM Ensure npm uses the correct proxy endpoints for this session
npm config set proxy http://127.0.0.1:7897 >nul
npm config set https-proxy http://127.0.0.1:7897 >nul

REM Start Expo in tunnel mode on a non-default port to avoid conflicts
npx expo start --tunnel --port 8082 --max-workers 1
