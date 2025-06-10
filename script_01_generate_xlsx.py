#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_01_generate_xlsx.py

掃描 messages.po 與 zh-TW.json，偵測歧義關鍵字，輸出 tobemodified.xlsx
欄位：
  • source / key / value
  • 敏感詞
  • 修正方案(企業) / 修正結果(企業)
  • 修正方案(公部門) / 修正結果(公部門)
  • 修正方案(培訓機構) / 修正結果(培訓機構)

改進點：
1. 修正檔名引用錯誤
2. 改進敏感詞對應方案的邏輯
3. 增加錯誤處理和日志
4. 優化替換邏輯
5. 增加統計資訊
"""

# ── StdLib ───────────────────────────────────
from pathlib import Path
import json
import re
import itertools
import sys
from collections import defaultdict

# ── 3rd-party ────────────────────────────────
try:
    import polib                       # pip install polib
    from openpyxl import Workbook      # pip install openpyxl
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install polib openpyxl")
    sys.exit(1)

def main():
    """主執行函數"""
    print("🚀 開始生成 tobemodified.xlsx")
    
    # ── 檔案路徑檢查 ────────────────────────────────
    PO_PATH = Path("messages.po")
    JSON_PATH = Path("zh-TW.json")
    OUT_XLSX = Path("tobemodified.xlsx")
    
    # ── 載入字典檔案 ────────────────────────────────
    def load_detection_terms():
        """載入所有檢測詞典，並進行錯誤處理"""
        try:
            from detection_terms import DETECTION_TERMS
            # 修正：統一檔名
            from detection_terms_enterprises import DETECTION_TERMS as ENT_TERMS
            from detection_terms_public_sector import DETECTION_TERMS as GOV_TERMS
            from detection_terms_training_institutions import DETECTION_TERMS as EDU_TERMS
            
            print(f"✅ 成功載入檢測詞典")
            print(f"   基礎敏感詞: {len(DETECTION_TERMS)} 類別")
            print(f"   企業方案: {len(ENT_TERMS)} 類別")
            print(f"   公部門方案: {len(GOV_TERMS)} 類別")
            print(f"   培訓機構方案: {len(EDU_TERMS)} 類別")
            
            return DETECTION_TERMS, ENT_TERMS, GOV_TERMS, EDU_TERMS
            
        except ImportError as e:
            print(f"❌ 無法載入檢測詞典：{e}")
            print("請確認以下檔案存在且格式正確：")
            print("  - detection_terms.py")
            print("  - detection_terms_enterprises.py") 
            print("  - detection_terms_public_sector.py")
            print("  - detection_terms_training_institutions.py")
            sys.exit(1)
    
    DETECTION_TERMS, ENT_TERMS, GOV_TERMS, EDU_TERMS = load_detection_terms()

    # ── 建立關鍵字到分類的映射 ────────────────────────────────
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

    # ── 改進：建立敏感詞到方案的映射 ────────────────────────────────
    def build_keyword_to_solution_mapping(solution_terms: dict, solution_name: str):
        """
        建立從敏感詞到解決方案的映射
        
        邏輯：
        1. 對每個敏感詞，找到其分類
        2. 在該分類的解決方案中按索引對應
        3. 如果沒有對應方案，保持原詞
        """
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
        
        print(f"   {solution_name}: {mapping_stats['mapped']} 個有方案, {mapping_stats['fallback']} 個回退, {mapping_stats['missing_category']} 個無分類方案")
        return keyword_to_solution

    print("\n🔄 建立敏感詞到方案映射...")
    ENT_MAPPING = build_keyword_to_solution_mapping(ENT_TERMS, "企業方案")
    GOV_MAPPING = build_keyword_to_solution_mapping(GOV_TERMS, "公部門方案")
    EDU_MAPPING = build_keyword_to_solution_mapping(EDU_TERMS, "培訓機構方案")

    # ── 改進：關鍵字檢測 ────────────────────────────────
    # 按長度排序，優先匹配長詞避免部分匹配問題
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

    # ── 改進：檔案讀取函數 ────────────────────────────────
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

    # ── 掃描檔案並收集資料 ────────────────────────────────
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
            rows.append([
                source,
                key,
                display_value,
                "、".join(all_keywords),  # 敏感詞列表
                build_replacement_plan(all_keywords, ENT_MAPPING),  # 企業修正方案
                apply_replacements(display_value, ENT_MAPPING),     # 企業修正結果
                build_replacement_plan(all_keywords, GOV_MAPPING),  # 公部門修正方案
                apply_replacements(display_value, GOV_MAPPING),     # 公部門修正結果
                build_replacement_plan(all_keywords, EDU_MAPPING),  # 培訓機構修正方案
                apply_replacements(display_value, EDU_MAPPING),     # 培訓機構修正結果
            ])

    print(f"   檢測統計：{dict(detection_stats)}")

    if not rows:
        print("✅ 未偵測到歧義詞，未產生 xlsx")
        return

    # ── 輸出 Excel ────────────────────────────────
    print(f"\n📝 生成 Excel 檔案...")
    
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "tobemodified"
        
        # 標題列
        headers = [
            "source", "key", "value", "敏感詞",
            "修正方案(企業)", "修正結果(企業)",
            "修正方案(公部門)", "修正結果(公部門)",
            "修正方案(培訓機構)", "修正結果(培訓機構)"
        ]
        ws.append(headers)

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

    # ── 生成統計報告 ────────────────────────────────
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