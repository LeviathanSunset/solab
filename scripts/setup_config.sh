#!/bin/bash

# SoLab Bot 配置脚本
# 用于快速配置环境变量

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/settings/.env"
ENV_EXAMPLE="$PROJECT_DIR/settings/.env.example"

echo "🔧 SoLab Bot 配置向导"
echo "===================="

# 检查示例文件是否存在
if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "❌ 未找到环境变量示例文件: $ENV_EXAMPLE"
    exit 1
fi

# 如果.env文件已存在，询问是否覆盖
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  环境变量文件已存在: $ENV_FILE"
    read -p "是否要重新配置？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 取消配置"
        exit 0
    fi
fi

# 复制示例文件
cp "$ENV_EXAMPLE" "$ENV_FILE"
echo "✅ 已创建环境变量文件: $ENV_FILE"

echo ""
echo "📝 请配置以下环境变量:"
echo ""

# 获取 Telegram API Key
echo "1️⃣ Telegram Bot API Key"
echo "   获取方式: 在Telegram中找到 @BotFather，发送 /newbot 创建机器人"
read -p "   请输入你的 Telegram API Key: " api_key

if [ -n "$api_key" ]; then
    sed -i "s/your_telegram_api_key_here/$api_key/" "$ENV_FILE"
    echo "   ✅ API Key 已设置"
else
    echo "   ⚠️  API Key 为空，请稍后手动编辑 $ENV_FILE"
fi

echo ""

# 获取 Chat ID
echo "2️⃣ Telegram 群组/频道 ID"
echo "   获取方式: 将机器人添加到群组，发送消息，然后访问:"
echo "   https://api.telegram.org/bot<你的API_KEY>/getUpdates"
read -p "   请输入群组/频道 ID (以-100开头): " chat_id

if [ -n "$chat_id" ]; then
    sed -i "s/your_telegram_chat_id_here/$chat_id/" "$ENV_FILE"
    echo "   ✅ Chat ID 已设置"
else
    echo "   ⚠️  Chat ID 为空，请稍后手动编辑 $ENV_FILE"
fi

echo ""

# 获取 Topic ID (可选)
echo "3️⃣ Telegram 话题 ID (可选)"
echo "   仅当群组启用了话题功能时需要"
read -p "   请输入话题 ID (可留空): " topic_id

if [ -n "$topic_id" ]; then
    sed -i "s/your_telegram_topic_id_here/$topic_id/" "$ENV_FILE"
    echo "   ✅ Topic ID 已设置"
else
    echo "   ✅ Topic ID 留空 (将发送到主聊天)"
fi

echo ""
echo "🎉 配置完成！"
echo ""
echo "📄 配置文件位置: $ENV_FILE"
echo "✏️  如需修改，请直接编辑该文件"
echo ""
echo "🚀 现在可以启动机器人了:"
echo "   ./scripts/manage_service.sh restart"
echo ""

# 询问是否立即重启服务
read -p "是否现在重启机器人服务？(Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "🔄 重启服务中..."
    bash "$SCRIPT_DIR/manage_service.sh" restart
    echo ""
    echo "📊 查看服务状态:"
    bash "$SCRIPT_DIR/manage_service.sh" status
fi
