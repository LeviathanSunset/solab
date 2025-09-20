#!/bin/bash

# SoLab Bot 快照清理脚本 - 每次服务启动前执行
# 保留最新的2个快照文件

LOG_FILE="/root/projects/solab/logs/cleanup.log"
STORAGE_DIR="/root/projects/solab/storage"

# 创建日志目录（如果不存在）
mkdir -p "$(dirname "$LOG_FILE")"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "===== 开始清理快照文件 ====="

# 进入存储目录
cd "$STORAGE_DIR" || {
    log "错误: 无法进入存储目录 $STORAGE_DIR"
    exit 1
}

# 清理 toptraded_ 开头的文件，按修改时间排序，保留最新2个
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

        # 计算剩余文件数
        REMAINING_COUNT=$(ls -1 toptraded_* 2>/dev/null | wc -l)
        log "清理完成，剩余 $REMAINING_COUNT 个toptraded文件"
    else
        log "没有找到需要删除的旧文件"
    fi
else
    log "toptraded文件数量 ($TOPTRADED_COUNT) 不超过2个，无需清理"
fi

# 清理临时文件
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

# 显示当前存储状态
TOTAL_FILES=$(ls -1 | wc -l)
STORAGE_SIZE=$(du -sh . | cut -f1)
log "存储目录状态: $TOTAL_FILES 个文件，占用空间: $STORAGE_SIZE"

log "===== 快照清理完成 ====="