#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SoLab Telegram Bot 命令处理器
Command Handlers for SoLab Telegram Bot
"""

import os
import sys
import asyncio
import threading
import time
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any
import telebot
from telebot import types

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from functions.topTradedTokenHolderAnalysis import TopTradedTokenHolderAnalyzer
from functions.gakeAnalysis import GakeTokenMonitor
from functions.logger import CrawlerLogger, get_logger
from settings.config_manager import ConfigManager

class RapeAnalysisManager:
    """持续分析管理器"""
    
    def __init__(self, bot: telebot.TeleBot, target_chat_id: str, topic_id: str):
        self.bot = bot
        self.target_chat_id = target_chat_id
        self.topic_id = topic_id
        self.is_running = False
        self.current_preset = None
        self.current_cycle = 0
        self.current_token_index = 0
        self.total_tokens = 0
        self.total_jupiter_tokens = 0  # Jupiter爬取到的总代币数
        self.qualified_count = 0
        self.analysis_thread = None
        self.config_manager = ConfigManager()
        
        # 初始化日志器
        self.logger = get_logger("TelegramBot.AnalysisManager")
        
    def get_available_presets(self) -> List[str]:
        """获取可用的预设列表"""
        try:
            config = ConfigManager()
            presets = config.get_jupiter_presets()
            return list(presets.keys())
        except Exception as e:
            self.logger.error(f"获取预设列表失败: {e}")
            return []
    
    def get_preset_info(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """获取预设的详细信息
        
        Args:
            preset_name: 预设名称
            
        Returns:
            预设信息字典，包含筛选条件等
        """
        try:
            config = ConfigManager()
            presets = config.get_jupiter_presets()
            preset_config = presets.get(preset_name)
            
            if preset_config:
                return {
                    'min_holders': preset_config.get('min_holders', 7),
                    'min_total_value': preset_config.get('min_total_value', 300000),
                    'timeFrame': preset_config.get('timeFrame', '24h'),
                    'minMcap': preset_config.get('minMcap', 0),
                    'maxMcap': preset_config.get('maxMcap', 0)
                }
            return None
        except Exception as e:
            self.logger.error(f"获取预设 {preset_name} 信息失败: {e}")
            return None
    
    def get_preset_display_info(self, preset_name: str) -> str:
        """获取预设的显示信息
        
        Args:
            preset_name: 预设名称
            
        Returns:
            格式化的显示文本
        """
        preset_info = self.get_preset_info(preset_name)
        if preset_info:
            holders = preset_info['min_holders']
            value_k = preset_info['min_total_value'] // 1000
            return f"{preset_name} (≥{holders}人, ≥${value_k}K)"
        return preset_name
    
    def start_analysis(self, preset_name: str, user_id: int):
        """开始持续分析"""
        if self.is_running:
            return False, "分析已在运行中"
        
        self.is_running = True
        self.current_preset = preset_name
        self.current_cycle = 1
        self.current_token_index = 0
        self.total_tokens = 0
        self.total_jupiter_tokens = 0
        self.qualified_count = 0
        
        # 启动分析线程
        self.analysis_thread = threading.Thread(
            target=self._analysis_loop,
            args=(user_id,),
            daemon=True
        )
        self.analysis_thread.start()
        
        return True, f"已启动持续分析，使用预设: {preset_name}"
    
    def stop_analysis(self):
        """停止分析"""
        if not self.is_running:
            return False, "没有正在运行的分析"
        
        self.is_running = False
        return True, "分析已停止"
    
    def get_status(self) -> str:
        """获取当前状态"""
        if not self.is_running:
            return "🔴 分析未运行"
        
        # 确保进度显示正确
        progress_str = f"{self.current_token_index}/{self.total_tokens}" if self.total_tokens > 0 else "准备中..."
        
        status = f"""
