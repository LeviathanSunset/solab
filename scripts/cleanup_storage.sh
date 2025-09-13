#!/bin/bash

# SoLab Storage Cleanup Script
# 此脚本会清理storage文件夹中的所有yaml文件，但保留.gitkeep文件

STORAGE_DIR="/root/projects/solab/storage"
LOG_FILE="/var/log/solab-cleanup.log"

# 创建日志条目
echo "$(date '+%Y-%m-%d %H:%M:%S') - Storage cleanup started" >> "$LOG_FILE"

# 检查storage目录是否存在
if [ ! -d "$STORAGE_DIR" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Storage directory does not exist: $STORAGE_DIR" >> "$LOG_FILE"
    exit 1
fi

# 计算删除前的文件数量
BEFORE_COUNT=$(find "$STORAGE_DIR" -name "*.yaml" -type f | wc -l)

# 删除所有yaml文件，但保留.gitkeep
find "$STORAGE_DIR" -name "*.yaml" -type f -delete

# 计算删除后的文件数量
AFTER_COUNT=$(find "$STORAGE_DIR" -name "*.yaml" -type f | wc -l)

# 记录结果
echo "$(date '+%Y-%m-%d %H:%M:%S') - Deleted $((BEFORE_COUNT - AFTER_COUNT)) yaml files from storage" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Storage cleanup completed" >> "$LOG_FILE"

exit 0