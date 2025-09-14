import yaml
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """配置管理器，用于加载和管理配置文件中的预设"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # 获取当前文件所在目录的config.yaml
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'config.yaml')
        
        self.config_path = config_path
        self._config = None
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file) or {}
            return self._config
        except FileNotFoundError:
            print(f"配置文件未找到: {self.config_path}")
            self._config = {}
            return self._config
        except yaml.YAMLError as e:
            print(f"配置文件格式错误: {e}")
            self._config = {}
            return self._config
    
    def get_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的预设配置
        
        Args:
            preset_name: 预设名称
            
        Returns:
            预设配置字典，如果不存在则返回None
        """
        if not self._config:
            self.load_config()
        
        presets = self._config.get('presets', {})
        return presets.get(preset_name)
    
    def list_presets(self) -> list:
        """列出所有可用的预设名称"""
        if not self._config:
            self.load_config()
        
        presets = self._config.get('presets', {})
        return list(presets.keys())
    
    def get_toptraded_params(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """获取指定预设的 toptraded 参数
        
        Args:
            preset_name: 预设名称
            
        Returns:
            toptraded 参数字典，如果不存在则返回None
        """
        presets = self._config.get('crawlers', {}).get('jupiter', {}).get('toptraded', {})
        return presets.get(preset_name)
    
    def get_crawler_performance_config(self, crawler_name: str, mode: str = 'balanced') -> Optional[Dict[str, Any]]:
        """获取爬虫性能配置
        
        Args:
            crawler_name: 爬虫名称 (如 'okx_address_balance')
            mode: 性能模式 ('conservative', 'balanced', 'high_speed', 'lightweight')
            
        Returns:
            性能配置字典，如果不存在则返回None
        """
        if not self._config:
            self.load_config()
        
        performance_configs = self._config.get('crawler_performance', {})
        crawler_configs = performance_configs.get(crawler_name, {})
        return crawler_configs.get(mode)
    
    def list_performance_modes(self, crawler_name: str) -> list:
        """列出指定爬虫的所有性能模式
        
        Args:
            crawler_name: 爬虫名称
            
        Returns:
            性能模式列表
        """
        if not self._config:
            self.load_config()
        
        performance_configs = self._config.get('crawler_performance', {})
        crawler_configs = performance_configs.get(crawler_name, {})
        return list(crawler_configs.keys())

    def get_jupiter_presets(self) -> Dict[str, Any]:
        """获取所有Jupiter预设配置
        
        Returns:
            Jupiter预设配置字典
        """
        if not self._config:
            self.load_config()
        
        return self._config.get('crawlers', {}).get('jupiter', {}).get('toptraded', {})

    def build_jupiter_api_params(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """构建Jupiter API请求参数
        
        Args:
            preset_name: 预设名称
            
        Returns:
            API请求参数字典，包含正确的时间后缀
        """
        params = self.get_toptraded_params(preset_name)
        if not params:
            return None
        
        # 复制参数避免修改原始配置
        api_params = params.copy()
        
        # 获取时间框架
        time_frame = api_params.pop('timeFrame', '5m')
        
        # 处理交易量参数，添加时间后缀
        if 'minVolume' in api_params:
            min_volume = api_params.pop('minVolume')
            api_params[f'minVolume{time_frame}'] = min_volume
        
        if 'maxVolume' in api_params:
            max_volume = api_params.pop('maxVolume')
            api_params[f'maxVolume{time_frame}'] = max_volume
        
        return {
            'timeFrame': time_frame,
            'params': api_params
        }

# 创建全局配置管理器实例
config_manager = ConfigManager()
