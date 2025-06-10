#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phrase_comparison.py

產生 phrase_comparison.xlsx
欄位固定：
敏感詞類型 │ 敏感詞 │ 對應方案(企業) │ 一對多校驗(企業)
                         │ 對應方案(公部門) │ 一對多校驗(公部門)
                         │ 對應方案(培訓機構) │ 一對多校驗(培訓機構)

邏輯說明：
- detection_terms.py: 存儲敏感詞
- 其他三個檔案: 存儲對應的解決方案
- 需要建立敏感詞到方案的對應關係
"""

from pathlib import Path
from collections import defaultdict
import importlib.util
import openpyxl
import sys

def main():
    """主執行函數"""
    print("🚀 開始生成 phrase_comparison.xlsx")
    
    # ─────────── 1. 檢查並讀入四份字典 ────────────
    def load_terms(py_file: str) -> dict:
        """載入 Python 檔案中的 DETECTION_TERMS 字典"""
        p = Path(py_file)
        if not p.exists():
            print(f"❌ 找不到檔案：{p.absolute()}")
            sys.exit(1)
        
        try:
            spec = importlib.util.spec_from_file_location(p.stem, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            if not hasattr(mod, 'DETECTION_TERMS'):
                print(f"❌ {py_file} 中找不到 DETECTION_TERMS")
                sys.exit(1)
                
            terms = mod.DETECTION_TERMS
            if not isinstance(terms, dict):
                print(f"❌ {py_file} 中 DETECTION_TERMS 不是字典格式")
                sys.exit(1)
                
            return terms
        except Exception as e:
            print(f"❌ 載入 {py_file} 失敗：{e}")
            sys.exit(1)

    # 載入四個檔案
    file_mapping = {
        "detection_terms.py": "基礎敏感詞",
        "detection_terms_enterprises.py": "企業方案",
        "detection_terms_public_sector.py": "公部門方案",
        "detection_terms_training_institutions.py": "培訓機構方案"
    }
    
    terms_data = {}
    for filename, description in file_mapping.items():
        print(f"📖 載入 {filename} ({description})")
        terms_data[filename] = load_terms(filename)
    
    BASE = terms_data["detection_terms.py"]  # 敏感詞
    ENT = terms_data["detection_terms_enterprises.py"]      # 企業方案
    GOV = terms_data["detection_terms_public_sector.py"]    # 公部門方案
    EDU = terms_data["detection_terms_training_institutions.py"]  # 培訓機構方案

    # 顯示載入統計
    print(f"\n📊 載入統計：")
    for filename, terms in terms_data.items():
        total_items = sum(len(items) for items in terms.values())
        print(f"   {filename}: {len(terms)} 類別, {total_items} 個項目")

    # ─────────── 2. 驗證分類一致性 ────────────
    def validate_categories():
        """驗證所有檔案的分類一致性"""
        base_cats = set(BASE.keys())
        all_files = [
            ("企業方案", ENT),
            ("公部門方案", GOV),
            ("培訓機構方案", EDU)
        ]
        
        validation_passed = True
        for name, terms_dict in all_files:
            target_cats = set(terms_dict.keys())
            missing_cats = base_cats - target_cats
            extra_cats = target_cats - base_cats
            
            if missing_cats:
                print(f"❌ {name} 缺少分類: {missing_cats}")
                validation_passed = False
            
            if extra_cats:
                print(f"⚠️  {name} 有額外分類: {extra_cats}")
        
        return validation_passed

    print(f"\n🔍 驗證分類一致性...")
    if not validate_categories():
        print("❌ 分類驗證失敗，請檢查檔案內容")
        sys.exit(1)
    print("✅ 分類驗證通過")

    # ─────────── 3. 建立敏感詞到方案的對應關係 ────────────
    def build_keyword_to_solution_mapping():
        """
        建立從敏感詞到解決方案的對應關係
        
        邏輯：
        1. 遍歷每個分類
        2. 對每個敏感詞，找到對應分類中的方案
        3. 如果方案數量不足，使用敏感詞本身作為方案
        """
        mappings = {
            'enterprise': {},  # 敏感詞 -> 企業方案
            'government': {},  # 敏感詞 -> 公部門方案
            'education': {}    # 敏感詞 -> 培訓機構方案
        }
        
        mapping_stats = defaultdict(lambda: defaultdict(int))
        
        for category, keywords in BASE.items():
            # 獲取該分類下的所有方案
            ent_solutions = ENT.get(category, [])
            gov_solutions = GOV.get(category, [])
            edu_solutions = EDU.get(category, [])
            
            print(f"\n📂 處理分類 '{category}':")
            print(f"   敏感詞: {len(keywords)} 個")
            print(f"   企業方案: {len(ent_solutions)} 個")
            print(f"   公部門方案: {len(gov_solutions)} 個") 
            print(f"   培訓機構方案: {len(edu_solutions)} 個")
            
            # 為每個敏感詞分配方案
            for i, keyword in enumerate(keywords):
                # 企業方案對應
                if i < len(ent_solutions):
                    mappings['enterprise'][keyword] = ent_solutions[i]
                    mapping_stats['enterprise']['mapped'] += 1
                else:
                    mappings['enterprise'][keyword] = keyword  # 回退到原詞
                    mapping_stats['enterprise']['fallback'] += 1
                
                # 公部門方案對應
                if i < len(gov_solutions):
                    mappings['government'][keyword] = gov_solutions[i]
                    mapping_stats['government']['mapped'] += 1
                else:
                    mappings['government'][keyword] = keyword
                    mapping_stats['government']['fallback'] += 1
                
                # 培訓機構方案對應
                if i < len(edu_solutions):
                    mappings['education'][keyword] = edu_solutions[i]
                    mapping_stats['education']['mapped'] += 1
                else:
                    mappings['education'][keyword] = keyword
                    mapping_stats['education']['fallback'] += 1
        
        # 顯示對應統計
        print(f"\n🔄 對應關係統計：")
        for mapping_type, stats in mapping_stats.items():
            total = stats['mapped'] + stats['fallback']
            print(f"   {mapping_type}: {stats['mapped']}/{total} 個有方案對應, {stats['fallback']} 個回退")
        
        return mappings

    mappings = build_keyword_to_solution_mapping()

    # ─────────── 4. 一對多校驗 ────────────
    def calculate_one_to_many(mapping: dict, mapping_name: str) -> dict:
        """計算一對多的情況（多個敏感詞對應到同一個方案）"""
        solution_to_keywords = defaultdict(list)
        
        for keyword, solution in mapping.items():
            solution_to_keywords[solution].append(keyword)
        
        # 找出一對多的情況
        one_to_many = {}
        for solution, keywords in solution_to_keywords.items():
            if len(keywords) > 1:
                one_to_many[solution] = len(keywords)
        
        if one_to_many:
            print(f"\n⚠️  {mapping_name} 一對多情況：")
            for solution, count in list(one_to_many.items())[:5]:  # 顯示前5個
                keywords = solution_to_keywords[solution]
                print(f"   方案 '{solution}' ← {count} 個敏感詞: {keywords[:3]}{'...' if len(keywords) > 3 else ''}")
            if len(one_to_many) > 5:
                print(f"   ... 另外 {len(one_to_many) - 5} 個一對多情況")
        else:
            print(f"✅ {mapping_name} 無一對多情況")
        
        return one_to_many

    print(f"\n🔍 檢查一對多對應...")
    ent_one_to_many = calculate_one_to_many(mappings['enterprise'], "企業方案")
    gov_one_to_many = calculate_one_to_many(mappings['government'], "公部門方案")
    edu_one_to_many = calculate_one_to_many(mappings['education'], "培訓機構方案")

    # ─────────── 5. 生成 Excel ────────────
    print(f"\n📝 生成 Excel 檔案...")
    
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "phrase_comparison"
        
        # 寫入標題列
        headers = [
            "敏感詞類型", "敏感詞",
            "對應方案(企業)", "一對多校驗(企業)",
            "對應方案(公部門)", "一對多校驗(公部門)",
            "對應方案(培訓機構)", "一對多校驗(培訓機構)"
        ]
        ws.append(headers)

        # 寫入資料列
        row_count = 0
        for category, keywords in sorted(BASE.items()):
            for keyword in sorted(keywords):
                # 獲取對應的方案
                ent_solution = mappings['enterprise'][keyword]
                gov_solution = mappings['government'][keyword]
                edu_solution = mappings['education'][keyword]
                
                # 獲取一對多計數
                ent_count = ent_one_to_many.get(ent_solution, "")
                gov_count = gov_one_to_many.get(gov_solution, "")
                edu_count = edu_one_to_many.get(edu_solution, "")
                
                ws.append([
                    category, keyword,
                    ent_solution, ent_count,
                    gov_solution, gov_count,
                    edu_solution, edu_count
                ])
                row_count += 1

        print(f"✅ 寫入 {row_count} 筆資料")

        # 自動調整欄寬
        print("🎨 調整欄寬...")
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
            
            # 設定欄寬，最小8，最大50
            adjusted_width = min(max(max_length + 2, 8), 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # 儲存檔案
        out_path = Path("phrase_comparison.xlsx")
        wb.save(out_path)
        
        print(f"🎉 生成完成：{out_path.absolute()}")
        print(f"📄 檔案大小：{out_path.stat().st_size / 1024:.1f} KB")

    except Exception as e:
        print(f"❌ 生成 Excel 檔案失敗：{e}")
        sys.exit(1)

    # ─────────── 6. 生成報告 ────────────
    print(f"\n📈 最終報告：")
    print(f"   總分類數：{len(BASE)}")
    print(f"   總敏感詞數：{sum(len(keywords) for keywords in BASE.values())}")
    print(f"   企業方案一對多：{len(ent_one_to_many)} 個")
    print(f"   公部門方案一對多：{len(gov_one_to_many)} 個")
    print(f"   培訓機構方案一對多：{len(edu_one_to_many)} 個")
    
    total_multi_mappings = len(ent_one_to_many) + len(gov_one_to_many) + len(edu_one_to_many)
    if total_multi_mappings > 0:
        print(f"\n⚠️  注意：共有 {total_multi_mappings} 個一對多對應，建議檢查是否需要調整")
    else:
        print(f"\n✅ 所有對應關係都是一對一，資料結構良好")


if __name__ == "__main__":
    main()