#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_01_generate_xlsx.py (v2.0)

掃描指定語言的 messages.po 與 json 檔案，偵測歧義關鍵字，輸出 tobemodified.xlsx
支援多語言和可配置的業態類型。

更新內容：
- 支援 config.yaml 配置
- 支援多語言選擇
- 支援可擴充的業態類型
- 動態生成 Excel 欄位
"""

from pathlib import Path
import json
import re
import itertools
import sys
import argparse
from collections import defaultdict
from config_loader import get_config

try:
    import polib
    from openpyxl import Workbook
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install polib openpyxl")
    sys.exit(1)

def main():
    """主執行函數"""
    print("🚀 開始生成 tobemodified.xlsx (v2.0)")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 處理命令列參數
    parser = argparse.ArgumentParser(description='生成敏感詞檢測結果 Excel 檔案')
    parser.add_argument('--language', '-l', 
                       choices=list(config.get_languages().keys()),
                       default=config.get_default_language(),
                       help='指定要處理的語言')
    
    args = parser.parse_args()
    selected_language = args.language
    
    print(f"\n🌐 選擇的語言：{selected_language}")
    
    # 獲取語言檔案路徑
    language_files = config.get_language_files(selected_language)
    PO_PATH = Path(language_files['po_file'])
    JSON_PATH = Path(language_files['json_file'])
    OUT_XLSX = Path(f"tobemodified_{selected_language}.xlsx")
    
    print(f"📁 處理檔案：")
    print(f"   PO 檔案: {PO_PATH}")
    print(f"   JSON 檔案: {JSON_PATH}")
    print(f"   輸出檔案: {OUT_XLSX}")

    # 載入檢測詞典
    def load_detection_terms():
        """載入所有檢測詞典，並進行錯誤處理"""
        try:
            detection_files = config.get_detection_terms_files()
            
            # 載入基礎敏感詞
            base_file = detection_files['base']
            from detection_terms import DETECTION_TERMS
            
            # 載入各業態方案
            business_terms = {}
            business_types = config.get_business_types()
            
            for bt_code, bt_config in business_types.items():
                bt_file = detection_files[bt_code]
                display_name = bt_config['display_name']
                
                try:
                    # 動態導入模組
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(f"terms_{bt_code}", bt_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    business_terms[bt_code] = module.DETECTION_TERMS
                    print(f"✅ 載入 {bt_file} ({display_name}方案)")
                except Exception as e:
                    print(f"❌ 載入 {bt_file} 失敗：{e}")
                    sys.exit(1)
            
            print(f"✅ 成功載入檢測詞典")
            print(f"   基礎敏感詞: {len(DETECTION_TERMS)} 類別")
            for bt_code, bt_config in business_types.items():
                terms_count = len(business_terms[bt_code])
                print(f"   {bt_config['display_name']}方案: {terms_count} 類別")
            
            return DETECTION_TERMS, business_terms
            
        except ImportError as e:
            print(f"❌ 無法載入檢測詞典：{e}")
            print("請確認以下檔案存在且格式正確：")
            detection_files = config.get_detection_terms_files()
            for name, filename in detection_files.items():
                print(f"  - {filename}")
            sys.exit(1)
    
    DETECTION_TERMS, BUSINESS_TERMS = load_detection_terms()

    # 建立關鍵字到分類的映射
    print("\n🔍 建立關鍵字映射...")
    kw2cat = {}
    category_stats = defaultdict(int)
    
    for cat, words in DETECTION_TERMS.items():
        for w in words:
            if w in kw2cat:
                print(f"⚠️  重複關鍵字 '{w}' 在分類 '{cat}' 和 '{kw2cat[w]}'")
            kw2cat[w] = cat
            category_stats[cat] += 1
    
    print(f"   總關鍵字數：{len(kw2cat)}")
    print(f"   分類統計：{dict(category_stats)}")

    # 建立敏感詞到方案的映射
    def build_keyword_to_solution_mappings():
        """建立從敏感詞到解決方案的映射"""
        mappings = {}
        business_types = config.get_business_types()
        
        print(f"\n🔄 建立敏感詞到方案映射...")
        
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            solution_terms = BUSINESS_TERMS[bt_code]
            
            keyword_to_solution = {}
            mapping_stats = {'mapped': 0, 'fallback': 0, 'missing_category': 0}
            
            for keyword, category in kw2cat.items():
                solutions = solution_terms.get(category, [])
                
                if not solutions:
                    # 該分類沒有解決方案
                    keyword_to_solution[keyword] = keyword
                    mapping_stats['missing_category'] += 1
                    continue
                
                # 找到該關鍵字在基礎詞典中的索引
                base_keywords = DETECTION_TERMS.get(category, [])
                try:
                    keyword_index = base_keywords.index(keyword)
                    if keyword_index < len(solutions):
                        # 有對應的解決方案
                        keyword_to_solution[keyword] = solutions[keyword_index]
                        mapping_stats['mapped'] += 1
                    else:
                        # 索引超出方案範圍
                        keyword_to_solution[keyword] = keyword
                        mapping_stats['fallback'] += 1
                except ValueError:
                    # 關鍵字不在基礎詞典中（理論上不應該發生）
                    keyword_to_solution[keyword] = keyword
                    mapping_stats['fallback'] += 1
            
            mappings[bt_code] = keyword_to_solution
            print(f"   {display_name}方案: {mapping_stats['mapped']} 個有方案, {mapping_stats['fallback']} 個回退, {mapping_stats['missing_category']} 個無分類方案")
        
        return mappings

    BUSINESS_MAPPINGS = build_keyword_to_solution_mappings()

    # 關鍵字檢測
    _kw_sorted = sorted(kw2cat.keys(), key=len, reverse=True)
    KW_RE = re.compile("|".join(map(re.escape, _kw_sorted)))

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

    def apply_replacements(text: str, mapping: dict) -> str:
        """應用關鍵字替換"""
        if not text:
            return text
        return KW_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)

    def build_replacement_plan(keywords: list[str], mapping: dict) -> str:
        """建立替換方案說明"""
        replacements = []
        for kw in keywords:
            replacement = mapping.get(kw, kw)
            if replacement != kw:
                replacements.append(f"{kw}→{replacement}")
        return "、".join(replacements)

    # 檔案讀取函數
    def iter_po_entries(po_path: Path):
        """迭代 PO 檔案條目，增加錯誤處理"""
        if not po_path.exists():
            print(f"⚠️  {po_path} 不存在，跳過")
            return
        
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
            print(f"❌ 讀取 {po_path} 失敗：{e}")

    def iter_json_entries(json_path: Path):
        """迭代 JSON 檔案條目，改進路徑表示"""
        if not json_path.exists():
            print(f"⚠️  {json_path} 不存在，跳過")
            return
        
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
            print(f"❌ 讀取 {json_path} 失敗：{e}")

    # 掃描檔案並收集資料
    print(f"\n📖 掃描檔案...")
    rows = []
    detection_stats = defaultdict(int)

    for source, key, value in itertools.chain(
        iter_po_entries(PO_PATH),
        iter_json_entries(JSON_PATH)
    ):
        # 如果 value 為空，使用 key
        display_value = value if value else key
        
        # 檢測 key 和 value 中的敏感詞
        key_keywords = find_keywords(key)
        value_keywords = find_keywords(display_value)
        
        # 合併關鍵字，避免重複
        all_keywords = key_keywords + [kw for kw in value_keywords if kw not in key_keywords]
        
        if all_keywords:
            detection_stats[source] += 1
            detection_stats['total_entries'] += 1
            
            # 建立修正方案和結果
            row_data = [
                source,
                key,
                display_value,
                "、".join(all_keywords),  # 敏感詞列表
            ]
            
            # 添加各業態的修正方案和結果
            business_types = config.get_business_types()
            for bt_code, bt_config in business_types.items():
                mapping = BUSINESS_MAPPINGS[bt_code]
                row_data.extend([
                    build_replacement_plan(all_keywords, mapping),  # 修正方案
                    apply_replacements(display_value, mapping),     # 修正結果
                ])
            
            rows.append(row_data)

    print(f"   檢測統計：{dict(detection_stats)}")

    if not rows:
        print("✅ 未偵測到歧義詞，未產生 xlsx")
        return

    # 輸出 Excel
    print(f"\n📝 生成 Excel 檔案...")
    
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "tobemodified"
        
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
        OUT_XLSX.parent.mkdir(exist_ok=True)
        wb.save(OUT_XLSX)
        
        print(f"✅ 已輸出 {OUT_XLSX.resolve()}")
        print(f"📄 檔案大小：{OUT_XLSX.stat().st_size / 1024:.1f} KB")
        print(f"📊 總共處理：{len(rows)} 個包含敏感詞的條目")
        
    except Exception as e:
        print(f"❌ 生成 Excel 檔案失敗：{e}")
        sys.exit(1)

    # 生成統計報告
    print(f"\n📈 處理報告：")
    
    # 統計各分類的敏感詞出現次數
    category_detections = defaultdict(int)
    keyword_detections = defaultdict(int)
    
    for row in rows:
        keywords = row[3].split("、") if row[3] else []
        for kw in keywords:
            if kw in kw2cat:
                category_detections[kw2cat[kw]] += 1
                keyword_detections[kw] += 1
    
    print(f"   最常出現的分類：")
    for cat, count in sorted(category_detections.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"     {cat}: {count} 次")
    
    print(f"   最常出現的敏感詞：")
    for kw, count in sorted(keyword_detections.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"     {kw}: {count} 次")


if __name__ == "__main__":
    main()