🟢 分析运行中
📊 预设: {self.current_preset}
🔄 周期: {self.current_cycle}
📈 分析进度: {progress_str}
🎯 Jupiter爬取: {self.total_jupiter_tokens}个代币
✅ 符合条件: {self.qualified_count}个代币
        """
        return status.strip()
    
    def _analysis_loop(self, user_id: int):
        """分析循环"""
        # 设置认证信息
        analyzer = TopTradedTokenHolderAnalyzer(performance_mode='high_speed')
        analyzer.set_auth(
            cookie="devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; locale=en_US; ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; ok_prefer_udColor=0; ok_prefer_udTimeZone=0; fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; ok_global={%22g_t%22:2}; _gcl_au=1.1.1005719754.1755091396; connectedWallet=1; _gid=GA1.2.950489538.1757092345; mse=nf=8|se=0; __cf_bm=KlSlz4ToD2eBrbV2YMpvOTgZSH9aJx8ZbSpNehX__70-1757227578-1.0.1.1-CVB_X0rNpOfUw.n3YJgAepDber7b9fzyAdFONBE5xbbJ9uokVrU0D0ZnKpCgKqWRX9MNMHAODFPNpxZDZYUw1XLYVw6RbsONqf7J5SbrKAc; ok-exp-time=1757227583876; okg.currentMedia=md; tmx_session_id=g42rqe6lkgv_1757227586034; connected=1; fp_s=0; traceId=2130772279702400005; _gat_UA-35324627-3=1; _ga=GA1.1.2083537763.1750302376; _ga_G0EKWWQGTZ=GS2.1.s1757227595$o127$g1$t1757227972$j58$l0$h0; ok-ses-id=ic8FZdwDJ9iztku9zy3wjshp7WSUVWnCq6wpmGltOew4BJU1wkFkGYHyg2jS3JIKpZCB7dnA0g1BCrndYsGLeFEXC9fKYuWwNU4qCZlHwpNQI42XTE4EYPY03Z1p2MaR; _monitor_extras={\"deviceId\":\"KmpeI8VVHan-2zL3_DbOJB\",\"eventId\":6313,\"sequenceNumber\":6313}",
            fp_token="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
            verify_sign="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4=",
            verify_token="ac90bf8e-b5fc-4643-a441-2d7b7eb08634",
            dev_id="01980a38-038a-44d9-8da3-a8276bbcb5b9",
            site_info="==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOi42bpdWZyJye"
        )
        
        while self.is_running:
            try:
                self.logger.info(f"🔄 开始第 {self.current_cycle + 1} 轮分析，预设: {self.current_preset}")
                
                # 定义即时发送回调函数
                def instant_send_callback(analysis_result):
                    """立即发送符合条件的代币"""
                    self.qualified_count += 1
                    
                    # 生成报告
                    token_info = analysis_result.get('token_info', {})
                    symbol = token_info.get('symbol', 'Unknown')
                    name = token_info.get('name', '')
                    contract_address = token_info.get('contract_address', '')
                    
                    # 特殊处理SOL代币 - 只基于合约地址匹配
                    if contract_address == "So11111111111111111111111111111111111111112":
                        token_display = "SOL"
                    else:
                        # 其他代币显示符号和链接
                        token_display = f"[{symbol}](https://gmgn.ai/sol/token/{contract_address})"
                    
                    report = analyzer.holder_analyzer.generate_detective_report(
                        analysis_result, symbol, top_holdings_count=15, show_not_in_top20=False
                    )
                    
                    # 立即发送到群组
                    self._send_to_group(f"🎯 发现符合条件的代币: {token_display}\n\n{report}")
                
                # 分析热门代币 - 传入即时回调
                def update_progress(current, total):
                    self.current_token_index = current
                    self.total_tokens = total
                
                def update_jupiter_count(jupiter_total):
                    """更新Jupiter爬取到的代币总数"""
                    self.total_jupiter_tokens = jupiter_total
                
                qualified_results = analyzer.analyze_top_traded_tokens(
                    preset_name=self.current_preset,
                    max_tokens=1000,  # 增加到1000个代币
                    delay_between_tokens=3.0,
                    progress_callback=update_progress,
                    qualified_callback=instant_send_callback,  # 🚀 添加即时发送回调
                    jupiter_callback=update_jupiter_count  # 新增：Jupiter数据回调
                )
                
                self.logger.info(f"📊 第 {self.current_cycle + 1} 轮分析完成，发现 {len(qualified_results)} 个符合条件的代币")
                
                # 注意：符合条件的代币已经通过回调即时发送到群组了，无需再次发送
                
                # 周期完成
                self.current_cycle += 1
                self.current_token_index = 0
                
                if self.is_running:
                    cycle_summary = f"""
🔄 第 {self.current_cycle} 轮分析完成

