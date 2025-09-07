#!/usr/bin/env python3
"""
代币持有者分析模块
Token Holder Analysis Module

输入: 代币合约地址
功能: 分析代币的顶级持有者
- 获取该代币的所有持有者地址
- 对所有持有者的持仓进行去重和基本信息获取
- 进行代币持仓排名（共同持有人数，总价值，>=3人）
- 统计目标代币在所有目标钱包中的排名（1:x,2:y...中位数）
- 集群分析：集群分数=共同持仓人数*共同代币人数（去除SOL和主流稳定币合约地址）

Input: token contract address
Function: analyze token top holders
- Get all holder addresses for the token
- Deduplicate and get basic information for all holder positions
- Perform token holding ranking (common holder count, total value, >=3 people)
- Calculate target token ranking in all target wallets (1:x, 2:y...median)
- Cluster analysis: cluster score = common holders count * common tokens count (excluding SOL and mainstream stablecoin addresses)
"""

import sys
import os
import json
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
import statistics

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入项目模块
from crawlers.okxdex.tokenTopHolders import SimpleOKXCrawler
from crawlers.okxdex.addressBalance import OKXAddressBalanceCrawler
from crawlers.jupiter.multiTokenProfiles import JupiterTokenCrawler
from functions.models import Address, TokenBalance
from settings.config_manager import ConfigManager


