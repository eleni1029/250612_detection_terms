#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_loader.py (v2.4.1 - 修正語言代碼檢測版本)

修正內容：
1. ✅ 修正語言代碼驗證邏輯，排除日期前綴目錄
2. ✅ 增強目錄名稱過濾，避免掃描到系統檔案和日期前綴目錄
3. ✅ 更嚴格的語言代碼格式驗證
4. ✅ 改善錯誤處理和日誌輸出
5. ✅ 修正所有語法錯誤
"""

import yaml
import json
import re
from pathlib import Path
import datetime
import sys
from typing import Dict, List, Optional, Tuple

class ConfigLoader:
    """多語言配置載入器 - 修正版本，支援部分檔案和合併功能"""
    
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
    
    def get_language_po_path(self, language: str) -> Path:
        """
        獲取語言 PO 檔案目錄路徑（在 LC_MESSAGES 子目錄中）
        
        Args:
            language: 語言代碼
            
        Returns:
            Path: PO 檔案目錄路徑
        """
        dirs = self.get_directories()
        file_handling = self.get_file_handling_config()
        
        input_dir = Path(dirs['input_dir'])
        lc_messages_subdir = file_handling.get('lc_messages_subdir', 'LC_MESSAGES')
        
        return input_dir / language / lc_messages_subdir
    
    def get_language_json_path(self, language: str) -> Path:
        """
        獲取語言 JSON 檔案目錄路徑（在語言根目錄中）
        
        Args:
            language: 語言代碼
            
        Returns:
            Path: JSON 檔案目錄路徑
        """
        dirs = self.get_directories()
        input_dir = Path(dirs['input_dir'])
        
        return input_dir / language
    
    def detect_available_languages(self) -> List[str]:
        """
        檢測 i18n_input 目錄中可用的語言 - 修正版，嚴格過濾無效目錄
        
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
        
        # 掃描所有語言目錄 - 新的路徑結構：JSON 在根目錄，PO 在 LC_MESSAGES 子目錄
        for lang_dir in input_dir.iterdir():
            if not lang_dir.is_dir():
                continue
            
            language = lang_dir.name
            
            # 【修正】更嚴格的目錄過濾
            if self._should_ignore_directory(language):
                print(f"⚠️  跳過無效目錄：{language}")
                continue
            
            # 【修正】嚴格的語言代碼格式驗證
            if not self._is_valid_language_code_strict(language):
                print(f"⚠️  跳過無效語言代碼：{language}")
                continue
            
            files_found = []
            
            # 檢查 PO 檔案 - 在 LC_MESSAGES 子目錄中
            po_dir = self.get_language_po_path(language)
            po_file = po_dir / po_pattern
            if po_file.exists():
                files_found.append('po')
            
            # 檢查 JSON 檔案 - 在語言根目錄中
            json_dir = self.get_language_json_path(language)
            json_filename = json_pattern.format(language=language)
            json_file = json_dir / json_filename
            
            # 大小寫不敏感檢查
            if not json_file.exists():
                # 在語言根目錄中查找符合命名的 JSON 檔案
                for file in json_dir.glob('*.json'):
                    if file.name.lower() == json_filename.lower():
                        files_found.append('json')
                        break
            else:
                files_found.append('json')
            
            # 驗證檔案要求：至少需要一個檔案
            if require_at_least_one and not files_found:
                print(f"⚠️  語言目錄 '{language}' 中沒有找到有效檔案")
                print(f"   PO 檔案預期路徑：{po_file}")
                print(f"   JSON 檔案預期路徑：{json_file}")
                continue
            
            available_languages.append(language)
            print(f"✅ 檢測到語言：{language} (檔案：{', '.join(files_found)})")
            if 'po' in files_found:
                print(f"   PO: {po_file}")
            if 'json' in files_found:
                print(f"   JSON: {json_file}")
        
        if not available_languages:
            print(f"❌ 在 {input_dir} 中沒有檢測到任何有效的語言目錄")
            print("請確認目錄結構：")
            print(f"  {input_dir}/")
            print(f"  ├── zh-TW/")
            print(f"  │   ├── zh-TW.json          # JSON 檔案在語言根目錄")
            print(f"  │   └── LC_MESSAGES/")
            print(f"  │       └── messages.po     # PO 檔案在 LC_MESSAGES 子目錄")
            print(f"  └── en/")
            print(f"      ├── en.json")
            print(f"      └── LC_MESSAGES/")
            print(f"          └── messages.po")
            sys.exit(1)
        
        self._detected_languages = available_languages
        return available_languages

    def _should_ignore_directory(self, dir_name: str) -> bool:
        """
        【新增】檢查目錄是否應該被忽略 - 更嚴格的過濾規則
        
        Args:
            dir_name: 目錄名稱
            
        Returns:
            bool: 是否應該忽略此目錄
        """
        import fnmatch
        
        # 定義需要過濾的目錄名稱模式
        ignore_patterns = [
            '~$*',           # Excel/Word 臨時檔案前綴
            '.*',            # 隱藏目錄（以點開頭）
            '__*',           # Python 特殊目錄
            '__pycache__',   # Python 快取目錄
            '.DS_Store',     # macOS 系統檔案
            'Thumbs.db',     # Windows 縮圖快取
            '*.tmp',         # 臨時目錄
            '*.temp',        # 臨時目錄
            '*.bak',         # 備份目錄
            '*~',            # 臨時檔案
        ]
        
        # 檢查常見的忽略模式
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(dir_name, pattern):
                return True
        
        # 【新增】檢查日期前綴模式（如 "250616 zh-TW"）
        if self._has_date_prefix(dir_name):
            return True
        
        # 【新增】檢查是否包含不適當的字符
        if self._contains_invalid_chars(dir_name):
            return True
        
        return False
    
    def _has_date_prefix(self, dir_name: str) -> bool:
        """
        【新增】檢查目錄名是否包含日期前綴
        
        Args:
            dir_name: 目錄名稱
            
        Returns:
            bool: 是否包含日期前綴
        """
        # 檢查常見的日期前綴模式
        date_patterns = [
            r'^\d{6}\s',      # 6位數字開頭 + 空格 (如 "250616 zh-TW")
            r'^\d{8}\s',      # 8位數字開頭 + 空格 (如 "20250616 zh-TW")
            r'^\d{4}-\d{2}-\d{2}\s',  # YYYY-MM-DD 格式 + 空格
            r'^\d{2}-\d{2}-\d{4}\s',  # DD-MM-YYYY 格式 + 空格
            r'^\d{4}_\d{2}_\d{2}_',   # 時間戳格式
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, dir_name):
                return True
        
        return False
    
    def _contains_invalid_chars(self, dir_name: str) -> bool:
        """
        【新增】檢查目錄名是否包含不適當的字符
        
        Args:
            dir_name: 目錄名稱
            
        Returns:
            bool: 是否包含無效字符
        """
        # 語言代碼中不應該包含的字符
        invalid_chars = [' ', '\t', '\n', '\r']  # 空格和空白字符
        
        for char in invalid_chars:
            if char in dir_name:
                return True
        
        # 檢查是否包含多個連續的特殊字符
        if re.search(r'[_-]{3,}', dir_name):  # 3個或更多連續的下劃線或破折號
            return True
        
        return False

    def _is_valid_language_code_strict(self, language: str) -> bool:
        """
        【修正】嚴格驗證語言代碼格式是否有效
        
        Args:
            language: 語言代碼字符串
            
        Returns:
            bool: 是否為有效的語言代碼
        """
        # 【修正】更嚴格的語言代碼格式驗證
        strict_patterns = [
            r'^[a-z]{2}$',                      # en, zh (小寫2字母)
            r'^[a-z]{2}-[A-Z]{2}$',            # en-US, zh-TW (標準格式)
            r'^[a-z]{2}_[A-Z]{2}$',            # en_US, zh_TW (下劃線格式)
            r'^[a-z]{2}-[a-z]{2,4}$',          # en-us, zh-hans (小寫區域)
            r'^[a-z]{2}_[a-z]{2,4}$',          # en_us, zh_hans (下劃線小寫區域)
            r'^[a-z]{3}$',                      # eng, zho (3字母語言代碼)
            r'^[a-z]{2}-[A-Z]{2}-[a-z]+$',     # en-US-variant (帶變體)
        ]
        
        # 檢查是否符合任何一個嚴格模式
        for pattern in strict_patterns:
            if re.match(pattern, language):
                return True
        
        return False
    
    def _is_valid_language_code(self, language: str) -> bool:
        """
        【保留】原有的語言代碼驗證（向後相容）
        現在使用 _is_valid_language_code_strict 替代
        """
        return self._is_valid_language_code_strict(language)
        
    def get_language_files(self, language: str) -> Dict[str, Path]:
        """
        獲取指定語言的檔案路徑 - 修正版本：JSON 在根目錄，PO 在 LC_MESSAGES 子目錄
        
        Args:
            language: 語言代碼
            
        Returns:
            包含檔案路徑的字典，只返回存在的檔案
        """
        file_patterns = self.get_file_patterns()
        result = {}
        
        # 檢查 PO 檔案 - 在 LC_MESSAGES 子目錄中
        po_pattern = file_patterns.get('po_file', 'messages.po')
        po_dir = self.get_language_po_path(language)
        po_file = po_dir / po_pattern
        
        if po_file.exists():
            result['po_file'] = po_file
        
        # 檢查 JSON 檔案 - 在語言根目錄中
        json_pattern = file_patterns.get('json_file', '{language}.json')
        json_filename = json_pattern.format(language=language)
        json_dir = self.get_language_json_path(language)
        json_file = json_dir / json_filename
        
        # 大小寫不敏感查找
        if not json_file.exists():
            for file in json_dir.glob('*.json'):
                if file.name.lower() == json_filename.lower():
                    json_file = file
                    break
        
        if json_file.exists():
            result['json_file'] = json_file
        
        # 檢查是否至少有一個檔案
        file_handling = self.get_file_handling_config()
        require_at_least_one = file_handling.get('require_at_least_one', True)
        
        if require_at_least_one and not result:
            raise FileNotFoundError(
                f"語言 '{language}' 的必要檔案不存在。\n"
                f"PO 檔案預期路徑：{po_file}\n"
                f"JSON 檔案預期路徑：{json_file}"
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
    
    def get_partial_file_config(self) -> Dict:
        """獲取部分檔案處理配置"""
        return self.config.get('partial_file_handling', {})

    def get_partial_output_paths(self, language: str, timestamp: Optional[str] = None) -> Dict[str, Path]:
        """
        獲取指定語言的部分檔案輸出路徑
        
        Args:
            language: 語言代碼
            timestamp: 時間戳（如果為 None 則自動生成）
            
        Returns:
            包含部分檔案輸出路徑的字典
        """
        dirs = self.get_directories()
        file_patterns = self.get_file_patterns()
        
        # 生成時間戳
        if timestamp is None:
            timestamp_format = self.config.get('backup', {}).get('timestamp_format', '%Y%m%d_%H%M%S')
            timestamp = datetime.datetime.now().strftime(timestamp_format)
        
        # 輸出目錄
        output_dir = Path(dirs['output_dir'])
        subdir_pattern = file_patterns.get('partial_output_subdir', '{language}_{timestamp}_partial')
        lang_output_dir = output_dir / subdir_pattern.format(language=language, timestamp=timestamp)
        
        return {
            'output_dir': lang_output_dir,
            'timestamp': timestamp
        }

    def get_partial_file_paths(self, language: str, business_type: str, output_dir: Path) -> Dict[str, Path]:
        """
        獲取部分檔案的具體路徑
        
        Args:
            language: 語言代碼
            business_type: 業態代碼
            output_dir: 輸出目錄
            
        Returns:
            包含部分檔案路徑的字典
        """
        file_patterns = self.get_file_patterns()
        business_types = self.get_business_types()
        
        if business_type not in business_types:
            raise ValueError(f"未知的業態類型：{business_type}")
        
        suffix = business_types[business_type]['suffix']
        
        paths = {}
        
        # PO 部分檔案路徑
        po_pattern = file_patterns.get('partial_po', 'messages{suffix}_partial.po')
        paths['partial_po'] = output_dir / po_pattern.format(suffix=suffix)
        
        # JSON 部分檔案路徑
        json_pattern = file_patterns.get('partial_json', '{language}{suffix}_partial.json')
        paths['partial_json'] = output_dir / json_pattern.format(language=language, suffix=suffix)
        
        return paths

    def validate_partial_file_config(self) -> bool:
        """
        驗證部分檔案配置是否正確
        
        Returns:
            配置是否有效
        """
        try:
            partial_config = self.get_partial_file_config()
            
            # 檢查必要的配置項
            required_sections = ['po_files', 'json_files', 'output']
            for section in required_sections:
                if section not in partial_config:
                    print(f"⚠️  部分檔案配置缺少 '{section}' 部分")
                    return False
            
            # 檢查輸出配置
            output_config = partial_config.get('output', {})
            if not isinstance(output_config, dict):
                print("⚠️  部分檔案輸出配置格式錯誤")
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  部分檔案配置驗證失敗：{e}")
            return False

    def print_partial_config_summary(self):
        """打印部分檔案配置摘要"""
        print("📋 部分檔案配置摘要：")
        
        try:
            partial_config = self.get_partial_file_config()
            
            # PO 檔案配置
            po_config = partial_config.get('po_files', {})
            print(f"   PO 檔案：")
            print(f"     保留元信息：{po_config.get('preserve_metadata', True)}")
            print(f"     保留註解：{po_config.get('preserve_comments', True)}")
            print(f"     添加處理信息：{po_config.get('add_processing_comments', True)}")
            
            # JSON 檔案配置
            json_config = partial_config.get('json_files', {})
            print(f"   JSON 檔案：")
            print(f"     添加元信息：{json_config.get('add_metadata', True)}")
            print(f"     保持結構：{json_config.get('preserve_structure', True)}")
            print(f"     縮排空格：{json_config.get('indent', 2)}")
            
            # 輸出配置
            output_config = partial_config.get('output', {})
            print(f"   輸出設定：")
            print(f"     獨立目錄：{output_config.get('create_separate_dirs', True)}")
            print(f"     包含摘要：{output_config.get('include_summary', True)}")
            
        except Exception as e:
            print(f"   配置讀取失敗：{e}")

    # 合併功能相關方法
    def get_combine_config(self) -> Dict:
        """獲取檔案合併配置"""
        return self.config.get('combine', {
            'combine_dir': 'i18n_combine',
            'output': {
                'create_timestamped_dirs': True,
                'directory_suffix': '_combined',
                'multi_directory_suffix': '_multi_combined',
                'preserve_original_structure': True,
                'file_suffix': '_combined'
            },
            'multilang': {
                'enabled': True,
                'auto_detect_structure': True,
                'language_path_mapping': True,
                'cross_language_conflict_check': True,
                'merge_multiple_tobemodified': True,
                'json_structure': {
                    'top_level_languages': True,
                    'language_code_pattern': r'^[a-z]{2}(-[A-Z]{2})?$',
                    'auto_create_language_sections': True,
                    'preserve_non_language_keys': True
                },
                'path_mapping': {
                    'json_prefix_with_language': True,
                    'po_language_context': False,
                    'preserve_original_path': True
                }
            },
            'conflict_handling': {
                'stop_on_conflict': True,
                'show_conflict_details': True,
                'max_conflicts_to_show': 10,
                'log_all_conflicts': True,
                'include_language_in_conflict': True
            },
            'validation': {
                'check_file_existence': True,
                'validate_json_format': True,
                'validate_po_format': True,
                'warn_missing_target_files': True,
                'validate_multilang_structure': True
            },
            'merge_strategy': {
                'skip_identical_values': True,
                'case_sensitive_comparison': True,
                'trim_whitespace': True,
                'handle_empty_values': 'skip',
                'auto_detect_business_types': True,
                'merge_cross_language': True
            },
            'reporting': {
                'language_level_stats': True,
                'business_type_stats': True,
                'detailed_conflict_report': True,
                'include_path_mapping_info': True
            },
            'logging': {
                'detailed_merge_log': True,
                'include_skipped_items': False,
                'include_debug_info': True,
                'log_file_pattern': 'combine_{timestamp}.log',
                'multi_log_file_pattern': 'multi_combine_{timestamp}.log'
            }
        })

    def get_multilang_combine_config(self) -> Dict:
        """獲取多語言合併專用配置"""
        combine_config = self.get_combine_config()
        return combine_config.get('multilang', {})

    def get_combine_output_paths(self, language: str = None, timestamp: Optional[str] = None, 
                               is_multilang: bool = False, languages: List[str] = None) -> Dict[str, Path]:
        """
        獲取合併輸出路徑（支援多語言模式）
        
        Args:
            language: 語言代碼（單語言模式）
            timestamp: 時間戳（如果為 None 則自動生成）
            is_multilang: 是否為多語言模式
            languages: 多語言列表（多語言模式）
            
        Returns:
            包含合併輸出路徑的字典
        """
        combine_config = self.get_combine_config()
        dirs = self.get_directories()
        
        # 生成時間戳
        if timestamp is None:
            timestamp_format = self.config.get('backup', {}).get('timestamp_format', '%Y%m%d_%H%M%S')
            timestamp = datetime.datetime.now().strftime(timestamp_format)
        
        # 合併目錄
        combine_dir = Path(combine_config['combine_dir'])
        output_config = combine_config.get('output', {})
        
        # 輸出目錄
        output_dir = Path(dirs['output_dir'])
        
        if is_multilang and languages:
            # 多語言模式
            directory_suffix = output_config.get('multi_directory_suffix', '_multi_combined')
            languages_str = '_'.join(sorted(languages))
            combine_output_dir = output_dir / f"{timestamp}{directory_suffix}_{languages_str}"
        else:
            # 單語言模式
            directory_suffix = output_config.get('directory_suffix', '_combined')
            combine_output_dir = output_dir / f"{language}_{timestamp}{directory_suffix}"
        
        return {
            'output_dir': combine_output_dir,
            'combine_dir': combine_dir,
            'timestamp': timestamp,
            'is_multilang': is_multilang
        }

    def get_combine_file_paths(self, output_dir: Path, timestamp: str, is_multilang: bool = False) -> Dict[str, Path]:
        """
        獲取合併相關檔案路徑（支援多語言模式）
        
        Args:
            output_dir: 輸出目錄
            timestamp: 時間戳
            is_multilang: 是否為多語言模式
            
        Returns:
            包含合併檔案路徑的字典
        """
        file_patterns = self.get_file_patterns()
        combine_config = self.get_combine_config()
        
        paths = {}
        
        if is_multilang:
            # 多語言模式檔案路徑
            summary_pattern = file_patterns.get('multi_combine_summary', 'multi_combine_summary_{timestamp}.txt')
            log_pattern = combine_config.get('logging', {}).get('multi_log_file_pattern', 'multi_combine_{timestamp}.log')
        else:
            # 單語言模式檔案路徑
            summary_pattern = file_patterns.get('combine_summary', 'combine_summary_{timestamp}.txt')
            log_pattern = combine_config.get('logging', {}).get('log_file_pattern', 'combine_{timestamp}.log')
        
        paths['summary_report'] = output_dir / summary_pattern.format(timestamp=timestamp)
        paths['log_file'] = output_dir / log_pattern.format(timestamp=timestamp)
        
        return paths

    def get_combine_file_suffix(self, file_type: str) -> str:
        """
        獲取合併檔案的後綴
        
        Args:
            file_type: 檔案類型 ('po' 或 'json')
            
        Returns:
            檔案後綴字符串
        """
        file_patterns = self.get_file_patterns()
        
        if file_type.lower() == 'po':
            return file_patterns.get('combine_po_suffix', '_combined')
        elif file_type.lower() == 'json':
            return file_patterns.get('combine_json_suffix', '_combined')
        else:
            return '_combined'

    def validate_combine_config(self) -> bool:
        """
        驗證合併配置是否正確（支援多語言檢查）
        
        Returns:
            配置是否有效
        """
        try:
            combine_config = self.get_combine_config()
            
            # 檢查必要的配置項
            required_sections = ['combine_dir', 'output', 'conflict_handling']
            for section in required_sections:
                if section not in combine_config:
                    print(f"⚠️  合併配置缺少 '{section}' 部分")
                    return False
            
            # 檢查合併目錄是否存在
            combine_dir = Path(combine_config['combine_dir'])
            if not combine_dir.exists():
                print(f"⚠️  合併目錄不存在：{combine_dir}")
                print(f"    請創建 {combine_dir} 目錄並放入要合併的檔案")
                return False
            
            # 檢查多語言配置
            multilang_config = combine_config.get('multilang', {})
            if multilang_config.get('enabled', True):
                json_structure = multilang_config.get('json_structure', {})
                if json_structure.get('top_level_languages', True):
                    pattern = json_structure.get('language_code_pattern', r'^[a-z]{2}(-[A-Z]{2})?$')
                    try:
                        re.compile(pattern)
                    except re.error:
                        print(f"⚠️  多語言配置中的語言代碼模式無效：{pattern}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  合併配置驗證失敗：{e}")
            return False

    def print_combine_config_summary(self):
        """打印合併配置摘要（包含多語言信息）"""
        print("📋 檔案合併配置摘要：")
        
        try:
            combine_config = self.get_combine_config()
            
            # 基本配置
            combine_dir = combine_config.get('combine_dir', 'i18n_combine')
            print(f"   合併目錄：{combine_dir}")
            
            # 輸出配置
            output_config = combine_config.get('output', {})
            print(f"   時間戳目錄：{output_config.get('create_timestamped_dirs', True)}")
            print(f"   單語言目錄後綴：{output_config.get('directory_suffix', '_combined')}")
            print(f"   多語言目錄後綴：{output_config.get('multi_directory_suffix', '_multi_combined')}")
            print(f"   檔案後綴：{output_config.get('file_suffix', '_combined')}")
            
            # 多語言配置
            multilang_config = combine_config.get('multilang', {})
            print(f"   多語言功能：{multilang_config.get('enabled', True)}")
            if multilang_config.get('enabled', True):
                print(f"     自動檢測結構：{multilang_config.get('auto_detect_structure', True)}")
                print(f"     語言路徑映射：{multilang_config.get('language_path_mapping', True)}")
                print(f"     跨語言衝突檢查：{multilang_config.get('cross_language_conflict_check', True)}")
                print(f"     多檔案合併：{multilang_config.get('merge_multiple_tobemodified', True)}")
            
            # 衝突處理配置
            conflict_config = combine_config.get('conflict_handling', {})
            print(f"   遇衝突停止：{conflict_config.get('stop_on_conflict', True)}")
            print(f"   顯示衝突詳情：{conflict_config.get('show_conflict_details', True)}")
            print(f"   包含語言信息：{conflict_config.get('include_language_in_conflict', True)}")
            
            # 合併策略配置
            merge_config = combine_config.get('merge_strategy', {})
            print(f"   跳過相同值：{merge_config.get('skip_identical_values', True)}")
            print(f"   自動檢測業態：{merge_config.get('auto_detect_business_types', True)}")
            print(f"   跨語言合併：{merge_config.get('merge_cross_language', True)}")
            
            # 檢查目錄是否存在
            combine_dir_path = Path(combine_dir)
            if combine_dir_path.exists():
                print(f"   目錄狀態：存在")
                
                # 統計檔案
                json_files = list(combine_dir_path.rglob('*.json'))
                po_files = list(combine_dir_path.rglob('*.po'))
                
                print(f"   發現檔案：JSON {len(json_files)} 個，PO {len(po_files)} 個")
                
                # 檢查多語言 JSON 結構
                if json_files:
                    multilang_json_count = 0
                    for json_file in json_files:
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            if self._is_multilang_json_structure(data):
                                multilang_json_count += 1
                        except:
                            pass
                    print(f"   多語言 JSON：{multilang_json_count} 個")
            else:
                print(f"   目錄狀態：不存在")
            
        except Exception as e:
            print(f"   配置讀取失敗：{e}")

    def _is_multilang_json_structure(self, data: dict) -> bool:
        """檢查 JSON 是否為多語言結構"""
        if not isinstance(data, dict):
            return False
        
        combine_config = self.get_combine_config()
        multilang_config = combine_config.get('multilang', {})
        json_structure = multilang_config.get('json_structure', {})
        pattern = json_structure.get('language_code_pattern', r'^[a-z]{2}(-[A-Z]{2})?$')
        
        # 檢查頂層 key 是否像語言代碼
        try:
            for key in data.keys():
                if isinstance(key, str) and re.match(pattern, key):
                    # 如果至少有一個 key 像語言代碼，且其值是字典，則認為是多語言結構
                    if isinstance(data[key], dict):
                        return True
        except re.error:
            # 如果正則表達式模式無效，回退到簡單檢查
            pass
        
        return False
    
    def print_config_summary(self):
        """打印配置摘要 - 更新版本，包含多語言合併功能"""
        print("📋 系統配置摘要：")
        
        # 目錄配置
        dirs = self.get_directories()
        print(f"   輸入目錄：{dirs['input_dir']}")
        print(f"   檔案結構：JSON 在語言根目錄，PO 在 LC_MESSAGES 子目錄")
        print(f"   輸出目錄：{dirs['output_dir']}")
        print(f"   備份目錄：{dirs['backup_dir']}")
        
        # 檔案處理規則
        file_handling = self.get_file_handling_config()
        print(f"   檔案處理：至少需要一個檔案 = {file_handling.get('require_at_least_one', True)}")
        print(f"   LC_MESSAGES 子目錄：{file_handling.get('lc_messages_subdir', 'LC_MESSAGES')}")
        
        # 檢測到的語言
        try:
            languages = self.detect_available_languages()
            print(f"   檢測到語言：{', '.join(languages)}")
        except Exception as e:
            print(f"   語言檢測失敗：{e}")
        
        # 業態配置
        business_types = self.get_business_types()
        business_names = [bt['display_name'] for bt in business_types.values()]
        print(f"   支援業態：{', '.join(business_names)}")
        
        # 部分檔案功能
        try:
            output_config = self.config.get('output', {})
            partial_enabled = output_config.get('partial_files', {}).get('enabled', False)
            print(f"   部分檔案功能：{'啟用' if partial_enabled else '停用'}")
            
            if partial_enabled and self.validate_partial_file_config():
                print(f"   部分檔案配置：有效")
            elif partial_enabled:
                print(f"   部分檔案配置：無效")
        except Exception as e:
            print(f"   部分檔案配置檢查失敗：{e}")
        
        # 合併功能配置（包含多語言支援）
        try:
            combine_config = self.config.get('combine', {})
            if combine_config:
                print(f"   合併功能：啟用")
                combine_dir = combine_config.get('combine_dir', 'i18n_combine')
                combine_dir_path = Path(combine_dir)
                print(f"   合併目錄：{combine_dir} ({'存在' if combine_dir_path.exists() else '不存在'})")
                
                # 多語言功能狀態
                multilang_config = combine_config.get('multilang', {})
                multilang_enabled = multilang_config.get('enabled', True)
                print(f"   多語言合併：{'啟用' if multilang_enabled else '停用'}")
                
                if self.validate_combine_config():
                    print(f"   合併配置：有效")
                else:
                    print(f"   合併配置：無效")
            else:
                print(f"   合併功能：停用")
        except Exception as e:
            print(f"   合併功能檢查失敗：{e}")
        
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
            
            # 測試部分檔案輸出路徑
            partial_paths = config.get_partial_output_paths(lang)
            print(f"     部分檔案輸出目錄: {partial_paths['output_dir']}")
            
            # 測試 Excel 路徑
            comparison_path = config.get_comparison_excel_path()
            tobemodified_path = config.get_tobemodified_excel_path(lang)
            print(f"     統一對照表: {comparison_path}")
            print(f"     待修正: {tobemodified_path}")
            print()
        except Exception as e:
            print(f"   {lang}: 錯誤 - {e}")
    
    # 測試部分檔案配置
    if config.validate_partial_file_config():
        print("\n🔧 部分檔案配置測試：")
        config.print_partial_config_summary()
    
    # 測試合併配置
    if config.validate_combine_config():
        print("\n🔧 合併配置測試：")
        config.print_combine_config_summary()