📊 预设: {self.current_preset}
🎯 Jupiter爬取: {self.total_jupiter_tokens} 个代币
📈 实际分析: {self.total_tokens} 个代币
✅ 本轮发现: {len(qualified_results)} 个符合条件代币
� 累计符合条件: {self.qualified_count} 个代币
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔄 准备开始下一轮分析...
                    """
                    self._send_to_group(cycle_summary.strip())
                    self.logger.info(f"📊 周期 {self.current_cycle} 分析统计已发送，等待下一轮")
                    
                    # 等待一段时间再开始下一轮
                    time.sleep(30)
                
            except Exception as e:
                error_msg = f"❌ 分析过程中发生错误: {e}"
                self.logger.error(error_msg)
                self._send_to_group(error_msg)
                time.sleep(60)  # 出错后等待更长时间
    
    def _send_to_group(self, message: str):
        """发送消息到群组"""
        try:
            # 将Markdown链接转换为HTML格式
            import re
            # 转换 [text](url) 为 <a href="url">text</a>
            html_message = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', message)
            
            if self.topic_id:
                # 发送到指定话题
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=html_message,
                    message_thread_id=int(self.topic_id),
                    parse_mode='HTML',  # 改为HTML格式
                    disable_web_page_preview=True  # 禁用链接预览
                )
                self.logger.debug(f"📤 消息已发送到话题 {self.topic_id}")
            else:
                # 发送到群组
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=html_message,
                    parse_mode='HTML',  # 改为HTML格式
                    disable_web_page_preview=True  # 禁用链接预览
                )
                self.logger.debug("📤 消息已发送到群组")
        except Exception as e:
            error_msg = f"发送消息到群组失败: {e}"
            self.logger.error(error_msg)

    def _send_to_group_html(self, message: str, keyboard: List[List[Dict[str, str]]] = None):
        """发送HTML格式消息到群组，支持内联键盘"""
        try:
            # 创建内联键盘
            markup = None
            if keyboard:
                from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup()
                for row in keyboard:
                    buttons = [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) for btn in row]
                    markup.add(*buttons)

            if self.topic_id:
                # 发送到指定话题
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    message_thread_id=int(self.topic_id),
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
                self.logger.debug(f"📤 HTML消息已发送到话题 {self.topic_id}")
            else:
                # 发送到群组
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
                self.logger.debug("📤 HTML消息已发送到群组")
        except Exception as e:
            error_msg = f"发送HTML消息到群组失败: {e}"
            self.logger.error(error_msg)


class GakeAnalysisManager:
    """Gake分析管理器"""

    def __init__(self, bot: telebot.TeleBot, target_chat_id: str, topic_id: str):
        self.bot = bot
        self.target_chat_id = target_chat_id
        self.topic_id = topic_id
        self.gake_monitor = GakeTokenMonitor()
        self.is_running = False

        # 初始化日志器
        self.logger = get_logger("TelegramBot.GakeAnalysisManager")

    def start_gake_monitoring(self, user_id: int):
        """开始Gake监控"""
        if self.is_running:
            return False, "Gake监控已在运行中"

        # 定义警报回调函数
        def gake_alert_callback(alert):
            """Gake警报回调函数"""
            try:
                # 获取代币symbols
                token_symbols = {}
                if alert.common_tokens:
                    token_symbols = self.gake_monitor._get_token_symbols(alert.common_tokens)

                # 格式化警报消息
                message = alert.format_message(token_symbols)

                # 获取内联键盘
                keyboard = alert.get_inline_keyboard(token_symbols)

                # 发送到群组 - 使用HTML格式
                self._send_to_group_html(message, keyboard)

            except Exception as e:
                self.logger.error(f"❌ 发送Gake警报失败: {str(e)}")

        # 启动监控
        success = self.gake_monitor.start_monitoring(callback=gake_alert_callback)

        if success:
            self.is_running = True
            return True, "Gake监控已启动"
        else:
            return False, "启动Gake监控失败"

    def stop_gake_monitoring(self):
        """停止Gake监控"""
        if not self.is_running:
            return False, "没有正在运行的Gake监控"

        success = self.gake_monitor.stop_monitoring()

        if success:
            self.is_running = False
            return True, "Gake监控已停止"
        else:
            return False, "停止Gake监控失败"

    def get_gake_status(self) -> str:
        """获取Gake监控状态"""
        if not self.is_running:
            return "🔴 Gake监控未运行"

        status_info = self.gake_monitor.get_status()

        status = f"""
🟢 Gake监控运行中

📊 监控配置:
   • 市值范围: ${self.gake_monitor.min_market_cap:,} - ${self.gake_monitor.max_market_cap:,}
   • 最小成交量: ${self.gake_monitor.min_volume_1h:,} (1小时)
   • 最小年龄: {self.gake_monitor.min_age_minutes} 分钟
   • 涨幅阈值: {self.gake_monitor.price_increase_threshold}%

