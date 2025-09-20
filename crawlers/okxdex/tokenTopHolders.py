#!/usr/bin/env python3
"""
OKX 代币持有者爬虫 (OKXTokenTopHoldersCrawler)
=========================================

功能: 获取代币的顶级持有者地址列表
API: OKX DEX API
用途: 分析代币持有者结构，识别大户和机构

主要方法:
- get_top_holders(): 获取代币持有者列表
- 自动区分真人地址和池子/交易所地址
- 过滤掉合约地址，只返回EOA地址

返回数据:
- 持有者地址数组
- 持有量和占比信息
- 地址类型标识

适用场景: 分析代币集中度，寻找潜在的操控地址
"""

import requests
import time
import json
from typing import List, Dict

class SimpleOKXCrawler:
    """简化版 OKX 持有者爬虫"""
    
    def __init__(self):
        self.base_url = "https://web3.okx.com/priapi/v1/dx/market/v2/holders/ranking-list"
        self.headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-locale": "en_US",
            "x-utc": "0",
        }
    
    def set_auth(self, cookie: str, fp_token: str, verify_sign: str, verify_token: str, dev_id: str, site_info: str):
        """设置认证信息"""
        timestamp = str(int(time.time() * 1000))
        self.headers.update({
            "cookie": cookie,
            "x-fptoken": fp_token,
            "ok-verify-sign": verify_sign,
            "ok-verify-token": verify_token,
            "ok-timestamp": timestamp,
            "devid": dev_id,
            "x-site-info": site_info,
            "x-request-timestamp": timestamp,
        })
    
    def get_holders(self, chain_id: str, token_address: str) -> List[Dict]:
        """
        获取持有者地址数组
        
        Returns:
            地址数组，每个元素包含：
            {
                "address": "地址",
                "balance": "余额",
                "value_usd": "USD价值", 
                "tag": "human" | "pool" | "exchange" | "contract"
            }
        """
        try:
            # 构建请求参数
            params = {
                "chainId": chain_id,
                "tokenAddress": token_address,
                "t": str(int(time.time() * 1000))
            }
            
            # 设置 referer
            self.headers["referer"] = f"https://web3.okx.com/token/solana/{token_address}"
            
            # 发送请求
            response = requests.get(self.base_url, params=params, headers=self.headers)
            
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                return []
            
            data = response.json()
            
            if data.get("code") != 0:
                print(f"❌ API错误: {data.get('msg', '未知错误')}")
                return []
            
            # 解析持有者数据
            holder_list = data.get("data", {}).get("holderRankingList", [])
            addresses = []
            
            for holder in holder_list:
                address = holder.get("holderWalletAddress", "")
                if not address:
                    continue
                
                # 获取基本信息
                balance = holder.get("holdAmount", "0")
                value_usd = holder.get("holdVolume", "0")
                
                # 分析标签，确定地址类型
                tag = self._analyze_address_type(holder)
                
                addresses.append({
                    "address": address,
                    "balance": balance,
                    "value_usd": value_usd,
                    "tag": tag
                })
            
            return addresses
            
        except Exception as e:
            print(f"❌ 爬取失败: {str(e)}")
            return []
    
    def _analyze_address_type(self, holder: Dict) -> str:
        """分析地址类型"""
        
        # 获取标签列表
        tag_list = holder.get("tagList", [])
        tags = []
        for tag in tag_list:
            if isinstance(tag, list) and tag:
                tags.append(tag[0])
            elif isinstance(tag, str):
                tags.append(tag)
        
        # 根据标签判断类型
        for tag in tags:
            if tag in ["liquidityPool", "pool"]:
                return "pool"
            elif tag in ["exchange", "cex", "dex"]:
                return "exchange"
            elif tag in ["contract", "smartContract"]:
                return "contract"
        
        # 如果没有特殊标签，认为是真人地址
        return "human"

