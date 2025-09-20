#!/usr/bin/env python3
"""
OKX 地址代币列表爬虫 (OKXAddressTokenListCrawler)
============================================

功能: 获取地址最近交易过的代币合约地址列表
API: https://web3.okx.com/priapi/v1/dx/market/v2/pnl/token-list
用途: 分析地址的代币交易偏好，发现共同交易代币

主要方法:
- get_address_token_contracts(): 获取代币合约地址数组
- get_address_token_details(): 获取代币详细信息
- batch_get_token_contracts(): 批量处理多个地址

返回数据:
- tokenContractAddress: 代币合约地址
- tokenSymbol: 代币符号
- balance: 持有余额
- pnl: 盈亏情况
- pnlPercentage: 盈亏百分比

适用场景: GAKE系统中分析可疑地址的共同代币，识别cabal模式
"""
import requests
import json
import time
import yaml
import random
import threading
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import asdict
from datetime import datetime
import sys
import os
import uuid

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入项目模型和配置管理器
from functions.models import Address, Token
from settings.config_manager import config_manager


class OKXAddressTokenListCrawler:
    """OKX地址代币列表爬虫 - 获取地址最近交易的代币合约地址"""
    
    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化爬虫
        
        Args:
            performance_mode: 性能模式 ('conservative', 'balanced', 'high_speed', 'lightweight')
        """
        self.base_url = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/token-list"
        
        # 加载性能配置
        self.performance_config = config_manager.get_crawler_performance_config(
            'okx_address_token_list', performance_mode
        )
        
        # 如果配置不存在，使用默认平衡配置
        if not self.performance_config:
            self.performance_config = {
                'max_workers': 3,
                'base_delay': 0.5,
                'timeout': 5.0,
                'expected_speed': 2.6,
                'success_rate': 100.0,
                'description': "默认平衡配置"
            }
        
        print(f"🔧 使用性能模式: {performance_mode}")
        print(f"   {self.performance_config.get('description', '无描述')}")
        print(f"   并发数: {self.performance_config['max_workers']}")
        print(f"   延迟: {self.performance_config['base_delay']}s")
        print(f"   预期速度: {self.performance_config['expected_speed']} 地址/秒")
        
        # 为每个线程创建独立的session池
        self.session_pool = []
        self.session_lock = threading.Lock()
        
        # 随机化配置
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        
        self.device_ids = [
            "01980a38-038a-44d9-8da3-a8276bbcb5b9",
            "02471b49-149b-55ea-9ed4-b9387ccdc6ca", 
            "03562c5a-25ac-66fb-af25-ca498ddde7db",
            "04653d6b-36bd-77gc-bg36-db5a9eef8ec",
            "05744e7c-47ce-88hd-ch47-ec6baffa9fd"
        ]
        
        # 存储认证信息
        self.auth_cookie = None
        self.auth_fp_token = None
        self.auth_verify_sign = None
        self.auth_verify_token = None
        self.auth_dev_id = None
        self.auth_site_info = None
    
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
        
        # 生成时间戳
        timestamp = str(int(time.time() * 1000))
        
        headers = {
            'accept': 'application/json',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2',
            'app-type': 'web',
            'device-token': device_id,
            'devid': device_id,
            'platform': 'web',
            'priority': 'u=1, i',
            'referer': 'https://web3.okx.com/portfolio',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent,
            'x-cdn': 'https://web3.okx.com',
            'x-locale': 'en_US',
            'x-request-timestamp': timestamp,
            'x-simulated-trading': 'undefined',
            'x-utc': '0',
            'x-zkdex-env': '0'
        }
        
        session.headers.update(headers)
        session.timeout = self.performance_config['timeout']
        session.verify = False
        
        return session
    
    def _return_session(self, session: requests.Session):
        """归还session到池中"""
        with self.session_lock:
            self.session_pool.append(session)
    
    def _build_request_url(self, wallet_address: str, chain_id: int = 501, 
                          is_asc: bool = True, sort_type: int = 1,
                          filter_empty_balance: bool = False, 
                          offset: int = 0, limit: int = 50) -> str:
        """构建请求URL
        
        Args:
            wallet_address: 钱包地址
            chain_id: 链ID，默认501 (Solana)
            is_asc: 是否升序排序
            sort_type: 排序类型
            filter_empty_balance: 是否过滤空余额
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            完整的请求URL
        """
        timestamp = str(int(time.time() * 1000))
        
        params = {
            'walletAddress': wallet_address,
            'chainId': chain_id,
            'isAsc': str(is_asc).lower(),
            'sortType': sort_type,
            'filterEmptyBalance': str(filter_empty_balance).lower(),
            'offset': offset,
            'limit': limit,
            't': timestamp
        }
        
        # 构建查询参数
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        
        return f"{self.base_url}?{query_string}"
    
    def get_address_token_contracts(self, wallet_address: str, limit: int = 50) -> List[str]:
        """获取地址最近交易的代币合约地址数组
        
        Args:
            wallet_address: 钱包地址
            limit: 获取数量限制
            
        Returns:
            代币合约地址数组
        """
        session = self._get_or_create_session()
        
        try:
            url = self._build_request_url(wallet_address, limit=limit)
            
            # 添加随机延迟
            time.sleep(random.uniform(0.1, self.performance_config['base_delay']))
            
            response = session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析响应数据
            token_contracts = []
            
            if data.get('code') == 0 and 'data' in data:
                token_list = data['data'].get('tokenList', [])
                
                for token in token_list:
                    # 获取代币合约地址
                    contract_address = token.get('tokenContractAddress')
                    if contract_address:
                        token_contracts.append(contract_address)
            
            print(f"✅ 成功获取地址 {wallet_address[:8]}... 的 {len(token_contracts)} 个代币合约地址")
            
            return token_contracts
            
        except requests.RequestException as e:
            print(f"❌ 请求失败: {wallet_address[:8]}... - {str(e)}")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ 数据解析失败: {wallet_address[:8]}... - {str(e)}")
            return []
        except Exception as e:
            print(f"❌ 未知错误: {wallet_address[:8]}... - {str(e)}")
            return []
        finally:
            self._return_session(session)
    
    def get_address_token_details(self, wallet_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取地址最近交易的代币详细信息
        
        Args:
            wallet_address: 钱包地址
            limit: 获取数量限制
            
        Returns:
            代币详细信息列表
        """
        session = self._get_or_create_session()
        
        try:
            url = self._build_request_url(wallet_address, limit=limit)
            
            # 添加随机延迟
            time.sleep(random.uniform(0.1, self.performance_config['base_delay']))
            
            response = session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析响应数据
            token_details = []
            
            if data.get('code') == 0 and 'data' in data:
                token_list = data['data'].get('tokenList', [])
                
                for token in token_list:
                    token_info = {
                        'contract_address': token.get('tokenContractAddress'),
                        'symbol': token.get('tokenSymbol'),
                        'name': token.get('tokenName'),
                        'balance': token.get('balance', '0'),
                        'balance_usd': token.get('balanceUsd', '0'),
                        'pnl': token.get('pnl', '0'),
                        'pnl_usd': token.get('pnlUsd', '0'),
                        'pnl_percentage': token.get('pnlPercentage', '0'),
                        'price': token.get('price', '0'),
                        'decimals': token.get('decimals', 0),
                        'logo_url': token.get('logoUrl', ''),
                        'is_verified': token.get('isVerified', False)
                    }
                    
                    if token_info['contract_address']:
                        token_details.append(token_info)
            
            print(f"✅ 成功获取地址 {wallet_address[:8]}... 的 {len(token_details)} 个代币详细信息")
            
            return token_details
            
        except requests.RequestException as e:
            print(f"❌ 请求失败: {wallet_address[:8]}... - {str(e)}")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ 数据解析失败: {wallet_address[:8]}... - {str(e)}")
            return []
        except Exception as e:
            print(f"❌ 未知错误: {wallet_address[:8]}... - {str(e)}")
            return []
        finally:
            self._return_session(session)
    
    def batch_get_token_contracts(self, wallet_addresses: List[str], 
                                 limit: int = 50) -> Dict[str, List[str]]:
        """批量获取多个地址的代币合约地址
        
        Args:
            wallet_addresses: 钱包地址列表
            limit: 每个地址获取的代币数量限制
            
        Returns:
            地址到代币合约地址数组的映射
        """
        print(f"🚀 开始批量获取 {len(wallet_addresses)} 个地址的代币合约地址...")
        start_time = time.time()
        
        results = {}
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.performance_config['max_workers']) as executor:
            # 提交任务
            future_to_address = {
                executor.submit(self.get_address_token_contracts, addr, limit): addr 
                for addr in wallet_addresses
            }
            
            # 收集结果
            for future in as_completed(future_to_address):
                address = future_to_address[future]
                try:
                    token_contracts = future.result()
                    results[address] = token_contracts
                except Exception as exc:
                    print(f"❌ 地址 {address[:8]}... 处理失败: {exc}")
                    results[address] = []
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 统计信息
        total_tokens = sum(len(contracts) for contracts in results.values())
        success_count = len([r for r in results.values() if r])
        
        print(f"✅ 批量获取完成!")
        print(f"   处理地址: {len(wallet_addresses)}")
        print(f"   成功地址: {success_count}")
        print(f"   获取代币: {total_tokens}")
        print(f"   用时: {elapsed_time:.2f}秒")
        print(f"   速度: {len(wallet_addresses)/elapsed_time:.2f} 地址/秒")
        
        return results
    
    def save_token_contracts_to_yaml(self, data: Dict[str, List[str]], 
                                   filename: Optional[str] = None) -> str:
        """保存代币合约地址数据到YAML文件
        
        Args:
            data: 地址到代币合约地址数组的映射
            filename: 文件名，如果为None则自动生成
            
        Returns:
            保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"token_contracts_{timestamp}.yaml"
        
        # 确保storage目录存在
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'storage')
        os.makedirs(storage_dir, exist_ok=True)
        
        filepath = os.path.join(storage_dir, filename)
        
        # 添加元数据
        output_data = {
            'metadata': {
                'crawler': 'OKXAddressTokenListCrawler',
                'timestamp': datetime.now().isoformat(),
                'total_addresses': len(data),
                'total_tokens': sum(len(contracts) for contracts in data.values())
            },
            'data': data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, allow_unicode=True)
        
        print(f"💾 数据已保存到: {filepath}")
        return filepath


def main():
    """主函数 - 示例用法"""
    # 初始化爬虫
    crawler = OKXAddressTokenListCrawler(performance_mode='high_speed')
    
    # 示例地址
    test_address = "AK2rUWkiZ6ZohFb7UQ6EbRN22m1kYKbYGi3X9USXGrMA"
    
    print("=" * 60)
    print("OKX地址代币列表爬虫测试")
    print("=" * 60)
    
    # 测试单个地址
    print("\n1. 测试获取单个地址的代币合约地址:")
    token_contracts = crawler.get_address_token_contracts(test_address, limit=10)
    print(f"代币合约地址: {token_contracts}")
    
    # 测试获取详细信息
    print("\n2. 测试获取单个地址的代币详细信息:")
    token_details = crawler.get_address_token_details(test_address, limit=5)
    for i, token in enumerate(token_details[:3]):  # 只显示前3个
        print(f"  代币 {i+1}: {token['symbol']} ({token['contract_address'][:8]}...)")
    
    # 测试批量处理
    print("\n3. 测试批量处理:")
    test_addresses = [test_address]  # 可以添加更多地址
    results = crawler.batch_get_token_contracts(test_addresses, limit=5)
    
    # 保存结果
    if results:
        print("\n4. 保存结果到文件:")
        filepath = crawler.save_token_contracts_to_yaml(results)


if __name__ == "__main__":
    main()