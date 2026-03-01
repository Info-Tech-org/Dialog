@echo off
chcp 65001 >nul
echo ========================================
echo 家庭情绪系统 - 一键部署
echo ========================================
echo.

set SERVER_IP=47.236.106.225
set SERVER_USER=root

echo [1/4] 正在连接服务器...
echo 提示：请在弹出的 SSH 窗口中输入服务器密码
echo.

echo [2/4] 创建部署脚本...
(
echo #!/bin/bash
echo set -e
echo cd /opt
echo mkdir -p info-tech
echo cd info-tech
echo.
echo # 下载代码
echo echo "克隆项目..."
echo if [ -d ".git" ]; then
echo   git pull origin master
echo else
echo   git clone https://github.com/Info-Tech-org/info-tech.git .
echo fi
echo.
echo cd deploy
echo.
echo # 配置环境变量
echo echo "配置环境变量..."
echo JWT_SECRET=$(openssl rand -base64 32^)
echo.
echo cat ^> .env ^<^< 'ENVEOF'
echo COS_SECRET_ID=YOUR_COS_SECRET_ID
echo COS_SECRET_KEY=YOUR_COS_SECRET_KEY
echo COS_BUCKET=your-bucket-name
echo COS_REGION=ap-guangzhou
echo TENCENT_SECRET_ID=YOUR_TENCENT_SECRET_ID
echo TENCENT_SECRET_KEY=YOUR_TENCENT_SECRET_KEY
echo TENCENT_ASR_REGION=ap-guangzhou
echo OPENROUTER_API_KEY=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
echo OPENROUTER_MODEL=google/gemma-2-27b-it
echo DATABASE_URL=sqlite:///./data/family.db
echo APP_NAME=Family Emotion System
echo DEBUG=false
echo LOG_LEVEL=INFO
echo CORS_ORIGINS=https://47.236.106.225,http://47.236.106.225
echo ENVEOF
echo.
echo echo "JWT_SECRET=${JWT_SECRET}" ^>^> .env
echo.
echo # 执行部署
echo chmod +x deploy.sh
echo ./deploy.sh
) > %TEMP%\deploy-script.sh

echo [3/4] 上传并执行部署脚本...
echo 正在连接服务器，请输入密码...
scp %TEMP%\deploy-script.sh %SERVER_USER%@%SERVER_IP%:/tmp/
ssh %SERVER_USER%@%SERVER_IP% "bash /tmp/deploy-script.sh"

echo.
echo [4/4] 创建管理员账户...
ssh %SERVER_USER%@%SERVER_IP% "cd /opt/info-tech/deploy && docker compose exec -T backend python simple_create_admin.py admin Admin123!"

echo.
echo ========================================
echo 🎉 部署完成！
echo ========================================
echo.
echo 访问地址：https://%SERVER_IP%
echo 管理员账户：
echo   用户名: admin
echo   密码: Admin123!
echo.
pause