📈 监控状态:
   • 监控代币: {status_info['monitored_tokens']} 个
   • 快照总数: {status_info['total_snapshots']} 个
   • 快照间隔: {status_info['snapshot_interval']} 秒
        """
        return status.strip()

    def _send_to_group(self, message: str):
        """发送消息到群组"""
        try:
            # 将Markdown链接转换为HTML格式
            import re
            # 转换 [text](url) 为 <a href="url">text</a>
            html_message = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', message)

            if self.topic_id:
                # 发送到指定话题
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=html_message,
                    message_thread_id=int(self.topic_id),
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                self.logger.debug(f"📤 Gake消息已发送到话题 {self.topic_id}")
            else:
                # 发送到群组
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=html_message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                self.logger.debug("📤 Gake消息已发送到群组")
        except Exception as e:
            error_msg = f"发送Gake消息到群组失败: {e}"
            self.logger.error(error_msg)

    def _send_to_group_html(self, message: str, keyboard: List[List[Dict[str, str]]] = None):
        """发送HTML格式消息到群组，支持内联键盘"""
        try:
            # 创建内联键盘
            markup = None
            if keyboard:
                from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup()
                for row in keyboard:
                    buttons = [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) for btn in row]
                    markup.add(*buttons)

            if self.topic_id:
                # 发送到指定话题
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    message_thread_id=int(self.topic_id),
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
                self.logger.debug(f"📤 Gake HTML消息已发送到话题 {self.topic_id}")
            else:
                # 发送到群组
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=markup
                )
                self.logger.debug("📤 Gake HTML消息已发送到群组")
        except Exception as e:
            error_msg = f"发送Gake HTML消息到群组失败: {e}"
            self.logger.error(error_msg)


def setup_rape_handlers(bot: telebot.TeleBot, chat_id: str, topic_id: str):
    """设置rape相关命令处理器"""

    # 创建分析管理器
    analysis_manager = RapeAnalysisManager(bot, chat_id, topic_id)
    gake_manager = GakeAnalysisManager(bot, chat_id, topic_id)
    
    def _should_respond_to_command(message):
        """检查是否应该响应此命令"""
        if not message.text or not message.text.startswith('/'):
            return True
        
        command = message.text.split()[0]
        
        # 如果命令包含@，检查是否是针对这个bot的
        if '@' in command:
            try:
                bot_info = bot.get_me()
                bot_username = bot_info.username
                
                # 如果不是针对这个bot的命令，不响应
                if not command.endswith(f'@{bot_username}'):
                    return False
            except:
                # 如果获取bot信息失败，不响应带@的命令
                return False
        
        return True
    
    @bot.message_handler(commands=['rape'])
    def rape_command(message):
        """处理 /rape 命令 - 根据参数执行不同操作"""
        # 检查命令是否针对此bot
        if not _should_respond_to_command(message):
            return
            
        # 解析命令参数
        command_text = message.text.strip()
        parts = command_text.split()
        
        if len(parts) == 1:
            # 只有 /rape - 查看状态
            status = analysis_manager.get_status()
            bot.reply_to(message, status)
        
        elif len(parts) == 2:
            action = parts[1].lower()
            
            if action == 'on':
                # /rape on - 启动分析
                if analysis_manager.is_running:
                    bot.reply_to(message, "🔴 分析已在运行中，请先使用 /rape off 停止")
                    return
                
                # 获取可用预设
                presets = analysis_manager.get_available_presets()
                
                # 创建内联键盘
                markup = types.InlineKeyboardMarkup(row_width=1)
                for preset in presets:
                    callback_data = f"start_analysis:{preset}"
                    display_text = analysis_manager.get_preset_display_info(preset)
                    markup.add(types.InlineKeyboardButton(
                        text=f"📊 {display_text}",
                        callback_data=callback_data
                    ))
                
                bot.reply_to(
                    message,
                    "🚀 选择要使用的分析预设:",
                    reply_markup=markup
                )
            
            elif action == 'off':
                # /rape off - 停止分析
                success, msg = analysis_manager.stop_analysis()
                if success:
                    bot.reply_to(message, f"🛑 {msg}")
                else:
                    bot.reply_to(message, f"⚠️ {msg}")
            
            else:
                bot.reply_to(message, "❌ 未知参数。使用: /rape, /rape on, /rape off")
        
        else:
            bot.reply_to(message, "❌ 参数错误。使用: /rape, /rape on, /rape off")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('start_analysis:'))
    def handle_preset_selection(call):
        """处理预设选择"""
        preset_name = call.data.split(':')[1]
        
        # 获取预设的筛选条件
        preset_info = analysis_manager.get_preset_info(preset_name)
        filter_info = ""
        if preset_info:
            filter_info = f"\n📋 筛选条件: ≥{preset_info['min_holders']}人持有, ≥${preset_info['min_total_value']:,}"
        
        success, msg = analysis_manager.start_analysis(preset_name, call.from_user.id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ 分析已启动!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🚀 {msg}{filter_info}\n\n🔄 正在启动分析循环...\n📊 符合条件的代币将自动推送到群组"
            )
        else:
            bot.answer_callback_query(call.id, f"❌ {msg}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('token_details_'))
    def handle_token_details(call):
        """处理查看交易地址按钮点击 - 显示目标代币交易者中也交易过该共同代币的地址"""
        try:
            # 解析callback_data: token_details_{共同代币地址}_{目标代币地址}
            data_parts = call.data.replace('token_details_', '').split('_')
            if len(data_parts) >= 2:
                common_token_address = '_'.join(data_parts[:-1])  # 共同代币地址可能包含下划线
                target_token_address = data_parts[-1]
            else:
                # 兼容旧格式
                common_token_address = call.data.replace('token_details_', '')
                target_token_address = None

            # 获取共同代币信息
            from crawlers.jupiter.multiTokenProfiles import JupiterTokenCrawler
            jupiter_crawler = JupiterTokenCrawler()
            tokens = jupiter_crawler.get_token_info([common_token_address])

            if tokens:
                common_token = tokens[0]
                token_url = f"https://gmgn.ai/sol/token/{common_token_address}"

                if target_token_address:
                    # 获取目标代币的交易地址
                    target_addresses = gake_manager.gake_monitor.okx_crawler.get_token_trading_addresses(
                        target_token_address, limit=100
                    )

                    if target_addresses:
                        # 在目标代币交易者中，找出也交易过共同代币的地址
                        intersection_addresses = []
                        for addr in target_addresses:
                            try:
                                # 获取该地址的代币列表
                                token_contracts = gake_manager.gake_monitor.address_crawler.get_address_token_contracts(addr, limit=100)
                                if token_contracts and common_token_address in token_contracts:
                                    intersection_addresses.append(addr)
                            except:
                                continue

                        detail_message = f"""🪙 <a href="{token_url}">{common_token.symbol}</a> 相关地址

