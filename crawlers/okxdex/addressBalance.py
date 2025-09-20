#!/usr/bin/env python3
"""
OKX 地址资产余额爬虫 (OKXAddressBalanceCrawler)
==============================================

功能: 获取钱包地址的所有资产信息
API: https://web3.okx.com/priapi/v2/wallet/asset/profile/all/explorer
用途: 分析地址持仓结构，计算总资产价值

主要方法:
- get_address_balance(): 获取地址所有代币余额
- get_balance_summary(): 获取资产汇总信息
- 返回每个代币的余额、价值、价格等详细信息

返回数据:
- tokenSymbol: 代币符号
- balance: 持有数量
- balanceUsd: 美元价值
- price: 当前价格
- logoUrl: 代币图标
- isVerified: 是否验证

适用场景: 分析地址财富水平，识别大户行为
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
from functions.models import Address, TokenBalance
from settings.config_manager import config_manager


class OKXAddressBalanceCrawler:
    """OKX地址资产爬虫 - 支持多线程高速爬取"""
    
    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化爬虫
        
        Args:
            performance_mode: 性能模式 ('conservative', 'balanced', 'high_speed', 'lightweight')
        """
        self.base_url = "https://web3.okx.com/priapi/v2/wallet/asset/profile/all/explorer"
        
        # 加载性能配置
        self.performance_config = config_manager.get_crawler_performance_config(
            'okx_address_balance', performance_mode
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
    
    def _return_session(self, session: requests.Session):
        """归还session到池中"""
        with self.session_lock:
            self.session_pool.append(session)
    
    def _create_new_session(self) -> requests.Session:
        """创建新的session实例"""
        session = requests.Session()
        
        # 随机选择User-Agent和设备ID
        user_agent = random.choice(self.user_agents)
        device_id = random.choice(self.device_ids)
        
        session.headers.update({
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2",
            "app-type": "web",
            "content-type": "application/json",
            "device-token": device_id,
            "devid": device_id,
            "origin": "https://web3.okx.com",
            "platform": "web",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": user_agent,
            "x-cdn": "https://web3.okx.com",
            "x-locale": "en_US",
            "x-simulated-trading": "undefined",
            "x-utc": "0",
            "x-zkdex-env": "0",
        })
        
        return session

    def set_auth(self, cookie: str, fp_token: str, verify_sign: str, 
                 verify_token: str, dev_id: str, site_info: str):
        """设置认证信息"""
        self.auth_cookie = cookie
        self.auth_fp_token = fp_token
        self.auth_verify_sign = verify_sign
        self.auth_verify_token = verify_token
        self.auth_dev_id = dev_id
        self.auth_site_info = site_info
    
    def _update_dynamic_headers(self, session: requests.Session, wallet_address: str):
        """更新动态请求头"""
        current_timestamp = int(time.time() * 1000)
        
        # 添加随机延迟模拟真实用户行为
        jitter = random.randint(-100, 100)
        timestamp_with_jitter = current_timestamp + jitter
        
        # 随机生成一些动态参数
        request_id = str(uuid.uuid4())
        group_id = f"{timestamp_with_jitter}-c-{random.randint(10, 20)}"
        
        # 使用存储的认证信息或默认值
        cookie_string = self.auth_cookie if self.auth_cookie else (
            "devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; "
            "ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; "
            "locale=en_US; "
            "ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; "
            "ok_prefer_udColor=0; "
            "ok_prefer_udTimeZone=0; "
            "fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; "
            "first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; "
            "ok_global={%22g_t%22:2}; "
            "_gcl_au=1.1.1005719754.1755091396; "
            "connectedWallet=1; "
            "_gid=GA1.2.950489538.1757092345; "
            "mse=nf=8|se=0; "
            "connected=1; "
            "fp_s=0; "
            "okg.currentMedia=xl; "
            "_gat_UA-35324627-3=1; "
            "ok_prefer_exp=1; "
            "_ga=GA1.1.2083537763.1750302376"
        )
        
        fp_token = self.auth_fp_token if self.auth_fp_token else "eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg"
        
        site_info = self.auth_site_info if self.auth_site_info else "==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye"
        
        headers_update = {
            "referer": f"https://web3.okx.com/portfolio/{wallet_address}/analysis",
            "x-request-timestamp": str(timestamp_with_jitter),
            "x-id-group": group_id,
            "x-request-id": request_id,
            "cookie": cookie_string,
            "b-locale": "en_US",
            "x-site-info": site_info,
            "x-fptoken": fp_token,
            "x-fptoken-signature": "{P1363}a+WvAdH7qkrC168mAWUm9m6Ij5vnXVeh83m1fL+bYGwYhtIpK92pOSWwIbXmILxMj93b7GYNGE6EEm4Ei7f8IA==",
            "x-brokerid": "0",
        }
        
        # 如果有验证签名和令牌，添加它们
        if self.auth_verify_sign:
            headers_update["ok-verify-sign"] = self.auth_verify_sign
        if self.auth_verify_token:
            headers_update["ok-verify-token"] = self.auth_verify_token
            
        session.headers.update(headers_update)
    
    def fetch_multiple_addresses_fast(self, wallet_addresses: List[str], 
                                     chain_id: int = 501, 
                                     max_workers: int = None,
                                     timeout_per_request: float = None,
                                     debug: bool = False) -> Dict[str, Optional[Address]]:
        """
        高速批量获取多个地址的资产信息 - 使用配置优化
        
        Args:
            wallet_addresses: 钱包地址列表
            chain_id: 链ID，默认501(Solana)
            max_workers: 最大并发线程数，None时使用配置值
            timeout_per_request: 每个请求的超时时间(秒)，None时使用配置值
            debug: 是否开启调试模式
            
        Returns:
            地址映射到Address对象的字典
        """
        if not wallet_addresses:
            return {}
        
        # 使用配置中的参数，如果没有传入的话
        if max_workers is None:
            max_workers = self.performance_config['max_workers']
        if timeout_per_request is None:
            timeout_per_request = self.performance_config['timeout']
        
        base_delay = self.performance_config['base_delay']
        
        print(f"🚀 开始高成功率批量爬取 {len(wallet_addresses)} 个地址资产...")
        print(f"⚡ 使用 {max_workers} 个线程并发处理（优化成功率）")
        
        results = {}
        start_time = time.time()
        
        # 使用智能延迟策略提高成功率
        def fetch_with_smart_delay(address: str, index: int) -> Tuple[str, Optional[Address]]:
            # 基于索引的智能延迟，避免所有请求同时发起
            delay_factor = (index % max_workers) * base_delay
            jitter = random.uniform(0.1, base_delay * 0.5)
            delay = delay_factor + jitter
            time.sleep(delay)
            
            try:
                result = self.fetch_address_assets(address, chain_id=chain_id, debug=debug)
                return address, result
            except Exception as e:
                if debug:
                    print(f"❌ 处理地址 {address} 时出错: {e}")
                return address, None
        
        # 使用线程池执行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务，带索引用于智能延迟
            future_to_address = {
                executor.submit(fetch_with_smart_delay, addr, i): addr 
                for i, addr in enumerate(wallet_addresses)
            }
            
            # 收集结果
            completed = 0
            failed_count = 0
            
            for future in as_completed(future_to_address, timeout=len(wallet_addresses) * timeout_per_request):
                address = future_to_address[future]
                completed += 1
                
                try:
                    addr, result = future.result()
                    results[addr] = result
                    
                    if result:
                        status = "✅"
                    else:
                        status = "❌"
                        failed_count += 1
                        
                    # 显示进度，包含成功率
                    success_rate = ((completed - failed_count) / completed) * 100
                    print(f"  {status} {completed}/{len(wallet_addresses)}: {addr[:8]}... (成功率: {success_rate:.1f}%)")
                    
                except Exception as e:
                    results[address] = None
                    failed_count += 1
                    success_rate = ((completed - failed_count) / completed) * 100
                    print(f"  ❌ {completed}/{len(wallet_addresses)}: {address[:8]}... - 错误: {e} (成功率: {success_rate:.1f}%)")
        
        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in results.values() if r is not None)
        final_success_rate = (success_count / len(wallet_addresses)) * 100
        
        print(f"✅ 批量爬取完成!")
        print(f"⏱️  总耗时: {elapsed_time:.2f} 秒")
        print(f"📊 最终成功率: {success_count}/{len(wallet_addresses)} ({final_success_rate:.1f}%)")
        print(f"🚀 平均速度: {len(wallet_addresses)/elapsed_time:.1f} 地址/秒")
        
        if final_success_rate >= 90:
            print(f"🎉 成功率达到 {final_success_rate:.1f}% - 优秀!")
        elif final_success_rate >= 70:
            print(f"👍 成功率达到 {final_success_rate:.1f}% - 良好!")
        else:
            print(f"⚠️  成功率 {final_success_rate:.1f}% - 需要进一步优化")
        
        return results
    
    def _make_request_with_retry(self, session: requests.Session, url: str, 
                                params: dict, payload: dict, 
                                max_retries: int = 3, debug: bool = False) -> Optional[dict]:
        """带重试机制的网络请求"""
        for attempt in range(max_retries):
            try:
                # 每次重试前随机延迟
                if attempt > 0:
                    delay = random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    if debug:
                        print(f"    第{attempt + 1}次重试...")
                
                response = session.post(
                    url,
                    params=params,
                    json=payload,
                    timeout=(2, 5),  # 连接超时2秒，读取超时5秒
                    verify=False  # 禁用SSL验证
                )
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        if debug:
                            print(f"    JSON解析失败，尝试{attempt + 1}/{max_retries}")
                        continue
                        
                elif response.status_code == 429:
                    # 遇到限流，延长等待时间
                    wait_time = 2 ** attempt + random.uniform(1, 3)
                    if debug:
                        print(f"    遇到限流(429)，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    if debug:
                        print(f"    HTTP错误: {response.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                if debug:
                    print(f"    请求超时，尝试{attempt + 1}/{max_retries}")
                continue
                
            except requests.exceptions.ConnectionError:
                if debug:
                    print(f"    连接错误，尝试{attempt + 1}/{max_retries}")
                continue
                
            except Exception as e:
                if debug:
                    print(f"    未知错误: {e}")
                continue
        
        return None

    def fetch_address_assets(self, wallet_address: str, chain_id: int = 501, limit: int = 20, debug: bool = False) -> Optional[Address]:
        """
        获取地址资产信息
        
        Args:
            wallet_address: 钱包地址
            chain_id: 链ID，默认501(Solana)
            limit: 获取代币数量限制，默认20
            debug: 是否开启调试模式
            
        Returns:
            Address对象或None
        """
        session = self._get_or_create_session()
        
        try:
            # 更新动态请求头
            self._update_dynamic_headers(session, wallet_address)
            
            # 构建请求参数
            current_timestamp = int(time.time() * 1000)
            params = {
                "t": current_timestamp + random.randint(-50, 50)  # 添加随机扰动
            }
            
            # 使用正确的payload格式，添加随机化
            payload = {
                "userUniqueId": str(uuid.uuid4()),  # 随机化用户ID
                "hideValueless": random.choice([True, False]),  # 随机化参数
                "address": wallet_address,
                "forceRefresh": random.choice([True, False]),  # 随机化刷新
                "page": 1,
                "limit": limit,
                "chainIndexes": [chain_id]
            }
            
            if debug:
                print(f"请求URL: {self.base_url}")
                print(f"请求参数: {params}")
                print(f"请求体: {json.dumps(payload, indent=2)}")
            
            # 使用重试机制发送请求
            data = self._make_request_with_retry(
                session, 
                self.base_url, 
                params, 
                payload, 
                max_retries=5,  # 增加重试次数
                debug=debug
            )
            
            if data:
                # 解析响应数据
                result = self._parse_assets_data(data, wallet_address, chain_id, debug)
                return result
            else:
                if debug:
                    print(f"请求失败，无法获取数据")
                return None
                
        except Exception as e:
            if debug:
                print(f"处理地址 {wallet_address} 时出错: {e}")
            return None
        finally:
            # 归还session到池中
            self._return_session(session)
    
    def _parse_assets_data(self, data: Dict[str, Any], wallet_address: str, chain_id: int, debug: bool = False) -> Optional[Address]:
        """解析资产数据 - 增强容错性"""
        try:
            # 检查响应结构
            if not isinstance(data, dict):
                if debug:
                    print("响应数据不是字典格式")
                return None
                
            if data.get("code") != 0:
                if debug:
                    print(f"API返回错误: {data.get('msg', '未知错误')}")
                return None
            
            result = data.get("data", {})
            if not isinstance(result, dict):
                if debug:
                    print("数据字段不是字典格式")
                return None
            
            # 获取总资产信息 - 安全处理
            tokens_info = result.get("tokens", {})
            if not isinstance(tokens_info, dict):
                tokens_info = {}
            
            token_count = tokens_info.get("total", 0)
            
            # 从walletAssetSummary获取汇总信息（如果存在）
            wallet_summary = result.get("walletAssetSummary", {})
            if wallet_summary is None or not isinstance(wallet_summary, dict):
                wallet_summary = {}
            
            total_amount = str(wallet_summary.get("tokenTotalCurrencyAmount", "0"))
            defi_amount = str(wallet_summary.get("defiTotalCurrencyAmount", "0"))
            nft_amount = str(wallet_summary.get("nftTotalCurrencyAmount", "0"))
            
            # 创建地址对象
            address = Address(
                address=wallet_address,
                note=f"总资产: ${total_amount}, 代币: {token_count}, DeFi: ${defi_amount}, NFT: ${nft_amount}",
                tag="爬取资产"
            )
            
            # 解析代币资产列表 - 使用正确的路径并增强容错性
            assets_list = tokens_info.get("tokenlist", [])
            if assets_list is None:
                assets_list = []
            
            if debug:
                print(f"找到 {len(assets_list)} 种代币")
            
            for i, asset_data in enumerate(assets_list):
                if not isinstance(asset_data, dict):
                    continue
                    
                try:
                    # 提取基本信息
                    token_symbol = asset_data.get("symbol", "")
                    coin_amount = str(asset_data.get("coinAmount", "0"))
                    currency_amount = str(asset_data.get("currencyAmount", "0"))
                    
                    # 从coinBalanceDetails获取详细信息
                    coin_details = asset_data.get("coinBalanceDetails", [])
                    if coin_details is None:
                        coin_details = []
                    
                    if coin_details and isinstance(coin_details, list) and len(coin_details) > 0:
                        detail = coin_details[0]  # 取第一个详情
                        if isinstance(detail, dict):
                            token_address = detail.get("address", "")
                        else:
                            token_address = ""
                    else:
                        token_address = ""
                    
                    # 检查是否为原生代币(SOL)
                    is_native = (token_symbol.upper() == "SOL" or 
                               token_address.upper() == "SOL")
                    
                    if is_native:
                        # SOL作为原生代币，使用特殊标识
                        address.add_balance("SOL", coin_amount, currency_amount)
                        if debug:
                            print(f"发现原生代币 SOL: {coin_amount} (${currency_amount})")
                    else:
                        # 添加代币余额
                        if token_address:  # 只有有地址的代币才添加
                            address.add_balance(token_address, coin_amount, currency_amount)
                            
                            if debug and i < 5:  # 只显示前5个代币的详情
                                print(f"代币 {i+1}: {token_symbol} - {coin_amount} (${currency_amount})")
                
                except Exception as e:
                    if debug:
                        print(f"解析第{i+1}个代币时出错: {e}")
                    continue
            
            # 检查是否有DeFi资产 - 安全处理空值
            defis = result.get("defis")
            if defis is None:
                defis = []
            defi_total = sum(float(defi.get("balance", "0")) for defi in defis if defi and isinstance(defi, dict))
            
            # 检查是否有NFT资产 - 安全处理空值
            nfts = result.get("nfts")
            if nfts is None:
                nfts = []
            nft_total = 0
            for nft in nfts:
                if nft and isinstance(nft, dict):
                    try:
                        nft_total += float(nft.get("valuation", "0"))
                    except (ValueError, TypeError):
                        continue
            
            # 更新note以包含更多信息
            wallet_summary_safe = result.get("walletAssetSummary")
            if wallet_summary_safe is None or not isinstance(wallet_summary_safe, dict):
                wallet_summary_safe = {}
            total_value = str(wallet_summary_safe.get("tokenTotalCurrencyAmount", "0"))
            address.note = f"总资产: ${total_value}, 代币: {len(address.balances)}, DeFi: ${defi_total:.2f}, NFT: ${nft_total:.2f}"
            
            if debug:
                print(f"\n成功解析资产数据:")
                print(f"  - 总资产价值: ${total_value}")
                print(f"  - 持有代币种类: {len(address.balances)}")
                if defi_total > 0:
                    print(f"  - DeFi资产价值: ${defi_total:.2f}")
                if nft_total > 0:
                    print(f"  - NFT资产价值: ${nft_total:.2f}")
            
            return address
            
        except Exception as e:
            if debug:
                print(f"解析资产数据时出错: {e}")
                import traceback
                traceback.print_exc()
            return None
    
    def save_to_file(self, address: Address, filename: Optional[str] = None) -> bool:
        """保存数据到文件"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                short_address = address.address[:8]
                filename = f"storage/address_{short_address}_{timestamp}.yaml"
            
            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # 转换为字典格式
            data = asdict(address)
            
            # 保存到YAML文件
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            print(f"数据已保存到: {filename}")
            return True
            
        except Exception as e:
            print(f"保存文件时出错: {e}")
            return False


def main():
    """主函数 - 示例用法"""
    crawler = OKXAddressBalanceCrawler()
    
    print("=== OKX 地址资产爬虫 - 高速版 ===")
    
    # 示例地址列表 - 测试多个Solana地址
    test_addresses = [
        "4Be9CvxqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7t",
        "A54Px5ZmqHW6BYhRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7u", 
        "DCBzkdY6qHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7v",
        "DNfuF1L6qHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7w",
        "5j8QfEqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7x",
        "6k9RgFrHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7y",
        "7l0ShGsHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7z",
        "8m1TiHtHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha8a",
        "9n2UjIuHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha8b",
        "0o3VkJvHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha8c"
    ]
    
    print(f"准备爬取 {len(test_addresses)} 个地址的资产信息")
    print("使用多线程高速模式...")
    
    # 批量爬取
    results = crawler.fetch_multiple_addresses_fast(
        test_addresses, 
        max_workers=10,
        debug=False
    )
    
    print("\n=== 爬取结果汇总 ===")
    success_count = 0
    for addr, result in results.items():
        short_addr = addr[:8] + "..." + addr[-4:]
        if result:
            success_count += 1
            token_count = len(result.balances)
            print(f"✅ {short_addr}: {token_count} 种代币")
            if result.note:
                print(f"   {result.note}")
        else:
            print(f"❌ {short_addr}: 获取失败")
    
    print(f"\n📊 总结:")
    print(f"成功: {success_count}/{len(test_addresses)} 个地址")
    print(f"成功率: {success_count/len(test_addresses)*100:.1f}%")
    
    # 单个地址详细测试
    print("\n=== 单个地址详细测试 ===")
    test_address = "4Be9CvxqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7t"
    print(f"开始爬取地址资产: {test_address}")
    
    address = crawler.fetch_address_assets(test_address, debug=False)
    
    if address:
        print("\n=== 地址资产详情 ===")
        print(f"钱包地址: {address.address}")
        print(f"备注: {address.note}")
        print(f"标签: {address.tag}")
        print(f"持有代币数量: {len(address.balances)}")
        
        if address.balances:
            print("\n=== 代币余额 (前10个) ===")
            for i, balance in enumerate(address.balances[:10]):
                print(f"{i+1}. 地址: {balance.token_contract_address}")
                print(f"   数量: {balance.amount}")
                print(f"   价值: ${balance.value}")
                print()
        
        # 保存到文件
        if crawler.save_to_file(address):
            print("✅ 数据已保存到文件")
    else:
        print("❌ 未能获取到资产信息")


if __name__ == "__main__":
    main()