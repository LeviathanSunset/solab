import requests
import json
import yaml
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from settings.config_manager import config_manager
from functions.models import Token

class JupiterTopTradedCrawler:
    """Jupiter 热门交易代币爬虫"""
    
    BASE_URL = "https://datapi.jup.ag/v1/pools/toptraded"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://jup.ag',
            'Referer': 'https://jup.ag/'
        })
    
    def crawl_with_preset(self, preset_name: str) -> List[Token]:
        """使用预设配置爬取热门交易代币
        
        Args:
            preset_name: 预设名称
            
        Returns:
            Token列表
        """
        # 构建API参数
        config = config_manager.build_jupiter_api_params(preset_name)
        if not config:
            raise ValueError(f"预设 '{preset_name}' 不存在")
        
        time_frame = config['timeFrame']
        params = config['params']
        
        print(f"使用预设: {preset_name}")
        print(f"时间框架: {time_frame}")
        print(f"请求参数: {params}")
        
        all_tokens = []
        page = 1
        max_pages = 10  # 防止无限循环
        
        while page <= max_pages:
            # 构建API URL
            url = f"{self.BASE_URL}/{time_frame}"
            current_params = params.copy()
            
            print(f"\n🔍 第 {page} 页爬取...")
            print(f"请求URL: {url}")
            print(f"当前参数: {current_params}")
            
            tokens = self._fetch_tokens(url, current_params)
            
            if not tokens:
                print("❌ 未获取到代币数据，停止爬取")
                break
            
            all_tokens.extend(tokens)
            print(f"✅ 第 {page} 页获取 {len(tokens)} 个代币")
            
            # 检查是否需要继续分页
            if len(tokens) < 50:
                print("📄 返回数据少于50个，已到最后一页")
                break
            
            # 获取最后一个代币的交易量作为下一页的maxVolume
            last_token_volume = self._get_token_volume(tokens[-1], time_frame)
            if last_token_volume is None:
                print("⚠️  无法获取最后一个代币的交易量，停止分页")
                break
            
            # 检查是否有最小交易量限制
            min_volume_key = f'minVolume{time_frame}'
            if min_volume_key in current_params:
                min_volume = current_params[min_volume_key]
                if last_token_volume <= min_volume:
                    print(f"📊 最后代币交易量 {last_token_volume} 已达到最小值 {min_volume}，停止分页")
                    break
                
                # 设置maxVolume为最后一个代币的交易量，继续下一页
                max_volume_key = f'maxVolume{time_frame}'
                params[max_volume_key] = last_token_volume - 1  # 减1避免重复
                print(f"🔄 设置最大交易量 {max_volume_key}={last_token_volume - 1}，继续下一页")
            else:
                print("ℹ️  预设中没有最小交易量限制，无法判断是否继续分页")
                break
            
            page += 1
            
            # 添加延迟避免请求过快
            time.sleep(1)
        
        print(f"\n🎉 分页爬取完成！总共获取 {len(all_tokens)} 个代币")
        return all_tokens
    
    def _get_token_volume(self, token: Token, time_frame: str) -> Optional[float]:
        """获取代币的指定时间框架交易量"""
        # 从临时保存的交易量数据中获取
        if hasattr(token, '_volume_data') and token._volume_data and time_frame in token._volume_data:
            return token._volume_data[time_frame]
        return None
    
    def _fetch_tokens(self, url: str, params: Dict[str, Any]) -> List[Token]:
        """获取代币数据
        
        Args:
            url: API URL
            params: 请求参数
            
        Returns:
            Token列表
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            tokens = []
            
            # 解析代币数据
            for pool_data in data.get('pools', []):
                base_asset = pool_data.get('baseAsset', {})
                
                # 获取真实的代币创建时间
                first_pool = base_asset.get('firstPool', {})
                created_at_str = first_pool.get('createdAt')
                created_at = None
                if created_at_str:
                    try:
                        # 解析ISO格式的时间字符串
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.now()
                else:
                    created_at = datetime.now()

                # 获取交易量数据 (用于分页逻辑，但不保存到Token对象)
                volume_data = {}
                for time_frame in ['5m', '1h', '6h', '24h']:
                    stats_key = f'stats{time_frame}'
                    if stats_key in base_asset:
                        stats = base_asset[stats_key]
                        buy_volume = stats.get('buyVolume', 0)
                        sell_volume = stats.get('sellVolume', 0)
                        total_volume = buy_volume + sell_volume
                        volume_data[time_frame] = total_volume

                token = Token(
                    contract_address=base_asset.get('id', ''),
                    symbol=base_asset.get('symbol', ''),
                    name=base_asset.get('name', ''),
                    token_supply=str(base_asset.get('totalSupply', 0)),
                    decimals=base_asset.get('decimals', 0),
                    created_at=created_at
                )

                # 临时保存交易量信息用于分页逻辑
                token._volume_data = volume_data  # 临时属性

                # 添加市值和价格信息
                token._market_cap = base_asset.get('mcap', 0)  # 市值
                token._price = base_asset.get('usdPrice', 0)    # USD价格
                token._fdv = base_asset.get('fdv', 0)           # 完全摊薄估值
                token._liquidity = base_asset.get('liquidity', 0)  # 流动性

                tokens.append(token)
            
            print(f"成功获取 {len(tokens)} 个代币")
            return tokens
            
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return []
        except Exception as e:
            print(f"未知错误: {e}")
            return []
    
    def save_tokens(self, tokens: List[Token], preset_name: str) -> str:
        """保存代币数据到文件
        
        Args:
            tokens: Token列表
            preset_name: 预设名称
            
        Returns:
            保存的文件路径
        """
        # 创建存储目录
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'storage')
        os.makedirs(storage_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jupiter_toptraded_{preset_name}_{timestamp}.yaml"
        filepath = os.path.join(storage_dir, filename)
        
        # 转换为字典格式 - 与multiTokenProfiles保持一致
        tokens_data = []
        for token in tokens:
            token_dict = {
                'contract_address': token.contract_address,
                'symbol': token.symbol,
                'name': token.name,
                'token_supply': token.token_supply,
                'decimals': token.decimals,
                'created_at': token.created_at.isoformat() if token.created_at else None
            }
            tokens_data.append(token_dict)
        
        # 添加元数据
        data_with_metadata = {
            'metadata': {
                'crawler': 'jupiter_toptraded',
                'preset': preset_name,
                'timestamp': timestamp,
                'count': len(tokens)
            },
            'tokens': tokens_data
        }
        
        # 保存到YAML文件
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data_with_metadata, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        print(f"代币数据已保存到: {filepath}")
        return filepath

def main():
    """主函数 - 使用预设爬取代币"""
    crawler = JupiterTopTradedCrawler()
    
    # 列出可用预设
    jupiter_config = config_manager._config.get('crawlers', {}).get('jupiter', {}).get('toptraded', {})
    presets = list(jupiter_config.keys())
    print("可用预设:")
    for preset in presets:
        print(f"- {preset}")
    
    # 使用 lowCapGem_24h 预设爬取
    preset_name = "lowCapGem_24h"
    try:
        tokens = crawler.crawl_with_preset(preset_name)
        if tokens:
            filepath = crawler.save_tokens(tokens, preset_name)
            print(f"\n爬取完成！获取到 {len(tokens)} 个代币")
            print(f"文件保存路径: {filepath}")
            
            # 显示前5个代币的信息
            print("\n前5个代币:")
            for i, token in enumerate(tokens[:5], 1):
                print(f"{i}. {token.symbol} ({token.name}) - {token.contract_address}")
        else:
            print("未获取到任何代币数据")
    except Exception as e:
        print(f"爬取失败: {e}")

if __name__ == "__main__":
    main()
