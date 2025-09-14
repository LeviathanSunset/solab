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


def setup_rape_handlers(bot: telebot.TeleBot, chat_id: str, topic_id: str):
    """设置rape相关命令处理器"""
    
    # 创建分析管理器
    analysis_manager = RapeAnalysisManager(bot, chat_id, topic_id)
    
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
    
    return analysis_manager