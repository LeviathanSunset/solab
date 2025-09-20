#!/bin/bash

# SoLab Bot 重启脚本 - 每12小时运行一次，清理旧快照
# 保留最新的2个快照文件

LOG_FILE="/root/projects/solab/logs/restart_cleanup.log"
STORAGE_DIR="/root/projects/solab/storage"
SERVICE_NAME="solab-bot"

# 创建日志目录（如果不存在）
mkdir -p "$(dirname "$LOG_FILE")"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "===== 开始重启和清理任务 ====="

# 1. 停止服务
log "停止 $SERVICE_NAME 服务..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl stop "$SERVICE_NAME"
    log "服务已停止"
else
    log "服务未运行，跳过停止步骤"
fi

# 2. 清理快照文件（保留最新2个）
log "开始清理快照文件..."

# 清理 toptraded_ 开头的文件，按修改时间排序，保留最新2个
cd "$STORAGE_DIR" || {
    log "错误: 无法进入存储目录 $STORAGE_DIR"
    exit 1
}

# 计算 toptraded_ 文件数量
TOPTRADED_COUNT=$(ls -1 toptraded_* 2>/dev/null | wc -l)

if [ "$TOPTRADED_COUNT" -gt 2 ]; then
    # 获取最旧的文件列表（除了最新的2个）
    OLD_FILES=$(ls -t toptraded_* | tail -n +3)

    if [ -n "$OLD_FILES" ]; then
        log "发现 $TOPTRADED_COUNT 个toptraded文件，删除最旧的 $((TOPTRADED_COUNT - 2)) 个..."
        echo "$OLD_FILES" | while read -r file; do
            if [ -f "$file" ]; then
                rm -f "$file"
                log "已删除: $file"
            fi
        done

        # 计算释放的空间
        REMAINING_COUNT=$(ls -1 toptraded_* 2>/dev/null | wc -l)
        log "清理完成，剩余 $REMAINING_COUNT 个toptraded文件"
    else
        log "没有找到需要删除的旧文件"
    fi
else
    log "toptraded文件数量 ($TOPTRADED_COUNT) 不超过2个，无需清理"
fi

# 清理其他可能的临时文件
TEMP_COUNT=0
for pattern in "*.tmp" "*.temp" "*.bak" "*~"; do
    if ls $pattern 1> /dev/null 2>&1; then
        TEMP_COUNT=$((TEMP_COUNT + $(ls -1 $pattern | wc -l)))
        rm -f $pattern
    fi
done

if [ "$TEMP_COUNT" -gt 0 ]; then
    log "已清理 $TEMP_COUNT 个临时文件"
fi

# 显示当前存储目录状态
TOTAL_FILES=$(ls -1 | wc -l)
STORAGE_SIZE=$(du -sh . | cut -f1)
log "存储目录状态: $TOTAL_FILES 个文件，占用空间: $STORAGE_SIZE"

# 3. 启动服务
log "启动 $SERVICE_NAME 服务..."
systemctl start "$SERVICE_NAME"

# 等待服务启动
sleep 5

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "服务启动成功"
    log "===== 重启和清理任务完成 ====="
else
    log "错误: 服务启动失败！"
    log "===== 重启和清理任务异常结束 ====="
    exit 1
fi

# 显示最终状态
systemctl status "$SERVICE_NAME" --no-pager -l >> "$LOG_FILE"

log "任务完成时间: $(date '+%Y-%m-%d %H:%M:%S')"