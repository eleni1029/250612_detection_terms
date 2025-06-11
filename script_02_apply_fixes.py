#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_02_apply_fixes.py (v2.1 - Pure Excel Version)

依據 tobemodified.xlsx，把「修正結果」寫回翻譯檔。
完全基於 Excel 檔案，不再依賴任何 Python 字典檔案。

更新內容：
- 完全移除對 detection_terms.py 的依賴
- 完全基於 Excel 檔案的工作流程
- 簡化配置和邏輯
- 更直觀的純 Excel 方案
"""

from pathlib import Path
import json
import sys
import shutil
import re
import datetime
import argparse
import glob
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
    print("🚀 開始套用修正結果 (v2.1 - Pure Excel Version)")
    print("📊 完全基於 Excel 的修正套用系統")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 設置備份目錄
    backup_config = config.config.get('system', {}).get('backup', {})
    backup_dir = Path(config.get_base_files()['backup_dir'])
    backup_dir.mkdir(exist_ok=True)
    
    timestamp_format = backup_config.get('timestamp_format', '%Y%m%d_%H%M%S')
    timestamp = datetime.datetime.now().strftime(timestamp_format)
    log_file = backup_dir / f"apply_fixes_{timestamp}.log"
    
    def log_detail(message: str):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n")

    # 處理命令列參數
    parser = argparse.ArgumentParser(description='套用敏感詞修正結果')
    parser.add_argument('--language', '-l', 
                       choices=list(config.get_languages().keys()),
                       help='指定要處理的語言 (若未指定將自動檢測)')
    parser.add_argument('--business-types', '-b',
                       nargs='+',
                       choices=list(config.get_business_types().keys()) + ['all'],
                       help='指定要處理的業態 (可多選，或使用 all)')
    
    args = parser.parse_args()

    # 自動檢測或選擇語言
    def detect_or_choose_language():
        """檢測或選擇要處理的語言"""
        if args.language:
            return args.language
        
        # 自動檢測 tobemodified 檔案
        available_languages = config.get_languages()
        found_files = []
        
        output_template = config.config.get('file_generation', {}).get('tobemodified_template', 'tobemodified_{language}.xlsx')
        
        for lang_code in available_languages.keys():
            xlsx_file = Path(output_template.format(language=lang_code))
            if xlsx_file.exists():
                found_files.append((lang_code, xlsx_file))
        
        if not found_files:
            # 檢查是否有預設檔案
            default_xlsx = Path("tobemodified.xlsx")
            if default_xlsx.exists():
                default_lang = config.get_default_language()
                print(f"🔍 找到 tobemodified.xlsx，假設為 {default_lang} 語言")
                return default_lang, default_xlsx
            
            print("❌ 找不到任何 tobemodified 檔案")
            print("請先執行 script_01_generate_xlsx.py 生成檔案")
            sys.exit(1)
        
        if len(found_files) == 1:
            lang_code, xlsx_file = found_files[0]
            print(f"🔍 自動檢測到語言：{lang_code} ({xlsx_file})")
            return lang_code, xlsx_file
        
        # 多個檔案，讓使用者選擇
        print("\n🌐 發現多個語言的 tobemodified 檔案：")
        for i, (lang_code, xlsx_file) in enumerate(found_files, 1):
            lang_name = available_languages[lang_code].get('description', lang_code)
            print(f"  {i}) {lang_code} - {lang_name} ({xlsx_file})")
        
        while True:
            try:
                choice = input(f"\n請選擇語言 (1-{len(found_files)})：").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(found_files):
                    lang_code, xlsx_file = found_files[idx]
                    print(f"✅ 選擇了 {lang_code}")
                    return lang_code, xlsx_file
                else:
                    print(f"⚠️  請輸入 1-{len(found_files)} 之間的數字")
            except (ValueError, KeyboardInterrupt):
                print("\n❌ 使用者取消操作")
                sys.exit(0)

    # 選擇或檢測語言
    if args.language:
        selected_language = args.language
        output_template = config.config.get('file_generation', {}).get('tobemodified_template', 'tobemodified_{language}.xlsx')
        XLSX = Path(output_template.format(language=selected_language))
        if not XLSX.exists():
            # 嘗試預設檔名
            XLSX = Path("tobemodified.xlsx")
            if not XLSX.exists():
                print(f"❌ 找不到 {selected_language} 語言的 tobemodified 檔案")
                sys.exit(1)
    else:
        selected_language, XLSX = detect_or_choose_language()

    print(f"\n🌐 處理語言：{selected_language}")
    print(f"📄 Excel 檔案：{XLSX}")

    # 獲取語言檔案
    language_files = config.get_language_files(selected_language)
    ORIG_PO = Path(language_files['po_file'])
    ORIG_JSON = Path(language_files['json_file'])

    # 檢查必要檔案
    missing_files = []
    if not ORIG_PO.exists():
        missing_files.append(str(ORIG_PO))
    if not ORIG_JSON.exists():
        missing_files.append(str(ORIG_JSON))
    if not XLSX.exists():
        missing_files.append(str(XLSX))
    
    if missing_files:
        print(f"❌ 找不到必要檔案：{', '.join(missing_files)}")
        sys.exit(1)

    # 業態選擇
    def choose_business_types():
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

    target_business_types = choose_business_types()
    business_types = config.get_business_types()
    
    print(f"\n👉 將套用至：{', '.join([business_types[bt]['display_name'] for bt in target_business_types])}")

    # 預先備份現有的目標檔案
    def backup_existing_files():
        print(f"🔍 檢查並備份現有檔案...")
        backup_count = 0
        
        for bt_code in target_business_types:
            suffix = business_types[bt_code]['suffix']
            
            # 使用配置中的檔案命名模板
            file_gen_config = config.config.get('file_generation', {}).get('output_files', {})
            po_template = file_gen_config.get('po_template', '{base_name}{suffix}.po')
            json_template = file_gen_config.get('json_template', '{base_name}{suffix}.json')
            
            po_target = Path(po_template.format(base_name=ORIG_PO.stem, suffix=suffix))
            json_target = Path(json_template.format(base_name=ORIG_JSON.stem, suffix=suffix))
            
            # 備份 PO 檔案
            if po_target.exists():
                backup_filename = f"{po_target.stem}_{timestamp}{po_target.suffix}"
                backup_path = backup_dir / backup_filename
                shutil.copy2(po_target, backup_path)
                log_detail(f"預備份現有檔案: {po_target.name} → backup/{backup_path.name}")
                backup_count += 1
            
            # 備份 JSON 檔案
            if json_target.exists():
                backup_filename = f"{json_target.stem}_{timestamp}{json_target.suffix}"
                backup_path = backup_dir / backup_filename
                shutil.copy2(json_target, backup_path)
                log_detail(f"預備份現有檔案: {json_target.name} → backup/{backup_path.name}")
                backup_count += 1
        
        if backup_count > 0:
            print(f"✅ 已備份 {backup_count} 個現有檔案到 backup/")
            log_detail(f"預備份完成，共備份 {backup_count} 個現有檔案")
        else:
            print(f"ℹ️  無現有目標檔案需要備份")
            log_detail("無現有目標檔案需要備份")

    backup_existing_files()

    # 讀取 Excel 並驗證
    def read_and_validate_xlsx():
        try:
            print(f"📖 讀取 {XLSX}...")
            log_detail(f"開始讀取 Excel 檔案: {XLSX}")
            wb = openpyxl.load_workbook(XLSX, data_only=True)
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
            for bt_code in target_business_types:
                display_name = business_types[bt_code]['display_name']
                col_name = f"修正結果({display_name})"
                if col_name not in header:
                    missing_columns.append(col_name)
            
            if missing_columns:
                error_msg = f"Excel 缺少必要欄位：{missing_columns}"
                print(f"❌ {error_msg}")
                log_detail(f"錯誤: {error_msg}")
                sys.exit(1)
            
            return wb, ws, header
            
        except Exception as e:
            error_msg = f"讀取 Excel 檔案失敗：{e}"
            print(f"❌ {error_msg}")
            log_detail(f"錯誤: {error_msg}")
            sys.exit(1)

    wb, ws, header = read_and_validate_xlsx()

    def get_column_index(name: str) -> int:
        if name not in header:
            raise KeyError(f"Excel 缺少欄位：{name}")
        return header[name]

    # 解析 Excel 資料
    print(f"🔍 解析修正資料...")
    log_detail("開始解析 Excel 修正資料")
    updates = {bt_code: {"po": [], "json": []} for bt_code in target_business_types}
    stats = defaultdict(int)

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

    print(f"✅ 解析完成 - 總行數: {stats['total_rows']}")
    for bt_code in target_business_types:
        display_name = business_types[bt_code]['display_name']
        update_count = stats[f'{bt_code}_updates']
        print(f"   {display_name}: {update_count} 個更新")
    
    log_detail(f"解析完成統計: {dict(stats)}")

    # 檔案操作函數
    def create_backup_and_copy(src: Path, dest: Path) -> bool:
        try:
            if dest.exists():
                backup_filename = f"{dest.stem}_{timestamp}{dest.suffix}"
                backup_path = backup_dir / backup_filename
                
                shutil.copy2(dest, backup_path)
                log_detail(f"備份: {dest.name} → backup/{backup_path.name}")
            
            shutil.copy2(src, dest)
            log_detail(f"複製: {src.name} → {dest.name}")
            return True
            
        except Exception as e:
            error_msg = f"複製失敗: {e}"
            log_detail(f"錯誤: {error_msg}")
            return False

    def update_po_file(po_path: Path, updates_list: list[tuple[str, str]]) -> dict:
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
            log_detail(f"JSON 路徑解析失敗 '{path}': {e}")
            return False

    def update_json_file(json_path: Path, updates_list: list[tuple[str, str]]) -> dict:
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

    # 處理每個業態
    results = {}
    
    # 使用配置中的檔案命名模板
    file_gen_config = config.config.get('file_generation', {}).get('output_files', {})
    po_template = file_gen_config.get('po_template', '{base_name}{suffix}.po')
    json_template = file_gen_config.get('json_template', '{base_name}{suffix}.json')
    
    for bt_code in target_business_types:
        bt_config = business_types[bt_code]
        suffix = bt_config['suffix']
        display_name = bt_config['display_name']
        
        po_dest = Path(po_template.format(base_name=ORIG_PO.stem, suffix=suffix))
        json_dest = Path(json_template.format(base_name=ORIG_JSON.stem, suffix=suffix))

        print(f"\n📝 處理 {display_name}...")
        log_detail(f"開始處理業態: {display_name}")
        
        domain_result = {
            "po_file": str(po_dest),
            "json_file": str(json_dest),
            "po_result": {"success": False, "updated": 0, "errors": []},
            "json_result": {"success": False, "updated": 0, "errors": []}
        }
        
        po_copy_success = create_backup_and_copy(ORIG_PO, po_dest)
        json_copy_success = create_backup_and_copy(ORIG_JSON, json_dest)
        
        if not (po_copy_success and json_copy_success):
            error_msg = f"{display_name} 檔案複製失敗，跳過處理"
            print(f"  ❌ {error_msg}")
            log_detail(f"錯誤: {error_msg}")
            results[bt_code] = domain_result
            continue
        
        domain_result["po_result"] = update_po_file(po_dest, updates[bt_code]["po"])
        domain_result["json_result"] = update_json_file(json_dest, updates[bt_code]["json"])
        
        results[bt_code] = domain_result
        
        print(f"  ✅ 完成 - PO: {domain_result['po_result']['updated']} 個, JSON: {domain_result['json_result']['updated']} 個")
        
        log_detail(f"{display_name} 處理完成: PO 更新 {domain_result['po_result']['updated']} 個, JSON 更新 {domain_result['json_result']['updated']} 個")

    # 生成最終報告
    print(f"\n🎉 處理完畢！")
    
    all_success = True
    total_updates = 0
    
    for bt_code, result in results.items():
        display_name = business_types[bt_code]['display_name']
        po_updated = result["po_result"]["updated"]
        json_updated = result["json_result"]["updated"]
        domain_total = po_updated + json_updated
        total_updates += domain_total
        
        po_success = result["po_result"]["success"]
        json_success = result["json_result"]["success"]
        domain_success = po_success and json_success
        
        if not domain_success:
            all_success = False
        
        status_icon = "✅" if domain_success else "❌"
        print(f"{status_icon} {display_name}: {domain_total} 個更新 ({result['po_file']}, {result['json_file']})")
        
        log_detail(f"最終結果 - {display_name}: PO={po_updated}, JSON={json_updated}, 成功={domain_success}")
        
        all_errors = result["po_result"]["errors"] + result["json_result"]["errors"]
        if all_errors:
            for error in all_errors:
                log_detail(f"錯誤詳情 - {display_name}: {error}")
    
    print(f"\n📊 總計: {total_updates} 個更新，狀態: {'✅ 成功' if all_success else '⚠️ 部分失敗'}")
    print(f"📄 詳細日誌: {log_file}")
    
    print(f"\n✨ 純 Excel 方案優勢：")
    print(f"   ✅ 完全基於 Excel 檔案")
    print(f"   ✅ 無需維護 Python 字典")
    print(f"   ✅ 工作流程極其簡單")
    print(f"   ✅ 修改 Excel 立即生效")
    
    log_detail(f"處理完成 - 總更新: {total_updates}, 整體成功: {all_success}")
    
    if not all_success:
        sys.exit(1)


if __name__ == "__main__":
    main()