🔄 地址归类结果:
📊 目标代币交易者: {len(target_addresses)}个
🎯 其中也交易过该代币: {len(intersection_addresses)}个
"""

                        if intersection_addresses:
                            detail_message += "\n📋 同时交易两个代币的地址:\n"
                            # 显示前20个交集地址
                            for i, addr in enumerate(intersection_addresses[:20]):
                                detail_message += f"{i+1:2d}. <code>{addr}</code>\n"

                            if len(intersection_addresses) > 20:
                                detail_message += f"\n... 还有 {len(intersection_addresses) - 20} 个地址"
                        else:
                            detail_message += "\n❌ 目标代币交易者中没有找到交易过该代币的地址"

                        detail_message += f"\n\n🔗 查看代币详情请点击上方链接"
                    else:
                        detail_message = f"""🪙 <a href="{token_url}">{common_token.symbol}</a> 相关地址

❌ 无法获取交易地址数据进行交集分析

🔗 查看代币详情请点击上方链接"""
                else:
                    # 兼容旧格式，显示该代币的交易地址
                    trading_addresses = gake_manager.gake_monitor.okx_crawler.get_token_trading_addresses(
                        common_token_address, limit=100
                    )

                    if trading_addresses:
                        detail_message = f"""🪙 <a href="{token_url}">{common_token.symbol}</a> 交易地址

📊 交易过该代币的地址 ({len(trading_addresses)}个):
"""
                        for i, addr in enumerate(trading_addresses[:20]):
                            detail_message += f"{i+1:2d}. <code>{addr}</code>\n"

                        if len(trading_addresses) > 20:
                            detail_message += f"\n... 还有 {len(trading_addresses) - 20} 个地址"

                        detail_message += f"\n\n🔗 查看代币详情请点击上方链接"
                    else:
                        detail_message = f"""🪙 <a href="{token_url}">{common_token.symbol}</a> 交易地址

❌ 无法获取该代币的交易地址

