from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Token:
    """代币模型
    
    Attributes:
        contract_address: 合约地址
        symbol: 代币符号
        name: 代币名称
        token_supply: 代币总供应量
        decimals: 小数位数
        created_at: 创建时间 (可选)
    """
    contract_address: str
    symbol: str
    name: str
    token_supply: str
    decimals: int
    created_at: Optional[datetime] = None


@dataclass
class TokenBalance:
    """代币余额模型
    
    Attributes:
        token_contract_address: 代币合约地址
        amount: 代币数量
        value: 代币价值USD
    """
    token_contract_address: str
    amount: str = "0"  # 使用字符串存储大数值
    value: str = "0"   # USD价值

    def __post_init__(self):
        # 确保amount和value是字符串格式
        if not isinstance(self.amount, str):
            self.amount = str(self.amount)
        if not isinstance(self.value, str):
            self.value = str(self.value)

@dataclass
class Address:
    """地址模型
    
    Attributes:
        address: 钱包地址
        note: 地址备注
        tag: 地址标签
        balances: 代币余额数组 (可选)
        transaction_stats: 时间周期交易统计 (可选)
            格式: {"period": {"buy": count, "sell": count, "total": count}}
            例如: {"1d": {"buy": 5, "sell": 3, "total": 8}, "30d": {"buy": 50, "sell": 30, "total": 80}}
    """
    address: str
    note: str
    tag: str
    balances: Optional[List[TokenBalance]] = None
    transaction_stats: Optional[Dict[str, Dict[str, int]]] = None
    
    
    def __post_init__(self):
        if self.balances is None:
            self.balances = []
        if self.transaction_stats is None:
            self.transaction_stats = {}
    
    def add_balance(self, token_contract_address: str, amount: str, 
                    value: str = "0") -> None:
        """添加或更新代币余额"""
        if self.balances is None:
            self.balances = []
        
        # 查找是否已存在该代币
        for balance in self.balances:
            if balance.token_contract_address == token_contract_address:
                balance.amount = amount
                balance.value = value
                return
        
        # 如果不存在，添加新的余额记录
        self.balances.append(TokenBalance(
            token_contract_address=token_contract_address,
            amount=amount,
            value=value,
        ))
    
    def get_balance(self, token_contract_address: str) -> Optional[str]:
        """获取指定代币的余额"""
        if self.balances is None:
            return None
        
        for balance in self.balances:
            if balance.token_contract_address == token_contract_address:
                return balance.amount
        return None
    
    def get_token_value(self, token_contract_address: str) -> Optional[str]:
        """获取指定代币的总价值"""
        if self.balances is None:
            return None
        
        for balance in self.balances:
            if balance.token_contract_address == token_contract_address:
                return balance.value
        return None
    
    def get_total_value(self) -> str:
        """获取地址的总资产价值"""
        if self.balances is None:
            return "0"
        
        from decimal import Decimal
        total = Decimal("0")
        for balance in self.balances:
            try:
                total += Decimal(balance.value)
            except:
                continue
        return str(total)
    
    def get_all_token_addresses(self) -> List[str]:
        """获取该地址持有的所有代币合约地址"""
        if self.balances is None:
            return []
        return [balance.token_contract_address for balance in self.balances]
    
    @staticmethod
    def period_to_key(period: int) -> str:
        """将OKX周期数字转换为字符串键
        
        Args:
            period: OKX周期 (1=1D, 2=3D, 3=7D, 4=1M, 5=3M)
            
        Returns:
            对应的字符串键
        """
        period_mapping = {
            1: "1d",
            2: "3d", 
            3: "7d",
            4: "30d",  # 1M约等于30天
            5: "90d"   # 3M约等于90天
        }
        return period_mapping.get(period, f"period_{period}")
    
    def set_transaction_data(self, period: str, buy_trades: int, sell_trades: int) -> None:
        """设置指定时间周期的交易数据
        
        Args:
            period: 时间周期 (如 "1d", "7d", "30d") 或 OKX周期数字
            buy_trades: 买入交易数
            sell_trades: 卖出交易数
        """
        if self.transaction_stats is None:
            self.transaction_stats = {}
        
        # 如果传入的是数字，转换为字符串键
        if isinstance(period, int):
            period = self.period_to_key(period)
        
        total_trades = buy_trades + sell_trades
        self.transaction_stats[period] = {
            "buy": buy_trades,
            "sell": sell_trades,
            "total": total_trades
        }
    
    def set_transaction_data_from_okx(self, okx_period: int, buy_trades: int, sell_trades: int) -> None:
        """从OKX数据设置交易统计
        
        Args:
            okx_period: OKX周期 (1=1D, 2=3D, 3=7D, 4=1M, 5=3M)
            buy_trades: 买入交易数
            sell_trades: 卖出交易数
        """
        period_key = self.period_to_key(okx_period)
        self.set_transaction_data(period_key, buy_trades, sell_trades)
    
    def get_buy_trades(self, period: str) -> int:
        """获取指定时间周期的买入交易数"""
        if self.transaction_stats is None or period not in self.transaction_stats:
            return 0
        return self.transaction_stats[period].get("buy", 0)
    
    def get_sell_trades(self, period: str) -> int:
        """获取指定时间周期的卖出交易数"""
        if self.transaction_stats is None or period not in self.transaction_stats:
            return 0
        return self.transaction_stats[period].get("sell", 0)
    
    def get_total_trades(self, period: str) -> int:
        """获取指定时间周期的总交易数"""
        if self.transaction_stats is None or period not in self.transaction_stats:
            return 0
        return self.transaction_stats[period].get("total", 0)


