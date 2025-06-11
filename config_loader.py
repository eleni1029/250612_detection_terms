#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_loader.py (v2.3 - 修正路徑結構版本)

基於現有邏輯進行最小化調整，主要修正：
1. 路徑結構從 i18n_input/{language}/ 改為 i18n_input/{language}/LC_MESSAGES/
2. 檔案讀取邏輯：優先讀取 messages.po 和 {language}.json，忽略其他檔案
3. 如果兩個檔案都不存在才報錯，有其中一個就可以處理
"""

import yaml
from pathlib import Path
import datetime
import sys
import re
from typing import Dict, List, Optional, Tuple

class ConfigLoader:
    """多語言配置載入器 - 修正版本"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置載入器
        
        Args:
            config_path: 配置檔案路徑
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._detected_languages = None
        
    def _load_config(self) -> dict:
        """載入配置檔案"""
        if not self.config_path.exists():
            print(f"❌ 找不到配置檔案：{self.config_path}")
            sys.exit(1)
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            print(f"❌ 配置檔案格式錯誤：{e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 載入配置檔案失敗：{e}")
            sys.exit(1)
    
    def get_directories(self) -> Dict[str, str]:
        """獲取目錄配置"""
        dirs = self.config.get('directories', {})
        return {
            'input_dir': dirs.get('input_dir', 'i18n_input'),
            'output_dir': dirs.get('output_dir', 'i18n_output'),
            'backup_dir': dirs.get('backup_dir', 'backup'),
            'language_subdir': dirs.get('language_subdir', '{language}/LC_MESSAGES')  # 新增
        }
    
    def get_file_patterns(self) -> Dict[str, str]:
        """獲取檔案命名模式"""
        return self.config.get('file_patterns', {})
    
    def get_business_types(self) -> Dict[str, Dict]:
        """獲取業態配置"""
        return self.config.get('business_types', {})
    
    def get_language_input_path(self, language: str) -> Path:
        """
        獲取語言輸入目錄路徑 - 新的路徑結構
        
        Args:
            language: 語言代碼
            
        Returns:
            Path: 語言輸入目錄路徑
        """
        dirs = self.get_directories()
        input_dir = Path(dirs['input_dir'])
        language_subdir = dirs['language_subdir'].format(language=language)
        
        return input_dir / language_subdir
    
    def detect_available_languages(self) -> List[str]:
        """
        檢測 i18n_input 目錄中可用的語言 - 使用新的路徑結構
        
        Returns:
            可用語言列表
        """
        if self._detected_languages is not None:
            return self._detected_languages
        
        dirs = self.get_directories()
        input_dir = Path(dirs['input_dir'])
        
        if not input_dir.exists():
            print(f"❌ 輸入目錄不存在：{input_dir}")
            print(f"請創建 {input_dir} 目錄並放入各語言的檔案")
            sys.exit(1)
        
        available_languages = []
        file_patterns = self.get_file_patterns()
        po_pattern = file_patterns.get('po_file', 'messages.po')
        json_pattern = file_patterns.get('json_file', '{language}.json')
        
        # 檔案處理規則
        file_handling = self.config.get('file_handling', {})
        require_at_least_one = file_handling.get('require_at_least_one', True)
        ignore_patterns = file_handling.get('ignore_patterns', ['*.tmp', '*.bak', '*.log', '*~'])
        
        # 掃描所有語言目錄 - 考慮新的路徑結構
        for lang_dir in input_dir.iterdir():
            if not lang_dir.is_dir():
                continue
            
            language = lang_dir.name
            # 構建完整的語言檔案路徑
            language_files_dir = self.get_language_input_path(language)
            
            if not language_files_dir.exists():
                # 如果 LC_MESSAGES 目錄不存在，也檢查直接在語言目錄下的情況（向下相容）
                language_files_dir = lang_dir
            
            files_found = []
            
            # 檢查 PO 檔案 - 只查找 messages.po
            po_file = language_files_dir / po_pattern
            if po_file.exists():
                files_found.append('po')
            
            # 檢查 JSON 檔案 - 只查找 {language}.json
            json_filename = json_pattern.format(language=language)
            json_file = language_files_dir / json_filename
            
            # 大小寫不敏感檢查
            if not json_file.exists():
                # 在目錄中查找符合命名的 JSON 檔案
                for file in language_files_dir.glob('*.json'):
                    if file.name.lower() == json_filename.lower():
                        files_found.append('json')
                        break
            else:
                files_found.append('json')
            
            # 驗證檔案要求：至少需要一個檔案
            if require_at_least_one and not files_found:
                print(f"⚠️  語言目錄 '{language}' 中沒有找到有效檔案")
                print(f"   預期路徑：{language_files_dir}")
                print(f"   預期檔案：{po_pattern} 或 {json_filename}")
                continue
            
            available_languages.append(language)
            print(f"✅ 檢測到語言：{language} (檔案：{', '.join(files_found)})")
            print(f"   路徑：{language_files_dir}")
        
        if not available_languages:
            print(f"❌ 在 {input_dir} 中沒有檢測到任何有效的語言目錄")
            print("請確認目錄結構：")
            print(f"  {input_dir}/")
            print(f"  ├── zh-TW/")
            print(f"  │   └── LC_MESSAGES/")
            print(f"  │       ├── messages.po")
            print(f"  │       └── zh-TW.json")
            print(f"  └── en/")
            print(f"      └── LC_MESSAGES/")
            print(f"          ├── messages.po")
            print(f"          └── en.json")
            sys.exit(1)
        
        self._detected_languages = available_languages
        return available_languages
    
    def get_language_files(self, language: str) -> Dict[str, Path]:
        """
        獲取指定語言的檔案路徑 - 修正版本
        
        Args:
            language: 語言代碼
            
        Returns:
            包含檔案路徑的字典，只返回存在的檔案
        """
        language_files_dir = self.get_language_input_path(language)
        
        # 如果 LC_MESSAGES 目錄不存在，嘗試直接在語言目錄下查找（向下相容）
        if not language_files_dir.exists():
            dirs = self.get_directories()
            input_dir = Path(dirs['input_dir'])
            language_files_dir = input_dir / language
        
        if not language_files_dir.exists():
            raise ValueError(f"語言目錄不存在：{language_files_dir}")
        
        file_patterns = self.get_file_patterns()
        result = {}
        
        # 檢查 PO 檔案 - 只查找 messages.po
        po_pattern = file_patterns.get('po_file', 'messages.po')
        po_file = language_files_dir / po_pattern
        
        if po_file.exists():
            result['po_file'] = po_file
        
        # 檢查 JSON 檔案 - 只查找 {language}.json
        json_pattern = file_patterns.get('json_file', '{language}.json')
        json_filename = json_pattern.format(language=language)
        json_file = language_files_dir / json_filename
        
        # 大小寫不敏感查找
        if not json_file.exists():
            for file in language_files_dir.glob('*.json'):
                if file.name.lower() == json_filename.lower():
                    json_file = file
                    break
        
        if json_file.exists():
            result['json_file'] = json_file
        
        # 檢查是否至少有一個檔案
        file_handling = self.config.get('file_handling', {})
        require_at_least_one = file_handling.get('require_at_least_one', True)
        
        if require_at_least_one and not result:
            raise FileNotFoundError(
                f"語言 '{language}' 的必要檔案不存在。\n"
                f"預期路徑：{language_files_dir}\n"
                f"預期檔案：{po_pattern} 或 {json_filename}"
            )
        
        return result
    
    def get_output_paths(self, language: str, timestamp: Optional[str] = None) -> Dict[str, Path]:
        """
        獲取指定語言的輸出路徑
        
        Args:
            language: 語言代碼
            timestamp: 時間戳（如果為 None 則自動生成）
            
        Returns:
            包含輸出路徑的字典
        """
        dirs = self.get_directories()
        file_patterns = self.get_file_patterns()
        
        # 生成時間戳
        if timestamp is None:
            timestamp_format = self.config.get('backup', {}).get('timestamp_format', '%Y%m%d_%H%M%S')
            timestamp = datetime.datetime.now().strftime(timestamp_format)
        
        # 輸出目錄
        output_dir = Path(dirs['output_dir'])
        subdir_pattern = file_patterns.get('output_subdir', '{language}_{timestamp}')
        lang_output_dir = output_dir / subdir_pattern.format(language=language, timestamp=timestamp)
        
        return {
            'output_dir': lang_output_dir,
            'timestamp': timestamp
        }
    
    def get_comparison_excel_path(self, language: str = None) -> Path:
        """
        獲取 phrase_comparison Excel 路徑 - 統一版本
        
        Args:
            language: 語言代碼（保留參數以維持相容性，但實際不使用）
            
        Returns:
            Excel 檔案路徑
        """
        file_patterns = self.get_file_patterns()
        # 使用統一的檔案名，不再按語言分別
        pattern = file_patterns.get('phrase_comparison', 'phrase_comparison.xlsx')
        return Path(pattern)
    
    def get_tobemodified_excel_path(self, language: str) -> Path:
        """
        獲取指定語言的 tobemodified Excel 路徑
        
        Args:
            language: 語言代碼
            
        Returns:
            Excel 檔案路徑
        """
        file_patterns = self.get_file_patterns()
        pattern = file_patterns.get('tobemodified', 'tobemodified_{language}.xlsx')
        return Path(pattern.format(language=language))
    
    def get_backup_dir(self) -> Path:
        """獲取備份目錄路徑"""
        dirs = self.get_directories()
        return Path(dirs['backup_dir'])
    
    def get_excel_config(self) -> Dict:
        """獲取 Excel 配置"""
        return self.config.get('excel_config', {})
    
    def get_keyword_detection_config(self) -> Dict:
        """獲取敏感詞檢測配置"""
        return self.config.get('keyword_detection', {})
    
    def get_backup_config(self) -> Dict:
        """獲取備份配置"""
        return self.config.get('backup', {})
    
    def get_file_handling_config(self) -> Dict:
        """獲取檔案處理配置"""
        return self.config.get('file_handling', {})
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 系統配置摘要：")
        
        # 目錄配置
        dirs = self.get_directories()
        print(f"   輸入目錄：{dirs['input_dir']}")
        print(f"   語言子目錄模式：{dirs['language_subdir']}")
        print(f"   輸出目錄：{dirs['output_dir']}")
        print(f"   備份目錄：{dirs['backup_dir']}")
        
        # 檔案處理規則
        file_handling = self.get_file_handling_config()
        print(f"   檔案處理：至少需要一個檔案 = {file_handling.get('require_at_least_one', True)}")
        
        # 檢測到的語言
        languages = self.detect_available_languages()
        print(f"   檢測到語言：{', '.join(languages)}")
        
        # 業態配置
        business_types = self.get_business_types()
        business_names = [bt['display_name'] for bt in business_types.values()]
        print(f"   支援業態：{', '.join(business_names)}")
        
        # 版本資訊
        version = self.config.get('version', 'Unknown')
        system_type = self.config.get('system_type', 'Unknown')
        print(f"   系統版本：{version} ({system_type})")


# 全域配置實例
_config_instance = None

def get_config() -> ConfigLoader:
    """獲取全域配置實例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance

def reload_config():
    """重新載入配置"""
    global _config_instance
    _config_instance = None
    return get_config()


if __name__ == "__main__":
    # 測試配置載入
    config = get_config()
    config.print_config_summary()
    
    print("\n🔍 檢測檔案路徑：")
    for lang in config.detect_available_languages():
        try:
            files = config.get_language_files(lang)
            print(f"   {lang}:")
            for file_type, file_path in files.items():
                print(f"     {file_type}: {file_path}")
            
            # 測試輸出路徑
            output_paths = config.get_output_paths(lang)
            print(f"     輸出目錄: {output_paths['output_dir']}")
            
            # 測試 Excel 路徑
            comparison_path = config.get_comparison_excel_path()
            tobemodified_path = config.get_tobemodified_excel_path(lang)
            print(f"     統一對照表: {comparison_path}")
            print(f"     待修正: {tobemodified_path}")
            print()
        except Exception as e:
            print(f"   {lang}: 錯誤 - {e}")