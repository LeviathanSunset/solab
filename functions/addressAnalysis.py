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
from crawlers.okxdex.addressTokenList import OKXAddressTokenListCrawler
from functions.logger import get_logger
from settings.config_manager import ConfigManager

# 创建全局配置管理器实例
_config_manager = ConfigManager()

def get_cabal_tokens():
    # 需要实现这个方法
    if not _config_manager._config:
        return ["So11111111111111111111111111111111111111112"]  # 默认SOL
    return _config_manager._config.get('cabal_tokens', {}).get('addresses', [
        "So11111111111111111111111111111111111111112"
    ])

def get_suspicious_criteria():
    # 需要实现这个方法
    if not _config_manager._config:
        return {
            'max_tx_count_7d': 50,
            'max_tx_count_30d': 50,
            'min_suspicious_addresses': 2
        }
    return _config_manager._config.get('cabal_tokens', {}).get('suspicious_criteria', {
        'max_tx_count_7d': 50,
        'max_tx_count_30d': 50,
        'min_suspicious_addresses': 2
    })


class AddressAnalyzer:
    """地址交易历史分析器"""

    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化分析器

        Args:
            performance_mode: 性能模式
        """
        self.logger = get_logger("AddressAnalyzer")
        self.okx_transaction_crawler = OKXTransactionCrawler()
        self.okx_token_list_crawler = OKXAddressTokenListCrawler(performance_mode=performance_mode)

        # 从配置文件加载cabal代币列表
        self.cabal_tokens = set(get_cabal_tokens())

        # 从配置文件加载可疑地址判断标准
        self.suspicious_criteria = get_suspicious_criteria()

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

            # 获取地址交易过的代币详细信息
            self.logger.info(f"🔍 获取地址 {address[:8]}... 的历史交易代币")
            token_details = self.okx_token_list_crawler.get_address_token_details(address, limit=100)

            # 提取代币合约地址和创建代币信息映射
            all_traded_tokens = []
            token_info_map = {}

            for token in token_details:
                contract_addr = token.get('contract_address')
                if contract_addr:
                    all_traded_tokens.append(contract_addr)
                    token_info_map[contract_addr] = {
                        'symbol': token.get('symbol', contract_addr[:8] + '...'),
                        'name': token.get('name', 'Unknown'),
                        'decimals': token.get('decimals', 0),
                        'is_verified': token.get('is_verified', False)
                    }

            # 检查cabal代币
            cabal_tokens_found = []
            if all_traded_tokens:
                for token in all_traded_tokens:
                    if token in self.cabal_tokens:
                        cabal_tokens_found.append(token)

                self.logger.info(f"✅ 地址 {address[:8]}... 交易过 {len(all_traded_tokens)} 个代币，发现 {len(cabal_tokens_found)} 个cabal代币")

            profile = {
                'address': address,
                'transaction_count_7d': tx_count_7d,
                'transaction_count_30d': tx_count_30d,
                'traded_tokens_7d': all_traded_tokens,  # 使用获取到的代币列表
                'traded_tokens_30d': all_traded_tokens,  # 使用获取到的代币列表
                'all_traded_tokens': all_traded_tokens,
                'token_info_map': token_info_map,  # 添加代币信息映射
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

        # 先批量获取所有地址的代币详细信息（提高效率）
        self.logger.info(f"🔍 批量获取 {len(addresses)} 个地址的历史交易代币...")
        # 使用ThreadPoolExecutor来批量获取代币详细信息
        from concurrent.futures import ThreadPoolExecutor, as_completed

        address_token_details = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_address = {
                executor.submit(self.okx_token_list_crawler.get_address_token_details, addr, 100): addr
                for addr in addresses
            }

            for future in as_completed(future_to_address):
                address = future_to_address[future]
                try:
                    token_details = future.result()
                    address_token_details[address] = token_details
                except Exception as exc:
                    self.logger.error(f"❌ 获取地址 {address[:8]}... 代币详情失败: {exc}")
                    address_token_details[address] = []

        for i, address in enumerate(addresses):
            try:
                self.logger.info(f"🔍 分析地址 {i+1}/{len(addresses)}: {address[:8]}...")

                # 获取7天交易数据 (period=3)
                tx_data_7d = self.okx_transaction_crawler.get_transaction_data(address, period=3)

                # 获取30天交易数据 (period=4)
                tx_data_30d = self.okx_transaction_crawler.get_transaction_data(address, period=4)

                # 提取交易次数
                tx_count_7d = tx_data_7d.total_trades if tx_data_7d else 0
                tx_count_30d = tx_data_30d.total_trades if tx_data_30d else 0

                # 使用已获取的代币详细信息
                token_details = address_token_details.get(address, [])

                # 提取代币合约地址和创建代币信息映射
                all_traded_tokens = []
                token_info_map = {}

                for token in token_details:
                    contract_addr = token.get('contract_address')
                    if contract_addr:
                        all_traded_tokens.append(contract_addr)
                        token_info_map[contract_addr] = {
                            'symbol': token.get('symbol', contract_addr[:8] + '...'),
                            'name': token.get('name', 'Unknown'),
                            'decimals': token.get('decimals', 0),
                            'is_verified': token.get('is_verified', False)
                        }

                # 检查cabal代币
                cabal_tokens_found = []
                if all_traded_tokens:
                    for token in all_traded_tokens:
                        if token in self.cabal_tokens:
                            cabal_tokens_found.append(token)

                profile = {
                    'address': address,
                    'transaction_count_7d': tx_count_7d,
                    'transaction_count_30d': tx_count_30d,
                    'traded_tokens_7d': all_traded_tokens,
                    'traded_tokens_30d': all_traded_tokens,
                    'all_traded_tokens': all_traded_tokens,
                    'token_info_map': token_info_map,  # 添加代币信息映射
                    'cabal_tokens': cabal_tokens_found,
                    'analysis_timestamp': datetime.now().isoformat()
                }

                results[address] = profile

                if profile:
                    tx_7d = profile['transaction_count_7d']
                    tx_30d = profile['transaction_count_30d']
                    token_count = len(all_traded_tokens)
                    cabal_count = len(cabal_tokens_found)
                    self.logger.info(f"✅ {address[:8]}...: 7d={tx_7d}, 30d={tx_30d}, 代币={token_count}, cabal={cabal_count}")
                else:
                    self.logger.warning(f"❌ {address[:8]}...: 分析失败")

                # 添加延迟避免请求过频
                if i < len(addresses) - 1:
                    time.sleep(0.5)

            except Exception as e:
                self.logger.error(f"❌ 处理地址 {address} 时出错: {str(e)}")
                results[address] = None

        self.logger.info(f"📊 批量分析完成，成功: {sum(1 for r in results.values() if r is not None)}/{len(addresses)}")
        return results

    def find_suspicious_addresses(self, address_profiles: Dict[str, Dict[str, Any]],
                                max_tx_count_7d: int = None,
                                max_tx_count_30d: int = None) -> List[str]:
        """找出可疑地址（交易次数较少的地址）

        Args:
            address_profiles: 地址档案字典
            max_tx_count_7d: 7天最大交易次数阈值（None时使用配置文件）
            max_tx_count_30d: 30天最大交易次数阈值（None时使用配置文件）

        Returns:
            可疑地址列表
        """
        # 使用配置文件中的阈值（如果参数未提供）
        if max_tx_count_7d is None:
            max_tx_count_7d = self.suspicious_criteria.get('max_tx_count_7d', 50)
        if max_tx_count_30d is None:
            max_tx_count_30d = self.suspicious_criteria.get('max_tx_count_30d', 50)

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

    def format_rape_alert_message(self, summary: Dict[str, Any],
                                 address_profiles: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """生成/rape风格的简洁警报消息

        Args:
            summary: 分析摘要
            address_profiles: 地址档案字典

        Returns:
            格式化的警报消息，如果不满足条件则返回None
        """
        # 只有当≥3个可疑地址且有共同代币时才生成特殊警报
        if (len(summary['suspicious_addresses']) < 3 or
            len(summary['common_tokens']) == 0):
            return None

        suspicious_count = len(summary['suspicious_addresses'])
        common_tokens_count = len(summary['common_tokens'])

        message = f"🔥 [地址群体]异动交易者\n"
        message += f"🔢 共同交易代币种类: {common_tokens_count}\n"
        message += f"───────────────────────────────────\n"

        # 添加共同代币信息 - 计算每个代币被多少人交易
        for i, token_addr in enumerate(summary['common_tokens'][:8]):
            # 计算交易这个代币的地址数量
            addr_count = 0
            token_symbol = token_addr[:8] + '...'  # 默认显示地址

            for addr in summary['suspicious_addresses']:
                if addr in address_profiles:
                    profile = address_profiles[addr]
                    if token_addr in profile.get('all_traded_tokens', []):
                        addr_count += 1

                    # 尝试获取代币的symbol
                    token_info_map = profile.get('token_info_map', {})
                    if token_addr in token_info_map:
                        token_symbol = token_info_map[token_addr].get('symbol', token_addr[:8] + '...')

            token_url = f"https://gmgn.ai/sol/token/{token_addr}"
            message += f" {i+1}. {token_symbol} ({token_url}) ({addr_count}人)\n"


        message += f"\n📊 [地址群体] 分析统计\n"
        message += f"🕒 分析时间: {summary['analysis_timestamp'][:10]}\n"
        message += f"👥 分析地址: 最近{suspicious_count} 个\n"

        return message

    def get_rape_inline_keyboard(self, summary: Dict[str, Any]) -> List[List[Dict[str, str]]]:
        """生成/rape风格的Telegram内联键盘按钮"""
        if (len(summary['suspicious_addresses']) < 3 or
            len(summary['common_tokens']) == 0):
            return []

        keyboard = []

        # 为前4个代币创建按钮
        for i, token_addr in enumerate(summary['common_tokens'][:4]):
            button_text = f"代币{i+1}: {token_addr[:8]}..."
            callback_data = f"token_details_{token_addr}"
            keyboard.append([{
                "text": button_text,
                "callback_data": callback_data
            }])

        # 添加查看所有低频交易者按钮
        keyboard.append([{
            "text": "🔍 查看所有低频交易者",
            "callback_data": f"low_freq_traders_group_{len(summary['suspicious_addresses'])}"
        }])

        return keyboard


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