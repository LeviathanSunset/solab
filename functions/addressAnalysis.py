#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地址交易历史分析模块
分析地址的7天、30天交易次数，找出共同代币和cabal代币
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crawlers.okxdex.addressProfileTxs import OKXTransactionCrawler
from functions.logger import get_logger


class AddressAnalyzer:
    """地址交易历史分析器"""

    def __init__(self, performance_mode: str = 'balanced'):
        """初始化分析器

        Args:
            performance_mode: 性能模式
        """
        self.logger = get_logger("AddressAnalyzer")
        self.okx_transaction_crawler = OKXTransactionCrawler()

        # cabal代币列表（需要根据实际情况配置）
        self.cabal_tokens = {
            "So11111111111111111111111111111111111111112",  # SOL (WSOL)
            # 这里添加更多已知的cabal代币地址
        }

    def analyze_address_trading_profile(self, address: str) -> Optional[Dict[str, Any]]:
        """分析地址交易档案

        Args:
            address: 钱包地址

        Returns:
            地址交易档案信息
        """
        try:
            self.logger.info(f"🔍 分析地址交易档案: {address}")

            # 获取7天交易数据 (period=3)
            tx_data_7d = self.okx_transaction_crawler.get_transaction_data(address, period=3)  # 7天

            # 获取30天交易数据 (period=4)
            tx_data_30d = self.okx_transaction_crawler.get_transaction_data(address, period=4)  # 1个月

            # 提取交易次数
            tx_count_7d = tx_data_7d.total_trades if tx_data_7d else 0
            tx_count_30d = tx_data_30d.total_trades if tx_data_30d else 0

            # TODO: 从OKX获取交易过的代币列表（暂时简化）
            # 目前OKX的addressProfileTxs只返回交易次数，不返回具体代币列表
            # 可以考虑使用tokenTradingHistory来补充这部分信息
            all_traded_tokens = []
            cabal_tokens_found = []

            profile = {
                'address': address,
                'transaction_count_7d': tx_count_7d,
                'transaction_count_30d': tx_count_30d,
                'traded_tokens_7d': [],  # 暂时为空，需要其他API获取
                'traded_tokens_30d': [],  # 暂时为空，需要其他API获取
                'all_traded_tokens': all_traded_tokens,
                'cabal_tokens': cabal_tokens_found,
                'analysis_timestamp': datetime.now().isoformat()
            }

            self.logger.info(f"✅ 地址 {address} 分析完成: 7d={tx_count_7d}笔, 30d={tx_count_30d}笔")
            return profile

        except Exception as e:
            self.logger.error(f"❌ 分析地址交易档案失败 {address}: {str(e)}")
            return None


    def analyze_multiple_addresses(self, addresses: List[str],
                                 max_workers: int = 3) -> Dict[str, Optional[Dict[str, Any]]]:
        """批量分析多个地址

        Args:
            addresses: 地址列表
            max_workers: 最大并发数（暂时不用，OKX有频率限制）

        Returns:
            {地址: 分析结果} 字典
        """
        results = {}

        self.logger.info(f"📊 开始批量分析 {len(addresses)} 个地址")

        for i, address in enumerate(addresses):
            try:
                self.logger.info(f"🔍 分析地址 {i+1}/{len(addresses)}: {address[:8]}...")

                profile = self.analyze_address_trading_profile(address)
                results[address] = profile

                if profile:
                    tx_7d = profile['transaction_count_7d']
                    tx_30d = profile['transaction_count_30d']
                    self.logger.info(f"✅ {address[:8]}...: 7d={tx_7d}, 30d={tx_30d}")
                else:
                    self.logger.warning(f"❌ {address[:8]}...: 分析失败")

                # 添加延迟避免请求过频
                if i < len(addresses) - 1:
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"❌ 处理地址 {address} 时出错: {str(e)}")
                results[address] = None

        self.logger.info(f"📊 批量分析完成，成功: {sum(1 for r in results.values() if r is not None)}/{len(addresses)}")
        return results

    def find_suspicious_addresses(self, address_profiles: Dict[str, Dict[str, Any]],
                                max_tx_count_7d: int = 50,
                                max_tx_count_30d: int = 50) -> List[str]:
        """找出可疑地址（交易次数较少的地址）

        Args:
            address_profiles: 地址档案字典
            max_tx_count_7d: 7天最大交易次数阈值
            max_tx_count_30d: 30天最大交易次数阈值

        Returns:
            可疑地址列表
        """
        suspicious_addresses = []

        for address, profile in address_profiles.items():
            if not profile:
                continue

            tx_7d = profile['transaction_count_7d']
            tx_30d = profile['transaction_count_30d']

            # 如果7天或30天交易次数都小于阈值，认为可疑
            if tx_7d < max_tx_count_7d and tx_30d < max_tx_count_30d:
                suspicious_addresses.append(address)

        return suspicious_addresses

    def find_common_tokens(self, address_profiles: Dict[str, Dict[str, Any]],
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
            if not profile:
                continue

            for token in profile['all_traded_tokens']:
                if token not in token_count:
                    token_count[token] = set()
                token_count[token].add(address)

        # 找出被至少min_addresses个地址交易的代币
        common_tokens = []
        for token, addresses in token_count.items():
            if len(addresses) >= min_addresses:
                common_tokens.append(token)

        return common_tokens

    def find_cabal_tokens(self, address_profiles: Dict[str, Dict[str, Any]]) -> List[str]:
        """找出所有地址中包含的cabal代币

        Args:
            address_profiles: 地址档案字典

        Returns:
            cabal代币列表
        """
        all_cabal_tokens = set()

        for address, profile in address_profiles.items():
            if not profile:
                continue

            all_cabal_tokens.update(profile['cabal_tokens'])

        return list(all_cabal_tokens)

    def generate_analysis_summary(self, address_profiles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """生成分析摘要

        Args:
            address_profiles: 地址档案字典

        Returns:
            分析摘要
        """
        # 统计信息
        total_addresses = len(address_profiles)
        successful_analyses = sum(1 for p in address_profiles.values() if p is not None)

        # 找出可疑地址
        suspicious_addresses = self.find_suspicious_addresses(address_profiles)

        # 找出共同代币
        common_tokens = self.find_common_tokens(address_profiles)

        # 找出cabal代币
        cabal_tokens = self.find_cabal_tokens(address_profiles)

        # 计算可疑地址比例
        suspicious_ratio = len(suspicious_addresses) / successful_analyses if successful_analyses > 0 else 0

        summary = {
            'total_addresses': total_addresses,
            'successful_analyses': successful_analyses,
            'suspicious_addresses': suspicious_addresses,
            'suspicious_ratio': suspicious_ratio,
            'common_tokens': common_tokens,
            'cabal_tokens': cabal_tokens,
            'analysis_timestamp': datetime.now().isoformat()
        }

        return summary


def test_address_analyzer():
    """测试地址分析器"""
    print("🧪 测试地址分析器...")

    analyzer = AddressAnalyzer()

    # 测试地址列表（使用一些示例地址）
    test_addresses = [
        "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # 示例地址1
        "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",  # 示例地址2
    ]

    # 分析单个地址
    print(f"\n📊 测试单个地址分析...")
    profile = analyzer.analyze_address_trading_profile(test_addresses[0])
    if profile:
        print("✅ 单个地址分析结果:")
        for key, value in profile.items():
            if isinstance(value, list) and len(value) > 5:
                print(f"   {key}: {len(value)} 项 (前5个: {value[:5]})")
            else:
                print(f"   {key}: {value}")

    # 批量分析地址
    print(f"\n📊 测试批量地址分析...")
    batch_results = analyzer.analyze_multiple_addresses(test_addresses)

    if batch_results:
        print("✅ 批量分析结果:")
        for addr, profile in batch_results.items():
            if profile:
                tx_7d = profile['transaction_count_7d']
                tx_30d = profile['transaction_count_30d']
                print(f"   {addr[:8]}...: 7d={tx_7d}, 30d={tx_30d}")

        # 生成分析摘要
        summary = analyzer.generate_analysis_summary(batch_results)
        print(f"\n📋 分析摘要:")
        print(f"   总地址数: {summary['total_addresses']}")
        print(f"   成功分析: {summary['successful_analyses']}")
        print(f"   可疑地址: {len(summary['suspicious_addresses'])} ({summary['suspicious_ratio']:.2%})")
        print(f"   共同代币: {len(summary['common_tokens'])} 个")
        print(f"   Cabal代币: {len(summary['cabal_tokens'])} 个")

    print("✅ 测试完成")


if __name__ == "__main__":
    test_address_analyzer()