#!/usr/bin/env python3
"""
OKX 地址画像分析爬虫 (OKXAddressProfileCrawler)
============================================

功能: 获取地址的交易行为画像和统计数据
API: https://web3.okx.com/priapi/v1/dx/market/v2/pnl/address-overview
用途: 分析地址的交易活跃度、盈亏情况、风险等级

主要方法:
- get_address_profile(): 获取地址完整画像
- batch_get_profiles(): 批量获取多个地址画像
- 支持高并发处理和性能优化

返回数据:
- totalTradeCount: 总交易次数
- tradeCount7d/30d: 7天/30天交易次数
- totalPnl: 总盈亏
- winRate: 胜率
- avgHoldingTime: 平均持仓时间
- 风险等级评估

适用场景: GAKE系统中识别可疑地址，分析交易频率
- AddressProfile: 钱包地址完整资料模型
- DailyPnl: 每日盈亏数据
- TopToken: 表现最佳代币信息

Author: SoLab Team
Created: 2024
Last Modified: 2025-09-18
"""
import requests
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DailyPnl:
    """
    每日盈亏数据模型
    =============
    
    存储特定日期的盈亏信息，用于分析钱包的日常交易表现
    
    属性说明:
    - profit: 当日盈亏金额(字符串格式，保持精度)
    - timestamp: Unix时间戳(毫秒)
    - date: 自动转换的datetime对象，便于处理
    
    使用场景:
    - 绘制盈亏趋势图
    - 分析交易频率和表现
    - 计算连续盈利/亏损天数
    """
    profit: str
    timestamp: int
    date: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化后处理：将时间戳转换为可读的datetime对象"""
        if self.timestamp:
            self.date = datetime.fromtimestamp(self.timestamp / 1000)


@dataclass
class TopToken:
    """表现最佳代币"""
    token_address: str
    token_symbol: str
    token_name: str
    token_logo: str
    pnl: str
    roi: str
    inner_goto_url: str


@dataclass
class AddressProfile:
    """地址资料模型 - 基于真实API返回数据"""
    wallet_address: str
    chain_id: int
    period_type: int
    
    # 基础交易数据
    total_pnl: str = "0"                    # 总盈亏
    total_pnl_roi: str = "0"                # 总盈亏ROI
    total_profit_pnl: str = "0"             # 总盈利
    total_profit_pnl_roi: str = "0"         # 总盈利ROI
    unrealized_pnl: str = "0"               # 未实现盈亏
    unrealized_pnl_roi: str = "0"           # 未实现盈亏ROI
    
    # 交易统计
    total_txs_buy: int = 0                  # 买入交易数
    total_txs_sell: int = 0                 # 卖出交易数
    total_volume_buy: str = "0"             # 买入总量
    total_volume_sell: str = "0"            # 卖出总量
    total_win_rate: str = "0"               # 总胜率
    avg_cost_buy: str = "0"                 # 平均买入成本
    
    # 原生代币余额
    native_token_balance_amount: str = "0"   # 原生代币数量(SOL)
    native_token_balance_usd: str = "0"      # 原生代币USD价值
    
    # 偏好和分布数据
    favorite_mcap_type: str = "0"           # 偏好市值类型
    mcap_txs_buy_list: List[int] = None     # 不同市值交易分布
    new_win_rate_distribution: List[int] = None  # 胜率分布
    win_rate_list: List[str] = None         # 胜率列表
    
    # 最佳表现代币
    top_tokens: List[TopToken] = None       # 表现最佳的代币
    top_tokens_total_pnl: str = "0"        # 最佳代币总盈亏
    top_tokens_total_roi: str = "0"        # 最佳代币总ROI
    
    # 日盈亏数据
    date_pnl_list: List[DailyPnl] = None   # 日盈亏列表
    
    # 元数据
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.mcap_txs_buy_list is None:
            self.mcap_txs_buy_list = []
        if self.new_win_rate_distribution is None:
            self.new_win_rate_distribution = []
        if self.win_rate_list is None:
            self.win_rate_list = []
        if self.top_tokens is None:
            self.top_tokens = []
        if self.date_pnl_list is None:
            self.date_pnl_list = []
        if self.created_at is None:
            self.created_at = datetime.now()
    
    @property
    def total_transactions(self) -> int:
        """总交易数"""
        return self.total_txs_buy + self.total_txs_sell
    
    @property
    def win_rate_percentage(self) -> float:
        """胜率百分比"""
        try:
            return float(self.total_win_rate)
        except:
            return 0.0
    
    @property
    def is_profitable(self) -> bool:
        """是否盈利"""
        try:
            return float(self.total_pnl) > 0
        except:
            return False
    
    @property
    def profit_factor(self) -> float:
        """盈利因子 (总盈利/总亏损)"""
        try:
            total_pnl_value = float(self.total_pnl)
            total_profit_value = float(self.total_profit_pnl)
            if total_profit_value > 0 and total_pnl_value < total_profit_value:
                total_loss = total_profit_value - total_pnl_value
                return total_profit_value / total_loss if total_loss > 0 else float('inf')
            return 0.0
        except:
            return 0.0


class OKXAddressInfoCrawler:
    """OKX地址信息爬虫"""
    
    def __init__(self):
        self.base_url = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/wallet-profile/summary"
        self.session = requests.Session()
        self._setup_headers()
    
    def _setup_headers(self):
        """设置请求头"""
        self.session.headers.update({
            'accept': 'application/json',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2',
            'app-type': 'web',
            'device-token': '01980a38-038a-44d9-8da3-a8276bbcb5b9',
            'devid': '01980a38-038a-44d9-8da3-a8276bbcb5b9',
            'platform': 'web',
            'referer': 'https://web3.okx.com/portfolio/',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'x-cdn': 'https://web3.okx.com',
            'x-locale': 'en_US',
            'x-simulated-trading': 'undefined',
            'x-utc': '0',
            'x-zkdex-env': '0'
        })
    
    def get_address_profile(self, wallet_address: str, period_type: int = 4, 
                          chain_id: int = 501) -> Optional[AddressProfile]:
        """
        获取地址基本信息
        
        Args:
            wallet_address: 钱包地址
            period_type: 时间周期类型 (1=1D, 2=3D, 3=7D, 4=1M)
            chain_id: 链ID (501=Solana)
        
        Returns:
            AddressProfile: 地址资料对象
        """
        try:
            # 构建请求参数
            params = {
                'periodType': period_type,
                'chainId': chain_id,
                'walletAddress': wallet_address,
                't': int(time.time() * 1000)  # 时间戳
            }
            
            # 更新referer
            self.session.headers['referer'] = f'https://web3.okx.com/portfolio/{wallet_address}/analysis?periodType={period_type}'
            
            # 发送请求
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            
            if data.get('code') == 0 and 'data' in data:
                return self._parse_profile_data(data['data'], wallet_address, chain_id, period_type)
            else:
                print(f"API返回错误: {data.get('msg', 'Unknown error')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None
    
    def _parse_profile_data(self, data: Dict[str, Any], wallet_address: str, 
                          chain_id: int, period_type: int) -> AddressProfile:
        """解析API返回的数据"""
        
        # 解析日盈亏数据
        date_pnl_list = []
        for pnl_item in data.get('datePnlList', []):
            date_pnl_list.append(DailyPnl(
                profit=str(pnl_item.get('profit', '0')),
                timestamp=int(pnl_item.get('timestamp', 0))
            ))
        
        # 解析最佳表现代币
        top_tokens = []
        for token_item in data.get('topTokens', []):
            top_tokens.append(TopToken(
                token_address=token_item.get('tokenAddress', ''),
                token_symbol=token_item.get('tokenSymbol', ''),
                token_name=token_item.get('tokenName', ''),
                token_logo=token_item.get('tokenLogo', ''),
                pnl=str(token_item.get('pnl', '0')),
                roi=str(token_item.get('roi', '0')),
                inner_goto_url=token_item.get('innerGotoUrl', '')
            ))
        
        return AddressProfile(
            wallet_address=wallet_address,
            chain_id=chain_id,
            period_type=period_type,
            
            # 基础交易数据
            total_pnl=str(data.get('totalPnl', '0')),
            total_pnl_roi=str(data.get('totalPnlRoi', '0')),
            total_profit_pnl=str(data.get('totalProfitPnl', '0')),
            total_profit_pnl_roi=str(data.get('totalProfitPnlRoi', '0')),
            unrealized_pnl=str(data.get('unrealizedPnl', '0')),
            unrealized_pnl_roi=str(data.get('unrealizedPnlRoi', '0')),
            
            # 交易统计
            total_txs_buy=int(data.get('totalTxsBuy', 0)),
            total_txs_sell=int(data.get('totalTxsSell', 0)),
            total_volume_buy=str(data.get('totalVolumeBuy', '0')),
            total_volume_sell=str(data.get('totalVolumeSell', '0')),
            total_win_rate=str(data.get('totalWinRate', '0')),
            avg_cost_buy=str(data.get('avgCostBuy', '0')),
            
            # 原生代币余额
            native_token_balance_amount=str(data.get('nativeTokenBalanceAmount', '0')),
            native_token_balance_usd=str(data.get('nativeTokenBalanceUsd', '0')),
            
            # 偏好和分布数据
            favorite_mcap_type=str(data.get('favoriteMcapType', '0')),
            mcap_txs_buy_list=data.get('mcapTxsBuyList', []),
            new_win_rate_distribution=data.get('newWinRateDistribution', []),
            win_rate_list=data.get('winRateList', []),
            
            # 最佳表现代币
            top_tokens=top_tokens,
            top_tokens_total_pnl=str(data.get('topTokensTotalPnl', '0')),
            top_tokens_total_roi=str(data.get('topTokensTotalRoi', '0')),
            
            # 日盈亏数据
            date_pnl_list=date_pnl_list,
            
            created_at=datetime.now()
        )
    
    def batch_get_profiles(self, wallet_addresses: list, period_type: int = 4, 
                          chain_id: int = 501, delay: float = 1.0) -> Dict[str, AddressProfile]:
        """
        批量获取地址信息
        
        Args:
            wallet_addresses: 钱包地址列表
            period_type: 时间周期类型
            chain_id: 链ID
            delay: 请求间隔（秒）
        
        Returns:
            Dict[str, AddressProfile]: 地址 -> 资料的映射
        """
        results = {}
        
        for i, address in enumerate(wallet_addresses):
            print(f"正在获取地址 {i+1}/{len(wallet_addresses)}: {address[:20]}...")
            
            profile = self.get_address_profile(address, period_type, chain_id)
            if profile:
                results[address] = profile
                print(f"✓ 成功获取地址信息")
            else:
                print(f"✗ 获取失败")
            
            # 避免请求过于频繁
            if i < len(wallet_addresses) - 1:
                time.sleep(delay)
        
        return results
    
    def save_to_json(self, profiles: Dict[str, AddressProfile], filename: str):
        """保存结果到JSON文件"""
        data = {}
        for address, profile in profiles.items():
            data[address] = {
                'wallet_address': profile.wallet_address,
                'chain_id': profile.chain_id,
                'period_type': profile.period_type,
                'total_pnl': profile.total_pnl,
                'total_pnl_usd': profile.total_pnl_usd,
                'win_rate': profile.win_rate,
                'total_trades': profile.total_trades,
                'avg_hold_time': profile.avg_hold_time,
                'largest_profit': profile.largest_profit,
                'largest_loss': profile.largest_loss,
                'created_at': profile.created_at.isoformat() if profile.created_at else None
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"结果已保存到: {filename}")


def main():
    """测试主函数"""
    crawler = OKXAddressInfoCrawler()
    
    # 测试地址列表
    test_addresses = [
        "BoqNjoXHgjJ6ET8wc47BRwYmPZnYXpCPePJC9nvLPTob",
        "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
    ]
    
    print("=== OKX地址信息爬虫测试 (新模型) ===\n")
    
    # 单个地址测试
    print("1. 详细地址分析:")
    test_address = test_addresses[0]
    profile = crawler.get_address_profile(test_address)
    
    if profile:
        print(f"地址: {profile.wallet_address}")
        print(f"链ID: {profile.chain_id} | 周期: {profile.period_type}")
        
        print(f"\n📊 交易概览:")
        print(f"   总盈亏: ${profile.total_pnl} (ROI: {profile.total_pnl_roi}%)")
        print(f"   盈利总额: ${profile.total_profit_pnl} (ROI: {profile.total_profit_pnl_roi}%)")
        print(f"   未实现盈亏: ${profile.unrealized_pnl} (ROI: {profile.unrealized_pnl_roi}%)")
        print(f"   胜率: {profile.total_win_rate}%")
        print(f"   盈利因子: {profile.profit_factor:.2f}")
        
        print(f"\n💰 交易活动:")
        print(f"   买入交易: {profile.total_txs_buy} 笔")
        print(f"   卖出交易: {profile.total_txs_sell} 笔")
        print(f"   总交易: {profile.total_transactions} 笔")
        print(f"   买入金额: ${profile.total_volume_buy}")
        print(f"   卖出金额: ${profile.total_volume_sell}")
        print(f"   平均成本: ${profile.avg_cost_buy}")
        
        print(f"\n🔗 原生代币 (SOL):")
        print(f"   余额: {profile.native_token_balance_amount} SOL")
        print(f"   价值: ${profile.native_token_balance_usd}")
        
        print(f"\n🏆 表现最佳代币 ({len(profile.top_tokens)} 个):")
        for i, token in enumerate(profile.top_tokens[:3], 1):  # 显示前3个
            print(f"   {i}. {token.token_symbol} ({token.token_name})")
            print(f"      PnL: ${token.pnl} | ROI: {token.roi}%")
        
        if profile.top_tokens:
            print(f"   最佳代币总PnL: ${profile.top_tokens_total_pnl} (ROI: {profile.top_tokens_total_roi}%)")
        
        print(f"\n📈 偏好分析:")
        print(f"   偏好市值类型: {profile.favorite_mcap_type}")
        print(f"   胜率分布: {profile.new_win_rate_distribution}")
        print(f"   历史胜率: {profile.win_rate_list}")
        
        print(f"\n📅 近期盈亏 (最近5天):")
        recent_pnl = profile.date_pnl_list[-5:] if profile.date_pnl_list else []
        for daily in recent_pnl:
            date_str = daily.date.strftime('%Y-%m-%d') if daily.date else 'Unknown'
            print(f"   {date_str}: ${daily.profit}")
    
    print(f"\n{'='*60}")
    
    # 批量对比测试
    print("2. 批量地址对比:")
    profiles = crawler.batch_get_profiles(test_addresses, delay=2.0)
    
    print(f"\n地址对比分析:")
    print(f"{'地址':<25} {'总PnL':<15} {'胜率':<8} {'交易数':<8} {'SOL余额':<12}")
    print("-" * 70)
    
    for address, profile in profiles.items():
        addr_short = address[:20] + "..."
        total_txs = profile.total_transactions
        sol_balance = profile.native_token_balance_amount
        
        print(f"{addr_short:<25} ${profile.total_pnl:<14} {profile.total_win_rate:<7}% {total_txs:<8} {sol_balance:<12}")
    
    # 保存详细结果
    if profiles:
        filename = f"detailed_profiles_{int(time.time())}.json"
        
        # 转换为可序列化的格式
        serializable_data = {}
        for address, profile in profiles.items():
            serializable_data[address] = {
                'basic_info': {
                    'wallet_address': profile.wallet_address,
                    'chain_id': profile.chain_id,
                    'period_type': profile.period_type
                },
                'trading_performance': {
                    'total_pnl': profile.total_pnl,
                    'total_pnl_roi': profile.total_pnl_roi,
                    'total_profit_pnl': profile.total_profit_pnl,
                    'unrealized_pnl': profile.unrealized_pnl,
                    'win_rate': profile.total_win_rate,
                    'profit_factor': profile.profit_factor
                },
                'trading_activity': {
                    'total_transactions': profile.total_transactions,
                    'buy_transactions': profile.total_txs_buy,
                    'sell_transactions': profile.total_txs_sell,
                    'total_volume_buy': profile.total_volume_buy,
                    'total_volume_sell': profile.total_volume_sell
                },
                'native_balance': {
                    'amount': profile.native_token_balance_amount,
                    'usd_value': profile.native_token_balance_usd
                },
                'top_tokens': [
                    {
                        'symbol': token.token_symbol,
                        'name': token.token_name,
                        'pnl': token.pnl,
                        'roi': token.roi
                    }
                    for token in profile.top_tokens
                ],
                'created_at': profile.created_at.isoformat() if profile.created_at else None
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细分析结果已保存到: {filename}")
    
    print("\n✅ 新模型测试完成!")


if __name__ == "__main__":
    main()