class TokenHolderAnalyzer:
    """代币持有者分析器"""
    
    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化分析器
        
        Args:
            performance_mode: 性能模式
                - 'conservative': 保守模式，最稳定 (1.2 地址/秒)
                - 'balanced': 平衡模式，推荐使用 (2.6 地址/秒) 
                - 'high_speed': 高速模式，极限速度 (3.4 地址/秒)
                - 'lightweight': 轻量模式，适合网络不佳 (2.0 地址/秒)
        """
        self.performance_mode = performance_mode
        self.config = ConfigManager()
        self.holder_crawler = SimpleOKXCrawler()
        self.balance_crawler = OKXAddressBalanceCrawler(performance_mode=performance_mode)
        self.jupiter_crawler = JupiterTokenCrawler()
        
        # 代币信息缓存
        self.token_info_cache = {}
        
        # 主流稳定币和SOL地址，用于集群分析时排除
        self.excluded_tokens = {
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
            "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",   # SRM
        }
    
    def set_auth(self, cookie: str, fp_token: str, verify_sign: str, 
                 verify_token: str, dev_id: str, site_info: str):
        """设置认证信息"""
        self.holder_crawler.set_auth(cookie, fp_token, verify_sign, 
                                   verify_token, dev_id, site_info)
        self.balance_crawler.set_auth(cookie, fp_token, verify_sign, 
                                    verify_token, dev_id, site_info)
    
    def analyze_token_holders(self, token_address: str, 
                            chain_id: str = "501", 
                            max_addresses: int = None) -> Dict[str, Any]:
        """
        分析代币持有者
        
        Args:
            token_address: 代币合约地址
            chain_id: 链ID，默认为Solana(501)
            max_addresses: 最大分析地址数，None表示分析所有地址
            
        Returns:
            分析结果字典
        """
        print(f"🚀 开始分析代币持有者: {token_address}")
        
        # 1. 获取代币持有者
        holders = self.holder_crawler.get_holders(chain_id, token_address)
        if not holders:
            return {"error": "无法获取持有者数据"}
        
        print(f"✅ 获取到 {len(holders)} 个持有者")
        
        # 2. 筛选真人地址
        human_holders = [h for h in holders if h["tag"] == "human"]
        print(f"👤 真人持有者: {len(human_holders)} 个")
        
        if len(human_holders) < 3:
            return {"error": "真人持有者数量不足，无法进行有效分析"}
        
        # 3. 获取每个真人地址的详细资产信息 - 使用高速批量模式
        print(f"📊 正在高速批量获取 {len(human_holders)} 个地址的资产信息...")
        holder_profiles = []
        
        # 使用高速批量爬取
        addresses = [holder['address'] for holder in human_holders]
        
        # 批量获取所有地址的资产信息
        address_results = self.balance_crawler.fetch_multiple_addresses_fast(
            addresses, 
            max_workers=3,  # 降低并发数提高成功率
            timeout_per_request=5.0,  # 增加超时时间
            debug=False
        )
        
        # 处理结果
        for holder in human_holders:
            address = holder['address']
            profile = address_results.get(address)
            
            if profile and profile.balances:
                # 检查是否在前20资产中找到目标代币
                target_token_found = False
                target_balance_in_top20 = "0"
                target_value_in_top20 = "0"
                
                for balance in profile.balances:
                    if balance.token_contract_address == token_address:
                        target_token_found = True
                        target_balance_in_top20 = balance.amount
                        target_value_in_top20 = balance.value
                        break
                
                holder_profiles.append({
                    "address": holder["address"],
                    "target_token_balance": holder["balance"],  # 实际持有量
                    "target_token_value": holder["value_usd"],  # 实际价值
                    "target_in_top20": target_token_found,  # 是否在前20资产中
                    "target_balance_top20": target_balance_in_top20,  # 前20中的余额
                    "target_value_top20": target_value_in_top20,  # 前20中的价值
                    "profile": profile
                })
            else:
                print(f"    ⚠️ 获取 {holder['address']} 资产失败或无资产")
        
        print(f"✅ 成功获取 {len(holder_profiles)} 个地址的详细资产")
        
        # 4. 进行各种分析
        # 创建详细分析数据
        detailed_analysis = {}
        for profile in holder_profiles:
            addr = profile["address"]
            detailed_analysis[addr] = {
                "target_in_top20": profile["target_in_top20"],
                "target_balance": profile["target_token_balance"],
                "target_value": profile["target_token_value"],
                "target_balance_top20": profile["target_balance_top20"],
                "target_value_top20": profile["target_value_top20"]
            }
        
        analysis_result = {
            "token_address": token_address,
            "analysis_time": datetime.now().isoformat(),
            "total_holders": len(holders),
            "human_holders": len(human_holders),
            "analyzed_addresses": len(holder_profiles),
            "holder_stats": self._analyze_holder_stats(holders),
            "common_holdings": self._analyze_common_holdings(holder_profiles, token_address),
            "target_token_ranking": self._analyze_target_token_ranking(holder_profiles, token_address),
            "cluster_analysis": self._analyze_clusters(holder_profiles),
            "detailed_analysis": detailed_analysis,  # 添加详细分析数据
            "detailed_holders": holder_profiles,
            "all_holders": holders  # 添加原始持有者数据
        }
        
        return analysis_result
    
    def _analyze_holder_stats(self, holders: List[Dict]) -> Dict[str, Any]:
        """分析持有者统计信息"""
        stats = {"human": 0, "pool": 0, "exchange": 0, "contract": 0}
        total_value = 0
        human_values = []
        
        for holder in holders:
            stats[holder["tag"]] += 1
            if holder["tag"] == "human":
                try:
                    value = float(holder["value_usd"])
                    human_values.append(value)
                    total_value += value
                except:
                    pass
        
        return {
            "by_type": stats,
            "human_total_value": total_value,
            "human_avg_value": total_value / stats["human"] if stats["human"] > 0 else 0,
            "human_median_value": statistics.median(human_values) if human_values else 0
        }
    
    def _get_token_info(self, token_addresses: List[str]) -> Dict[str, Dict]:
        """获取代币完整信息"""
        print(f"🪙 正在获取 {len(token_addresses)} 个代币的完整信息...")
        
        # 检查缓存
        uncached_addresses = []
        for addr in token_addresses:
            if addr not in self.token_info_cache:
                uncached_addresses.append(addr)
        
        # 批量获取未缓存的代币信息
        if uncached_addresses:
            try:
                tokens = self.jupiter_crawler.get_token_info(uncached_addresses)
                for token in tokens:
                    self.token_info_cache[token.contract_address] = {
                        'symbol': token.symbol,
                        'name': token.name,
                        'decimals': token.decimals
                    }
                print(f"✅ 成功获取 {len(tokens)} 个代币信息")
            except Exception as e:
                print(f"⚠️ 获取代币信息失败: {e}")
        
        # 为未找到信息的代币创建默认信息
        result = {}
        for addr in token_addresses:
            if addr in self.token_info_cache:
                result[addr] = self.token_info_cache[addr]
            else:
                # 使用地址作为默认值
                result[addr] = {
                    'symbol': f"{addr[:6]}...{addr[-4:]}",
                    'name': f"Unknown Token ({addr[:6]}...)",
                    'decimals': 6
                }
        
        return result

    def _analyze_common_holdings(self, holder_profiles: List[Dict], 
                               target_token: str) -> Dict[str, Any]:
        """分析共同持仓情况"""
        # 统计每个代币被多少个地址持有
        token_holders = defaultdict(list)
        
        for profile in holder_profiles:
            address = profile["address"]
            for balance in profile["profile"].balances:
                token_addr = balance.token_contract_address
                token_holders[token_addr].append({
                    "address": address,
                    "amount": balance.amount,
                    "value": balance.value
                })
        
        # 筛选被>=3个地址持有且总资产>10k的代币
        common_tokens = {}
        qualified_token_addresses = []  # 用于后续批量查询代币信息
        
        for token_addr, holders in token_holders.items():
            if len(holders) >= 3:
                total_value = sum(float(h["value"]) for h in holders if h["value"])
                
                # 只保留总资产>10k的代币
                if total_value > 10000:
                    common_tokens[token_addr] = {
                        "holder_count": len(holders),
                        "total_value": total_value,
                        "avg_value": total_value / len(holders),
                        "holders": holders
                    }
                    qualified_token_addresses.append(token_addr)
        
        # 只获取符合条件的代币信息
        token_info_map = {}
        if qualified_token_addresses:
            token_info_map = self._get_token_info(qualified_token_addresses)
        
        # 添加代币信息到common_tokens
        for token_addr in common_tokens:
            token_info = token_info_map.get(token_addr, {})
            common_tokens[token_addr].update({
                "symbol": token_info.get('symbol', f"{token_addr[:6]}..."),
                "name": token_info.get('name', f"Unknown Token ({token_addr[:6]}...)"),
                "decimals": token_info.get('decimals', 6)
            })
        
        # 按持有人数排序
        sorted_tokens = sorted(common_tokens.items(), 
                             key=lambda x: x[1]["holder_count"], 
                             reverse=True)
        
        return {
            "total_common_tokens": len(common_tokens),
            "top_common_tokens": dict(sorted_tokens[:20]),  # 前20个
            "token_info_map": token_info_map,  # 只包含符合条件的代币信息
            "summary": {
                "most_held_token": sorted_tokens[0] if sorted_tokens else None,
                "avg_holders_per_token": sum(t["holder_count"] for t in common_tokens.values()) / len(common_tokens) if common_tokens else 0
            }
        }
    
    def _analyze_target_token_ranking(self, holder_profiles: List[Dict], 
                                    target_token: str) -> Dict[str, Any]:
        """分析目标代币在各钱包中的排名"""
        rankings = []
        
        for profile in holder_profiles:
            balances = profile["profile"].balances
            # 按价值排序
            sorted_balances = sorted(balances, 
                                   key=lambda x: float(x.value) if x.value else 0, 
                                   reverse=True)
            
            # 找到目标代币的排名
            for rank, balance in enumerate(sorted_balances, 1):
                if balance.token_contract_address == target_token:
                    rankings.append(rank)
                    break
        
        if not rankings:
            return {"error": "无法计算目标代币排名"}
        
        # 统计排名分布
        ranking_dist = Counter(rankings)
        
        return {
            "rankings": rankings,
            "median_rank": statistics.median(rankings),
            "avg_rank": sum(rankings) / len(rankings),
            "ranking_distribution": dict(ranking_dist),
            "top_ranked_count": sum(1 for r in rankings if r <= 3),  # 前3名的钱包数
            "summary": {
                "best_rank": min(rankings),
                "worst_rank": max(rankings),
                "top_5_percentage": sum(1 for r in rankings if r <= 5) / len(rankings) * 100
            }
        }
    
    def _analyze_clusters(self, holder_profiles: List[Dict]) -> Dict[str, Any]:
        """集群分析：计算集群分数"""
        # 为每个地址建立代币集合（排除主流币）
        address_tokens = {}
        for profile in holder_profiles:
            address = profile["address"]
            tokens = set()
            for balance in profile["profile"].balances:
                if balance.token_contract_address not in self.excluded_tokens:
                    if float(balance.value) > 1:  # 价值>1USD的代币才计入
                        tokens.add(balance.token_contract_address)
            address_tokens[address] = tokens
        
        # 计算地址间的相似度和集群
        clusters = []
        addresses = list(address_tokens.keys())
        
        for i in range(len(addresses)):
            for j in range(i + 1, len(addresses)):
                addr1, addr2 = addresses[i], addresses[j]
                tokens1, tokens2 = address_tokens[addr1], address_tokens[addr2]
                
                # 计算共同代币
                common_tokens = tokens1 & tokens2
                if len(common_tokens) >= 2:  # 至少2个共同代币
                    similarity_score = len(common_tokens)
                    clusters.append({
                        "addresses": [addr1, addr2],
                        "common_tokens": list(common_tokens),
                        "common_token_count": len(common_tokens),
                        "cluster_score": 2 * len(common_tokens)  # 2个地址 * 共同代币数
                    })
        
        # 尝试找到更大的集群（3个或更多地址）
        large_clusters = self._find_large_clusters(address_tokens)
        
        # 按集群分数排序
        clusters.sort(key=lambda x: x["cluster_score"], reverse=True)
        
        return {
            "total_clusters": len(clusters),
            "large_clusters": large_clusters,
            "top_clusters": clusters[:10],  # 前10个集群
            "cluster_summary": {
                "max_cluster_score": clusters[0]["cluster_score"] if clusters else 0,
                "avg_cluster_score": sum(c["cluster_score"] for c in clusters) / len(clusters) if clusters else 0,
                "addresses_in_clusters": len(set().union(*[c["addresses"] for c in clusters])) if clusters else 0
            }
        }
    
    def _find_large_clusters(self, address_tokens: Dict[str, set]) -> List[Dict]:
        """寻找大型集群（3个或更多地址的共同持仓）"""
        addresses = list(address_tokens.keys())
        large_clusters = []
        
        # 使用简单的贪心算法寻找集群
        for token in set().union(*address_tokens.values()):
            # 找到持有该代币的所有地址
            holders = [addr for addr, tokens in address_tokens.items() if token in tokens]
            
            if len(holders) >= 3:
                # 计算这些地址的共同代币
                common_tokens = set(address_tokens[holders[0]])
                for addr in holders[1:]:
                    common_tokens &= address_tokens[addr]
                
                if len(common_tokens) >= 2:  # 至少2个共同代币
                    cluster_score = len(holders) * len(common_tokens)
                    large_clusters.append({
                        "addresses": holders,
                        "address_count": len(holders),
                        "common_tokens": list(common_tokens),
                        "common_token_count": len(common_tokens),
                        "cluster_score": cluster_score
                    })
        
        # 去重和排序
        unique_clusters = []
        seen_address_sets = set()
        
        for cluster in large_clusters:
            addr_set = frozenset(cluster["addresses"])
            if addr_set not in seen_address_sets:
                seen_address_sets.add(addr_set)
                unique_clusters.append(cluster)
        
        unique_clusters.sort(key=lambda x: x["cluster_score"], reverse=True)
        return unique_clusters[:5]  # 返回前5个大集群
    
    def generate_detective_report(self, result: Dict[str, Any], 
                                token_symbol: str = None, 
                                top_holdings_count: int = 20) -> str:
        """
        生成DETECTIVE风格的美观分析报告
        
        Args:
            result: 分析结果字典
            token_symbol: 代币符号，如果未提供会尝试从地址推断
            top_holdings_count: 显示前N大持仓的排名
            
        Returns:
            格式化的报告字符串
        """
        if "error" in result:
            return f"❌ 分析失败: {result['error']}"
        
        # 获取基本信息
        token_address = result['token_address']
        
        # 获取目标代币的符号 - 从共同持仓信息或代币信息映射中获取
        if not token_symbol:
            token_info_map = result.get('common_holdings', {}).get('token_info_map', {})
            target_token_info = token_info_map.get(token_address, {})
            token_symbol = target_token_info.get('symbol', token_address[:8] + "...")
        
        analyzed_count = result['analyzed_addresses']
        common_holdings = result['common_holdings']
        top_tokens = common_holdings.get('top_common_tokens', {})
        
        # 计算总资产和代币种类
        total_value = 0
        token_types = 0
        
        # 从详细持有者数据计算总资产
        for holder in result.get('detailed_holders', []):
            if holder.get('profile') and holder['profile'].balances:
                for balance in holder['profile'].balances:
                    try:
                        total_value += float(balance.value)
                    except:
                        pass
        
        token_types = len([info for info in top_tokens.values() if info['holder_count'] >= 3 and info['total_value'] > 10000])
        
        # 构建报告
        report_lines = []
        report_lines.append(f"🔥 {token_symbol}大户主要持仓 (👥 按持有人数排序)")
        report_lines.append(f"💰 总资产: ${total_value:,.0f}")
        report_lines.append(f"🔢 代币种类: {token_types}")
        report_lines.append("─" * 39)
        
        # 排序并显示前N个代币（只显示被≥3人持有的）
        sorted_tokens = sorted(top_tokens.items(), 
                             key=lambda x: x[1]['holder_count'], 
                             reverse=True)
        
        # 过滤掉持有人数少于3或总资产小于10k的代币
        filtered_tokens = [(addr, info) for addr, info in sorted_tokens if info['holder_count'] >= 3 and info['total_value'] > 10000]
        
        for i, (token_addr, token_info) in enumerate(filtered_tokens[:top_holdings_count], 1):
            holder_count = token_info['holder_count']
            total_token_value = token_info['total_value']
            
            # 从代币信息中获取符号和名称
            symbol = token_info.get('symbol', f"{token_addr[:6]}...")
            name = token_info.get('name', '')
            
            # 构建显示名称
            if name and name != symbol:
                display_name = f"{symbol} ({name})"
            else:
                display_name = symbol
            
            # 生成 gmgn 链接
            gmgn_url = f" (https://gmgn.ai/sol/token/{token_addr})"
            
            # 格式化金额
            if total_token_value >= 1000000:
                value_str = f"${total_token_value/1000000:.1f}M"
            elif total_token_value >= 1000:
                value_str = f"${total_token_value/1000:.1f}K"
            else:
                value_str = f"${total_token_value:.0f}"
            
            report_lines.append(f"{i:2d}. {display_name}{gmgn_url} ({holder_count}人) {value_str}")
        
        # 添加分析统计
        report_lines.append("")
        report_lines.append("👥 分析人类地址:")
        
        # 找到目标代币的持有人数 - 在已分析的地址中
        target_token_holders = 0
        for token_addr, token_info in top_tokens.items():
            if token_addr == result['token_address']:
                target_token_holders = token_info['holder_count']
                break
        
        # 如果在共同持仓中没找到目标代币，说明持有人数少于3个
        if target_token_holders == 0:
            # 从详细持有者数据中统计实际持有目标代币的人数
            target_token_holders = 0
            for holder in result.get('detailed_holders', []):
                if holder.get('target_token_balance') and float(holder['target_token_balance']) > 0:
                    target_token_holders += 1
            
            # 如果还是0，使用已分析地址数作为备选
            if target_token_holders == 0:
                target_token_holders = analyzed_count
        
        total_human_holders = result.get('human_holders', analyzed_count)
        
        report_lines.append(f"🎯 实际持有 {token_symbol.replace('...', '')}: {target_token_holders} 人 (共分析 {analyzed_count} 个地址)")
        report_lines.append(f"📈 统计范围: 分析每个地址的完整持仓，显示被≥3人持有的代币")
        report_lines.append(f"📊 总体情况: {total_human_holders} 个真人地址中的 {analyzed_count} 个已完成分析")
        
        # 显示目标代币不在前20资产中的地址
        not_in_top20_holders = []
        for addr, data in result.get('detailed_analysis', {}).items():
            if not data.get('target_in_top20', True):  # 默认True，只有明确为False才算
                not_in_top20_holders.append(addr)
        
        if not_in_top20_holders:
            report_lines.append(f"\n📉 目标代币不在前20资产中的地址 ({len(not_in_top20_holders)} 个):")
            for i, addr in enumerate(not_in_top20_holders, 1):
                report_lines.append(f"   {i}. {addr[:6]}...{addr[-4:]}")
            report_lines.append(f"   注: 这些地址持有目标代币，但金额较小，未进入个人前20资产排行")
        
        # 添加非人类地址信息
        all_holders = result.get('all_holders', [])
        non_human_holders = [h for h in all_holders if h.get('tag') != 'human']
        
        if non_human_holders:
            report_lines.append("")
            report_lines.append("🏦 非人类地址:")
            
            # 按类型分组
            pools = [h for h in non_human_holders if h.get('tag') == 'pool']
            exchanges = [h for h in non_human_holders if h.get('tag') == 'exchange']
            contracts = [h for h in non_human_holders if h.get('tag') == 'contract']
            
            # 显示流动性池
            if pools:
                report_lines.append(f"💧 流动性池 ({len(pools)}个):")
                for pool in pools:
                    balance = float(pool.get('balance', 0))
                    value = float(pool.get('value_usd', 0))
                    if balance >= 1000000:
                        balance_str = f"{balance/1000000:.1f}M"
                    elif balance >= 1000:
                        balance_str = f"{balance/1000:.1f}K"
                    else:
                        balance_str = f"{balance:.0f}"
                    
                    if value >= 1000:
                        value_str = f"${value/1000:.1f}K"
                    else:
                        value_str = f"${value:.0f}"
                    
                    address_short = pool['address'][:6] + "..." + pool['address'][-4:]
                    report_lines.append(f"   • {address_short}: {balance_str} ({value_str})")
            
            # 显示交易所
            if exchanges:
                report_lines.append(f"🏛️ 交易所 ({len(exchanges)}个):")
                for exchange in exchanges:
                    balance = float(exchange.get('balance', 0))
                    value = float(exchange.get('value_usd', 0))
                    if balance >= 1000000:
                        balance_str = f"{balance/1000000:.1f}M"
                    elif balance >= 1000:
                        balance_str = f"{balance/1000:.1f}K"
                    else:
                        balance_str = f"{balance:.0f}"
                    
                    if value >= 1000:
                        value_str = f"${value/1000:.1f}K"
                    else:
                        value_str = f"${value:.0f}"
                    
                    address_short = exchange['address'][:6] + "..." + exchange['address'][-4:]
                    report_lines.append(f"   • {address_short}: {balance_str} ({value_str})")
            
            # 显示合约
            if contracts:
                report_lines.append(f"📜 合约 ({len(contracts)}个):")
                for contract in contracts:
                    balance = float(contract.get('balance', 0))
                    value = float(contract.get('value_usd', 0))
                    if balance >= 1000000:
                        balance_str = f"{balance/1000000:.1f}M"
                    elif balance >= 1000:
                        balance_str = f"{balance/1000:.1f}K"
                    else:
                        balance_str = f"{balance:.0f}"
                    
                    if value >= 1000:
                        value_str = f"${value/1000:.1f}K"
                    else:
                        value_str = f"${value:.0f}"
                    
                    address_short = contract['address'][:6] + "..." + contract['address'][-4:]
                    report_lines.append(f"   • {address_short}: {balance_str} ({value_str})")
        
        return "\n".join(report_lines)
    
    def _get_token_symbol(self, token_address: str) -> str:
        """获取代币符号的简化显示名称"""
        # 已知代币地址映射
        known_tokens = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT", 
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "RAY",
            "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt": "SRM",
            "So11111111111111111111111111111111111111112": "SOL"
        }
        
        if token_address in known_tokens:
            return known_tokens[token_address]
        else:
            # 对于未知代币，返回地址的前几位
            return token_address[:6] + "..."
    
    def save_analysis_result(self, result: Dict[str, Any], 
                           filename: Optional[str] = None) -> str:
        """保存分析结果到文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            token_short = result["token_address"][:8]
            filename = f"token_analysis_{token_short}_{timestamp}.yaml"
        
        filepath = os.path.join("storage", filename)
        
        # 确保storage目录存在
        os.makedirs("storage", exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(result, f, default_flow_style=False, 
                     allow_unicode=True, sort_keys=False)
        
        print(f"📁 分析结果已保存到: {filepath}")
        return filepath


def main():
    """测试函数 - 可在这里修改性能模式"""
    
    # 🔧 在这里修改性能模式:
    # 'conservative' = 保守模式 (1.2 地址/秒) - 最稳定
    # 'balanced'     = 平衡模式 (2.6 地址/秒) - 推荐使用  
    # 'high_speed'   = 高速模式 (3.4 地址/秒) - 极限速度
    # 'lightweight'  = 轻量模式 (2.0 地址/秒) - 网络不佳时使用
    
    PERFORMANCE_MODE = 'high_speed'  # 👈 在这里修改模式
    
    print(f"🔧 使用性能模式: {PERFORMANCE_MODE}")
    analyzer = TokenHolderAnalyzer(performance_mode=PERFORMANCE_MODE)
    
    # 设置认证信息（需要替换为真实数据）
    analyzer.set_auth(
        cookie="devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; locale=en_US; ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; ok_prefer_udColor=0; ok_prefer_udTimeZone=0; fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; ok_global={%22g_t%22:2}; _gcl_au=1.1.1005719754.1755091396; connectedWallet=1; _gid=GA1.2.950489538.1757092345; mse=nf=8|se=0; __cf_bm=KlSlz4ToD2eBrbV2YMpvOTgZSH9aJx8ZbSpNehX__70-1757227578-1.0.1.1-CVB_X0rNpOfUw.n3YJgAepDber7b9fzyAdFONBE5xbbJ9uokVrU0D0ZnKpCgKqWRX9MNMHAODFPNpxZDZYUw1XLYVw6RbsONqf7J5SbrKAc; ok-exp-time=1757227583876; okg.currentMedia=md; tmx_session_id=g42rqe6lkgv_1757227586034; connected=1; fp_s=0; traceId=2130772279702400005; _gat_UA-35324627-3=1; _ga=GA1.1.2083537763.1750302376; _ga_G0EKWWQGTZ=GS2.1.s1757227595$o127$g1$t1757227972$j58$l0$h0; ok-ses-id=ic8FZdwDJ9iztku9zy3wjshp7WSUVWnCq6wpmGltOew4BJU1wkFkGYHyg2jS3JIKpZCB7dnA0g1BCrndYsGLeFEXC9fKYuWwNU4qCZlHwpNQI42XTE4EYPY03Z1p2MaR; _monitor_extras={\"deviceId\":\"KmpeI8VVHan-2zL3_DbOJB\",\"eventId\":6313,\"sequenceNumber\":6313}",
        fp_token="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
        verify_sign="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4=",
        verify_token="ac90bf8e-b5fc-4643-a441-2d7b7eb08634",
        dev_id="01980a38-038a-44d9-8da3-a8276bbcb5b9",
        site_info="==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye"
    )
    
    # 分析示例代币
    token_address = "9X45NjtGbGo9zdCFmMyqZyNzC6Wa67KFbfvGc8nubonk"
    
    print("🚀 开始代币持有者分析...")
    result = analyzer.analyze_token_holders(token_address)
    
    if "error" in result:
        print(f"❌ 分析失败: {result['error']}")
        return
    
    # 保存结果
    filepath = analyzer.save_analysis_result(result)
    
    # 生成并输出
    print("="*60)
    detective_report = analyzer.generate_detective_report(result, "DETECTIVE")
    print(detective_report)
    
    print(f"\n📁 详细结果已保存到: {filepath}")


if __name__ == "__main__":
    main()

