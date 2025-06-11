#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_loader.py (v2.2 - Multi-language Version)

多語言敏感詞檢測系統的配置載入器
支援自動語言檢測和多語言檔案組織

更新內容：
- 支援 i18n_input 目錄結構
- 自動檢測可用語言
- 多語言檔案路徑管理
- 時間戳目錄支援
"""

import yaml
from pathlib import Path
import datetime
import sys
import re
from typing import Dict, List, Optional, Tuple

class ConfigLoader:
    """多語言配置載入器"""
    
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
            'backup_dir': dirs.get('backup_dir', 'backup')
        }
    
    def get_file_patterns(self) -> Dict[str, str]:
        """獲取檔案命名模式"""
        return self.config.get('file_patterns', {})
    
    def get_business_types(self) -> Dict[str, Dict]:
        """獲取業態配置"""
        return self.config.get('business_types', {})
    
    def detect_available_languages(self) -> List[str]:
        """
        檢測 i18n_input 目錄中可用的語言
        
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
        
        # 檢測配置
        detection_config = self.config.get('language_detection', {})
        ignore_case = detection_config.get('case_handling', {}).get('ignore_case', True)
        require_at_least_one = detection_config.get('validation', {}).get('require_at_least_one', True)
        
        # 掃描所有子目錄
        for lang_dir in input_dir.iterdir():
            if not lang_dir.is_dir():
                continue
            
            language = lang_dir.name
            files_found = []
            
            # 檢查 PO 檔案
            po_file = lang_dir / po_pattern
            if self._file_exists_ignore_case(po_file) if ignore_case else po_file.exists():
                files_found.append('po')
            
            # 檢查 JSON 檔案
            json_filename = json_pattern.format(language=language)
            json_file = lang_dir / json_filename
            
            if ignore_case:
                # 大小寫不敏感檢查
                json_found = False
                for file in lang_dir.glob('*.json'):
                    if file.name.lower() == json_filename.lower():
                        files_found.append('json')
                        json_found = True
                        break
                if not json_found:
                    # 檢查是否只有一個 JSON 檔案且檔名匹配語言
                    json_files = list(lang_dir.glob('*.json'))
                    for json_f in json_files:
                        if json_f.stem.lower() == language.lower():
                            files_found.append('json')
                            break
            else:
                if json_file.exists():
                    files_found.append('json')
            
            # 驗證檔案要求
            if require_at_least_one and not files_found:
                print(f"⚠️  語言目錄 '{language}' 中沒有找到有效檔案")
                print(f"   預期檔案：{po_pattern} 或 {json_filename}")
                continue
            
            available_languages.append(language)
            print(f"✅ 檢測到語言：{language} (檔案：{', '.join(files_found)})")
        
        if not available_languages:
            print(f"❌ 在 {input_dir} 中沒有檢測到任何有效的語言目錄")
            print("請確認目錄結構：")
            print(f"  {input_dir}/")
            print(f"  ├── zh-TW/")
            print(f"  │   ├── messages.po")
            print(f"  │   └── zh-TW.json")
            print(f"  └── en/")
            print(f"      ├── messages.po")
            print(f"      └── en.json")
            sys.exit(1)
        
        self._detected_languages = available_languages
        return available_languages
    
    def _file_exists_ignore_case(self, file_path: Path) -> bool:
        """檢查檔案是否存在（忽略大小寫）"""
        if file_path.exists():
            return True
        
        parent = file_path.parent
        target_name = file_path.name.lower()
        
        if not parent.exists():
            return False
        
        for file in parent.iterdir():
            if file.name.lower() == target_name:
                return True
        
        return False
    
    def get_language_files(self, language: str) -> Dict[str, Path]:
        """
        獲取指定語言的檔案路徑
        
        Args:
            language: 語言代碼
            
        Returns:
            包含檔案路徑的字典
        """
        dirs = self.get_directories()
        file_patterns = self.get_file_patterns()
        detection_config = self.config.get('language_detection', {})
        ignore_case = detection_config.get('case_handling', {}).get('ignore_case', True)
        
        input_dir = Path(dirs['input_dir'])
        lang_dir = input_dir / language
        
        if not lang_dir.exists():
            raise ValueError(f"語言目錄不存在：{lang_dir}")
        
        # 獲取檔案路徑
        result = {}
        
        # PO 檔案
        po_pattern = file_patterns.get('po_file', 'messages.po')
        po_file = lang_dir / po_pattern
        
        if ignore_case and not po_file.exists():
            # 大小寫不敏感查找
            for file in lang_dir.glob('*.po'):
                if file.name.lower() == po_pattern.lower():
                    po_file = file
                    break
        
        if po_file.exists():
            result['po_file'] = po_file
        
        # JSON 檔案
        json_pattern = file_patterns.get('json_file', '{language}.json')
        json_filename = json_pattern.format(language=language)
        json_file = lang_dir / json_filename
        
        if ignore_case and not json_file.exists():
            # 大小寫不敏感查找
            for file in lang_dir.glob('*.json'):
                if file.name.lower() == json_filename.lower():
                    json_file = file
                    break
        
        if json_file.exists():
            result['json_file'] = json_file
        
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
    
    def get_comparison_excel_path(self, language: str) -> Path:
        """
        獲取指定語言的 phrase_comparison Excel 路徑
        
        Args:
            language: 語言代碼
            
        Returns:
            Excel 檔案路徑
        """
        file_patterns = self.get_file_patterns()
        pattern = file_patterns.get('phrase_comparison', 'phrase_comparison_{language}.xlsx')
        return Path(pattern.format(language=language))
    
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
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 系統配置摘要：")
        
        # 目錄配置
        dirs = self.get_directories()
        print(f"   輸入目錄：{dirs['input_dir']}")
        print(f"   輸出目錄：{dirs['output_dir']}")
        print(f"   備份目錄：{dirs['backup_dir']}")
        
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
        files = config.get_language_files(lang)
        print(f"   {lang}:")
        for file_type, file_path in files.items():
            print(f"     {file_type}: {file_path}")
        
        # 測試輸出路徑
        output_paths = config.get_output_paths(lang)
        print(f"     輸出目錄: {output_paths['output_dir']}")
        
        # 測試 Excel 路徑
        comparison_path = config.get_comparison_excel_path(lang)
        tobemodified_path = config.get_tobemodified_excel_path(lang)
        print(f"     對照表: {comparison_path}")
        print(f"     待修正: {tobemodified_path}")
        print()