#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_02_apply_fixes.py (v2.2 - Multi-language Version)

依據各語言的 tobemodified_{language}.xlsx，將修正結果寫回翻譯檔，
並輸出到 i18n_output/{language}_{timestamp}/ 目錄中

功能：
1. 自動檢測可用的 tobemodified 檔案
2. 支援多語言檔案處理
3. 輸出到時間戳目錄結構
4. 保持原始檔案名稱
"""

import json
import sys
import shutil
import datetime
import argparse
import glob
from pathlib import Path
from collections import defaultdict
from config_loader import get_config

try:
    import openpyxl
    import polib
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install openpyxl polib")
    sys.exit(1)


def main():
    """主執行函數"""
    print("🚀 開始套用多語言修正結果")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 處理命令列參數
    parser = argparse.ArgumentParser(description='套用多語言敏感詞修正結果')
    parser.add_argument('--language', '-l', 
                       help='指定要處理的語言（若未指定將自動檢測）')
    parser.add_argument('--business-types', '-b',
                       nargs='+',
                       choices=list(config.get_business_types().keys()) + ['all'],
                       help='指定要處理的業態 (可多選，或使用 all)')
    parser.add_argument('--list-files', action='store_true',
                       help='列出所有可用的 tobemodified 檔案')
    
    args = parser.parse_args()
    
    # 檢測可用的 tobemodified 檔案
    available_files = detect_tobemodified_files(config)
    
    if args.list_files:
        print(f"\n📄 可用的 tobemodified 檔案：")
        for lang, filepath in available_files.items():
            print(f"   {lang}: {filepath}")
        return
    
    if not available_files:
        print("❌ 未找到任何 tobemodified 檔案")
        print("請先執行 script_01_generate_xlsx.py 生成檔案")
        sys.exit(1)
    
    # 選擇要處理的語言
    if args.language:
        if args.language not in available_files:
            print(f"❌ 語言 '{args.language}' 的 tobemodified 檔案不存在")
            print(f"可用語言：{list(available_files.keys())}")
            sys.exit(1)
        target_languages = [args.language]
        print(f"\n🌐 將處理指定語言：{args.language}")
    else:
        target_languages = list(available_files.keys())
        print(f"\n🌐 將處理所有語言：{', '.join(target_languages)}")
    
    # 選擇業態
    target_business_types = choose_business_types(config, args)
    
    # 處理每個語言
    success_count = 0
    total_count = len(target_languages)
    
    for language in target_languages:
        print(f"\n{'='*60}")
        print(f"📋 處理語言：{language}")
        
        if process_language(config, language, target_business_types):
            success_count += 1
        else:
            print(f"❌ {language} 處理失敗")
    
    # 最終報告
    print(f"\n🎉 處理完畢！")
    print(f"📊 成功處理：{success_count}/{total_count} 個語言")
    
    if success_count < total_count:
        sys.exit(1)


def detect_tobemodified_files(config) -> dict:
    """
    檢測可用的 tobemodified 檔案
    
    Returns:
        語言到檔案路徑的映射字典
    """
    available_files = {}
    
    # 檢測標準命名的檔案
    available_languages = config.detect_available_languages()
    
    for language in available_languages:
        tobemodified_path = config.get_tobemodified_excel_path(language)
        if tobemodified_path.exists():
            available_files[language] = tobemodified_path
    
    # 額外檢測通配符檔案
    tobemodified_pattern = "tobemodified_*.xlsx"
    for file_path in Path('.').glob(tobemodified_pattern):
        # 提取語言代碼
        filename = file_path.stem
        if filename.startswith('tobemodified_'):
            language = filename[len('tobemodified_'):]
            if language not in available_files:
                available_files[language] = file_path
    
    return available_files


def choose_business_types(config, args) -> list:
    """選擇要處理的業態"""
    if args.business_types:
        if 'all' in args.business_types:
            return list(config.get_business_types().keys())
        return args.business_types
    
    # 互動式選擇
    business_types = config.get_business_types()
    choices = list(business_types.items())
    
    print("\n請選擇要套用修正的業態：")
    for i, (bt_code, bt_config) in enumerate(choices, 1):
        print(f"  {i}) {bt_config['display_name']}")
    print(f"  {len(choices) + 1}) 全部")
    
    while True:
        try:
            opt = input(f"\n輸入選項 (1-{len(choices) + 1})：").strip()
            choice_idx = int(opt) - 1
            
            if choice_idx == len(choices):  # 全部
                return list(business_types.keys())
            elif 0 <= choice_idx < len(choices):
                bt_code = choices[choice_idx][0]
                return [bt_code]
            else:
                print(f"⚠️  請輸入 1-{len(choices) + 1} 之間的數字")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 使用者取消操作")
            sys.exit(0)


def process_language(config, language: str, target_business_types: list) -> bool:
    """
    處理單個語言的修正套用
    
    Args:
        config: 配置物件
        language: 語言代碼
        target_business_types: 目標業態列表
    
    Returns:
        是否成功
    """
    
    # 獲取檔案路徑
    tobemodified_path = config.get_tobemodified_excel_path(language)
    language_files = config.get_language_files(language)
    
    print(f"   來源 Excel：{tobemodified_path}")
    print(f"   原始檔案：{list(language_files.values())}")
    
    if not tobemodified_path.exists():
        print(f"❌ 找不到 {language} 的 tobemodified 檔案")
        return False
    
    # 獲取輸出路徑
    output_paths = config.get_output_paths(language)
    output_dir = output_paths['output_dir']
    timestamp = output_paths['timestamp']
    
    print(f"   輸出目錄：{output_dir}")
    
    # 創建輸出目錄
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 設置日誌
    log_file = output_dir / f"apply_fixes_{timestamp}.log"
    
    def log_detail(message: str):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n")
    
    log_detail(f"開始處理語言: {language}")
    log_detail(f"目標業態: {', '.join(target_business_types)}")
    
    # 讀取並驗證 Excel
    wb, ws, header = read_and_validate_xlsx(tobemodified_path, config, target_business_types, log_detail)
    if not wb:
        return False
    
    # 解析修正資料
    updates = parse_excel_updates(ws, header, config, target_business_types, log_detail)
    
    # 處理每個業態
    business_types = config.get_business_types()
    results = {}
    
    for bt_code in target_business_types:
        bt_config = business_types[bt_code]
        display_name = bt_config['display_name']
        
        print(f"\n📝 處理 {display_name}...")
        log_detail(f"開始處理業態: {display_name}")
        
        # 生成輸出檔案路徑
        output_files = generate_output_files(config, language, bt_code, language_files, output_dir)
        if not output_files:
            log_detail(f"錯誤: {display_name} 輸出檔案生成失敗")
            continue
        
        # 套用修正
        result = apply_fixes_to_business_type(
            config, bt_code, updates[bt_code], output_files, log_detail
        )
        
        results[bt_code] = result
        
        if result['success']:
            total_updates = result['po_updated'] + result['json_updated']
            print(f"  ✅ 完成 - PO: {result['po_updated']} 個, JSON: {result['json_updated']} 個")
            log_detail(f"{display_name} 處理完成: 總更新 {total_updates} 個")
        else:
            print(f"  ❌ 失敗")
            log_detail(f"{display_name} 處理失敗")
    
    # 生成最終報告
    success_count = sum(1 for r in results.values() if r['success'])
    total_count = len(results)
    
    print(f"\n📊 {language} 處理結果：")
    print(f"   成功業態：{success_count}/{total_count}")
    print(f"   輸出目錄：{output_dir}")
    print(f"   詳細日誌：{log_file}")
    
    log_detail(f"語言 {language} 處理完成: 成功 {success_count}/{total_count} 個業態")
    
    return success_count > 0


def read_and_validate_xlsx(xlsx_path: Path, config, target_business_types: list, log_detail) -> tuple:
    """讀取並驗證 Excel 檔案"""
    try:
        log_detail(f"開始讀取 Excel 檔案: {xlsx_path}")
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        
        header_row = list(ws[1])
        header = {cell.value: idx for idx, cell in enumerate(header_row) if cell.value}
        
        log_detail(f"發現欄位: {list(header.keys())}")
        
        required_columns = ["source", "key", "value"]
        missing_columns = []
        
        for col in required_columns:
            if col not in header:
                missing_columns.append(col)
        
        # 檢查業態欄位
        business_types = config.get_business_types()
        for bt_code in target_business_types:
            display_name = business_types[bt_code]['display_name']
            col_name = f"修正結果({display_name})"
            if col_name not in header:
                missing_columns.append(col_name)
        
        if missing_columns:
            error_msg = f"Excel 缺少必要欄位：{missing_columns}"
            print(f"❌ {error_msg}")
            log_detail(f"錯誤: {error_msg}")
            return None, None, None
        
        return wb, ws, header
        
    except Exception as e:
        error_msg = f"讀取 Excel 檔案失敗：{e}"
        print(f"❌ {error_msg}")
        log_detail(f"錯誤: {error_msg}")
        return None, None, None


def parse_excel_updates(ws, header, config, target_business_types: list, log_detail) -> dict:
    """解析 Excel 中的修正資料"""
    log_detail("開始解析 Excel 修正資料")
    updates = {bt_code: {"po": [], "json": []} for bt_code in target_business_types}
    stats = defaultdict(int)
    
    def get_column_index(name: str) -> int:
        if name not in header:
            raise KeyError(f"Excel 缺少欄位：{name}")
        return header[name]
    
    business_types = config.get_business_types()
    
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or len(row) <= max(header.values()):
            continue
        
        try:
            source = row[get_column_index("source")]
            key = row[get_column_index("key")]
            
            if not source or not key:
                continue
            
            stats['total_rows'] += 1
            
            # 處理每個目標業態
            for bt_code in target_business_types:
                display_name = business_types[bt_code]['display_name']
                col_name = f"修正結果({display_name})"
                new_value = row[get_column_index(col_name)]
                
                if not (isinstance(new_value, str) and new_value.strip()):
                    continue
                
                new_value = new_value.strip()
                stats[f'{bt_code}_updates'] += 1
                
                if source == "po":
                    updates[bt_code]["po"].append((key, new_value))
                    log_detail(f"PO 更新 - {display_name}: {key} → {new_value}")
                elif source == "json":
                    updates[bt_code]["json"].append((key, new_value))
                    log_detail(f"JSON 更新 - {display_name}: {key} → {new_value}")
                else:
                    log_detail(f"警告: 第 {row_num} 行未知的 source 類型 '{source}'")
        
        except Exception as e:
            log_detail(f"錯誤: 第 {row_num} 行處理失敗: {e}")
            continue
    
    log_detail(f"解析完成統計: {dict(stats)}")
    return updates


def generate_output_files(config, language: str, bt_code: str, language_files: dict, output_dir: Path) -> dict:
    """生成輸出檔案"""
    business_types = config.get_business_types()
    bt_config = business_types[bt_code]
    suffix = bt_config['suffix']
    
    output_files = {}
    
    # 處理 PO 檔案
    if 'po_file' in language_files:
        original_po = language_files['po_file']
        output_po = output_dir / f"{original_po.stem}{suffix}{original_po.suffix}"
        
        # 複製原始檔案
        shutil.copy2(original_po, output_po)
        output_files['po_file'] = output_po
    
    # 處理 JSON 檔案
    if 'json_file' in language_files:
        original_json = language_files['json_file']
        output_json = output_dir / f"{original_json.stem}{suffix}{original_json.suffix}"
        
        # 複製原始檔案
        shutil.copy2(original_json, output_json)
        output_files['json_file'] = output_json
    
    return output_files


def apply_fixes_to_business_type(config, bt_code: str, updates: dict, output_files: dict, log_detail) -> dict:
    """套用修正到指定業態"""
    result = {
        'success': True,
        'po_updated': 0,
        'json_updated': 0,
        'errors': []
    }
    
    try:
        # 處理 PO 檔案
        if 'po_file' in output_files and updates['po']:
            po_result = update_po_file(output_files['po_file'], updates['po'], log_detail)
            result['po_updated'] = po_result['updated']
            result['errors'].extend(po_result['errors'])
            if not po_result['success']:
                result['success'] = False
        
        # 處理 JSON 檔案
        if 'json_file' in output_files and updates['json']:
            json_result = update_json_file(output_files['json_file'], updates['json'], log_detail)
            result['json_updated'] = json_result['updated']
            result['errors'].extend(json_result['errors'])
            if not json_result['success']:
                result['success'] = False
        
    except Exception as e:
        error_msg = f"套用修正失敗：{e}"
        result['errors'].append(error_msg)
        result['success'] = False
        log_detail(f"錯誤: {error_msg}")
    
    return result


def update_po_file(po_path: Path, updates_list: list, log_detail) -> dict:
    """更新 PO 檔案"""
    result = {"success": False, "updated": 0, "errors": []}
    
    if not updates_list:
        result["success"] = True
        return result
    
    try:
        log_detail(f"開始更新 PO 檔案: {po_path.name}")
        po_file = polib.pofile(str(po_path))
        
        for msgid, new_msgstr in updates_list:
            entry = po_file.find(msgid)
            if entry:
                if entry.msgstr != new_msgstr:
                    old_value = entry.msgstr
                    entry.msgstr = new_msgstr
                    result["updated"] += 1
                    log_detail(f"PO 更新: '{msgid}' 從 '{old_value}' 改為 '{new_msgstr}'")
            else:
                error_msg = f"找不到條目：{msgid}"
                result["errors"].append(error_msg)
                log_detail(f"PO 錯誤: {error_msg}")
        
        if result["updated"] > 0:
            po_file.save(str(po_path))
            log_detail(f"PO 檔案已儲存: {po_path.name}, 更新 {result['updated']} 個條目")
        
        result["success"] = True
        
    except Exception as e:
        error_msg = f"PO 檔案處理失敗：{e}"
        result["errors"].append(error_msg)
        log_detail(f"PO 錯誤: {error_msg}")
    
    return result


def parse_json_path(path: str) -> list:
    """解析 JSON 路徑"""
    parts = []
    current = ""
    in_bracket = False
    
    for char in path:
        if char == '[':
            if current:
                parts.append(('key', current))
                current = ""
            in_bracket = True
        elif char == ']':
            if in_bracket and current:
                try:
                    parts.append(('index', int(current)))
                except ValueError:
                    raise ValueError(f"無效的陣列索引：{current}")
                current = ""
            in_bracket = False
        elif char == '.' and not in_bracket:
            if current:
                parts.append(('key', current))
                current = ""
        else:
            current += char
    
    if current:
        parts.append(('key', current))
    
    return parts


def set_json_value_by_path(data: dict, path: str, new_value: str) -> bool:
    """按路徑設置 JSON 值"""
    try:
        path_parts = parse_json_path(path)
        current = data
        
        for i, (part_type, part_value) in enumerate(path_parts):
            is_last = (i == len(path_parts) - 1)
            
            if part_type == 'key':
                if is_last:
                    current[part_value] = new_value
                else:
                    if part_value not in current:
                        next_part_type = path_parts[i + 1][0] if i + 1 < len(path_parts) else 'key'
                        current[part_value] = [] if next_part_type == 'index' else {}
                    current = current[part_value]
            
            elif part_type == 'index':
                if is_last:
                    while len(current) <= part_value:
                        current.append(None)
                    current[part_value] = new_value
                else:
                    while len(current) <= part_value:
                        current.append(None)
                    if current[part_value] is None:
                        next_part_type = path_parts[i + 1][0] if i + 1 < len(path_parts) else 'key'
                        current[part_value] = [] if next_part_type == 'index' else {}
                    current = current[part_value]
        
        return True
        
    except Exception as e:
        return False


def update_json_file(json_path: Path, updates_list: list, log_detail) -> dict:
    """更新 JSON 檔案"""
    result = {"success": False, "updated": 0, "errors": []}
    
    if not updates_list:
        result["success"] = True
        return result
    
    try:
        log_detail(f"開始更新 JSON 檔案: {json_path.name}")
        
        data = json.loads(json_path.read_text(encoding="utf-8"))
        
        for json_path_str, new_value in updates_list:
            if set_json_value_by_path(data, json_path_str, new_value):
                result["updated"] += 1
                log_detail(f"JSON 更新: '{json_path_str}' → '{new_value}'")
            else:
                error_msg = f"無法更新路徑：{json_path_str}"
                result["errors"].append(error_msg)
                log_detail(f"JSON 錯誤: {error_msg}")
        
        if result["updated"] > 0:
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            json_path.write_text(json_content, encoding="utf-8")
            log_detail(f"JSON 檔案已儲存: {json_path.name}, 更新 {result['updated']} 個條目")
        
        result["success"] = True
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON 格式錯誤：{e}"
        result["errors"].append(error_msg)
        log_detail(f"JSON 錯誤: {error_msg}")
    except Exception as e:
        error_msg = f"JSON 檔案處理失敗：{e}"
        result["errors"].append(error_msg)
        log_detail(f"JSON 錯誤: {error_msg}")
    
    return result


if __name__ == "__main__":
    main()