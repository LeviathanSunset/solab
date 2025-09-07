#!/usr/bin/env python3
"""
爬虫极限性能测试
测试不同并发数和延迟参数下的成功率，找到最优配置
"""
import time
import sys
import os
from datetime import datetime
from typing import List, Dict, Tuple

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

from crawlers.okxdex.addressBalance import OKXAddressBalanceCrawler

class CrawlerPerformanceTester:
    """爬虫性能测试器"""
    
    def __init__(self):
        self.crawler = OKXAddressBalanceCrawler()
        
        # 设置认证信息
        self.crawler.set_auth(
            cookie="devId=01980a38-038a-44d9-8da3-a8276bbcb5b9; ok_site_info===QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye; locale=en_US; ok_prefer_currency=0%7C1%7Cfalse%7CUSD%7C2%7C%24%7C1%7C1%7CUSD; ok_prefer_udColor=0; ok_prefer_udTimeZone=0; fingerprint_id=01980a38-038a-44d9-8da3-a8276bbcb5b9; first_ref=https%3A%2F%2Fweb3.okx.com%2Ftoken%2Fsolana%2FFbGsCHv8qPvUdmomVAiG72ET5D5kgBJgGoxxfMZipump; ok_global={%22g_t%22:2}; _gcl_au=1.1.1005719754.1755091396; connectedWallet=1; _gid=GA1.2.950489538.1757092345; mse=nf=8|se=0; connected=1; fp_s=0; okg.currentMedia=xl; _gat_UA-35324627-3=1; ok_prefer_exp=1; _ga=GA1.1.2083537763.1750302376",
            fp_token="eyJraWQiOiIxNjgzMzgiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE3NTcyMjc1ODksImVmcCI6Ikw1bHcvc0JPNENzV040MXB4MVlTLzRUSjBQaDViZlg0QjhiMTQrTGlHK21NdEt6WWx4TWpFdi9yK0o2MXlCcnIiLCJkaWQiOiIwMTk4MGEzOC0wMzhhLTQ0ZDktOGRhMy1hODI3NmJiY2I1YjkiLCJjcGsiOiJNRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVGOGE4RnFDNElLWDJxSHFaOHhaamJnd3BiMDloU2VCSWdxSkdjZ1FEWng0SEp2Z1lIN0g3NE5QblZsRHFWWWNUR0VBWm41aUw4bWdEQTVKbjY5SHJ5Zz09In0.Z1TlLWz0sQ3TvPxo6czcnmZjw1oQ20rvscyTT0CNCx3_e9zPa2WJrfppdAlJ5GbrqqEwyfI2upOd-fy2UGFnSg",
            verify_sign="z0wcDnWum9Gxbbxbq+G6gvmUd7xATTa7V+XX5HvXEe4=",
            verify_token="ac90bf8e-b5fc-4643-a441-2d7b7eb08634",
            dev_id="01980a38-038a-44d9-8da3-a8276bbcb5b9",
            site_info="==QfxojI5RXa05WZiwiIMFkQPx0Rfh1SPJiOiUGZvNmIsICUKJiOi42bpdWZyJye"
        )
        
        # 测试地址池 - 使用已知有资产的真实地址
        self.test_addresses = [
            "4Be9CvxqHW6BYiRAxW9Q3xu1ycTMWaL5z8NX4HR3ha7t",
            "6kBZzp4dwbKm7qCFWBprP7yfYbRvEm7iW2qxVpQxFbL",
            "CA4keXLtq1MdWZuVwmLShZj3xGgGkZQZQdxr6VdCdWGS",
            "3Lf1ZzB4tDfWUYcVLtj4n3YxXpCKKwgVYd6PrS2b4nJg",
            "BB3MxN1Au8VrqGmStx5VBnJHr7LGYz2dR8HdPvZjRfkM",
            "GpMZbSM2FVQdPjnJLfVyNvHZ8Y4kX3bGt9WhDcRxFbL",
            "TdkmFssn1xeTRnt8cN8vJeD85n4phWGdk6SuzcE2MMj",
            "H1gJR25VXi5Ape1gAU7fTWzZFWaCpuP3rzRtKun8Dwo2",
            "Gm54kDvwoA7829ynguwLHkAnmnVGdcWw1WZhXyhz81WP",
            "2ufmjQpzwxV5jjLfgZBm3qCs1Nt16zSDKA19APLotqwR",
            "9widFhnaG8V4TnR3zPgRqcStDJd6mU2yL9vKqBw5hX7J",
            "Cn4PFeEov8AThL2m4XqMzGcTdGfZ1j8HnRqSjPkK9vbN",
            "J24gvR5DY9fKkWdZmC3LtPnhF6G8VxQjpYTNrBs1MzAg",
            "AXvimVUMQ4hFjWpN2xK7LdCyB9r8zPsGtE3nVJkT6vRD",
            "4wiLZ6NDavftBufsbsMDjEXYjD72EziktwoHXuotB56z",
            "HYMmhz7YBGHLtcvULf2UJSb7Du8p6XFHC3wB3CVeoHm7",
            "9STntG7hKY41cdmpJ73CQnFvfQxeQ6ysmbPbrRixLnti",
            "CXTnkWuHGGJeVqwDVPARXPct9NWY8avSi22xbwW4npji",
            "CJT2f73sp6kCGNbcLcSyFLxjnx3QVGELWadNUBDaqB5t",
            "32ABTFG6PfhjjaWbxMSsFxDVDZi1eHiZBzv4RPCk4Pm1"
        ]
        
        # 测试结果存储
        self.test_results = []
    
    def run_single_test(self, test_name: str, addresses: List[str], 
                       max_workers: int, base_delay: float, 
                       timeout: float = 5.0) -> Dict:
        """运行单次测试"""
        print(f"\n🚀 {test_name}")
        print(f"   并发数: {max_workers}, 延迟: {base_delay}s, 超时: {timeout}s")
        
        start_time = time.time()
        
        # 临时修改延迟策略
        original_fetch = self.crawler.fetch_multiple_addresses_fast
        
        def modified_fetch(addrs, **kwargs):
            return original_fetch(
                addrs, 
                max_workers=max_workers,
                timeout_per_request=timeout,
                debug=False
            )
        
        # 运行测试
        results = modified_fetch(addresses)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 计算统计数据
        success_count = sum(1 for r in results.values() if r is not None)
        success_rate = (success_count / len(addresses)) * 100
        speed = len(addresses) / duration
        
        test_result = {
            "name": test_name,
            "addresses_count": len(addresses),
            "max_workers": max_workers,
            "base_delay": base_delay,
            "timeout": timeout,
            "duration": duration,
            "success_count": success_count,
            "success_rate": success_rate,
            "speed": speed,
            "timestamp": datetime.now()
        }
        
        self.test_results.append(test_result)
        
        # 显示结果
        print(f"   ✅ 成功率: {success_rate:.1f}% ({success_count}/{len(addresses)})")
        print(f"   ⏱️  耗时: {duration:.2f}s")
        print(f"   🚀 速度: {speed:.1f} 地址/秒")
        
        return test_result
    
    def run_progressive_tests(self):
        """运行渐进式测试，寻找极限"""
        print("🔥 开始爬虫极限性能测试")
        print("="*60)
        
        # 测试配置列表：(名称, 地址数量, 并发数, 延迟)
        test_configs = [
            # 阶段1：保守测试 - 确保稳定性
            ("阶段1-1: 保守测试", 10, 1, 1.0),
            ("阶段1-2: 轻度并发", 10, 2, 0.8),
            ("阶段1-3: 中等并发", 10, 3, 0.5),
            
            # 阶段2：增加负载 - 测试基础性能
            ("阶段2-1: 增加地址", 15, 3, 0.5),
            ("阶段2-2: 增加并发", 15, 4, 0.4),
            ("阶段2-3: 缩短延迟", 15, 4, 0.3),
            
            # 阶段3：压力测试 - 寻找临界点
            ("阶段3-1: 高并发测试", 20, 5, 0.3),
            ("阶段3-2: 极短延迟", 20, 5, 0.2),
            ("阶段3-3: 极限并发", 20, 6, 0.2),
            
            # 阶段4：极限测试 - 挑战边界
            ("阶段4-1: 终极测试", 20, 8, 0.1),
            ("阶段4-2: 无延迟测试", 20, 8, 0.05),
            ("阶段4-3: 最大并发", 20, 10, 0.05),
            
            # 阶段5：极端测试 - 寻找崩溃点
            ("阶段5-1: 疯狂模式", 20, 12, 0.02),
            ("阶段5-2: 机枪模式", 20, 15, 0.01),
        ]
        
        # 运行所有测试
        for i, (name, addr_count, workers, delay) in enumerate(test_configs, 1):
            # 选择测试地址
            test_addrs = self.test_addresses[:addr_count]
            
            # 运行测试
            result = self.run_single_test(name, test_addrs, workers, delay)
            
            # 在测试间隔中休息，让API服务器恢复
            if i < len(test_configs):
                rest_time = 3 if result['success_rate'] >= 90 else 5
                print(f"   😴 休息 {rest_time} 秒...")
                time.sleep(rest_time)
    
    def run_endurance_test(self, rounds: int = 5):
        """运行耐力测试 - 连续5次相同配置"""
        print(f"\n🏃‍♂️ 开始耐力测试 - 连续{rounds}轮")
        print("="*60)
        
        # 使用当前最优配置
        best_config = {
            "max_workers": 3,
            "base_delay": 0.5,
            "timeout": 5.0
        }
        
        endurance_results = []
        
        for round_num in range(1, rounds + 1):
            print(f"\n🔄 第 {round_num}/{rounds} 轮测试")
            
            result = self.run_single_test(
                f"耐力测试第{round_num}轮",
                self.test_addresses[:15],  # 使用15个地址
                **best_config
            )
            
            endurance_results.append(result)
            
            # 轮次间休息1秒
            if round_num < rounds:
                print("   😴 轮次间休息 1 秒...")
                time.sleep(1)
        
        # 分析耐力测试结果
        avg_success_rate = sum(r['success_rate'] for r in endurance_results) / len(endurance_results)
        avg_speed = sum(r['speed'] for r in endurance_results) / len(endurance_results)
        min_success_rate = min(r['success_rate'] for r in endurance_results)
        
        print(f"\n📊 耐力测试总结:")
        print(f"   平均成功率: {avg_success_rate:.1f}%")
        print(f"   最低成功率: {min_success_rate:.1f}%")
        print(f"   平均速度: {avg_speed:.1f} 地址/秒")
        
        return endurance_results
    
    def print_summary(self):
        """打印测试总结"""
        if not self.test_results:
            return
        
        print("\n📈 测试结果总结")
        print("="*80)
        
        # 按成功率排序
        sorted_results = sorted(self.test_results, key=lambda x: x['success_rate'], reverse=True)
        
        print("🏆 最佳性能配置:")
        best = sorted_results[0]
        print(f"   测试: {best['name']}")
        print(f"   成功率: {best['success_rate']:.1f}%")
        print(f"   并发数: {best['max_workers']}")
        print(f"   延迟: {best['base_delay']}s")
        print(f"   速度: {best['speed']:.1f} 地址/秒")
        
        # 按速度排序
        fastest = max(self.test_results, key=lambda x: x['speed'])
        print(f"\n⚡ 最快速度配置:")
        print(f"   测试: {fastest['name']}")
        print(f"   速度: {fastest['speed']:.1f} 地址/秒")
        print(f"   成功率: {fastest['success_rate']:.1f}%")
        print(f"   并发数: {fastest['max_workers']}")
        
        # 找出极限点
        high_success_tests = [r for r in self.test_results if r['success_rate'] >= 95]
        if high_success_tests:
            optimal = max(high_success_tests, key=lambda x: x['speed'])
            print(f"\n🎯 推荐配置 (≥95%成功率下最快):")
            print(f"   测试: {optimal['name']}")
            print(f"   成功率: {optimal['success_rate']:.1f}%")
            print(f"   速度: {optimal['speed']:.1f} 地址/秒")
            print(f"   并发数: {optimal['max_workers']}")
            print(f"   延迟: {optimal['base_delay']}s")
        
        print(f"\n📋 详细结果:")
        print(f"{'测试名称':<20} {'成功率':<8} {'速度':<12} {'并发':<6} {'延迟':<8}")
        print("-" * 60)
        for result in sorted_results:
            print(f"{result['name']:<20} {result['success_rate']:>6.1f}% {result['speed']:>10.1f}/s {result['max_workers']:>4d} {result['base_delay']:>6.2f}s")


def main():
    """主函数"""
    tester = CrawlerPerformanceTester()
    
    try:
        # 运行渐进式性能测试
        tester.run_progressive_tests()
        
        # 运行耐力测试
        tester.run_endurance_test(rounds=5)
        
        # 打印总结
        tester.print_summary()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        tester.print_summary()
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        tester.print_summary()
    
    print("\n🎯 极限性能测试完成！")


if __name__ == "__main__":
    main()
