#!/usr/bin/env python3
"""
SoLab 日志配置模块
Logging Configuration Module
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Optional

class SoLabLogger:
    """SoLab 日志管理器"""
    
    def __init__(self, name: str = "SoLab", log_level: str = "INFO"):
        self.name = name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = None
        self.setup_logger()
    
    def setup_logger(self):
        """设置日志器"""
        # 创建日志器
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.log_level)
        
        # 避免重复添加处理器
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器 - 实时输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        
        # 文件处理器 - 保存到文件
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 按日期创建日志文件
        today = datetime.now().strftime('%Y%m%d')
        log_file = os.path.join(log_dir, f'solab_{today}.log')
        
        # 使用RotatingFileHandler避免日志文件过大
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        
        # 添加处理器到日志器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        # 防止日志向上传播
        self.logger.propagate = False
    
    def get_logger(self):
        """获取日志器"""
        return self.logger
    
    def info(self, message: str):
        """输出信息日志"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """输出调试日志"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """输出警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """输出错误日志"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """输出严重错误日志"""
        self.logger.critical(message)


class CrawlerLogger:
    """爬虫专用日志器"""
    
    def __init__(self, crawler_name: str, log_level: str = "INFO"):
        self.crawler_name = crawler_name
        self.logger = SoLabLogger(f"Crawler.{crawler_name}", log_level)
        self.start_time = datetime.now()
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
    
    def log_start(self, task_description: str, total_items: Optional[int] = None):
        """记录任务开始"""
        self.start_time = datetime.now()
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        
        message = f"🚀 开始任务: {task_description}"
        if total_items:
            message += f" (共{total_items}项)"
        
        self.logger.info(message)
        self.logger.info("="*60)
    
    def log_progress(self, current: int, total: int, item_description: str, status: str = "处理中"):
        """记录进度"""
        self.processed_count = current
        percentage = (current / total * 100) if total > 0 else 0
        
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        speed = current / elapsed_time if elapsed_time > 0 else 0
        
        self.logger.info(f"📈 [{current}/{total}] ({percentage:.1f}%) {item_description} - {status}")
        
        if current % 10 == 0 or current == total:  # 每10个或最后一个显示速度
            self.logger.info(f"⏱️  处理速度: {speed:.2f} 项/秒, 已用时: {elapsed_time:.1f}秒")
    
    def log_success(self, item_description: str, details: str = ""):
        """记录成功"""
        self.success_count += 1
        message = f"✅ 成功: {item_description}"
        if details:
            message += f" - {details}"
        self.logger.info(message)
    
    def log_error(self, item_description: str, error_message: str):
        """记录错误"""
        self.error_count += 1
        self.logger.error(f"❌ 失败: {item_description} - {error_message}")
    
    def log_warning(self, item_description: str, warning_message: str):
        """记录警告"""
        self.logger.warning(f"⚠️  警告: {item_description} - {warning_message}")
    
    def log_completion(self, task_description: str):
        """记录任务完成"""
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        success_rate = (self.success_count / self.processed_count * 100) if self.processed_count > 0 else 0
        
        self.logger.info("="*60)
        self.logger.info(f"🎉 任务完成: {task_description}")
        self.logger.info(f"📊 统计信息:")
        self.logger.info(f"   - 总处理数: {self.processed_count}")
        self.logger.info(f"   - 成功数: {self.success_count}")
        self.logger.info(f"   - 失败数: {self.error_count}")
        self.logger.info(f"   - 成功率: {success_rate:.1f}%")
        self.logger.info(f"   - 总用时: {elapsed_time:.1f}秒")
        self.logger.info(f"   - 平均速度: {self.processed_count/elapsed_time:.2f} 项/秒")
        self.logger.info("="*60)
    
    def log_qualified_found(self, item_description: str, qualification_details: str):
        """记录找到符合条件的项目"""
        self.logger.info(f"🎯 发现符合条件: {item_description}")
        self.logger.info(f"📋 条件详情: {qualification_details}")
    
    def debug(self, message: str):
        """调试日志"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)


# 全局日志器实例
main_logger = SoLabLogger("SoLab.Main")

def get_logger(name: str = "SoLab", log_level: str = "INFO") -> SoLabLogger:
    """获取日志器实例"""
    return SoLabLogger(name, log_level)

def get_crawler_logger(crawler_name: str, log_level: str = "INFO") -> CrawlerLogger:
    """获取爬虫日志器实例"""
    return CrawlerLogger(crawler_name, log_level)