🔗 查看代币详情请点击上方链接"""

                # 创建返回按钮
                from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                return_markup = InlineKeyboardMarkup()
                return_markup.add(InlineKeyboardButton(
                    "↩️ 返回GAKE警报",
                    callback_data=f"back_to_gake_{call.message.message_id}"
                ))

                bot.answer_callback_query(call.id, f"📊 {token.symbol} 交易地址")
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=detail_message,
                    parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=return_markup,
                    message_thread_id=call.message.message_thread_id
                )
            else:
                bot.answer_callback_query(call.id, "❌ 无法获取代币信息")

        except Exception as e:
            bot.answer_callback_query(call.id, "❌ 处理失败")
            print(f"❌ 处理代币详情按钮失败: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('low_freq_traders_'))
    def handle_low_freq_traders(call):
        """处理查看低频交易者按钮点击"""
        try:
            # 提取代币地址
            token_address = call.data.replace('low_freq_traders_', '')

            # 这里可以实现查看低频交易者的详细信息
            # 目前先返回一个简单的消息
            detail_message = f"""🔍 低频交易者详情

📊 正在分析代币的低频交易者...
🔗 代币地址: <code>{token_address}</code>

⚠️ 此功能正在开发中"""

            # 创建返回按钮
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            return_markup = InlineKeyboardMarkup()
            return_markup.add(InlineKeyboardButton(
                "↩️ 返回GAKE警报",
                callback_data=f"back_to_gake_{call.message.message_id}"
            ))

            bot.answer_callback_query(call.id, "🔍 查看低频交易者")
            bot.send_message(
                chat_id=call.message.chat.id,
                text=detail_message,
                parse_mode='HTML',
                reply_markup=return_markup,
                message_thread_id=call.message.message_thread_id
            )

        except Exception as e:
            bot.answer_callback_query(call.id, "❌ 处理失败")
            print(f"❌ 处理低频交易者按钮失败: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_gake_'))
    def handle_back_to_gake(call):
        """处理返回GAKE警报按钮点击"""
        try:
            # 提取原始消息ID
            original_message_id = call.data.replace('back_to_gake_', '')

            # 删除当前详情消息
            bot.delete_message(call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id, "↩️ 已返回")

        except Exception as e:
            bot.answer_callback_query(call.id, "❌ 返回失败")
            print(f"❌ 处理返回按钮失败: {e}")

    @bot.message_handler(commands=['gake'])
    def gake_command(message):
        """处理 /gake 命令"""
        # 检查命令是否针对此bot
        if not _should_respond_to_command(message):
            return

        # 解析命令参数
        command_text = message.text.strip()
        parts = command_text.split()

        if len(parts) == 1:
            # 只有 /gake - 查看状态
            status = gake_manager.get_gake_status()
            bot.reply_to(message, status)

        elif len(parts) == 2:
            action = parts[1].lower()

            if action == 'on':
                # /gake on - 启动Gake监控
                if gake_manager.is_running:
                    bot.reply_to(message, "🔴 Gake监控已在运行中，请先使用 /gake off 停止")
                    return

                success, msg = gake_manager.start_gake_monitoring(message.from_user.id)

                if success:
                    startup_msg = f"""🚀 **Gake监控已启动** 🚀

📊 **监控配置:**
• 市值范围: $10,000 - $30,000
• 最小成交量: $1,000 (1小时)
• 最小年龄: 720 分钟 (12小时)
• 涨幅阈值: 3%
• 监控间隔: 30秒
• 分析交易地址: 100条记录 (~35个唯一地址)

🔍 **分析内容:**
• 监控符合条件的代币价格变动
• 分析交易地址的7天、30天交易频率
• 检测可疑地址共同交易的代币
• 识别cabal代币关联

⚠️ **触发条件:**
• 代币价格30秒内上涨超过3%
• 至少2个可疑地址参与交易
• 可疑地址定义: 7天或30天交易次数<50

📢 **符合条件的可疑活动将自动推送到群组**
                    """
                    bot.reply_to(message, startup_msg.strip())
                else:
                    bot.reply_to(message, f"❌ {msg}")

            elif action == 'off':
                # /gake off - 停止Gake监控
                success, msg = gake_manager.stop_gake_monitoring()
                if success:
                    bot.reply_to(message, f"🛑 {msg}")
                else:
                    bot.reply_to(message, f"⚠️ {msg}")

            else:
                bot.reply_to(message, "❌ 未知参数。使用: /gake, /gake on, /gake off")

        else:
            bot.reply_to(message, "❌ 参数错误。使用: /gake, /gake on, /gake off")

    # 返回管理器（主要是analysis_manager用于向后兼容）
    return analysis_manager