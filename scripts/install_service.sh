#!/bin/bash

echo "=========================================="
echo "SoLab Telegram Bot 自动启动脚本安装程序"
echo "=========================================="

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用sudo运行此脚本"
    exit 1
fi

# 设置变量
SERVICE_NAME="solab-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📁 当前目录: $CURRENT_DIR"

# 检查主文件是否存在
if [ ! -f "$CURRENT_DIR/main.py" ]; then
    echo "❌ 找不到main.py文件"
    exit 1
fi

echo "✅ 找到main.py文件"

# 复制服务文件到系统目录
echo "📋 复制服务文件到 $SERVICE_FILE"
cp "$CURRENT_DIR/solab-bot.service" "$SERVICE_FILE"

if [ $? -ne 0 ]; then
    echo "❌ 复制服务文件失败"
    exit 1
fi

echo "✅ 服务文件复制成功"

# 重新加载systemd
echo "🔄 重新加载systemd..."
systemctl daemon-reload

# 启用服务
echo "🚀 启用服务..."
systemctl enable $SERVICE_NAME

# 启动服务
echo "▶️ 启动服务..."
systemctl start $SERVICE_NAME

# 检查服务状态
echo "📊 检查服务状态..."
sleep 2
systemctl status $SERVICE_NAME

echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo "=========================================="
echo ""
echo "🔧 常用命令："
echo "  查看状态:   sudo systemctl status $SERVICE_NAME"
echo "  启动服务:   sudo systemctl start $SERVICE_NAME"
echo "  停止服务:   sudo systemctl stop $SERVICE_NAME"
echo "  重启服务:   sudo systemctl restart $SERVICE_NAME"
echo "  查看日志:   sudo journalctl -u $SERVICE_NAME -f"
echo "  禁用自启:   sudo systemctl disable $SERVICE_NAME"
echo ""
