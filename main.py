#!/usr/bin/env python3
"""
SoLab Telegram Bot 主程序
Simple Telegram Bot Main Program
"""

import os
import sys
import time
import telebot
from telebot import types
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

# 加载环境变量
try:
    from dotenv import load_dotenv
    # 加载 settings/.env 文件
    env_path = os.path.join(os.path.dirname(__file__), 'settings', '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ 已加载环境变量文件: {env_path}")
    else:
        print(f"⚠️  未找到环境变量文件: {env_path}")
        print("📝 请从 settings/.env.copy 复制并配置 settings/.env 文件")
except ImportError:
    print("⚠️  python-dotenv 未安装，将只使用系统环境变量")

from functions.handles import setup_rape_handlers
from settings.config_manager import ConfigManager

class SoLabBot:
    """SoLab Telegram Bot 主类"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.load_config()
        self.setup_bot()
        
    def load_config(self):
        """加载配置"""
        try:
            # 从环境变量加载，没有默认值
            self.api_key = os.getenv('TELEGRAM_API_KEY')
            self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
            self.topic_id = os.getenv('TELEGRAM_TOPIC_ID')
            
            # 检查必需的配置是否存在
            if not self.api_key:
                print("❌ 错误: 未找到 TELEGRAM_API_KEY 环境变量")
                print("📝 请创建 settings/.env 文件并配置必要的环境变量")
                sys.exit(1)
                
            if not self.chat_id:
                print("❌ 错误: 未找到 TELEGRAM_CHAT_ID 环境变量")
                print("📝 请在 settings/.env 文件中配置 TELEGRAM_CHAT_ID")
                sys.exit(1)
                
            print(f"✅ 配置加载成功")
            print(f"📱 群组ID: {self.chat_id}")
            print(f"💬 话题ID: {self.topic_id}")
            
        except Exception as e:
            print(f"❌ 配置加载失败: {e}")
            sys.exit(1)
    
    def setup_bot(self):
        """初始化bot"""
        try:
            self.bot = telebot.TeleBot(self.api_key)
            print("✅ Bot初始化成功")
            
            # 设置命令处理器
            self.setup_handlers()
            
        except Exception as e:
            print(f"❌ Bot初始化失败: {e}")
            sys.exit(1)
    
    def _is_command_for_this_bot(self, message):
        """检查命令是否是针对这个bot的"""
        if not message.text or not message.text.startswith('/'):
            return False
        
        # 获取命令部分（第一个单词）
        command = message.text.split()[0]
        
        # 如果命令包含@，检查是否是针对这个bot的
        if '@' in command:
            # 获取bot的用户名
            try:
                bot_info = self.bot.get_me()
                bot_username = bot_info.username
                
                # 检查命令是否针对这个bot
                if not command.endswith(f'@{bot_username}'):
                    return False
            except:
                # 如果获取bot信息失败，保守处理
                return False
        
        # 检查是否是已知命令
        known_commands = ['start', 'help', 'status', 'ping', 'rape']
        base_command = command.split('@')[0][1:]  # 移除 / 和 @部分
        
        # 如果是已知命令，不在这里处理（让其他handler处理）
        if base_command in known_commands:
            return False
        
        # 只有未知的、针对这个bot的命令才在这里处理
        return True

    def setup_handlers(self):
        """设置命令处理器"""
        
        # 基础命令处理器
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            """欢迎信息"""
            welcome_text = """
🤖 SoLab Bot 已启动

📋 可用命令:
/start - 显示欢迎信息
/help - 显示帮助信息
/status - 显示bot状态
/ping - 测试连接
/rape - 代币分析相关命令
  • /rape - 查看分析状态
  • /rape on - 启动分析
  • /rape off - 停止分析

🔧 功能:
• 持续监控热门代币
• 智能持有者分析
• 自动推送符合条件的代币

💡 使用 /rape on 开始分析
            """
            self.bot.reply_to(message, welcome_text.strip())
        
        @self.bot.message_handler(commands=['status'])
        def bot_status(message):
            """Bot状态"""
            status_text = f"""
🤖 Bot状态: 运行中
⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📱 群组ID: {self.chat_id}
💬 话题ID: {self.topic_id}
🔧 功能: 正常
            """
            self.bot.reply_to(message, status_text.strip())
        
        @self.bot.message_handler(commands=['ping'])
        def ping_command(message):
            """测试连接"""
            self.bot.reply_to(message, "🏓 Pong! Bot正常运行")
        
        # 设置rape分析处理器
        self.analysis_manager = setup_rape_handlers(
            self.bot, 
            self.chat_id, 
            self.topic_id
        )
        
        # 错误处理 - 只处理针对本bot的未知命令
        @self.bot.message_handler(func=lambda message: self._is_command_for_this_bot(message))
        def handle_unknown_command(message):
            """处理未知命令"""
            command = message.text.split()[0]
            self.bot.reply_to(
                message, 
                f"❓ 未知命令 {command}。使用 /help 查看可用命令"
            )
    
    def start_polling(self):
        """开始轮询"""
        print("🚀 Bot开始运行...")
        print("按 Ctrl+C 停止bot")
        
        try:
            # 设置轮询参数
            self.bot.infinity_polling(
                timeout=10,
                long_polling_timeout=5,
                none_stop=True,
                interval=0
            )
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号")
        except Exception as e:
            print(f"❌ Bot运行错误: {e}")
        finally:
            self.stop_bot()
    
    def stop_bot(self):
        """停止bot"""
        try:
            # 停止正在运行的分析
            if hasattr(self, 'analysis_manager') and self.analysis_manager:
                self.analysis_manager.stop_analysis()
            
            # 停止bot
            self.bot.stop_polling()
            print("👋 Bot已停止")
            
        except Exception as e:
            print(f"⚠️ Bot停止时发生错误: {e}")
    
    def send_startup_notification(self):
        """发送启动通知"""
        try:
            startup_msg = f"""
🚀 SoLab Bot 已启动

⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 状态: 正常运行
📋 使用 /help 查看可用命令

💡 准备就绪，可以开始使用！
            """
            
            if self.topic_id:
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=startup_msg.strip(),
                    message_thread_id=int(self.topic_id)
                )
            else:
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=startup_msg.strip()
                )
            
            print("📨 启动通知已发送")
            
        except Exception as e:
            print(f"⚠️ 发送启动通知失败: {e}")


def main():
    """主函数"""
    print("="*50)
    print("🤖 SoLab Telegram Bot")
    print("="*50)
    
    try:
        # 创建bot实例
        bot = SoLabBot()
        
        # 发送启动通知
        bot.send_startup_notification()
        
        # 开始运行
        bot.start_polling()
        
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
