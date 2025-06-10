#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_loader.py

配置文件載入器，提供統一的配置管理功能
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any
import sys

class ConfigLoader:
    """配置載入器類別"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置載入器
        
        Args:
            config_path: 配置文件路徑，預設為 config.yaml
        """
        self.config_path = Path(config_path)
        self.config = None
        self.load_config()
    
    def load_config(self):
        """載入配置文件"""
        try:
            if not self.config_path.exists():
                print(f"❌ 找不到配置文件：{self.config_path}")
                print("請確認 config.yaml 檔案存在")
                sys.exit(1)
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 驗證配置完整性
            self._validate_config()
            
        except yaml.YAMLError as e:
            print(f"❌ 配置文件格式錯誤：{e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 載入配置文件失敗：{e}")
            sys.exit(1)
    
    def _validate_config(self):
        """驗證配置文件完整性"""
        required_sections = ['languages', 'business_types', 'base_files']
        
        for section in required_sections:
            if section not in self.config:
                print(f"❌ 配置文件缺少必要區段：{section}")
                sys.exit(1)
        
        # 驗證至少有一種語言
        if not self.config['languages']:
            print("❌ 配置文件必須至少定義一種語言")
            sys.exit(1)
        
        # 驗證至少有一種業態
        if not self.config['business_types']:
            print("❌ 配置文件必須至少定義一種業態")
            sys.exit(1)
        
        # 驗證預設語言是否存在
        default_lang = self.config.get('default_language')
        if default_lang and default_lang not in self.config['languages']:
            print(f"❌ 預設語言 '{default_lang}' 未在語言列表中定義")
            sys.exit(1)
    
    def get_languages(self) -> Dict[str, Dict[str, Any]]:
        """獲取語言配置"""
        return self.config['languages']
    
    def get_business_types(self) -> Dict[str, Dict[str, Any]]:
        """獲取業態配置"""
        return self.config['business_types']
    
    def get_default_language(self) -> str:
        """獲取預設語言"""
        return self.config.get('default_language', list(self.config['languages'].keys())[0])
    
    def get_language_files(self, language: str = None) -> Dict[str, str]:
        """
        獲取指定語言的檔案配置
        
        Args:
            language: 語言代碼，若未指定則使用預設語言
        
        Returns:
            包含 po_file 和 json_file 的字典
        """
        if language is None:
            language = self.get_default_language()
        
        if language not in self.config['languages']:
            print(f"❌ 未知的語言：{language}")
            sys.exit(1)
        
        return self.config['languages'][language]
    
    def get_base_files(self) -> Dict[str, str]:
        """獲取基礎檔案配置"""
        return self.config['base_files']
    
    def get_excel_columns(self) -> Dict[str, Any]:
        """獲取 Excel 欄位配置"""
        return self.config.get('excel_columns', {})
    
    def get_detection_terms_files(self) -> Dict[str, str]:
        """
        獲取所有 detection_terms 檔案的映射
        
        Returns:
            字典，鍵為業態代碼，值為檔案路徑
        """
        base_name = self.get_base_files()['detection_terms']
        files = {'base': base_name}
        
        for bt_code, bt_config in self.get_business_types().items():
            suffix = bt_config['suffix']
            filename = base_name.replace('.py', f'{suffix}.py')
            files[bt_code] = filename
        
        return files
    
    def get_output_files(self, language: str = None) -> Dict[str, str]:
        """
        獲取輸出檔案路徑
        
        Args:
            language: 語言代碼
        
        Returns:
            包含各業態輸出檔案路徑的字典
        """
        if language is None:
            language = self.get_default_language()
        
        lang_files = self.get_language_files(language)
        po_base = Path(lang_files['po_file'])
        json_base = Path(lang_files['json_file'])
        
        files = {}
        
        for bt_code, bt_config in self.get_business_types().items():
            suffix = bt_config['suffix']
            files[bt_code] = {
                'po': str(po_base.with_name(f"{po_base.stem}{suffix}.po")),
                'json': str(json_base.with_name(f"{json_base.stem}{suffix}.json")),
                'display_name': bt_config['display_name']
            }
        
        return files
    
    def get_business_type_choices(self) -> List[tuple]:
        """
        獲取業態選擇列表，用於互動式選擇
        
        Returns:
            [(代碼, 顯示名稱), ...] 的列表
        """
        choices = []
        for bt_code, bt_config in self.get_business_types().items():
            choices.append((bt_code, bt_config['display_name']))
        return choices
    
    def format_excel_columns(self) -> Dict[str, str]:
        """
        格式化 Excel 欄位名稱
        
        Returns:
            包含所有業態對應欄位的字典
        """
        excel_config = self.get_excel_columns()
        business_types = self.get_business_types()
        
        columns = {}
        
        # 基礎欄位
        base_columns = excel_config.get('base_columns', [])
        for col in base_columns:
            columns[col] = col
        
        # 業態相關欄位
        bt_columns = excel_config.get('business_type_columns', {})
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            
            for col_type, col_template in bt_columns.items():
                col_name = col_template.format(display_name=display_name)
                columns[f"{col_type}_{bt_code}"] = col_name
        
        return columns
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 配置摘要：")
        print(f"   版本：{self.config.get('version', 'N/A')}")
        print(f"   語言數量：{len(self.get_languages())}")
        print(f"   業態數量：{len(self.get_business_types())}")
        print(f"   預設語言：{self.get_default_language()}")
        
        print(f"\n🌐 支援語言：")
        for lang_code, lang_config in self.get_languages().items():
            print(f"   {lang_code}: {lang_config.get('description', lang_code)}")
        
        print(f"\n🏢 支援業態：")
        for bt_code, bt_config in self.get_business_types().items():
            print(f"   {bt_code}: {bt_config['display_name']}")


# 全域配置實例
config = ConfigLoader()

# 便利函數
def get_config() -> ConfigLoader:
    """獲取全域配置實例"""
    return config

def reload_config():
    """重新載入配置"""
    config.load_config()