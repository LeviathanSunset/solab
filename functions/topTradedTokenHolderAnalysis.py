#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热门交易代币持有者分析模块
Top Traded Token Holder Analysis Module

输入: 使用Jupiter预设配置爬取热门交易代币
输出: 按照tokenHolderAnalysis逐个输出符合条件的代币报告
筛选条件: 目标代币大户至少5个地址持有同一个代币(除了目标代币, 稳定币, SOL), 该代币持有者的总价值超过10万美元

Input: Use Jupiter preset configuration to crawl top traded tokens
Output: Output qualified token reports one by one according to tokenHolderAnalysis
Filter condition: Target token holders must have at least 5 addresses holding the same token (excluding target token, stablecoins, SOL), with total value exceeding $100,000
"""

import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入项目模块
from crawlers.jupiter.topTradedTokens import JupiterTopTradedCrawler
from functions.tokenHolderAnalysis import TokenHolderAnalyzer
from functions.logger import CrawlerLogger, get_logger
from settings.config_manager import ConfigManager


class TopTradedTokenHolderAnalyzer:
    """热门交易代币持有者分析器"""
    
    def __init__(self, performance_mode: str = 'high_speed'):
        """初始化分析器
        
        Args:
            performance_mode: 性能模式 ('conservative', 'balanced', 'high_speed', 'lightweight')
        """
        self.performance_mode = performance_mode
        self.config = ConfigManager()
        self.jupiter_crawler = JupiterTopTradedCrawler()
        self.holder_analyzer = TokenHolderAnalyzer(performance_mode=performance_mode)
        
        # 初始化日志器
        self.logger = CrawlerLogger("TopTradedTokenAnalyzer")
        
        # 更严格的筛选条件
        self.min_holders = 5  # 至少5个地址持有
        self.min_total_value = 300000  # 总价值超过30万美元
        
        # 主流稳定币和SOL地址，筛选时排除
        self.excluded_tokens = {
            "So11111111111111111111111111111111111111112",  # SOL 完整地址
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        }
        
    def set_auth(self, cookie: str, fp_token: str, verify_sign: str, 
                 verify_token: str, dev_id: str, site_info: str):
        """设置OKX认证信息"""
        self.holder_analyzer.set_auth(cookie, fp_token, verify_sign, 
                                    verify_token, dev_id, site_info)
    
    def analyze_top_traded_tokens(self, preset_name: str = 'lowCapGem_24h',
                                max_tokens: int = 20,
                                delay_between_tokens: float = 2.0,
                                progress_callback=None,
                                qualified_callback=None) -> List[Dict[str, Any]]:
        """
        分析热门交易代币的持有者
        
        Args:
            preset_name: Jupiter预设名称, 默认为'lowCapGem_24h'
            max_tokens: 最大分析代币数量
            delay_between_tokens: 代币分析间隔时间(秒)
            progress_callback: 进度回调函数
            qualified_callback: 发现符合条件代币时的回调函数
            
        Returns:
            符合条件的分析结果列表
        """
        # 记录任务开始
        task_desc = f"热门交易代币持有者分析 - 预设:{preset_name}, 性能模式:{self.performance_mode}"
        self.logger.log_start(task_desc)
        
        self.logger.info(f"📋 筛选条件: 至少{self.min_holders}个地址持有, 总价值>${self.min_total_value:,}(排除SOL, USDC, USDT等主流币)")
        
        # 1. 获取热门交易代币
        try:
            self.logger.info("🔄 正在获取热门交易代币...")
            tokens = self.jupiter_crawler.crawl_with_preset(preset_name)
            self.logger.log_success("获取热门交易代币", f"获取到 {len(tokens)} 个代币")
        except Exception as e:
            self.logger.log_error("获取热门交易代币", str(e))
            return []
        
        if not tokens:
            self.logger.log_error("获取热门交易代币", "未获取到任何代币数据")
            return []
        
        # 限制分析数量
        tokens_to_analyze = tokens[:max_tokens]
        self.logger.info(f"📝 将分析前 {len(tokens_to_analyze)} 个代币")
        
        # 2. 逐个分析代币持有者
        qualified_results = []
        
        for i, token in enumerate(tokens_to_analyze, 1):
            try:
                # 更新进度回调
                if progress_callback:
                    progress_callback(i, len(tokens_to_analyze))
                
                # 记录当前处理进度
                self.logger.log_progress(
                    i, len(tokens_to_analyze), 
                    f"{token.symbol} ({token.contract_address[:8]}...)",
                    "分析中"
                )
                
                # 显示代币基本信息
                if hasattr(token, 'market_cap') and token.market_cap:
                    self.logger.info(f"💰 市值: ${token.market_cap:,.0f}")
                
                # 分析持有者
                analysis_result = self.holder_analyzer.analyze_token_holders(
                    token.contract_address,
                    chain_id="501"
                )
                
                if "error" in analysis_result:
                    self.logger.log_error(f"分析代币 {token.symbol}", analysis_result['error'])
                    continue
                
                # 检查是否符合条件
                if self._check_qualification(analysis_result, token):
                    self.logger.log_qualified_found(
                        f"{token.symbol} ({token.contract_address[:8]}...)",
                        f"符合持有者条件 - 大户共同持仓分析"
                    )
                    
                    # 添加代币基本信息
                    analysis_result['token_info'] = {
                        'symbol': token.symbol,
                        'name': token.name,
                        'contract_address': token.contract_address,
                        'market_cap': getattr(token, 'market_cap', None),
                        'volume_24h': getattr(token, 'volume_24h', None),
                        'price': getattr(token, 'price', None)
                    }
                    
                    qualified_results.append(analysis_result)
                    
                    # 🚀 立即通过回调发送到群组
                    if qualified_callback:
                        try:
                            self.logger.info(f"🎯 发现符合条件的代币: {token.symbol}, 立即发送到群组")
                            qualified_callback(analysis_result)
                            self.logger.info(f"✅ 已立即输出符合条件的代币: {token.symbol}")
                        except Exception as e:
                            self.logger.error(f"❌ 立即发送代币 {token.symbol} 失败: {e}")
                    
                    # 生成并输出报告到日志
                    self._output_token_report(analysis_result, token)
                    
                    self.logger.log_success(f"分析代币 {token.symbol}", "符合条件, 已添加到结果")
                    
                else:
                    self.logger.info(f"❌ {token.symbol} 不符合条件")
                
                # 延迟避免过于频繁的请求
                if i < len(tokens_to_analyze):
                    self.logger.debug(f"⏱️ 等待 {delay_between_tokens} 秒...")
                    time.sleep(delay_between_tokens)
                    
            except Exception as e:
                self.logger.log_error(f"分析代币 {token.symbol}", str(e))
                continue
        
        # 3. 输出总结
        self.logger.log_completion(task_desc)
        self._output_summary(qualified_results, len(tokens_to_analyze))
        
        return qualified_results
    
    def _check_qualification(self, analysis_result: Dict[str, Any], token) -> bool:
        """
        检查分析结果是否符合筛选条件
        
        Args:
            analysis_result: 分析结果
            token: 代币信息
            
        Returns:
            是否符合条件
        """
        common_holdings = analysis_result.get('common_holdings', {})
        top_tokens = common_holdings.get('top_common_tokens', {})
        token_info_map = common_holdings.get('token_info_map', {})
        
        # 检查是否有代币满足条件(除了目标代币本身)
        target_address = analysis_result['token_address']
        
        for token_addr, token_info in top_tokens.items():
            # 跳过目标代币本身
            if token_addr == target_address:
                continue
            
            # 跳过主流稳定币和SOL
            if token_addr in self.excluded_tokens:
                continue
            
            # 智能识别SOL: 检查是否为SOL的特殊格式
            if self._is_sol_token(token_addr, token_info_map):
                self.logger.debug(f"跳过SOL代币: {token_info.get('symbol', 'Unknown')} (识别为SOL)")
                continue
                
            holder_count = token_info['holder_count']
            total_value = token_info['total_value']
            
            # 检查是否满足条件: 至少5个地址持有, 总价值超过50万美元
            if holder_count >= self.min_holders and total_value >= self.min_total_value:
                self.logger.info(f"📊 符合条件的代币: {token_info.get('symbol', 'Unknown')} ({holder_count}人持有, ${total_value:,.0f})")
                return True
        
        self.logger.debug(f"无符合条件的共同持仓 (需要: >={self.min_holders}人持有 且 >=${self.min_total_value:,}, 排除主流币)")
        return False
    
    def _is_sol_token(self, token_addr: str, token_info_map: Dict[str, Any]) -> bool:
        """
        智能识别是否为SOL代币
        
        Args:
            token_addr: 代币地址/键名
            token_info_map: 代币信息映射
            
        Returns:
            是否为SOL代币
        """
        # 检查是否为完整的SOL地址
        if token_addr == "So11111111111111111111111111111111111111112":
            return True
        
        # 检查token_info_map中的详细信息
        token_info = token_info_map.get(token_addr, {})
        if token_info:
            symbol = token_info.get('symbol', '').upper()
            name = token_info.get('name', '').upper()
            
            # 识别SOL的特征: symbol包含"SOL...SOL", name包含"UNKNOWN TOKEN (SOL"
            if 'SOL...SOL' in symbol or 'UNKNOWN TOKEN (SOL' in name:
                return True
        
        return False
    
    def _output_token_report(self, analysis_result: Dict[str, Any], token) -> None:
        """输出单个代币的分析报告"""
        self.logger.info("="*60)
        self.logger.info(f"🎯 {token.symbol} 持有者分析报告")
        self.logger.info("="*60)
        
        # 生成详细报告
        report = self.holder_analyzer.generate_detective_report(
            analysis_result, 
            token.symbol,
            top_holdings_count=15  # 显示前15个持仓
        )
        
        # 将报告按行分割并逐行记录日志
        for line in report.split('\n'):
            if line.strip():  # 跳过空行
                self.logger.info(line)
        
        self.logger.info("="*60)
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"toptraded_{token.symbol}_{timestamp}.yaml"
        self.holder_analyzer.save_analysis_result(analysis_result, filename)
        self.logger.info(f"💾 分析结果已保存至: {filename}")
    
    def _output_summary(self, qualified_results: List[Dict[str, Any]], total_analyzed: int) -> None:
        """输出分析总结"""
        self.logger.info("🎉"*20)
        self.logger.info("📊 分析总结")
        self.logger.info("🎉"*20)
        self.logger.info(f"✅ 符合条件的代币: {len(qualified_results)}/{total_analyzed}")
        self.logger.info(f"📋 筛选标准: 至少{self.min_holders}个地址持有同一代币, 总价值>=${self.min_total_value:,}(排除SOL, USDC, USDT等主流币)")
        
        if qualified_results:
            self.logger.info("")
            self.logger.info("🏆 符合条件的代币列表:")
            for i, result in enumerate(qualified_results, 1):
                token_info = result.get('token_info', {})
                symbol = token_info.get('symbol', 'Unknown')
                contract = token_info.get('contract_address', '')
                self.logger.info(f"  {i}. {symbol} ({contract[:8]}...)")
        else:
            self.logger.info("")
            self.logger.info("❌ 本次分析中没有代币符合条件")
        
        self.logger.info("🎉"*20)


def main():
    """主函数"""
    # 🔧 配置参数
    PRESET_NAME = 'lowCapGem_24h'  # Jupiter预设名称
    PERFORMANCE_MODE = 'high_speed'   # 性能模式
    MAX_TOKENS = 1000                 # 最大分析代币数
    DELAY_BETWEEN_TOKENS = 1.0      # 代币间延迟(秒)
    
    # 初始化主日志器
    main_logger = get_logger("TopTradedAnalysis.Main")
    
    main_logger.info("🔧 配置参数:")
    main_logger.info(f"   预设名称: {PRESET_NAME}")
    main_logger.info(f"   性能模式: {PERFORMANCE_MODE}")
    main_logger.info(f"   最大分析数: {MAX_TOKENS}")
    main_logger.info(f"   间隔时间: {DELAY_BETWEEN_TOKENS}秒")
    
    # 初始化分析器
    analyzer = TopTradedTokenHolderAnalyzer(performance_mode=PERFORMANCE_MODE)
    
    # 设置OKX认证信息(需要替换为真实数据)
    analyzer.set_auth(
        cookie="devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOi42bpdWZyJye; locale=en_US; ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; ok_prefer_udColor=0; ok_prefer_udTimeZone=0; fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; ok_global={%22g_t%22:2}; _gcl_au=1.1.1005719754.1755091396; connectedWallet=1; _gid=GA1.2.950489538.1757092345; mse=nf=8|se=0; __cf_bm=KlSlz4ToD2eBrbV2YMpvOTgZSH9aJx8ZbSpNehX__70-1757227578-1.0.1.1-CVB_X0rNpOfUw.n3YJgAepDber7b9fzyAdFONBE5xbbJ9uokVrU0D0ZnKpCgKqWRX9MNMHAODFPNpxZDZYUw1XLYVw6RbsONqf7J5SbrKAc; ok-exp-time=1757227583876; okg.currentMedia=md; tmx_session_id=g42rqe6lkgv_1757227586034; connected=1; fp_s=0; traceId=2130772279702400005; _gat_UA-35324627-3=1; _ga=GA1.1.2083537763.1750302376; _ga_G0EKWWQGTZ=GS2.1.s1757227595$o127$g1$t1757227972$j58$l0$h0; ok-ses-id=ic8FZdwDJ9iztku9zy3wjshp7WSUVWnCq6wpmGltOew4BJU1wkFkGYHyg2jS3JIKpZCB7dnA0g1BCrndYsGLeFEXC9fKYuWwNU4qCZlHwpNQI42XTE4EYPY03Z1p2MaR; _monitor_extras={\"deviceId\":\"KmpeI8VVHan-2zL3_DbOJB\",\"eventId\":6313,\"sequenceNumber\":6313}",
        fp_token="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
        verify_sign="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4=",
        verify_token="ac90bf8e-b5fc-4643-a441-2d7b7eb08634",
        dev_id="01980a38-038a-44d9-8da3-a8276bbcb5b9",
        site_info="==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOi42bpdWZyJye"
    )
    
    # 开始分析
    qualified_results = analyzer.analyze_top_traded_tokens(
        preset_name=PRESET_NAME,
        max_tokens=MAX_TOKENS,
        delay_between_tokens=DELAY_BETWEEN_TOKENS
    )
    
    main_logger.info(f"🎯 分析完成！共找到 {len(qualified_results)} 个符合条件的代币")


if __name__ == "__main__":
    main()
