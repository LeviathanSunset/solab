"""
OKX交易数据爬虫 - 简化版本
只获取特定周期的买入和卖出交易数据
"""

import requests
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json


@dataclass
class TransactionData:
    """交易数据模型 - 简化版本，只关注买卖交易数量"""
    # 基础信息
    address: str
    chain_id: int
    period: int
    
    # 核心交易数据
    buy_trades: int = 0      # 买入交易数
    sell_trades: int = 0     # 卖出交易数
    total_trades: int = 0    # 总交易数
    
    def __post_init__(self):
        """计算总交易数"""
        self.total_trades = self.buy_trades + self.sell_trades


class OKXTransactionCrawler:
    """OKX交易数据爬虫 - 简化版本"""
    
    def __init__(self):
        self.base_url = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/wallet-profile/summary"
        self.headers = {
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-CH-UA': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }
    
    def get_transaction_data(self, address: str, period: int = 4, chain_id: int = 501) -> Optional[TransactionData]:
        """
        获取地址的交易数据
        
        Args:
            address: 钱包地址
            period: 时间周期 (1=1D, 2=3D, 3=7D, 4=1M, 5=3M)
            chain_id: 链ID (501=Solana)
            
        Returns:
            TransactionData对象或None
        """
        try:
            params = {
                'walletAddress': address,
                'chainId': chain_id,
                'periodType': period
            }
            
            response = requests.get(self.base_url, params=params, headers=self.headers)
            
            if response.status_code != 200:
                print(f"请求失败: {response.status_code}")
                return None
            
            data = response.json()
            
            if data.get('code') != 0:
                print(f"API错误: {data.get('msg', 'Unknown error')}")
                return None
            
            result_data = data.get('data', {})
            
            # 提取交易数据
            transaction_data = TransactionData(
                address=address,
                chain_id=chain_id,
                period=period,
                buy_trades=result_data.get('totalTxsBuy', 0),
                sell_trades=result_data.get('totalTxsSell', 0)
            )
            
            return transaction_data
            
        except Exception as e:
            print(f"获取交易数据时出错: {e}")
            return None
    
    def get_multiple_addresses_data(self, addresses: list, period: int = 4, chain_id: int = 501) -> Dict[str, TransactionData]:
        """
        批量获取多个地址的交易数据
        
        Args:
            addresses: 地址列表
            period: 时间周期
            chain_id: 链ID
            
        Returns:
            地址到TransactionData的映射
        """
        results = {}
        
        for i, address in enumerate(addresses):
            print(f"正在获取地址 {i+1}/{len(addresses)}: {address[:10]}...")
            
            data = self.get_transaction_data(address, period, chain_id)
            if data:
                results[address] = data
            
            # 添加延迟避免请求过频
            if i < len(addresses) - 1:
                time.sleep(1)
        
        return results


def format_transaction_summary(data: TransactionData) -> str:
    """格式化交易数据摘要"""
    return f"""
=== 交易数据摘要 ===
地址: {data.address[:10]}...
周期: {data.period} (1=1D, 2=3D, 3=7D, 4=1M, 5=3M)
链ID: {data.chain_id}

买入交易: {data.buy_trades}
卖出交易: {data.sell_trades}
总交易: {data.total_trades}
========================
"""


# 使用示例
if __name__ == "__main__":
    crawler = OKXTransactionCrawler()
    
    # 测试地址
    test_address = "BoqNjoXHgjJ6ET8wc47BRwYmPZnYXpCPePJC9nvLPTob"
    
    print("=== OKX交易数据爬虫 - 简化版本 ===")
    print(f"获取地址: {test_address}")
    
    # 获取90天数据
    data = crawler.get_transaction_data(test_address, period=4)
    
    if data:
        print(format_transaction_summary(data))
        
        # 输出JSON格式
        print("\n=== JSON格式 ===")
        print(json.dumps({
            'address': data.address,
            'chain_id': data.chain_id,
            'period': data.period,
            'buy_trades': data.buy_trades,
            'sell_trades': data.sell_trades,
            'total_trades': data.total_trades
        }, indent=2, ensure_ascii=False))
    else:
        print("获取数据失败")
