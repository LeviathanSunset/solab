#!/usr/bin/env python3
"""
SoLab Telegram Bot
Solana代币分析机器人
"""

import os
import logging
import telebot
from datetime import datetime

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 从环境变量获取Bot Token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("❌ 请设置环境变量 TELEGRAM_BOT_TOKEN")
    print("示例: export TELEGRAM_BOT_TOKEN='your_token_here'")
    exit(1)

# 创建bot实例
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_command(message):
    """处理 /start 命令"""
    user = message.from_user
    welcome_message = f"""
🚀 欢迎使用 SoLab 代币分析机器人！

👋 你好 {user.first_name}！

🔍 专业的Solana代币分析工具
⚡ 机器人正在开发中，敬请期待更多功能！
    """
    bot.reply_to(message, welcome_message)
    logger.info(f"用户 {user.id} ({user.username}) 启动了机器人")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """处理所有其他消息"""
    reply_text = "🤖 目前机器人还在开发阶段，请使用 /start 命令开始使用。"
    bot.reply_to(message, reply_text)

def main():
    """主函数"""
    print("🚀 SoLab Telegram Bot 启动中...")
    logger.info("Bot启动中...")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("⚡ 收到中断信号，正在停止...")
    except Exception as e:
        logger.error(f"❌ 运行时错误: {e}")

if __name__ == "__main__":
    main()
