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
from crawlers.okxdex.tokenTradingHistory import OKXTokenTradingHistoryCrawler
from functions.addressAnalysis import AddressAnalyzer
from functions.logger import get_logger


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

    def format_message(self) -> str:
        """格式化为Telegram消息"""
        price_percent = f"{self.price_increase:.2f}%"

        # GMGN链接
        token_url = f"https://gmgn.ai/sol/token/{self.token.contract_address}"

        message = f"""🚨 **GAKE警报** 🚨

🪙 代币: [{self.token.symbol}]({token_url})
📈 涨幅: **{price_percent}**
💰 市值: ${self.token.market_cap:,.0f}
⏰ 时间: {self.analysis_time.strftime('%H:%M:%S')}

🔍 **可疑地址** ({len(self.suspicious_addresses)}个):
"""

        # 添加可疑地址链接（最多显示10个）
        for i, addr in enumerate(self.suspicious_addresses[:10]):
            addr_url = f"https://gmgn.ai/sol/address/{addr}"
            message += f"[{addr[:8]}...]({addr_url})\n"

        if len(self.suspicious_addresses) > 10:
            message += f"...还有{len(self.suspicious_addresses) - 10}个地址\n"

        # 添加共同代币
        if self.common_tokens:
            message += f"\n🔗 **共同交易代币** ({len(self.common_tokens)}个):\n"
            for i, token_addr in enumerate(self.common_tokens[:5]):
                token_url = f"https://gmgn.ai/sol/token/{token_addr}"
                message += f"[{token_addr[:8]}...]({token_url})\n"

            if len(self.common_tokens) > 5:
                message += f"...还有{len(self.common_tokens) - 5}个代币\n"

        # 添加cabal代币
        if self.cabal_tokens:
            message += f"\n⚠️ **Cabal代币** ({len(self.cabal_tokens)}个):\n"
            for token_addr in self.cabal_tokens:
                token_url = f"https://gmgn.ai/sol/token/{token_addr}"
                message += f"[{token_addr[:8]}...]({token_url})\n"

        return message


class GakeTokenMonitor:
    """Gake代币监控器"""

    def __init__(self):
        self.logger = get_logger("GakeTokenMonitor")
        self.jupiter_crawler = JupiterTopTradedCrawler()
        self.okx_crawler = OKXTokenTradingHistoryCrawler(performance_mode='high_speed')
        self.address_analyzer = AddressAnalyzer(performance_mode='high_speed')

        # 设置OKX认证信息
        self._setup_okx_auth()

        # 监控状态
        self.is_running = False
        self.monitor_thread = None

        # 快照存储
        self.snapshots: Dict[str, List[TokenSnapshot]] = {}  # contract_address -> [snapshots]
        self.snapshot_lock = threading.Lock()

        # 监控配置
        self.min_market_cap = 10000  # 10k
        self.max_market_cap = 30000  # 30k
        self.min_volume_1h = 1000    # 1k
        self.min_age_minutes = 720   # 12小时 = 720分钟
        self.price_increase_threshold = 20.0  # 20%涨幅
        self.snapshot_interval = 30  # 30秒间隔

        # cabal代币列表 (示例，需要根据实际情况配置)
        self.cabal_tokens = set([
            # 这里需要添加已知的cabal代币地址
            "So11111111111111111111111111111111111111112",  # SOL (示例)
        ])

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

                    # 创建快照
                    current_time = datetime.now()
                    for token in tokens:
                        snapshot = self._create_token_snapshot(token, current_time)
                        if snapshot:
                            self._store_snapshot(snapshot)

                    # 检查价格变动
                    alerts = self._check_price_changes()

                    # 处理警报
                    for alert in alerts:
                        self._process_alert(alert)
                else:
                    self.logger.info("📊 本轮未获取到符合条件的代币")

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

    def _store_snapshot(self, snapshot: TokenSnapshot):
        """存储快照"""
        with self.snapshot_lock:
            if snapshot.contract_address not in self.snapshots:
                self.snapshots[snapshot.contract_address] = []

            # 添加新快照
            self.snapshots[snapshot.contract_address].append(snapshot)

            # 只保留最近的快照（比如最近10个）
            if len(self.snapshots[snapshot.contract_address]) > 10:
                self.snapshots[snapshot.contract_address] = \
                    self.snapshots[snapshot.contract_address][-10:]

    def _check_price_changes(self) -> List[GakeAlert]:
        """检查价格变动"""
        alerts = []

        with self.snapshot_lock:
            for contract_address, snapshots in self.snapshots.items():
                if len(snapshots) < 2:
                    continue  # 需要至少2个快照才能比较

                # 获取最新和前一个快照
                latest = snapshots[-1]
                previous = snapshots[-2]

                # 计算涨幅
                if previous.price > 0:
                    price_increase = ((latest.price - previous.price) / previous.price) * 100

                    if price_increase >= self.price_increase_threshold:
                        # 发现涨幅超过阈值，进行地址分析
                        alert = self._analyze_suspicious_activity(latest, price_increase)
                        if alert:
                            alerts.append(alert)

        return alerts

    def _analyze_suspicious_activity(self, token: TokenSnapshot, price_increase: float) -> Optional[GakeAlert]:
        """分析可疑活动"""
        try:
            self.logger.info(f"🔍 分析代币 {token.symbol} 的可疑活动 (涨幅: {price_increase:.2f}%)")

            # 获取最近20个交易地址
            trading_addresses = self.okx_crawler.get_token_trading_addresses(
                token.contract_address,
                limit=20
            )

            if not trading_addresses:
                self.logger.warning(f"⚠️ 无法获取 {token.symbol} 的交易地址")
                return None

            # 分析每个地址
            address_profiles = {}
            suspicious_addresses = []
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

                            if profile.is_suspicious():
                                suspicious_addresses.append(address)

                            # 收集cabal代币
                            all_cabal_tokens.update(profile.cabal_tokens)

                    except Exception as e:
                        self.logger.error(f"❌ 分析地址 {address} 时出错: {str(e)}")

            # 检查是否有足够的可疑地址
            if len(suspicious_addresses) >= 2:  # 至少2个可疑地址
                # 分析共同代币（仅分析可疑地址的共同代币）
                common_tokens = self._find_common_tokens_among_addresses(
                    {addr: address_profiles[addr] for addr in suspicious_addresses if addr in address_profiles},
                    min_addresses=2
                )

                # 取最多50个共同代币避免消息过长
                common_tokens = common_tokens[:50]

                alert = GakeAlert(
                    token=token,
                    price_increase=price_increase,
                    suspicious_addresses=suspicious_addresses,
                    common_tokens=common_tokens,
                    cabal_tokens=list(all_cabal_tokens),
                    analysis_time=datetime.now()
                )

                self.logger.info(f"🚨 发现可疑活动: {token.symbol}, {len(suspicious_addresses)}个可疑地址, {len(common_tokens)}个共同代币")
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
            monitored_tokens = len(self.snapshots)
            total_snapshots = sum(len(snaps) for snaps in self.snapshots.values())

        return {
            'is_running': self.is_running,
            'monitored_tokens': monitored_tokens,
            'total_snapshots': total_snapshots,
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