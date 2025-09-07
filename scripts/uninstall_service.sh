#!/bin/bash

echo "=========================================="
echo "SoLab Telegram Bot 服务卸载程序"
echo "=========================================="

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用sudo运行此脚本"
    exit 1
fi

# 设置变量
SERVICE_NAME="solab-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "🛑 停止服务..."
systemctl stop $SERVICE_NAME

echo "❌ 禁用自动启动..."
systemctl disable $SERVICE_NAME

echo "🗑️ 删除服务文件..."
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    echo "✅ 服务文件已删除"
else
    echo "⚠️ 服务文件不存在"
fi

echo "🔄 重新加载systemd..."
systemctl daemon-reload

echo ""
echo "✅ 卸载完成！"
echo ""