@dataclass
class TokenTransfer:
    """代币转账关系模型
    
    表示代币转账记录
    
    Attributes:
        from_address: 发送方地址
        to_address: 接收方地址
        token_contract_address: 代币合约地址
        amount: 转账数量
        value: 转账价值USD（可选）
        transaction_hash: 交易哈希
        block_number: 区块号 (可选)
        timestamp: 时间戳 (可选)
    """
    token_contract_address: str
    from_address: str
    to_address: str
    amount: str  # 使用字符串存储大数值
    value: Optional[str] = None  # 转账价值USD（可选）



class TokenManager:
    """代币管理器
    
    管理代币相关的操作
    """
    
    def __init__(self):
        self.tokens: Dict[str, Token] = {}
        self.addresses: Dict[str, Address] = {}
        self.transfers: List[TokenTransfer] = []
    
    def add_token(self, token: Token) -> None:
        """添加代币"""
        self.tokens[token.contract_address] = token
    
    def add_address(self, address: Address) -> None:
        """添加地址"""
        self.addresses[address.address] = address
    
    def add_transfer(self, transfer: TokenTransfer) -> None:
        """添加转账记录"""
        self.transfers.append(transfer)
    
    def get_token_by_address(self, contract_address: str) -> Optional[Token]:
        """根据合约地址获取代币信息"""
        return self.tokens.get(contract_address)


