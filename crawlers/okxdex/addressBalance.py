"""
OKX地址资产爬虫
获取指定地址的所有资产信息，包括代币余额、价值等
API: https://web3.okx.com/priapi/v2/wallet/asset/profile/all/explorer
"""
import requests
import json
import time
import yaml
from typing import Optional, Dict, Any, List
from dataclasses import asdict
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入项目模型
from functions.models import Address, TokenBalance


class OKXAddressBalanceCrawler:
    """OKX地址资产爬虫"""
    
    def __init__(self):
        self.base_url = "https://web3.okx.com/priapi/v2/wallet/asset/profile/all/explorer"
        self.session = requests.Session()
        self._setup_headers()
    
    def _setup_headers(self):
        """设置请求头"""
        self.session.headers.update({
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,zh-HK;q=0.8,zh-CN;q=0.7,zh;q=0.6,es-MX;q=0.5,es;q=0.4,ru-RU;q=0.3,ru;q=0.2",
            "app-type": "web",
            "content-type": "application/json",
            "device-token": "01980a38-038a-44d9-8da3-a8276bbcb5b9",
            "devid": "01980a38-038a-44d9-8da3-a8276bbcb5b9",
            "origin": "https://web3.okx.com",
            "platform": "web",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "x-cdn": "https://web3.okx.com",
            "x-locale": "en_US",
            "x-simulated-trading": "undefined",
            "x-utc": "0",
            "x-zkdex-env": "0",
        })
    
    def _update_dynamic_headers(self, wallet_address: str):
        """更新动态请求头"""
        current_timestamp = int(time.time() * 1000)
        
        # 完整的cookie字符串（基于你提供的请求信息）
        cookie_string = (
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
        
        self.session.headers.update({
            "referer": f"https://web3.okx.com/portfolio/{wallet_address}/analysis",
            "x-request-timestamp": str(current_timestamp),
            "x-id-group": f"{current_timestamp}-c-15",
            "cookie": cookie_string,
            "b-locale": "en_US",
            "x-site-info": "==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye",
            # 添加更多必需的头
            "x-fptoken": "eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
            "x-fptoken-signature": "{P1363}a+WvAdH7qkrC168mAWUm9m6Ij5vnXVeh83m1fL+bYGwYhtIpK92pOSWwIbXmILxMj93b7GYNGE6EEm4Ei7f8IA==",
            "x-brokerid": "0",
        })
    
    def test_network_connection(self) -> bool:
        """测试网络连接"""
        test_url = "https://httpbin.org/get"  # 简单的测试URL
        
        try:
            print("测试网络连接...")
            response = requests.get(test_url, timeout=10)
            if response.status_code == 200:
                print("✅ 网络连接正常")
                return True
            else:
                print(f"❌ 网络测试失败，状态码: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 网络连接测试失败: {e}")
            return False
    
    def test_okx_connection(self) -> bool:
        """测试OKX域名连接"""
        test_url = "https://web3.okx.com"
        
        try:
            print("测试OKX域名连接...")
            response = requests.get(test_url, timeout=15, verify=True)
            print(f"✅ OKX域名连接正常，状态码: {response.status_code}")
            return True
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL连接错误: {e}")
            print("尝试禁用SSL验证测试...")
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = requests.get(test_url, timeout=15, verify=False)
                print(f"⚠️ 禁用SSL验证后连接成功，状态码: {response.status_code}")
                return True
            except Exception as fallback_e:
                print(f"❌ 禁用SSL后仍然失败: {fallback_e}")
                return False
        except Exception as e:
            print(f"❌ OKX连接测试失败: {e}")
            return False

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
        try:
            # 更新动态请求头
            self._update_dynamic_headers(wallet_address)
            
            # 构建请求参数
            current_timestamp = int(time.time() * 1000)
            params = {
                "t": current_timestamp
            }
            
            # 使用正确的payload格式
            payload = {
                "userUniqueId": "485662AA-1409-4BC7-8F10-A6406C1F3532",
                "hideValueless": False,
                "address": wallet_address,
                "forceRefresh": True,
                "page": 1,
                "limit": 100,  # 增加限制以获取更多代币
                "chainIndexes": [chain_id]
            }
            
            if debug:
                print(f"请求URL: {self.base_url}")
                print(f"请求参数: {params}")
                print(f"请求体: {json.dumps(payload, indent=2)}")
                print(f"请求头数量: {len(self.session.headers)}")
            
            print(f"正在获取地址 {wallet_address} 的资产信息...")
            
            # 增强的网络请求处理
            try:
                response = self.session.post(
                    self.base_url,
                    params=params,
                    json=payload,
                    timeout=(10, 30),  # 连接超时10秒，读取超时30秒
                    verify=True  # 启用SSL验证
                )
            except requests.exceptions.SSLError as ssl_error:
                print(f"SSL验证错误: {ssl_error}")
                print("尝试禁用SSL验证...")
                
                try:
                    # 禁用SSL警告
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    response = self.session.post(
                        self.base_url,
                        params=params,
                        json=payload,
                        timeout=(10, 30),
                        verify=False  # 禁用SSL验证
                    )
                    print("SSL验证禁用后请求成功")
                except Exception as fallback_error:
                    print(f"禁用SSL后仍然失败: {fallback_error}")
                    return None
                    
            except requests.exceptions.ConnectionError as conn_error:
                print(f"网络连接错误: {conn_error}")
                print("请检查网络连接或代理设置")
                return None
                
            except requests.exceptions.Timeout as timeout_error:
                print(f"请求超时: {timeout_error}")
                print("请稍后重试")
                return None
            
            if debug:
                print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"成功获取响应，状态码: {response.status_code}")
                
                if debug:
                    print("=== API响应数据结构 ===")
                    print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 解析响应数据
                return self._parse_assets_data(data, wallet_address, chain_id)
            else:
                print(f"请求失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
        except requests.exceptions.SSLError as ssl_e:
            print(f"SSL连接错误: {ssl_e}")
            print("可能的解决方案:")
            print("1. 检查系统时间是否正确")
            print("2. 更新证书或尝试使用代理")
            print("3. 检查防火墙设置")
            return None
        except requests.exceptions.ConnectionError as conn_e:
            print(f"网络连接错误: {conn_e}")
            print("可能的解决方案:")
            print("1. 检查网络连接")
            print("2. 检查代理设置")
            print("3. 尝试更换网络环境")
            return None
        except requests.exceptions.Timeout as timeout_e:
            print(f"请求超时: {timeout_e}")
            print("请稍后重试")
            return None
        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None
    
    def _parse_assets_data(self, data: Dict[str, Any], wallet_address: str, chain_id: int) -> Optional[Address]:
        """解析资产数据"""
        try:
            # 检查响应结构
            if data.get("code") != 0:
                print(f"API返回错误: {data.get('msg', '未知错误')}")
                return None
            
            result = data.get("data", {})
            
            # 获取总资产信息
            tokens_info = result.get("tokens", {})
            token_count = tokens_info.get("total", 0)
            
            # 从walletAssetSummary获取汇总信息（如果存在）
            wallet_summary = result.get("walletAssetSummary", {})
            total_amount = wallet_summary.get("tokenTotalCurrencyAmount", "0")
            defi_amount = wallet_summary.get("defiTotalCurrencyAmount", "0")
            nft_amount = wallet_summary.get("nftTotalCurrencyAmount", "0")
            
            # 创建地址对象
            address = Address(
                address=wallet_address,
                note=f"总资产: ${total_amount}, 代币: {token_count}, DeFi: ${defi_amount}, NFT: ${nft_amount}",
                tag="爬取资产"
            )
            
            # 解析代币资产列表 - 使用正确的路径
            tokens_info = result.get("tokens", {})
            assets_list = tokens_info.get("tokenlist", [])
            
            print(f"找到 {len(assets_list)} 种代币")
            
            for i, asset_data in enumerate(assets_list):
                try:
                    # 提取基本信息
                    token_symbol = asset_data.get("symbol", "")
                    coin_amount = asset_data.get("coinAmount", "0")
                    currency_amount = asset_data.get("currencyAmount", "0")
                    
                    # 从coinBalanceDetails获取详细信息
                    coin_details = asset_data.get("coinBalanceDetails", [])
                    if coin_details:
                        detail = coin_details[0]  # 取第一个详情
                        token_address = detail.get("address", "")
                    else:
                        token_address = ""
                    
                    # 检查是否为原生代币(SOL)
                    is_native = (token_symbol.upper() == "SOL" or 
                               token_address.upper() == "SOL")
                    
                    if is_native:
                        # SOL作为原生代币，使用特殊标识
                        address.add_balance("SOL", str(coin_amount), str(currency_amount))
                        print(f"发现原生代币 SOL: {coin_amount} (${currency_amount})")
                    else:
                        # 添加代币余额
                        if token_address:  # 只有有地址的代币才添加
                            address.add_balance(token_address, str(coin_amount), str(currency_amount))
                            
                            if i < 5:  # 只显示前5个代币的详情
                                print(f"代币 {i+1}: {token_symbol} - {coin_amount} (${currency_amount})")
                
                except Exception as e:
                    print(f"解析第{i+1}个代币时出错: {e}")
                    continue
            
            # 检查是否有DeFi资产
            defis = result.get("defis", [])
            defi_total = sum(float(defi.get("balance", "0")) for defi in defis)
            
            # 检查是否有NFT资产
            nfts = result.get("nfts", [])
            nft_total = 0
            for nft in nfts:
                nft_total += float(nft.get("valuation", "0"))
            
            # 更新note以包含更多信息
            total_value = result.get("walletAssetSummary", {}).get("tokenTotalCurrencyAmount", "0")
            address.note = f"总资产: ${total_value}, 代币: {len(address.balances)}, DeFi: ${defi_total:.2f}, NFT: ${nft_total:.2f}"
            
            print(f"\n成功解析资产数据:")
            print(f"  - 总资产价值: ${total_value}")
            print(f"  - 持有代币种类: {len(address.balances)}")
            if defi_total > 0:
                print(f"  - DeFi资产价值: ${defi_total:.2f}")
            if nft_total > 0:
                print(f"  - NFT资产价值: ${nft_total:.2f}")
            
            return address
            
        except Exception as e:
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
    
    # 先进行网络测试
    print("=== 网络连接测试 ===")
    basic_network = crawler.test_network_connection()
    okx_network = crawler.test_okx_connection()
    
    if not basic_network:
        print("❌ 基础网络连接失败，请检查网络设置")
        return
    
    if not okx_network:
        print("⚠️ OKX连接有问题，但仍会尝试API请求")
    
    print("\n" + "="*50)
    
    # 示例地址 - Solana地址
    test_address = "DCBzkdY6XtSMNgqeppLtKoAcTYTNKLf6FVtYy5LZvB2G"
    
    print(f"开始爬取地址资产: {test_address}")
    
    # 获取资产信息
    address = crawler.fetch_address_assets(test_address, debug=False)
    
    if address:
        print("\n=== 地址资产详情 ===")
        print(f"钱包地址: {address.address}")
        print(f"备注: {address.note}")
        print(f"标签: {address.tag}")
        print(f"持有代币数量: {len(address.balances)}")
        
        if address.balances:
            print("\n=== 代币余额 ===")
            for i, balance in enumerate(address.balances[:10]):  # 显示前10个
                print(f"{i+1}. 地址: {balance.token_contract_address}")
                print(f"   数量: {balance.amount}")
                print(f"   价值: ${balance.value}")
                print()
        
        # 保存到文件
        crawler.save_to_file(address)
    else:
        print("未能获取到资产信息")


if __name__ == "__main__":
    main()