#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OKX DEX 代币交易历史爬虫
获取目标代币最近交易的地址数组
"""

import requests
import json
import time
import random
import threading
import sys
import os
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入项目模型和配置管理器
from settings.config_manager import ConfigManager


class OKXTokenTradingHistoryCrawler:
    """OKX DEX 代币交易历史爬虫"""
    
    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化爬虫
        
        Args:
            performance_mode: 性能模式 ('fast', 'balanced', 'stable')
        """
        self.base_url = "https://web3.okx.com/priapi/v1/dx/market/v2/trading-history/filter-list"
        
        # 性能配置管理
        self.config_manager = ConfigManager()
        self.performance_config = self.config_manager.get_performance_config(
            'okx_token_trading_history', performance_mode
        )
        
        # 如果配置不存在，使用默认平衡配置
        if not self.performance_config:
            self.performance_config = {
                'max_workers': 3,
                'base_delay': 0.5,
                'timeout': 10.0,
                'expected_speed': 2.0,
                'success_rate': 100.0,
                'description': "默认平衡配置"
            }
        
        print(f"🔧 使用性能模式: {performance_mode}")
        print(f"   {self.performance_config.get('description', '无描述')}")
        print(f"   并发数: {self.performance_config['max_workers']}")
        print(f"   延迟: {self.performance_config['base_delay']}s")
        print(f"   预期速度: {self.performance_config['expected_speed']} 请求/秒")
        
        # Session池管理
        self.session_pool = []
        self.session_lock = threading.Lock()
        
        # 设备和User-Agent池
        self.device_ids = [
            '01980a38-038a-44d9-8da3-a8276bbcb5b9',
            '12345678-1234-1234-1234-123456789abc',
            '87654321-4321-4321-4321-cba987654321',
            'abcd1234-5678-9012-3456-789abcdef012'
        ]
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        ]
        
        # 认证信息
        self.auth_verify_token = None
        self.auth_dev_id = None
        self.auth_site_info = None
        self.fptoken = None
        self.fptoken_signature = None
    
    def set_auth_tokens(self, fptoken: str = None, fptoken_signature: str = None):
        """设置认证token
        
        Args:
            fptoken: 指纹token
            fptoken_signature: 指纹签名
        """
        self.fptoken = fptoken
        self.fptoken_signature = fptoken_signature
        print(f"🔐 已设置认证令牌")
    
    def _generate_fptoken_headers(self) -> Dict[str, str]:
        """生成指纹认证相关的headers"""
        headers = {}
        
        if self.fptoken:
            headers['x-fptoken'] = self.fptoken
            
        if self.fptoken_signature:
            headers['x-fptoken-signature'] = self.fptoken_signature
            
        return headers
    
    def _handle_api_response(self, response: requests.Response, token_address: str) -> Dict[str, Any]:
        """处理API响应并提供详细的错误信息
        
        Args:
            response: requests响应对象
            token_address: 代币地址
            
        Returns:
            解析后的JSON数据或空字典
        """
        try:
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    return data
                else:
                    print(f"⚠️ API返回错误 (代币: {token_address})")
                    print(f"   错误代码: {data.get('code')}")
                    print(f"   错误信息: {data.get('msg', '未知错误')}")
                    if 'data' in data:
                        print(f"   数据字段: {data['data']}")
                    return {}
            else:
                print(f"❌ HTTP请求失败 (代币: {token_address})")
                print(f"   状态码: {response.status_code}")
                print(f"   响应文本: {response.text[:200]}...")
                return {}
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败 (代币: {token_address}): {str(e)}")
            print(f"   响应文本: {response.text[:200]}...")
            return {}
        except Exception as e:
            print(f"❌ 处理响应时出错 (代币: {token_address}): {str(e)}")
            return {}

    def _get_or_create_session(self) -> requests.Session:
        """获取或创建session实例"""
        with self.session_lock:
            if self.session_pool:
                return self.session_pool.pop()
            else:
                return self._create_new_session()
    
    def _create_new_session(self) -> requests.Session:
        """创建新的session实例"""
        session = requests.Session()
        
        # 随机化设备信息
        device_id = random.choice(self.device_ids)
        user_agent = random.choice(self.user_agents)
        
        # 生成时间戳和签名
        timestamp = str(int(time.time() * 1000))
        
        # 基础cookie模板
        base_cookies = (
            f'devId={device_id}; '
            'ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; '
            'ok_prefer_udColor=0; ok_prefer_udTimeZone=0; '
            f'fingerprint_id={device_id}; '
            '_gcl_au=1.1.1005719754.1755091396; connectedWallet=1; '
            'first_ref=https%3A%2F%2Fweb3.okx.com%2Fzh-hans%2Fboost%2Frewards; '
            'locale=en_US; preferLocale=en_US; '
            '_ym_uid=1747137423698075177; _ym_d=1757936348; '
            'ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; '
            'mse=nf=9|se=0; ok_global={%22g_t%22:2%2C%22okg_m%22:%22xl%22}; '
            f'tmx_session_id=60526eyniu8_1758172864386; '
            'fp_s=0; okg.currentMedia=xl; connected=1; '
            'ok_prefer_exp=1'
        )
        
        headers = {
            'accept': 'application/json',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2',
            'app-type': 'web',
            'content-type': 'application/json',
            'cookie': base_cookies,
            'devid': device_id,
            'origin': 'https://web3.okx.com',
            'priority': 'u=1, i',
            'referer': 'https://web3.okx.com/token/solana/AiM8uL5p7YVeKxGaEayYy7zXyyfJMpTRecqNpMeApump',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent,
            'x-cdn': 'https://web3.okx.com',
            'x-id-group': f'{timestamp}-c-1',
            'x-locale': 'en_US',
            'x-request-timestamp': timestamp,
            'x-simulated-trading': 'undefined',
            'x-site-info': '==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye',
            'x-utc': '0',
            'x-zkdex-env': '0'
        }
        
        # 添加认证headers（如果有的话）
        auth_headers = self._generate_fptoken_headers()
        headers.update(auth_headers)
        
        session.headers.update(headers)
        return session
    
    def _return_session(self, session: requests.Session):
        """返回session到池中"""
        with self.session_lock:
            if len(self.session_pool) < 10:  # 限制池大小
                self.session_pool.append(session)
    
    def _build_request_payload(self, token_contract, limit=20):
        """构建请求payload"""
        return {
            "desc": True,
            "orderBy": "timestamp",
            "limit": limit,
            "tradingHistoryFilter": {
                "chainId": "501",
                "tokenContractAddress": token_contract,
                "type": "0",
                "currentUserWalletAddress": "",
                "userAddressList": [],
                "volumeMin": "",
                "volumeMax": "",
                "priceMin": "",
                "priceMax": "",
                "amountMin": "",
                "amountMax": ""
            }
        }
    
    def get_token_trading_addresses(self, token_address: str,
                                  chain_id: int = 501,
                                  limit: int = 50) -> List[str]:
        """获取代币最近交易的地址数组
        
        Args:
            token_address: 代币合约地址
            chain_id: 链ID
            limit: 获取数量限制
            
        Returns:
            交易地址列表
        """
        session = self._get_or_create_session()
        
        try:
            # 构建请求URL和payload
            timestamp = str(int(time.time() * 1000))
            url = f"{self.base_url}?t={timestamp}"
            payload = self._build_request_payload(token_address, limit)
            
            # 添加随机延迟
            time.sleep(random.uniform(0.1, self.performance_config['base_delay']))
            
            # 发送POST请求
            print(f"[get_token_trading_addresses] 发送请求到: {url}")
            print(f"[get_token_trading_addresses] Payload: {payload}")
            print(f"[get_token_trading_addresses] Headers: {dict(session.headers)}")
            
            response = session.post(
                url, 
                json=payload,
                timeout=self.performance_config['timeout']
            )
            
            print(f"[get_token_trading_addresses] 响应状态码: {response.status_code}")
            print(f"[get_token_trading_addresses] 响应内容: {response.text[:1000]}...")
            
            # 使用新的响应处理方法
            parsed_data = self._handle_api_response(response, token_address)
            
            if parsed_data:
                # 修复：API返回的数据结构是 data.list，不是 data.rows
                trading_list = parsed_data.get('data', {}).get('list', [])
                
                # 提取交易地址
                addresses = []
                for trade in trading_list:
                    # 从测试输出可以看到，实际的用户地址字段是 'userAddress'
                    if 'userAddress' in trade and trade['userAddress']:
                        addresses.append(trade['userAddress'])
                    
                    # 也检查其他可能的地址字段（保留原有逻辑以防万一）
                    if 'fromAddress' in trade and trade['fromAddress']:
                        addresses.append(trade['fromAddress'])
                    if 'toAddress' in trade and trade['toAddress']:
                        addresses.append(trade['toAddress'])
                    if 'walletAddress' in trade and trade['walletAddress']:
                        addresses.append(trade['walletAddress'])
                    if 'senderAddress' in trade and trade['senderAddress']:
                        addresses.append(trade['senderAddress'])
                    if 'receiverAddress' in trade and trade['receiverAddress']:
                        addresses.append(trade['receiverAddress'])
                
                # 去重并返回
                unique_addresses = list(set(addresses))
                print(f"✅ 成功获取代币 {token_address} 的 {len(unique_addresses)} 个交易地址")
                return unique_addresses
            else:
                print(f"❌ 无法获取有效数据")
                return []
                
        except Exception as e:
            print(f"❌ 获取代币交易地址失败: {str(e)}")
            return []
        finally:
            self._return_session(session)

    def get_unique_trading_addresses(self, token_address: str,
                                   chain_id: int = 501,
                                   target_count: int = 50) -> List[str]:
        """获取精确数量的唯一交易地址

        Args:
            token_address: 代币合约地址
            chain_id: 链ID
            target_count: 目标获取的唯一地址数量

        Returns:
            唯一交易地址列表
        """
        unique_addresses = set()
        batch_size = target_count + 10  # 多获取一些以应对重复
        max_attempts = 3

        for attempt in range(max_attempts):
            # 获取更大批次的交易记录
            current_limit = batch_size * (attempt + 1)
            addresses = self.get_token_trading_addresses(token_address, chain_id, current_limit)

            if addresses:
                unique_addresses.update(addresses)
                print(f"尝试 {attempt + 1}: 获得 {len(unique_addresses)} 个唯一地址")

                # 如果获得足够的唯一地址，返回前target_count个
                if len(unique_addresses) >= target_count:
                    result = list(unique_addresses)[:target_count]
                    print(f"✅ 成功获取 {len(result)} 个唯一交易地址")
                    return result

            time.sleep(1)  # 避免请求过频

        # 如果无法获取足够数量，返回所有可用的
        result = list(unique_addresses)
        print(f"⚠️ 仅获取到 {len(result)} 个唯一地址（目标：{target_count}）")
        return result

    def get_token_trading_details(self, token_address: str, 
                                chain_id: int = 501, 
                                limit: int = 50) -> List[Dict[str, Any]]:
        """获取代币最近交易的详细信息
        
        Args:
            token_address: 代币合约地址
            chain_id: 链ID
            limit: 获取数量限制
            
        Returns:
            交易详细信息列表
        """
        session = self._get_or_create_session()
        
        try:
            # 构建请求URL和payload
            timestamp = str(int(time.time() * 1000))
            url = f"{self.base_url}?t={timestamp}"
            payload = self._build_request_payload(token_address, limit)
            
            # 添加随机延迟
            time.sleep(random.uniform(0.1, self.performance_config['base_delay']))
            
            # 发送POST请求
            response = session.post(
                url, 
                json=payload,
                timeout=self.performance_config['timeout']
            )
            
            # 使用新的响应处理方法
            parsed_data = self._handle_api_response(response, token_address)
            
            if parsed_data:
                # 修复：API返回的数据结构是 data.list，不是 data.rows
                trading_list = parsed_data.get('data', {}).get('list', [])
                print(f"✅ 成功获取代币 {token_address} 的 {len(trading_list)} 条交易记录")
                return trading_list
            else:
                print(f"❌ 无法获取有效数据")
                return []
                
        except Exception as e:
            print(f"❌ 获取代币交易详情失败: {str(e)}")
            return []
        finally:
            self._return_session(session)
    
    def get_multiple_tokens_trading_addresses(self, token_addresses: List[str], 
                                            chain_id: int = 501,
                                            limit: int = 50) -> Dict[str, List[str]]:
        """批量获取多个代币的交易地址
        
        Args:
            token_addresses: 代币合约地址列表
            chain_id: 链ID
            limit: 每个代币获取的交易数量限制
            
        Returns:
            {代币地址: [交易地址列表]} 的字典
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.performance_config['max_workers']) as executor:
            # 提交所有任务
            future_to_token = {
                executor.submit(self.get_token_trading_addresses, addr, chain_id, limit): addr 
                for addr in token_addresses
            }
            
            # 收集结果
            for future in as_completed(future_to_token):
                token_addr = future_to_token[future]
                try:
                    trading_addresses = future.result()
                    results[token_addr] = trading_addresses
                    print(f"✅ {token_addr}: {len(trading_addresses)} 个交易地址")
                except Exception as e:
                    print(f"❌ 处理代币 {token_addr} 时出错: {str(e)}")
                    results[token_addr] = []
        
        return results


def test_crawler():
    """测试爬虫功能"""
    print("🧪 开始测试 OKX 代币交易历史爬虫...")
    
    crawler = OKXTokenTradingHistoryCrawler()
    
    # 测试代币地址 (使用您提供的真实代币地址)
    test_token = "AiM8uL5p7YVeKxGaEayYy7zXyyfJMpTRecqNpMeApump"
    
    print(f"\n📊 测试获取代币交易地址...")
    print(f"测试代币地址: {test_token}")
    
    # 测试API请求构建
    payload = crawler._build_request_payload(test_token, 10)
    print(f"请求payload: {payload}")
    
    trading_addresses = crawler.get_token_trading_addresses(test_token, limit=10)
    print(f"返回结果: {trading_addresses}")
    print(f"交易地址数量: {len(trading_addresses) if trading_addresses else 0}")
    
    if trading_addresses:
        print("前5个交易地址:")
        for i, addr in enumerate(trading_addresses[:5]):
            print(f"  {i+1}. {addr}")
    
    print(f"\n📊 测试获取代币交易详情...")
    trading_details = crawler.get_token_trading_details(test_token, limit=5)
    print(f"交易详情数量: {len(trading_details) if trading_details else 0}")
    
    if trading_details:
        print("第一条交易详情的字段:")
        first_trade = trading_details[0]
        for key, value in first_trade.items():
            print(f"  {key}: {value}")
    else:
        print("❌ 未获取到交易详情")
    
    # 测试批量获取
    print(f"\n📊 测试批量获取代币交易地址...")
    test_tokens = [test_token]
    batch_results = crawler.get_multiple_tokens_trading_addresses(test_tokens, limit=5)
    print(f"批量结果: {batch_results}")


if __name__ == "__main__":
    test_crawler()