# 测试主程序
if __name__ == "__main__":
    print("=== Token Management System Test ===\n")
    
    # 1. 创建管理器
    print("1. 创建 TokenManager...")
    manager = TokenManager()
    
    # 2. 创建多个代币
    print("2. 添加代币到管理器...")
    tokens_data = [
        {
            "contract_address": "So11111111111111111111111111111111111111112",
            "symbol": "SOL",
            "name": "Solana",
            "token_supply": "548999845.926396263",
            "decimals": 9
        },
        {
            "contract_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "symbol": "USDC",
            "name": "USD Coin",
            "token_supply": "35000000000.000000",
            "decimals": 6
        },
        {
            "contract_address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "symbol": "USDT",
            "name": "Tether USD",
            "token_supply": "48000000000.000000",
            "decimals": 6
        }
    ]
    
    # 添加代币到管理器
    for token_data in tokens_data:
        token = Token(**token_data)
        manager.add_token(token)
        print(f"   ✓ 添加代币: {token.symbol} ({token.name})")
    
    # 3. 创建多个地址
    print("\n3. 创建地址...")
    addresses_data = [
        {"address": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1", "note": "Large holder wallet", "tag": "whale"},
        {"address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "note": "Institutional investor", "tag": "institution"},
        {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", "note": "DEX liquidity pool", "tag": "dex_pool"}
    ]
    
    for addr_data in addresses_data:
        address = Address(**addr_data)
        manager.add_address(address)
        print(f"   ✓ 添加地址: {address.tag} - {address.address[:20]}...")
    
    # 4. 为地址添加代币余额
    print("\n4. 添加代币余额...")
    
    # Whale地址的余额
    whale = manager.addresses["5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"]
    whale.add_balance("So11111111111111111111111111111111111111112", "1500000.123456789", "225000000.50")
    whale.add_balance("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "10000000.500000", "10000000.50")
    whale.add_balance("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "5000000.750000", "5000000.75")
    
    # Institution地址的余额
    institution = manager.addresses["7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"]
    institution.add_balance("So11111111111111111111111111111111111111112", "800000.987654321", "120000000.25")
    institution.add_balance("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "25000000.000000", "25000000.00")
    
    # DEX Pool地址的余额
    dex_pool = manager.addresses["9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"]
    dex_pool.add_balance("So11111111111111111111111111111111111111112", "50000000.000000000", "7500000000.00")
    dex_pool.add_balance("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "100000000.000000", "100000000.00")
    
    print("   ✓ 余额添加完成")
    
    # 5. 设置交易统计数据 (使用OKX周期映射)
    print("\n5. 设置交易统计数据 (模拟OKX数据)...")
    
    # 使用OKX周期数字设置交易统计
    whale.set_transaction_data_from_okx(1, buy_trades=3, sell_trades=2)    # 1D
    whale.set_transaction_data_from_okx(3, buy_trades=15, sell_trades=10)  # 7D  
    whale.set_transaction_data_from_okx(4, buy_trades=70, sell_trades=50)  # 1M
    
    institution.set_transaction_data_from_okx(1, buy_trades=8, sell_trades=7)    # 1D
    institution.set_transaction_data_from_okx(3, buy_trades=45, sell_trades=35)  # 7D
    institution.set_transaction_data_from_okx(4, buy_trades=180, sell_trades=120) # 1M
    
    dex_pool.set_transaction_data_from_okx(1, buy_trades=80, sell_trades=70)    # 1D
    dex_pool.set_transaction_data_from_okx(3, buy_trades=500, sell_trades=500)  # 7D
    dex_pool.set_transaction_data_from_okx(5, buy_trades=2100, sell_trades=2100) # 3M
    
    print("   ✓ 交易统计数据设置完成")
    
    # 6. 添加转账记录
    print("\n6. 添加转账记录...")
    transfers_data = [
        {
            "token_contract_address": "So11111111111111111111111111111111111111112",
            "from_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "to_address": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
            "amount": "100000.123456789",
            "value": "15000000.00"
        },
        {
            "token_contract_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "from_address": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
            "to_address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            "amount": "5000000.000000",
            "value": "5000000.00"
        }
    ]
    
    for transfer_data in transfers_data:
        transfer = TokenTransfer(**transfer_data)
        manager.add_transfer(transfer)
        token = manager.get_token_by_address(transfer.token_contract_address)
        print(f"   ✓ 转账: {transfer.amount} {token.symbol} (${transfer.value})")
    
    # 7. 显示测试结果
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    # 显示所有代币信息
    print(f"\n📊 代币信息 ({len(manager.tokens)} 个):")
    for contract_address, token in manager.tokens.items():
        print(f"   {token.symbol:4} | {token.name:15} | Supply: {token.token_supply:>20}")
    
    # 显示所有地址信息
    print(f"\n💰 地址资产 ({len(manager.addresses)} 个):")
    for address, addr_obj in manager.addresses.items():
        total_value = addr_obj.get_total_value()
        balance_count = len(addr_obj.balances) if addr_obj.balances else 0
        print(f"   {addr_obj.tag:12} | {balance_count} tokens | 总价值: ${total_value}")
        
        # 显示详细余额
        if addr_obj.balances:
            for balance in addr_obj.balances:
                token = manager.get_token_by_address(balance.token_contract_address)
                symbol = token.symbol if token else "UNKNOWN"
                print(f"      {symbol:4}: {balance.amount:>20} (${balance.value})")
    
    # 显示转账记录
    print(f"\n🔄 转账记录 ({len(manager.transfers)} 笔):")
    for i, transfer in enumerate(manager.transfers, 1):
        token = manager.get_token_by_address(transfer.token_contract_address)
        symbol = token.symbol if token else "UNKNOWN"
        from_tag = next((addr.tag for addr in manager.addresses.values() 
                        if addr.address == transfer.from_address), "unknown")
        to_tag = next((addr.tag for addr in manager.addresses.values() 
                      if addr.address == transfer.to_address), "unknown")
        print(f"   {i}. {from_tag} → {to_tag}: {transfer.amount} {symbol} (${transfer.value})")
    
    # 统计信息
    print(f"\n📈 系统统计:")
    total_addresses = len(manager.addresses)
    total_tokens = len(manager.tokens)
    total_transfers = len(manager.transfers)
    
    # 计算总资产价值
    from decimal import Decimal
    total_system_value = Decimal("0")
    for addr_obj in manager.addresses.values():
        try:
            total_system_value += Decimal(addr_obj.get_total_value())
        except:
            continue
    
    print(f"   • 管理的代币数量: {total_tokens}")
    print(f"   • 管理的地址数量: {total_addresses}")
    print(f"   • 转账记录数量: {total_transfers}")
    print(f"   • 系统总资产价值: ${total_system_value}")
    
    # 测试查询功能
    print(f"\n🔍 查询功能测试:")
    sol_address = "So11111111111111111111111111111111111111112"
    print(f"   • SOL代币信息: {manager.get_token_by_address(sol_address).name}")
    
    whale_sol_balance = whale.get_balance(sol_address)
    print(f"   • Whale的SOL余额: {whale_sol_balance}")
    
    whale_sol_value = whale.get_token_value(sol_address)
    print(f"   • Whale的SOL价值: ${whale_sol_value}")
    
    # 测试交易统计功能 (使用OKX周期映射)
    print(f"\n📊 交易统计测试 (OKX周期映射):")
    print(f"   • Whale 1天(1d)买入: {whale.get_buy_trades('1d')}, 卖出: {whale.get_sell_trades('1d')}, 总计: {whale.get_total_trades('1d')}")
    print(f"   • Whale 7天(7d)买入: {whale.get_buy_trades('7d')}, 卖出: {whale.get_sell_trades('7d')}, 总计: {whale.get_total_trades('7d')}")
    print(f"   • Whale 30天(30d)总交易: {whale.get_total_trades('30d')}")
    print(f"   • DEX Pool 90天(90d)总交易: {dex_pool.get_total_trades('90d')}")
    
    # 展示周期映射
    print(f"\n🔄 OKX周期映射:")
    for period_num in [1, 2, 3, 4, 5]:
        period_key = whale.period_to_key(period_num)
        period_desc = {1: "1天", 2: "3天", 3: "7天", 4: "1个月", 5: "3个月"}[period_num]
        print(f"   • OKX周期 {period_num} ({period_desc}) → 键: '{period_key}'")
    
    print(f"\n✅ 测试完成!")
    print("="*60)