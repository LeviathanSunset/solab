#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gake功能 - 代币监控和分析模块
监控10k-30k市值代币的价格变动和地址分析
"""

import os
import sys
import time
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.jupiter.topTradedTokens import JupiterTopTradedCrawler
from crawlers.jupiter.multiTokenProfiles import JupiterTokenCrawler
from crawlers.okxdex.tokenTradingHistory import OKXTokenTradingHistoryCrawler
from functions.addressAnalysis import AddressAnalyzer
from functions.logger import get_logger
from settings.config_manager import ConfigManager

# 创建全局配置管理器实例
_config_manager = ConfigManager()

def get_cabal_tokens():
    return _config_manager.get_cabal_tokens()

def get_suspicious_criteria():
    return _config_manager.get_suspicious_criteria()


@dataclass
class TokenSnapshot:
    """代币快照数据结构"""
    contract_address: str
    symbol: str
    name: str
    market_cap: float
    price: float
    volume_1h: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'contract_address': self.contract_address,
            'symbol': self.symbol,
            'name': self.name,
            'market_cap': self.market_cap,
            'price': self.price,
            'volume_1h': self.volume_1h,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AddressProfile:
    """地址交易档案"""
    address: str
    transaction_count_7d: int
    transaction_count_30d: int
    common_tokens: List[str]
    cabal_tokens: List[str]

    def is_suspicious(self, max_tx_count: int = 50) -> bool:
        """判断地址是否可疑（交易次数少）"""
        return (self.transaction_count_7d < max_tx_count or
                self.transaction_count_30d < max_tx_count)


@dataclass
class GakeAlert:
    """Gake警报数据结构"""
    token: TokenSnapshot
    price_increase: float
    suspicious_addresses: List[str]
    common_tokens: List[str]
    cabal_tokens: List[str]
    analysis_time: datetime
    # 新增字段：代币交易地址统计
    token_address_count: Dict[str, int]  # {代币地址: 交易该代币的地址数量}
    address_profiles: Dict[str, AddressProfile]  # {地址: 地址档案}

    def get_inline_keyboard(self, token_symbols: Dict[str, str] = None) -> List[List[Dict[str, str]]]:
        """生成Telegram内联键盘按钮

        Args:
            token_symbols: 代币地址到symbol的映射
        """
        if len(self.suspicious_addresses) < 3 or not self.common_tokens:
            return []

        keyboard = []

        # 为前4个代币创建按钮
        for i, token_addr in enumerate(self.common_tokens[:4]):
            # 获取代币symbol
            if token_symbols and token_addr in token_symbols:
                token_symbol = token_symbols[token_addr]
            else:
                # 后备方案
                if token_addr == 'So11111111111111111111111111111111111111112':
                    token_symbol = 'SOL'
                elif token_addr == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    token_symbol = 'USDC'
                else:
                    token_symbol = token_addr[:8] + '...'

            button_text = f"🪙 {token_symbol}"
            # 简化格式，只传递共同代币地址
            callback_data = f"token_details_{token_addr}"
            keyboard.append([{
                "text": button_text,
                "callback_data": callback_data
            }])

        # 添加查看所有低频交易者按钮
        keyboard.append([{
            "text": "🔍 查看所有低频交易者",
            "callback_data": f"low_freq_{self.token.contract_address[:20]}"  # 缩短到符合限制
        }])

        return keyboard

    def format_message(self, token_symbols: Dict[str, str] = None) -> str:
        """格式化为Telegram消息

        Args:
            token_symbols: 代币地址到symbol的映射
        """
        # GMGN链接
        token_url = f"https://gmgn.ai/sol/token/{self.token.contract_address}"

        # 使用HTML格式
        message = f"""🎯 发现符合条件的代币: <a href="{token_url}">{self.token.symbol}</a>

📈 涨幅: {self.price_increase:.2f}%
💰 当前市值: ${self.token.market_cap:,.0f}

🔥 [<a href="{token_url}">{self.token.symbol}</a>]交易者
🔢 共同交易代币种类: {len(self.common_tokens)}
───────────────────────────────────"""

        # 添加共同代币列表
        for i, token_addr in enumerate(self.common_tokens[:10]):
            token_url_item = f"https://gmgn.ai/sol/token/{token_addr}"

            # 获取交易该代币的地址数量
            addr_count = self.token_address_count.get(token_addr, 0)

            # 获取代币symbol
            if token_symbols and token_addr in token_symbols:
                token_symbol = token_symbols[token_addr]
            else:
                # 后备方案
                if token_addr == 'So11111111111111111111111111111111111111112':
                    token_symbol = 'SOL'
                elif token_addr == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    token_symbol = 'USDC'
                else:
                    token_symbol = token_addr[:8] + '...'

            message += f'\n {i+1}. <a href="{token_url_item}">{token_symbol}</a> ({addr_count}人)'

        # 计算低频交易者统计
        total_addresses = len(self.address_profiles)
        low_freq_7d = sum(1 for profile in self.address_profiles.values()
                         if profile.transaction_count_7d < 30)
        low_freq_30d = sum(1 for profile in self.address_profiles.values()
                          if profile.transaction_count_30d < 50)

        message += f"""

