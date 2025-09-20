#!/usr/bin/env python3
"""
Jupiter 代币基本信息爬虫 (JupiterTokenCrawler)
===================================================

功能: 通过 Jupiter API 获取多个代币的基本信息
API: https://token.jup.ag/strict
用途: 获取代币symbol、名称、logo等基础元数据

主要方法:
- get_token_info(token_addresses): 批量获取代币信息
- 支持批处理，最多100个代币
- 返回Token对象列表，包含contract_address, symbol, name, logo_url等

适用场景: 当需要显示代币名称和图标时使用
"""

import requests
import time
import json
import yaml
import os
from typing import List, Dict, Optional
from datetime import datetime
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from functions.models import Token


class JupiterTokenCrawler:
    """Jupiter 代币信息爬虫"""
    
    def __init__(self):
        self.base_url = "https://datapi.jup.ag/v1/assets/search"
        self.headers = {
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",  # 移除 br, zstd 避免压缩问题
            "accept-language": "en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2",
            "origin": "https://jup.ag",
            "referer": "https://jup.ag/",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        }
    
    def get_token_info(self, token_addresses: List[str]) -> List[Token]:
        """
        获取多个代币的基本信息
        
        Args:
            token_addresses: 代币合约地址列表
            
        Returns:
            Token 对象列表
        """
        if not token_addresses:
            return []
        
        try:
            # 将地址列表组合成查询字符串 (用逗号分隔)
            query_string = ",".join(token_addresses)
            
            # 构建请求参数
            params = {
                "query": query_string
            }
            
            print(f"🔍 正在查询 {len(token_addresses)} 个代币信息...")
            print(f"📝 查询地址: {query_string[:100]}{'...' if len(query_string) > 100 else ''}")
            
            # 发送请求
            response = requests.get(self.base_url, params=params, headers=self.headers)
            
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"❌ 响应内容: {response.text}")
                return []
            
            data = response.json()
            
            # 检查响应结构
            if not isinstance(data, list):
                print(f"❌ 意外的响应格式: {type(data)}")
                print(f"❌ 响应内容: {data}")
                return []
            
            tokens = []
            found_addresses = set()
            
            for token_data in data:
                try:
                    # 解析代币信息
                    token = self._parse_token_data(token_data)
                    if token:
                        tokens.append(token)
                        found_addresses.add(token.contract_address)
                        print(f"✅ 找到代币: {token.symbol} ({token.name}) - {token.contract_address}")
                    
                except Exception as e:
                    print(f"❌ 解析代币数据失败: {e}")
                    print(f"❌ 原始数据: {token_data}")
                    continue
            
            # 检查未找到的代币
            missing_addresses = set(token_addresses) - found_addresses
            if missing_addresses:
                print(f"⚠️  未找到以下代币信息:")
                for addr in missing_addresses:
                    print(f"   - {addr}")
            
            print(f"✅ 成功获取 {len(tokens)} 个代币信息")
            return tokens
            
        except Exception as e:
            print(f"❌ 获取代币信息失败: {e}")
            return []
    
    def _parse_token_data(self, token_data: Dict) -> Optional[Token]:
        """
        解析单个代币数据
        
        Args:
            token_data: API 返回的代币数据
            
        Returns:
            Token 对象或 None
        """
        try:
            # 提取必要字段 - Jupiter API 使用 'id' 作为合约地址
            contract_address = token_data.get("id", "") or token_data.get("address", "")
            symbol = token_data.get("symbol", "")
            name = token_data.get("name", "")
            decimals = token_data.get("decimals", 0)
            
            # 验证必要字段
            if not contract_address:
                print(f"⚠️  代币缺少合约地址: {token_data}")
                return None
            
            if not symbol:
                print(f"⚠️  代币缺少符号: {contract_address}")
                return None
            
            # 获取供应量信息（可能在不同字段中）
            token_supply = "0"
            supply_fields = ["totalSupply", "circSupply", "supply", "total_supply", "circulating_supply"]
            for field in supply_fields:
                if field in token_data and token_data[field] is not None:
                    token_supply = str(token_data[field])
                    break
            
            # 创建 Token 对象
            token = Token(
                contract_address=contract_address,
                symbol=symbol,
                name=name if name else symbol,  # 如果没有名称，使用符号
                token_supply=token_supply,
                decimals=int(decimals) if isinstance(decimals, (int, float, str)) else 0,
                created_at=datetime.now()
            )
            
            return token
            
        except Exception as e:
            print(f"❌ 解析代币数据失败: {e}")
            print(f"❌ 原始数据: {token_data}")
            return None
    
    def save_tokens_to_yaml(self, tokens: List[Token], filename: str = None) -> str:
        """
        将代币信息保存到 YAML 文件
        
        Args:
            tokens: Token 对象列表
            filename: 保存的文件名（可选）
            
        Returns:
            保存的文件路径
        """
        if not tokens:
            print("⚠️  没有代币数据需要保存")
            return ""
        
        try:
            # 生成文件名
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"jupiter_tokens_{timestamp}.yaml"
            
            # 确保文件名以 .yaml 结尾
            if not filename.endswith('.yaml'):
                filename += '.yaml'
            
            # 构建完整路径
            storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage")
            os.makedirs(storage_dir, exist_ok=True)
            file_path = os.path.join(storage_dir, filename)
            
            # 转换为可序列化的字典格式
            tokens_data = []
            for token in tokens:
                token_dict = {
                    "contract_address": token.contract_address,
                    "symbol": token.symbol,
                    "name": token.name,
                    "token_supply": token.token_supply,
                    "decimals": token.decimals,
                    "created_at": token.created_at.isoformat() if token.created_at else None
                }
                tokens_data.append(token_dict)
            
            # 保存到 YAML 文件
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(tokens_data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"✅ 代币信息已保存到: {file_path}")
            print(f"📊 共保存 {len(tokens)} 个代币信息")
            
            return file_path
            
        except Exception as e:
            print(f"❌ 保存代币信息失败: {e}")
            return ""
    
    def load_tokens_from_yaml(self, file_path: str) -> List[Token]:
        """
        从 YAML 文件加载代币信息
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            Token 对象列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tokens_data = yaml.safe_load(f)
            
            if not tokens_data:
                return []
            
            tokens = []
            for token_dict in tokens_data:
                created_at = None
                if token_dict.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(token_dict['created_at'])
                    except:
                        pass
                
                token = Token(
                    contract_address=token_dict.get('contract_address', ''),
                    symbol=token_dict.get('symbol', ''),
                    name=token_dict.get('name', ''),
                    token_supply=token_dict.get('token_supply', '0'),
                    decimals=token_dict.get('decimals', 0),
                    created_at=created_at
                )
                tokens.append(token)
            
            print(f"✅ 从 {file_path} 加载了 {len(tokens)} 个代币信息")
            return tokens
            
        except Exception as e:
            print(f"❌ 加载代币信息失败: {e}")
            return []


def main():
    """主函数 - 演示用法"""
    
    # 示例代币地址（从请求 URL 中提取）
    test_tokens = [
        "HL3dJsB6BZVdQYTpRYLS94Bmd62D1SFhonMBaajUbonk",
        "BXhVjDNucDJP2B8hZZbK4YtaVLjLdQ1PtW1ATcKrbonk", 
        "7XCR94NKErD9Y6GyWiLvATftcr2ne4wXEQJ2WrzJpump"
    ]
    
    # 创建爬虫实例
    crawler = JupiterTokenCrawler()
    
    print("🚀 开始获取 Jupiter 代币信息...")
    print("=" * 50)
    
    # 获取代币信息
    tokens = crawler.get_token_info(test_tokens)
    
    if tokens:
        print("\n📋 获取到的代币信息:")
        print("=" * 50)
        for i, token in enumerate(tokens, 1):
            print(f"{i}. {token.symbol} ({token.name})")
            print(f"   地址: {token.contract_address}")
            print(f"   总供应量: {token.token_supply}")
            print(f"   小数位数: {token.decimals}")
            print()
        
        # 保存到文件
        file_path = crawler.save_tokens_to_yaml(tokens)
        
        if file_path:
            print(f"✅ 代币信息已保存到: {file_path}")
            
            # 演示加载功能
            print("\n🔄 验证保存的数据...")
            loaded_tokens = crawler.load_tokens_from_yaml(file_path)
            print(f"✅ 验证成功，加载了 {len(loaded_tokens)} 个代币")
    
    else:
        print("❌ 未获取到任何代币信息")


def get_tokens_info(token_addresses: List[str], save_to_file: bool = True) -> List[Token]:
    """
    获取代币信息的便捷函数
    
    Args:
        token_addresses: 代币合约地址列表
        save_to_file: 是否保存到文件
        
    Returns:
        Token 对象列表
    """
    crawler = JupiterTokenCrawler()
    tokens = crawler.get_token_info(token_addresses)
    
    if tokens and save_to_file:
        crawler.save_tokens_to_yaml(tokens)
    
    return tokens


def get_single_token_info(token_address: str) -> Optional[Token]:
    """
    获取单个代币信息的便捷函数
    
    Args:
        token_address: 代币合约地址
        
    Returns:
        Token 对象或 None
    """
    tokens = get_tokens_info([token_address], save_to_file=False)
    return tokens[0] if tokens else None


if __name__ == "__main__":
    main()
