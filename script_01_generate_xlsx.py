#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_01_generate_xlsx.py (v2.2 - Multi-language Version)

掃描指定語言的檔案，偵測歧義關鍵字，輸出 tobemodified_{language}.xlsx
基於各語言獨立的 phrase_comparison_{language}.xlsx 檔案

功能：
1. 自動檢測可用語言或處理指定語言
2. 從對應的 phrase_comparison_{language}.xlsx 讀取敏感詞映射
3. 生成語言專屬的 tobemodified_{language}.xlsx
4. 支援多語言檔案結構
"""

import json
import re
import itertools
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from config_loader import get_config

try:
    import polib
    from openpyxl import Workbook
    import openpyxl
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install polib openpyxl")
    sys.exit(1)


class LanguageExcelMapping:
    """基於語言專屬 Excel 的映射類"""
    
    def __init__(self, config, language: str):
        """
        初始化語言專屬映射
        
        Args:
            config: 配置物件
            language: 語言代碼
        """
        self.config = config
        self.language = language
        self.excel_path = config.get_comparison_excel_path(language)
        self.mappings = {}
        self.keyword_categories = {}
        self.load_mappings()
    
    def load_mappings(self):
        """從語言專屬的 Excel 檔案載入映射關係"""
        if not self.excel_path.exists():
            print(f"❌ 找不到 {self.language} 的對照表：{self.excel_path}")
            print(f"請先執行：python generate_phrase_comparison.py --language {self.language}")
            sys.exit(1)
        
        try:
            print(f"📖 載入 {self.language} 的映射關係：{self.excel_path}")
            wb = openpyxl.load_workbook(self.excel_path, data_only=True)
            ws = wb.active
            
            # 讀取標題列
            header_row = list(ws[1])
            headers = [str(cell.value).strip() if cell.value else "" for cell in header_row]
            
            # 建立欄位索引映射
            column_indices = {header: idx for idx, header in enumerate(headers)}
            
            # 檢查必要欄位
            excel_config = self.config.get_excel_config()
            required_columns = excel_config.get('required_columns', {})
            category_col = required_columns.get('category', '敏感詞類型')
            keyword_col = required_columns.get('keyword', '敏感詞')
            
            missing_columns = []
            if category_col not in column_indices:
                missing_columns.append(category_col)
            if keyword_col not in column_indices:
                missing_columns.append(keyword_col)
            
            # 檢查業態欄位
            business_types = self.config.get_business_types()
            business_columns = excel_config.get('business_columns', {})
            solution_template = business_columns.get('solution_template', '對應方案({display_name})')
            
            for bt_code, bt_config in business_types.items():
                display_name = bt_config['display_name']
                solution_col = solution_template.format(display_name=display_name)
                if solution_col not in column_indices:
                    missing_columns.append(solution_col)
            
            if missing_columns:
                print(f"❌ Excel 缺少必要欄位：{missing_columns}")
                print(f"現有欄位：{headers}")
                sys.exit(1)
            
            # 初始化映射字典
            for bt_code in business_types.keys():
                self.mappings[bt_code] = {}
            
            # 讀取資料行
            row_count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not any(row):
                    continue
                
                # 安全讀取欄位值
                def get_cell_value(col_name):
                    if col_name in column_indices:
                        idx = column_indices[col_name]
                        if idx < len(row) and row[idx] is not None:
                            return str(row[idx]).strip()
                    return ""
                
                category = get_cell_value(category_col)
                keyword = get_cell_value(keyword_col)
                
                if not category or not keyword:
                    continue
                
                # 建立敏感詞到分類的映射
                self.keyword_categories[keyword] = category
                
                # 讀取各業態的對應方案
                for bt_code, bt_config in business_types.items():
                    display_name = bt_config['display_name']
                    solution_col = solution_template.format(display_name=display_name)
                    solution = get_cell_value(solution_col)
                    
                    # 如果沒有方案，使用原敏感詞
                    if not solution:
                        solution = keyword
                    
                    self.mappings[bt_code][keyword] = solution
                
                row_count += 1
            
            print(f"✅ 成功載入 {row_count} 個敏感詞的映射關係")
            
            # 顯示載入統計
            for bt_code, bt_config in business_types.items():
                display_name = bt_config['display_name']
                mapping_count = len(self.mappings[bt_code])
                replaced_count = sum(1 for k, v in self.mappings[bt_code].items() if k != v)
                print(f"   {display_name}: {mapping_count} 個敏感詞, {replaced_count} 個有替換方案")
            
        except Exception as e:
            print(f"❌ 載入 Excel 檔案失敗：{e}")
            sys.exit(1)
    
    def get_all_keywords(self) -> set:
        """獲取所有敏感詞"""
        return set(self.keyword_categories.keys())
    
    def get_replacement(self, keyword: str, business_type_code: str) -> str:
        """獲取指定敏感詞在指定業態下的替換方案"""
        mapping = self.mappings.get(business_type_code, {})
        return mapping.get(keyword, keyword)
    
    def apply_replacements(self, text: str, business_type_code: str) -> str:
        """對文本應用敏感詞替換"""
        if not text:
            return text
        
        mapping = self.mappings.get(business_type_code, {})
        result = text
        
        # 按長度排序，優先替換長詞
        sorted_keywords = sorted(mapping.keys(), key=len, reverse=True)
        
        for keyword in sorted_keywords:
            replacement = mapping[keyword]
            if keyword != replacement:
                result = result.replace(keyword, replacement)
        
        return result
    
    def build_replacement_plan(self, keywords: list, business_type_code: str) -> str:
        """建立替換方案說明"""
        mapping = self.mappings.get(business_type_code, {})
        replacements = []
        
        for keyword in keywords:
            replacement = mapping.get(keyword, keyword)
            if replacement != keyword:
                replacements.append(f"{keyword}→{replacement}")
        
        return "、".join(replacements)


def main():
    """主執行函數"""
    print("🚀 開始生成多語言 tobemodified Excel 檔案")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 處理命令列參數
    parser = argparse.ArgumentParser(description='生成敏感詞檢測結果 Excel 檔案')
    parser.add_argument('--language', '-l', 
                       help='指定要處理的語言（若未指定將處理所有可用語言）')
    parser.add_argument('--list-languages', action='store_true',
                       help='列出所有可用語言')
    
    args = parser.parse_args()
    
    # 檢測可用語言
    available_languages = config.detect_available_languages()
    
    if args.list_languages:
        print(f"\n🌐 可用語言列表：")
        for lang in available_languages:
            files = config.get_language_files(lang)
            comparison_path = config.get_comparison_excel_path(lang)
            status = "✅" if comparison_path.exists() else "❌ 缺少對照表"
            print(f"   {lang}: {list(files.keys())} - {status}")
        return
    
    # 選擇要處理的語言
    if args.language:
        if args.language not in available_languages:
            print(f"❌ 語言 '{args.language}' 不在可用列表中：{available_languages}")
            sys.exit(1)
        target_languages = [args.language]
        print(f"\n🌐 將處理指定語言：{args.language}")
    else:
        target_languages = available_languages
        print(f"\n🌐 將處理所有語言：{', '.join(target_languages)}")
    
    # 處理每個語言
    for language in target_languages:
        print(f"\n{'='*60}")
        print(f"📋 處理語言：{language}")
        process_language(config, language)
    
    print(f"\n🎉 所有語言處理完成！")


def process_language(config, language: str):
    """
    處理單個語言的 tobemodified 生成
    
    Args:
        config: 配置物件
        language: 語言代碼
    """
    
    # 獲取檔案路徑
    language_files = config.get_language_files(language)
    tobemodified_path = config.get_tobemodified_excel_path(language)
    
    print(f"   來源檔案：{list(language_files.values())}")
    print(f"   輸出檔案：{tobemodified_path}")
    
    # 載入語言專屬的 Excel 映射
    try:
        excel_mapper = LanguageExcelMapping(config, language)
    except Exception as e:
        print(f"❌ 載入 {language} 映射失敗：{e}")
        return False
    
    # 建立關鍵字檢測器
    all_keywords = excel_mapper.get_all_keywords()
    print(f"   敏感詞數量：{len(all_keywords)}")
    
    # 按長度排序，優先匹配長詞
    detection_config = config.get_keyword_detection_config()
    priority_by_length = detection_config.get('priority_by_length', True)
    
    if priority_by_length:
        sorted_keywords = sorted(all_keywords, key=len, reverse=True)
    else:
        sorted_keywords = sorted(all_keywords)
    
    KW_RE = re.compile("|".join(map(re.escape, sorted_keywords)))
    
    def find_keywords(text: str) -> list[str]:
        """在文本中找到所有敏感詞，避免重複"""
        if not text:
            return []
        
        seen = set()
        keywords = []
        for match in KW_RE.finditer(text):
            word = match.group(0)
            if word not in seen:
                seen.add(word)
                keywords.append(word)
        return keywords
    
    # 檔案讀取函數
    def iter_po_entries():
        """迭代 PO 檔案條目"""
        if 'po_file' not in language_files:
            return
        
        po_path = language_files['po_file']
        try:
            po_file = polib.pofile(str(po_path))
            count = 0
            for entry in po_file:
                msgid = entry.msgid or ""
                msgstr = entry.msgstr or ""
                yield ("po", msgid, msgstr)
                count += 1
            print(f"   PO 檔案: {count} 個條目")
        except Exception as e:
            print(f"❌ 讀取 PO 檔案失敗：{e}")
    
    def iter_json_entries():
        """迭代 JSON 檔案條目"""
        if 'json_file' not in language_files:
            return
        
        json_path = language_files['json_file']
        try:
            data = json.loads(json_path.read_text("utf-8"))
            
            def walk_json(node, path=""):
                """遞迴遍歷 JSON 結構"""
                if isinstance(node, dict):
                    for key, value in node.items():
                        new_path = f"{path}.{key}" if path else key
                        yield from walk_json(value, new_path)
                elif isinstance(node, list):
                    for index, value in enumerate(node):
                        new_path = f"{path}[{index}]"
                        yield from walk_json(value, new_path)
                else:
                    yield ("json", path, str(node))
            
            count = 0
            for entry in walk_json(data):
                yield entry
                count += 1
            print(f"   JSON 檔案: {count} 個條目")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 格式錯誤：{e}")
        except Exception as e:
            print(f"❌ 讀取 JSON 檔案失敗：{e}")
    
    # 掃描檔案並收集資料
    print(f"📖 掃描 {language} 檔案...")
    rows = []
    detection_stats = defaultdict(int)
    
    for source, key, value in itertools.chain(iter_po_entries(), iter_json_entries()):
        # 如果 value 為空，使用 key
        display_value = value if value else key
        
        # 檢測 key 和 value 中的敏感詞
        key_keywords = find_keywords(key)
        value_keywords = find_keywords(display_value)
        
        # 合併關鍵字，避免重複
        all_keywords_found = key_keywords + [kw for kw in value_keywords if kw not in key_keywords]
        
        if all_keywords_found:
            detection_stats[source] += 1
            detection_stats['total_entries'] += 1
            
            # 使用 Excel 映射建立修正方案和結果
            row_data = [
                source,
                key,
                display_value,
                "、".join(all_keywords_found),  # 敏感詞列表
            ]
            
            # 添加各業態的修正方案和結果
            business_types = config.get_business_types()
            for bt_code, bt_config in business_types.items():
                row_data.extend([
                    excel_mapper.build_replacement_plan(all_keywords_found, bt_code),  # 修正方案
                    excel_mapper.apply_replacements(display_value, bt_code),           # 修正結果
                ])
            
            rows.append(row_data)
    
    print(f"   檢測統計：{dict(detection_stats)}")
    
    if not rows:
        print(f"✅ {language} 未偵測到歧義詞，未產生 Excel")
        return True
    
    # 輸出 Excel
    print(f"📝 生成 {language} Excel 檔案...")
    
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = f"tobemodified_{language}"
        
        # 動態建立標題列
        headers = ["source", "key", "value", "敏感詞"]
        
        business_types = config.get_business_types()
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            headers.extend([
                f"修正方案({display_name})",
                f"修正結果({display_name})"
            ])
        
        ws.append(headers)
        print(f"   Excel 標題列: {headers}")
        
        # 資料列
        for row in rows:
            ws.append(row)
        
        # 自動調整欄寬
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            
            for cell in col:
                try:
                    cell_length = len(str(cell.value or ""))
                    if cell_length > max_length:
                        max_length = cell_length
                except:
                    pass
            
            # 設定欄寬，最小10，最大80
            adjusted_width = min(max(max_length + 4, 10), 80)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 確保輸出目錄存在
        tobemodified_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(tobemodified_path)
        
        print(f"✅ 已輸出 {tobemodified_path.resolve()}")
        print(f"📄 檔案大小：{tobemodified_path.stat().st_size / 1024:.1f} KB")
        print(f"📊 總共處理：{len(rows)} 個包含敏感詞的條目")
        
        # 生成統計報告
        if excel_mapper.keyword_categories:
            category_detections = defaultdict(int)
            keyword_detections = defaultdict(int)
            
            for row in rows:
                keywords = row[3].split("、") if row[3] else []
                for kw in keywords:
                    if kw in excel_mapper.keyword_categories:
                        category_detections[excel_mapper.keyword_categories[kw]] += 1
                        keyword_detections[kw] += 1
            
            print(f"   最常出現的分類：")
            for cat, count in sorted(category_detections.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"     {cat}: {count} 次")
            
            print(f"   最常出現的敏感詞：")
            for kw, count in sorted(keyword_detections.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"     {kw}: {count} 次")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成 Excel 檔案失敗：{e}")
        return False


if __name__ == "__main__":
    main()