#!/bin/bash

# Solab Bot Service Manager
# 用于管理 solab-bot systemctl 服务的脚本

SERVICE_NAME="solab-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

show_usage() {
    echo "用法: $0 [命令]"
    echo ""
    echo "可用命令:"
    echo "  install     安装并启动服务"
    echo "  uninstall   停止并卸载服务"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  logs        查看服务日志"
    echo "  enable      启用开机自启动"
    echo "  disable     禁用开机自启动"
    echo "  help        显示此帮助信息"
}

install_service() {
    echo "安装 $SERVICE_NAME 服务..."
    bash "$SCRIPT_DIR/install_service.sh"
}

uninstall_service() {
    echo "卸载 $SERVICE_NAME 服务..."
    bash "$SCRIPT_DIR/uninstall_service.sh"
}

start_service() {
    echo "启动 $SERVICE_NAME 服务..."
    sudo systemctl start $SERVICE_NAME
    echo "服务已启动"
}

stop_service() {
    echo "停止 $SERVICE_NAME 服务..."
    sudo systemctl stop $SERVICE_NAME
    echo "服务已停止"
}

restart_service() {
    echo "重启 $SERVICE_NAME 服务..."
    sudo systemctl restart $SERVICE_NAME
    echo "服务已重启"
}

show_status() {
    echo "查看 $SERVICE_NAME 服务状态..."
    sudo systemctl status $SERVICE_NAME --no-pager
}

show_logs() {
    echo "查看 $SERVICE_NAME 服务日志..."
    echo "按 Ctrl+C 退出日志查看"
    sudo journalctl -u $SERVICE_NAME -f
}

enable_service() {
    echo "启用 $SERVICE_NAME 开机自启动..."
    sudo systemctl enable $SERVICE_NAME
    echo "开机自启动已启用"
}

disable_service() {
    echo "禁用 $SERVICE_NAME 开机自启动..."
    sudo systemctl disable $SERVICE_NAME
    echo "开机自启动已禁用"
}

# 主逻辑
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    help|--help|-h)
        show_usage
        ;;
    "")
        echo "错误: 请指定一个命令"
        echo ""
        show_usage
        exit 1
        ;;
    *)
        echo "错误: 未知命令 '$1'"
        echo ""
        show_usage
        exit 1
        ;;
esac