───────────────────────────────────
📊 [<a href="{token_url}">{self.token.symbol}</a>] 低频交易者统计：
🕒 7d低频（小于30次）：{low_freq_7d}/{total_addresses}
🕒 30d低频（小于50次）：{low_freq_30d}/{total_addresses}
👥 分析地址: 最近 {total_addresses} 个"""

        return message


class GakeTokenMonitor:
    """Gake代币监控器"""

    def __init__(self):
        self.logger = get_logger("GakeTokenMonitor")
        self.jupiter_crawler = JupiterTopTradedCrawler()
        self.jupiter_token_crawler = JupiterTokenCrawler()
        self.okx_crawler = OKXTokenTradingHistoryCrawler(performance_mode='high_speed')
        self.address_analyzer = AddressAnalyzer(performance_mode='high_speed')

        # 设置OKX认证信息
        self._setup_okx_auth()

        # 监控状态
        self.is_running = False
        self.monitor_thread = None

        # 快照存储 - 只保留两个全局快照：上一次和当前
        self.previous_snapshots: Dict[str, TokenSnapshot] = {}  # contract_address -> snapshot
        self.current_snapshots: Dict[str, TokenSnapshot] = {}   # contract_address -> snapshot
        self.snapshot_lock = threading.Lock()

        # 监控配置 - 从配置文件读取
        gake_config = _config_manager._config.get('gake_monitor', {}) if _config_manager._config else {}
        self.min_market_cap = gake_config.get('min_market_cap', 10000)  # 10k
        self.max_market_cap = gake_config.get('max_market_cap', 30000)  # 30k
        self.min_volume_1h = gake_config.get('min_volume_1h', 500)     # 500
        self.min_age_minutes = gake_config.get('min_age_minutes', 720)   # 12小时 = 720分钟
        self.price_increase_threshold = gake_config.get('price_increase_threshold', 20.0)  # 20%涨幅
        self.snapshot_interval = gake_config.get('snapshot_interval', 20)  # 20秒间隔

        # 从配置文件加载cabal代币列表
        self.cabal_tokens = set(get_cabal_tokens())

        # 从配置文件加载可疑地址判断标准
        self.suspicious_criteria = get_suspicious_criteria()

    def _setup_okx_auth(self):
        """设置OKX认证信息"""
        self.okx_crawler.set_auth_tokens(
            fptoken="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
            fptoken_signature="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4="
        )

    def start_monitoring(self, callback=None) -> bool:
        """开始监控

        Args:
            callback: 发现可疑活动时的回调函数

        Returns:
            是否成功启动
        """
        if self.is_running:
            return False

        self.is_running = True
        self.callback = callback

        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()

        self.logger.info("🚀 Gake监控已启动")
        return True

    def stop_monitoring(self) -> bool:
        """停止监控"""
        if not self.is_running:
            return False

        self.is_running = False

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        self.logger.info("🛑 Gake监控已停止")
        return True

    def _monitoring_loop(self):
        """监控主循环"""
        self.logger.info("🔄 开始监控循环")

        while self.is_running:
            try:
                # 获取当前符合条件的代币
                tokens = self._fetch_qualified_tokens()

                if tokens:
                    self.logger.info(f"📊 本轮获取到 {len(tokens)} 个符合条件的代币")

                    # 更新快照：将当前快照移动到previous，创建新的current
                    with self.snapshot_lock:
                        self.previous_snapshots = self.current_snapshots.copy()
                        self.current_snapshots = {}

                        # 创建当前快照
                        current_time = datetime.now()
                        for token in tokens:
                            snapshot = self._create_token_snapshot(token, current_time)
                            if snapshot:
                                self.current_snapshots[snapshot.contract_address] = snapshot

                    # 检查价格变动
                    alerts = self._check_price_changes()

                    # 处理警报
                    for alert in alerts:
                        self._process_alert(alert)
                else:
                    self.logger.info("📊 本轮未获取到符合条件的代币")
                    # 清空快照
                    with self.snapshot_lock:
                        self.previous_snapshots = self.current_snapshots.copy()
                        self.current_snapshots = {}

                # 等待下一轮
                if self.is_running:
                    time.sleep(self.snapshot_interval)

            except Exception as e:
                self.logger.error(f"❌ 监控循环出错: {str(e)}")
                time.sleep(60)  # 出错后等待更长时间

    def _fetch_qualified_tokens(self) -> List[Any]:
        """获取符合条件的代币

        筛选条件:
        - 市值: 10k-30k
        - 1小时成交量: >1k
        - 年龄: >720分钟 (12小时)
        """
        try:
            # 使用Jupiter爬虫获取热门代币
            # 使用1H预设，这是专门为GAKE功能配置的预设
            tokens = self.jupiter_crawler.crawl_with_preset("1H")

            qualified_tokens = []
            current_time = datetime.now()

            for token in tokens:
                # 检查代币年龄
                if token.created_at:
                    # 确保时区一致性
                    if token.created_at.tzinfo is None:
                        # 如果token.created_at是naive，假设它是UTC
                        token_created_at = token.created_at
                    else:
                        # 如果token.created_at是aware，转换为naive UTC
                        token_created_at = token.created_at.replace(tzinfo=None)

                    age_minutes = (current_time - token_created_at).total_seconds() / 60
                    if age_minutes < self.min_age_minutes:
                        continue

                # 检查市值范围
                market_cap = getattr(token, '_market_cap', 0)
                if market_cap < self.min_market_cap or market_cap > self.max_market_cap:
                    continue

                # 检查1小时成交量
                volume_1h = 0
                if hasattr(token, '_volume_data') and token._volume_data:
                    volume_1h = token._volume_data.get('1h', 0)

                if volume_1h < self.min_volume_1h:
                    continue

                qualified_tokens.append(token)

            self.logger.info(f"📊 筛选出 {len(qualified_tokens)} 个符合条件的代币 (总共 {len(tokens)} 个)")
            return qualified_tokens

        except Exception as e:
            self.logger.error(f"❌ 获取合格代币失败: {str(e)}")
            return []

    def _create_token_snapshot(self, token: Any, timestamp: datetime) -> Optional[TokenSnapshot]:
        """创建代币快照"""
        try:
            # 从Jupiter数据获取真实的价格、市值和成交量
            market_cap = getattr(token, '_market_cap', 0)
            price = getattr(token, '_price', 0)

            # 获取1小时成交量
            volume_1h = 0
            if hasattr(token, '_volume_data') and token._volume_data:
                volume_1h = token._volume_data.get('1h', 0)

            snapshot = TokenSnapshot(
                contract_address=token.contract_address,
                symbol=token.symbol,
                name=token.name,
                market_cap=float(market_cap),
                price=float(price),
                volume_1h=float(volume_1h),
                timestamp=timestamp
            )

            return snapshot

        except Exception as e:
            self.logger.error(f"❌ 创建快照失败 {token.contract_address}: {str(e)}")
            return None

    # 已删除旧的 _store_snapshot 方法，现在直接在监控循环中管理快照

    def _check_price_changes(self) -> List[GakeAlert]:
        """检查价格变动 - 只比较当前和上一次的快照"""
        alerts = []

        with self.snapshot_lock:
            # 只比较在两个快照中都存在的代币
            common_addresses = set(self.current_snapshots.keys()) & set(self.previous_snapshots.keys())
            compared_count = len(common_addresses)

            if compared_count == 0:
                self.logger.info("📈 没有可比较的代币（需要连续两轮数据）")
                return alerts

            for i, contract_address in enumerate(common_addresses, 1):
                current = self.current_snapshots[contract_address]
                previous = self.previous_snapshots[contract_address]

                # 计算涨幅
                if previous.price > 0:
                    price_increase = ((current.price - previous.price) / previous.price) * 100

                    # 记录每次比较的详细信息
                    self.logger.info(f"📊 价格比较 #{i}: {current.symbol}")
                    self.logger.info(f"   前次: ${previous.price:.8f} (市值: ${previous.market_cap:,.0f}) - {previous.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   当前: ${current.price:.8f} (市值: ${current.market_cap:,.0f}) - {current.timestamp.strftime('%H:%M:%S')}")
                    self.logger.info(f"   变化: {price_increase:+.2f}% {'🚨' if abs(price_increase) >= self.price_increase_threshold else '✅'}")

                    if price_increase >= self.price_increase_threshold:
                        self.logger.warning(f"🚨 {current.symbol} 价格暴涨 {price_increase:+.2f}%! 开始地址分析...")
                        # 发现涨幅超过阈值，进行地址分析
                        alert = self._analyze_suspicious_activity(current, price_increase)
                        if alert:
                            alerts.append(alert)
                else:
                    self.logger.warning(f"⚠️ {current.symbol} 前次价格为0，跳过比较")

            self.logger.info(f"📈 本轮比较了 {compared_count} 个代币的价格变化")

        return alerts

    def _analyze_suspicious_activity(self, token: TokenSnapshot, price_increase: float) -> Optional[GakeAlert]:
        """分析可疑活动"""
        try:
            self.logger.info(f"🔍 分析代币 {token.symbol} 的可疑活动 (涨幅: {price_increase:.2f}%)")

            # 获取最近100个交易地址 (去重后约35个唯一地址)
            trading_addresses = self.okx_crawler.get_token_trading_addresses(
                token.contract_address,
                limit=100
            )

            if not trading_addresses:
                self.logger.warning(f"⚠️ 无法获取 {token.symbol} 的交易地址")
                return None

            # 分析每个地址
            address_profiles = {}
            all_cabal_tokens = set()

            # 使用线程池并发分析地址
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_address = {
                    executor.submit(self._analyze_address_profile, addr): addr
                    for addr in trading_addresses
                }

                for future in as_completed(future_to_address):
                    address = future_to_address[future]
                    try:
                        profile = future.result()
                        if profile:
                            address_profiles[address] = profile
                            # 收集cabal代币
                            all_cabal_tokens.update(profile.cabal_tokens)

                    except Exception as e:
                        self.logger.error(f"❌ 分析地址 {address} 时出错: {str(e)}")

            # 先分析所有地址的共同代币
            common_tokens, token_address_count = self._find_common_tokens_with_count(
                address_profiles,
                min_addresses=3
            )

            # 然后判断可疑地址
            suspicious_addresses = []
            for address, profile in address_profiles.items():
                if profile.is_suspicious():
                    suspicious_addresses.append(address)

            # 检查是否有足够的可疑地址
            min_suspicious = self.suspicious_criteria.get('min_suspicious_addresses', 5)
            if len(suspicious_addresses) >= min_suspicious:

                # 取最多50个共同代币避免消息过长
                common_tokens = common_tokens[:50]

                # 统计P&L记录中有目标代币的地址数量
                addresses_with_target_pnl = 0
                for addr in suspicious_addresses:
                    if addr in address_profiles:
                        profile = address_profiles[addr]
                        if token.contract_address in profile.common_tokens:
                            addresses_with_target_pnl += 1

                alert = GakeAlert(
                    token=token,
                    price_increase=price_increase,
                    suspicious_addresses=suspicious_addresses,
                    common_tokens=common_tokens,
                    cabal_tokens=list(all_cabal_tokens),
                    analysis_time=datetime.now(),
                    token_address_count=token_address_count,
                    address_profiles=address_profiles
                )

                self.logger.info(f"🚨 发现可疑活动: {token.symbol}")
                self.logger.info(f"   📊 分析地址: {len(suspicious_addresses)}个可疑地址")
                self.logger.info(f"   📈 P&L记录含目标代币: {addresses_with_target_pnl}个地址")
                self.logger.info(f"   🔗 共同交易代币: {len(common_tokens)}个")
                self.logger.info(f"   💡 说明: P&L API获取历史交易记录，可能不包含最新交易")
                return alert
            else:
                self.logger.info(f"✅ {token.symbol} 未发现足够的可疑活动 (可疑地址: {len(suspicious_addresses)})")
                return None

        except Exception as e:
            self.logger.error(f"❌ 分析可疑活动失败: {str(e)}")
            return None

    def _analyze_address_profile(self, address: str) -> Optional[AddressProfile]:
        """分析地址档案"""
        try:
            # 使用AddressAnalyzer获取真实的地址交易历史
            profile_data = self.address_analyzer.analyze_address_trading_profile(address)

            if not profile_data:
                return None

            # 转换为AddressProfile对象
            profile = AddressProfile(
                address=address,
                transaction_count_7d=profile_data['transaction_count_7d'],
                transaction_count_30d=profile_data['transaction_count_30d'],
                common_tokens=profile_data['all_traded_tokens'],  # 所有交易过的代币
                cabal_tokens=profile_data['cabal_tokens']
            )

            return profile

        except Exception as e:
            self.logger.error(f"❌ 分析地址档案失败 {address}: {str(e)}")
            return None

    def _find_common_tokens_among_addresses(self, address_profiles: Dict[str, AddressProfile],
                                          min_addresses: int = 2) -> List[str]:
        """找出多个地址共同交易的代币

        Args:
            address_profiles: 地址档案字典
            min_addresses: 最少地址数量

        Returns:
            共同交易的代币列表
        """
        # 统计每个代币被交易的地址数量
        token_count = {}

        for address, profile in address_profiles.items():
            for token in profile.common_tokens:
                if token not in token_count:
                    token_count[token] = set()
                token_count[token].add(address)

        # 找出被至少min_addresses个地址交易的代币
        common_tokens = []
        for token, addresses in token_count.items():
            if len(addresses) >= min_addresses:
                common_tokens.append(token)

        # 按被交易的地址数量降序排列
        common_tokens.sort(key=lambda t: len(token_count[t]), reverse=True)

        return common_tokens

    def _find_common_tokens_with_count(self, address_profiles: Dict[str, AddressProfile],
                                     min_addresses: int = 2) -> Tuple[List[str], Dict[str, int]]:
        """找出多个地址共同交易的代币并返回交易地址数量

        Args:
            address_profiles: 地址档案字典
            min_addresses: 最少地址数量

        Returns:
            (共同交易的代币列表, {代币地址: 交易该代币的地址数量})
        """
        # 统计每个代币被交易的地址数量
        token_count = {}

        for address, profile in address_profiles.items():
            for token in profile.common_tokens:
                if token not in token_count:
                    token_count[token] = set()
                token_count[token].add(address)

        # 找出被至少min_addresses个地址交易的代币
        common_tokens = []
        token_address_count = {}

        for token, addresses in token_count.items():
            if len(addresses) >= min_addresses:
                common_tokens.append(token)
                token_address_count[token] = len(addresses)

        # 按被交易的地址数量降序排列
        common_tokens.sort(key=lambda t: len(token_count[t]), reverse=True)

        return common_tokens, token_address_count

    def _get_token_symbols(self, token_addresses: List[str]) -> Dict[str, str]:
        """获取代币地址对应的symbol

        Args:
            token_addresses: 代币地址列表

        Returns:
            {代币地址: symbol} 的字典
        """
        try:
            if not token_addresses:
                return {}

            # 使用Jupiter爬虫获取代币信息
            tokens = self.jupiter_token_crawler.get_token_info(token_addresses)

            symbol_map = {}
            for token in tokens:
                symbol_map[token.contract_address] = token.symbol

            # 对于未找到的代币，使用默认处理
            for addr in token_addresses:
                if addr not in symbol_map:
                    if addr == 'So11111111111111111111111111111111111111112':
                        symbol_map[addr] = 'SOL'
                    elif addr == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                        symbol_map[addr] = 'USDC'
                    else:
                        symbol_map[addr] = addr[:8] + '...'

            return symbol_map

        except Exception as e:
            self.logger.error(f"❌ 获取代币symbol失败: {str(e)}")
            # 返回默认处理
            symbol_map = {}
            for addr in token_addresses:
                if addr == 'So11111111111111111111111111111111111111112':
                    symbol_map[addr] = 'SOL'
                elif addr == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                    symbol_map[addr] = 'USDC'
                else:
                    symbol_map[addr] = addr[:8] + '...'
            return symbol_map

    def _process_alert(self, alert: GakeAlert):
        """处理警报"""
        self.logger.info(f"🚨 处理警报: {alert.token.symbol}")

        # 调用回调函数
        if self.callback:
            try:
                self.callback(alert)
            except Exception as e:
                self.logger.error(f"❌ 调用警报回调失败: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        with self.snapshot_lock:
            current_tokens = len(self.current_snapshots)
            previous_tokens = len(self.previous_snapshots)

        return {
            'is_running': self.is_running,
            'current_tokens': current_tokens,
            'previous_tokens': previous_tokens,
            'snapshot_interval': self.snapshot_interval,
            'price_threshold': self.price_increase_threshold
        }


def test_gake_monitor():
    """测试Gake监控器"""
    print("🧪 测试Gake监控器...")

    def alert_callback(alert: GakeAlert):
        print("🚨 收到警报:")
        print(alert.format_message())

    monitor = GakeTokenMonitor()

    print("📊 开始监控...")
    monitor.start_monitoring(callback=alert_callback)

    try:
        # 运行5分钟进行测试
        time.sleep(300)
    except KeyboardInterrupt:
        print("\n⏸️ 用户中断测试")
    finally:
        monitor.stop_monitoring()
        print("✅ 测试完成")


if __name__ == "__main__":
    test_gake_monitor()