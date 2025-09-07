#!/usr/bin/env python3
"""
SoLab Telegram Bot 命令处理器
Bot Command Handlers
"""

import os
import sys
import asyncio
import threading
import time
import yaml
from datetime import datetime
from typing import Dict, List, Optional
import telebot
from telebot import types

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from functions.topTradedTokenHolderAnalysis import TopTradedTokenHolderAnalyzer
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
        self.qualified_count = 0
        self.analysis_thread = None
        self.config_manager = ConfigManager()
        
    def get_available_presets(self) -> List[str]:
        """获取可用的Jupiter预设"""
        try:
            with open('settings/config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            presets = list(config['crawlers']['jupiter']['toptraded'].keys())
            return presets
        except Exception as e:
            print(f"获取预设失败: {e}")
            return ['lowCapGem_24h', 'trending_24h', 'lowCapSusVol_5m']
    
    def start_analysis(self, preset_name: str, user_id: int):
        """开始持续分析"""
        if self.is_running:
            return False, "分析已在运行中"
        
        self.is_running = True
        self.current_preset = preset_name
        self.current_cycle = 1
        self.current_token_index = 0
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
        
        status = f"""
🟢 分析运行中
📊 预设: {self.current_preset}
🔄 周期: {self.current_cycle}
📈 进度: {self.current_token_index}/{self.total_tokens}
✅ 已找到符合条件代币: {self.qualified_count}个
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
                print(f"🔄 开始第 {self.current_cycle} 轮分析，预设: {self.current_preset}")
                
                # 分析热门代币
                qualified_results = analyzer.analyze_top_traded_tokens(
                    preset_name=self.current_preset,
                    max_tokens=15,
                    delay_between_tokens=3.0
                )
                
                self.total_tokens = 15  # 实际分析的代币数量
                
                # 发送符合条件的代币到群组
                for result in qualified_results:
                    if not self.is_running:
                        break
                    
                    self.qualified_count += 1
                    
                    # 生成报告
                    token_info = result.get('token_info', {})
                    symbol = token_info.get('symbol', 'Unknown')
                    
                    report = analyzer.holder_analyzer.generate_detective_report(
                        result, symbol, top_holdings_count=15
                    )
                    
                    # 发送到群组
                    self._send_to_group(f"🎯 发现符合条件的代币: {symbol}\n\n{report}")
                    
                    time.sleep(2)  # 避免发送过快
                
                # 周期完成
                self.current_cycle += 1
                self.current_token_index = 0
                
                if self.is_running:
                    cycle_summary = f"""
🔄 第 {self.current_cycle - 1} 轮分析完成

📊 预设: {self.current_preset}
🎯 本轮发现: {len(qualified_results)} 个符合条件代币
📈 累计发现: {self.qualified_count} 个代币
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔄 准备开始下一轮分析...
                    """
                    self._send_to_group(cycle_summary.strip())
                    
                    # 等待一段时间再开始下一轮
                    time.sleep(30)
                
            except Exception as e:
                error_msg = f"❌ 分析过程中发生错误: {e}"
                print(error_msg)
                self._send_to_group(error_msg)
                time.sleep(60)  # 出错后等待更长时间
    
    def _send_to_group(self, message: str):
        """发送消息到群组"""
        try:
            if self.topic_id:
                # 发送到指定话题
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    message_thread_id=int(self.topic_id),
                    parse_mode='Markdown',
                    disable_web_page_preview=True  # 禁用链接预览
                )
            else:
                # 发送到群组
                self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True  # 禁用链接预览
                )
        except Exception as e:
            print(f"发送消息到群组失败: {e}")


def setup_rape_handlers(bot: telebot.TeleBot, chat_id: str, topic_id: str):
    """设置rape相关命令处理器"""
    
    # 创建分析管理器
    analysis_manager = RapeAnalysisManager(bot, chat_id, topic_id)
    
    @bot.message_handler(commands=['rape'])
    def rape_command(message):
        """处理 /rape 命令 - 根据参数执行不同操作"""
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
                    markup.add(types.InlineKeyboardButton(
                        text=f"📊 {preset}",
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
        
        success, msg = analysis_manager.start_analysis(preset_name, call.from_user.id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ 分析已启动!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🚀 {msg}\n\n🔄 正在启动分析循环...\n📊 符合条件的代币将自动推送到群组"
            )
        else:
            bot.answer_callback_query(call.id, f"❌ {msg}")
    
    return analysis_manager