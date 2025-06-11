#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_01_generate_xlsx.py (v2.1 - Pure Excel Version)

掃描指定語言的 messages.po 與 json 檔案，偵測歧義關鍵字，輸出 tobemodified.xlsx
完全基於 phrase_comparison.xlsx，不再依賴任何 Python 字典檔案。

更新內容：
- 完全移除對 detection_terms.py 的依賴
- 直接從 phrase_comparison.xlsx 讀取所有敏感詞
- 簡化工作流程：只需維護一個 Excel 檔案
- 更安全、更直觀的純 Excel 方案
"""

from pathlib import Path
import json
import re
import itertools
import sys
import argparse
from collections import defaultdict
from config_loader import get_config
from excel_based_mapping import get_excel_mapping

try:
    import polib
    from openpyxl import Workbook
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install polib openpyxl")
    sys.exit(1)

def main():
    """主執行函數"""
    print("🚀 開始生成 tobemodified.xlsx (v2.1 - Pure Excel Version)")
    print("📊 完全基於 Excel 的敏感詞檢測系統")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 處理命令列參數
    parser = argparse.ArgumentParser(description='生成敏感詞檢測結果 Excel 檔案')
    parser.add_argument('--language', '-l', 
                       choices=list(config.get_languages().keys()),
                       default=config.get_default_language(),
                       help='指定要處理的語言')
    parser.add_argument('--excel-source', '-e',
                       default=config.config.get('base_files', {}).get('phrase_comparison_excel', 'phrase_comparison.xlsx'),
                       help='指定 phrase_comparison Excel 檔案路徑')
    
    args = parser.parse_args()
    selected_language = args.language
    excel_source = args.excel_source
    
    print(f"\n🌐 選擇的語言：{selected_language}")
    print(f"📊 數據來源：{excel_source}")
    
    # 獲取語言檔案路徑
    language_files = config.get_language_files(selected_language)
    PO_PATH = Path(language_files['po_file'])
    JSON_PATH = Path(language_files['json_file'])
    
    # 生成輸出檔案名
    output_template = config.config.get('file_generation', {}).get('tobemodified_template', 'tobemodified_{language}.xlsx')
    OUT_XLSX = Path(output_template.format(language=selected_language))
    
    print(f"📁 處理檔案：")
    print(f"   PO 檔案: {PO_PATH}")
    print(f"   JSON 檔案: {JSON_PATH}")
    print(f"   輸出檔案: {OUT_XLSX}")

    # 載入基於 Excel 的映射
    print(f"\n📖 載入 Excel 映射和敏感詞...")
    try:
        excel_mapper = get_excel_mapping(excel_source)
        
        # 驗證映射完整性
        excel_mapper.validate_completeness()
        
        print("✅ Excel 映射載入成功")
        
    except Exception as e:
        print(f"❌ 載入 Excel 映射失敗：{e}")
        print("請確認以下事項：")
        print(f"1. {excel_source} 檔案存在")
        print("2. 檔案格式正確，包含必要欄位")
        print("3. Excel 中有足夠的敏感詞數據")
        
        # 提供創建範例 Excel 的建議
        print(f"\n💡 如果您沒有 {excel_source}，可以手動創建包含以下欄位的 Excel：")
        print("   - 敏感詞類型")
        print("   - 敏感詞")
        business_types = config.get_business_types()
        for bt_code, bt_config in business_types.items():
            print(f"   - 對應方案({bt_config['display_name']})")
        
        sys.exit(1)

    # 從 Excel 映射中提取所有敏感詞
    print(f"\n🔍 從 Excel 提取敏感詞...")
    all_keywords = set()
    keyword_categories = {}  # 敏感詞到分類的映射
    
    # 從任一業態的映射中提取所有關鍵詞（它們應該是相同的）
    business_types = config.get_business_types()
    first_bt_code = list(business_types.keys())[0]
    first_mapping = excel_mapper.get_mapping(first_bt_code)
    
    all_keywords = set(first_mapping.keys())
    
    # 建立敏感詞到分類的映射（從 Excel 讀取）
    print(f"📋 建立敏感詞分類映射...")
    try:
        # 重新讀取 Excel 來獲取分類資訊
        import openpyxl
        wb = openpyxl.load_workbook(excel_source, data_only=True)
        ws = wb.active
        
        # 讀取標題列
        header_row = list(ws[1])
        headers = [str(cell.value).strip() if cell.value else "" for cell in header_row]
        column_indices = {header: idx for idx, header in enumerate(headers)}
        
        # 建立敏感詞到分類的映射
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not any(row):
                continue
            
            def get_cell_value(col_name):
                if col_name in column_indices:
                    idx = column_indices[col_name]
                    if idx < len(row) and row[idx] is not None:
                        return str(row[idx]).strip()
                return ""
            
            category = get_cell_value("敏感詞類型")
            keyword = get_cell_value("敏感詞")
            
            if category and keyword:
                keyword_categories[keyword] = category
        
        print(f"✅ 成功建立 {len(keyword_categories)} 個敏感詞的分類映射")
        
    except Exception as e:
        print(f"⚠️  無法建立分類映射：{e}")
        print("將繼續執行，但統計報告可能不完整")
    
    print(f"   總敏感詞數：{len(all_keywords)}")
    if keyword_categories:
        category_counts = defaultdict(int)
        for category in keyword_categories.values():
            category_counts[category] += 1
        print(f"   分類統計：{dict(category_counts)}")

    # 建立關鍵字檢測器
    print(f"\n🔍 建立關鍵字檢測器...")
    
    # 按長度排序，優先匹配長詞避免部分匹配
    keyword_detection_config = config.config.get('system', {}).get('keyword_detection', {})
    priority_by_length = keyword_detection_config.get('priority_by_length', True)
    
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
    def iter_po_entries(po_path: Path):
        """迭代 PO 檔案條目"""
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
        """迭代 JSON 檔案條目"""
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
            for bt_code, bt_config in business_types.items():
                row_data.extend([
                    excel_mapper.build_replacement_plan(all_keywords_found, bt_code),  # 修正方案
                    excel_mapper.apply_replacements(display_value, bt_code),           # 修正結果
                ])
            
            rows.append(row_data)

    print(f"   檢測統計：{dict(detection_stats)}")

    if not rows:
        print("✅ 未偵測到歧義詞，未產生 xlsx")
        print("這可能意味著：")
        print("1. 翻譯檔案中沒有敏感詞")
        print("2. Excel 中的敏感詞與翻譯檔案內容不匹配")
        print("3. 敏感詞列表需要更新")
        return

    # 輸出 Excel
    print(f"\n📝 生成 Excel 檔案...")
    
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = config.config.get('excel_config', {}).get('worksheet_name', 'tobemodified')
        
        # 動態建立標題列
        headers = ["source", "key", "value", "敏感詞"]
        
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
    
    if keyword_categories:
        # 統計各分類的敏感詞出現次數
        category_detections = defaultdict(int)
        keyword_detections = defaultdict(int)
        
        for row in rows:
            keywords = row[3].split("、") if row[3] else []
            for kw in keywords:
                if kw in keyword_categories:
                    category_detections[keyword_categories[kw]] += 1
                    keyword_detections[kw] += 1
        
        print(f"   最常出現的分類：")
        for cat, count in sorted(category_detections.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     {cat}: {count} 次")
        
        print(f"   最常出現的敏感詞：")
        for kw, count in sorted(keyword_detections.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     {kw}: {count} 次")
    else:
        print(f"   無法生成詳細統計（分類映射不可用）")

    print(f"\n✨ 純 Excel 方案優勢：")
    print(f"   ✅ 無需維護 Python 字典檔案")
    print(f"   ✅ 修改 Excel 立即生效")
    print(f"   ✅ 工作流程更簡單直觀")
    print(f"   ✅ 避免順序依賴風險")
    print(f"📊 數據來源：{excel_source}")


if __name__ == "__main__":
    main()