def main():
    """测试函数"""
    crawler = SimpleOKXCrawler()
    
    # 设置认证信息（需要替换为真实数据）
    crawler.set_auth(
        cookie="devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; locale=en_US; ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; ok_prefer_udColor=0; ok_prefer_udTimeZone=0; fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; ok_global={%22g_t%22:2}; _gcl_au=1.1.1005719754.1755091396; connectedWallet=1; _gid=GA1.2.950489538.1757092345; mse=nf=8|se=0; __cf_bm=KlSlz4ToD2eBrbV2YMpvOTgZSH9aJx8ZbSpNehX__70-1757227578-1.0.1.1-CVB_X0rNpOfUw.n3YJgAepDber7b9fzyAdFONBE5xbbJ9uokVrU0D0ZnKpCgKqWRX9MNMHAODFPNpxZDZYUw1XLYVw6RbsONqf7J5SbrKAc; ok-exp-time=1757227583876; okg.currentMedia=md; tmx_session_id=g42rqe6lkgv_1757227586034; connected=1; fp_s=0; traceId=2130772279702400005; _gat_UA-35324627-3=1; _ga=GA1.1.2083537763.1750302376; _ga_G0EKWWQGTZ=GS2.1.s1757227595$o127$g1$t1757227972$j58$l0$h0; ok-ses-id=ic8FZdwDJ9iztku9zy3wjshp7WSUVWnCq6wpmGltOew4BJU1wkFkGYHyg2jS3JIKpZCB7dnA0g1BCrndYsGLeFEXC9fKYuWwNU4qCZlHwpNQI42XTE4EYPY03Z1p2MaR; _monitor_extras={\"deviceId\":\"KmpeI8VVHan-2zL3_DbOJB\",\"eventId\":6313,\"sequenceNumber\":6313}",
        fp_token="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
        verify_sign="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4=",
        verify_token="ac90bf8e-b5fc-4643-a441-2d7b7eb08634",
        dev_id="01980a38-038a-44d9-8da3-a8276bbcb5b9",
        site_info="==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye"
    )
    
    # 爬取持有者
    token_address = "5zCETicUCJqJ5Z3wbfFPZqtSpHPYqnggs1wX7ZRpump"
    chain_id = "501"
    
    print("🚀 开始爬取持有者地址...")
    addresses = crawler.get_holders(chain_id, token_address)
    
    if not addresses:
        print("❌ 没有获取到数据")
        return
    
    print(f"✅ 成功获取 {len(addresses)} 个地址\n")
    
    # 按类型分组统计
    stats = {"human": 0, "pool": 0, "exchange": 0, "contract": 0}
    human_addresses = []
    other_addresses = []
    
    for addr in addresses:
        stats[addr["tag"]] += 1
        if addr["tag"] == "human":
            human_addresses.append(addr)
        else:
            other_addresses.append(addr)
    
    print("📊 地址类型统计:")
    print(f"   👤 真人地址: {stats['human']}")
    print(f"   🏊 流动性池: {stats['pool']}")
    print(f"   🏦 交易所: {stats['exchange']}")
    print(f"   📜 合约: {stats['contract']}")
    print()
    
    # 输出前10个真人地址
    print("👤 前10个真人地址:")
    for i, addr in enumerate(human_addresses[:10], 1):
        balance_k = float(addr['balance']) / 1000
        print(f"  {i:2d}. {addr['address']} (余额: {balance_k:.0f}K)")
    
    print()
    
    # 输出非真人地址
    print("🏦 池子/交易所/合约地址:")
    for addr in other_addresses:
        tag_name = {"pool": "流动性池", "exchange": "交易所", "contract": "合约"}[addr["tag"]]
        balance_k = float(addr['balance']) / 1000
        print(f"   [{tag_name}] {addr['address']} (余额: {balance_k:.0f}K)")
    
    print()
    print("📋 完整地址数组 (JSON格式):")
    print(json.dumps(addresses, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
