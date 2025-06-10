#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phrase_comparison.py (v2.0)

產生 phrase_comparison.xlsx
支援多語言和可配置的業態類型。

更新內容：
- 支援 config.yaml 配置
- 支援多語言
- 支援可擴充的業態類型
- 動態生成 Excel 欄位
"""

from pathlib import Path
from collections import defaultdict
import importlib.util
import openpyxl
import sys
from config_loader import get_config

def main():
    """主執行函數"""
    print("🚀 開始生成 phrase_comparison.xlsx (v2.0)")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 檢查並讀入所有字典
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

    # 載入所有檔案
    detection_files = config.get_detection_terms_files()
    
    print(f"\n📖 載入字典檔案...")
    terms_data = {}
    
    # 載入基礎敏感詞檔案
    base_file = detection_files['base']
    print(f"   載入 {base_file} (基礎敏感詞)")
    terms_data['base'] = load_terms(base_file)
    
    # 載入各業態方案檔案
    business_types = config.get_business_types()
    for bt_code, bt_config in business_types.items():
        bt_file = detection_files[bt_code]
        display_name = bt_config['display_name']
        print(f"   載入 {bt_file} ({display_name}方案)")
        terms_data[bt_code] = load_terms(bt_file)

    BASE = terms_data['base']
    
    # 顯示載入統計
    print(f"\n📊 載入統計：")
    for name, terms in terms_data.items():
        total_words = sum(len(words) for words in terms.values())
        if name == 'base':
            print(f"   {detection_files[name]}: {len(terms)} 類別, {total_words} 個敏感詞")
        else:
            bt_config = business_types[name]
            print(f"   {detection_files[name]}: {len(terms)} 類別, {total_words} 個{bt_config['display_name']}方案")

    # 驗證所有字典的分類一致性
    def validate_categories():
        """驗證所有檔案的分類一致性"""
        base_cats = set(BASE.keys())
        
        validation_passed = True
        for bt_code, bt_config in business_types.items():
            target_terms = terms_data[bt_code]
            target_cats = set(target_terms.keys())
            display_name = bt_config['display_name']
            
            missing_cats = base_cats - target_cats
            extra_cats = target_cats - base_cats
            
            if missing_cats:
                print(f"❌ {display_name}方案缺少分類: {missing_cats}")
                validation_passed = False
            
            if extra_cats:
                print(f"⚠️  {display_name}方案有額外分類: {extra_cats}")
        
        return validation_passed

    print(f"\n🔍 驗證分類一致性...")
    if not validate_categories():
        print("❌ 分類驗證失敗，請檢查檔案內容")
        sys.exit(1)
    print("✅ 分類驗證通過")

    # 建立敏感詞到方案的對應關係
    def build_keyword_to_solution_mapping():
        """建立從敏感詞到解決方案的對應關係"""
        mappings = {}
        
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            solution_terms = terms_data[bt_code]
            
            keyword_to_solution = {}
            mapping_stats = {'mapped': 0, 'fallback': 0, 'missing_category': 0}
            
            for category, keywords in BASE.items():
                solutions = solution_terms.get(category, [])
                
                if not solutions:
                    # 該分類沒有解決方案
                    for keyword in keywords:
                        keyword_to_solution[keyword] = keyword
                        mapping_stats['missing_category'] += 1
                    continue
                
                # 為每個敏感詞分配方案
                for i, keyword in enumerate(keywords):
                    if i < len(solutions):
                        # 有對應的解決方案
                        keyword_to_solution[keyword] = solutions[i]
                        mapping_stats['mapped'] += 1
                    else:
                        # 索引超出方案範圍
                        keyword_to_solution[keyword] = keyword
                        mapping_stats['fallback'] += 1
            
            mappings[bt_code] = keyword_to_solution
            print(f"   {display_name}方案: {mapping_stats['mapped']} 個有方案, {mapping_stats['fallback']} 個回退, {mapping_stats['missing_category']} 個無分類方案")
        
        return mappings

    print(f"\n🔄 建立敏感詞到方案映射...")
    mappings = build_keyword_to_solution_mapping()

    # 一對多校驗
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
    one_to_many_results = {}
    for bt_code, bt_config in business_types.items():
        display_name = bt_config['display_name']
        one_to_many_results[bt_code] = calculate_one_to_many(mappings[bt_code], f"{display_name}方案")

    # 生成 Excel
    print(f"\n📝 生成 Excel 檔案...")
    
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "phrase_comparison"
        
        # 動態建立標題列
        headers = ["敏感詞類型", "敏感詞"]
        
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            headers.extend([
                f"對應方案({display_name})",
                f"一對多校驗({display_name})"
            ])
        
        ws.append(headers)
        print(f"   Excel 標題列: {headers}")

        # 寫入資料列
        row_count = 0
        for category, keywords in sorted(BASE.items()):
            for keyword in sorted(keywords):
                row_data = [category, keyword]
                
                # 添加各業態的方案和一對多計數
                for bt_code in business_types.keys():
                    solution = mappings[bt_code][keyword]
                    one_to_many_count = one_to_many_results[bt_code].get(solution, "")
                    
                    row_data.extend([solution, one_to_many_count])
                
                ws.append(row_data)
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

    # 生成報告
    print(f"\n📈 最終報告：")
    print(f"   總分類數：{len(BASE)}")
    print(f"   總敏感詞數：{sum(len(keywords) for keywords in BASE.values())}")
    
    total_multi_mappings = 0
    for bt_code, bt_config in business_types.items():
        display_name = bt_config['display_name']
        count = len(one_to_many_results[bt_code])
        total_multi_mappings += count
        print(f"   {display_name}方案一對多：{count} 個")
    
    if total_multi_mappings > 0:
        print(f"\n⚠️  注意：共有 {total_multi_mappings} 個一對多對應，建議檢查是否需要調整")
    else:
        print(f"\n✅ 所有對應關係都是一對一，資料結構良好")


if __name__ == "__main__":
    main()