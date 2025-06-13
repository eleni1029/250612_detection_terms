#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_02_apply_combine.py (v1.0 - 檔案合併版)

功能：
1. 選擇要合併的 tobemodified Excel 檔案
2. 選擇 i18n_combine 目錄下的 JSON/PO 檔案作為合併目標
3. 檢測重複 key 並處理衝突
4. 生成合併後的檔案到 i18n_output/{language}_{timestamp}_combined/
5. 提供詳細的合併報告和日誌

依據用戶選擇的 tobemodified_{language}.xlsx，將修正結果合併到指定的翻譯檔案中
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


def detect_tobemodified_files(config) -> dict:
    """檢測可用的 tobemodified 檔案"""
    available_files = {}
    
    # 檢測輸出目錄中的檔案
    try:
        dirs = config.get_directories()
        output_dir = Path(dirs['output_dir'])
    except Exception:
        output_dir = Path('i18n_output')
    
    # 使用配置載入器的語言檢測
    try:
        available_languages = config.detect_available_languages()
    except Exception as e:
        print(f"⚠️  語言檢測失敗：{e}")
        available_languages = []
    
    # 檢測標準命名的檔案
    for language in available_languages:
        tobemodified_path = output_dir / f"{language}_tobemodified.xlsx"
        if tobemodified_path.exists():
            available_files[language] = tobemodified_path
    
    # 在當前目錄中查找額外的檔案
    for file_path in Path('.').glob("*_tobemodified.xlsx"):
        filename = file_path.stem
        if filename.endswith('_tobemodified'):
            language = filename[:-len('_tobemodified')]
            
            # 過濾系統臨時檔案
            if language.startswith(('~$', '.', '__')):
                continue
            
            if language not in available_files:
                available_files[language] = file_path

    return available_files


def scan_combine_directory(combine_dir: Path) -> dict:
    """掃描 i18n_combine 目錄中的檔案"""
    files = {
        'json': [],
        'po': []
    }
    
    if not combine_dir.exists():
        return files
    
    # 遞歸掃描所有 JSON 和 PO 檔案
    for file_path in combine_dir.rglob("*.json"):
        relative_path = file_path.relative_to(combine_dir)
        files['json'].append({
            'path': file_path,
            'relative_path': str(relative_path),
            'name': file_path.name
        })
    
    for file_path in combine_dir.rglob("*.po"):
        relative_path = file_path.relative_to(combine_dir)
        files['po'].append({
            'path': file_path,
            'relative_path': str(relative_path),
            'name': file_path.name
        })
    
    return files


def choose_tobemodified_file(available_files: dict) -> tuple:
    """選擇要使用的 tobemodified 檔案"""
    if not available_files:
        print("❌ 未找到任何 tobemodified 檔案")
        return None, None
    
    if len(available_files) == 1:
        language, file_path = list(available_files.items())[0]
        print(f"🎯 自動選擇唯一的 tobemodified 檔案：{language} ({file_path.name})")
        return language, file_path
    
    # 多個檔案，讓用戶選擇
    print("\n📄 可用的 tobemodified 檔案：")
    choices = list(available_files.items())
    
    for i, (language, file_path) in enumerate(choices, 1):
        print(f"  {i}) {language} ({file_path.name})")
    
    while True:
        try:
            choice = input(f"\n請選擇要使用的檔案 (1-{len(choices)})：").strip()
            choice_idx = int(choice) - 1
            
            if 0 <= choice_idx < len(choices):
                language, file_path = choices[choice_idx]
                print(f"✅ 選擇了：{language} ({file_path.name})")
                return language, file_path
            else:
                print(f"⚠️  請輸入 1-{len(choices)} 之間的數字")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 操作取消")
            return None, None


def choose_combine_file(files: list, file_type: str) -> Path:
    """選擇要合併的檔案"""
    if not files:
        print(f"⚠️  /i18n_combine/ 中沒有找到 {file_type.upper()} 檔案")
        return None
    
    print(f"\n📁 可用的 {file_type.upper()} 檔案：")
    for i, file_info in enumerate(files, 1):
        print(f"  {i}) {file_info['relative_path']}")
    
    print(f"  0) 跳過 {file_type.upper()} 檔案")
    
    while True:
        try:
            choice = input(f"\n請選擇要合併的 {file_type.upper()} 檔案 (0-{len(files)})：").strip()
            choice_idx = int(choice)
            
            if choice_idx == 0:
                print(f"⏭️  跳過 {file_type.upper()} 檔案")
                return None
            elif 1 <= choice_idx <= len(files):
                selected_file = files[choice_idx - 1]
                print(f"✅ 選擇了：{selected_file['relative_path']}")
                return selected_file['path']
            else:
                print(f"⚠️  請輸入 0-{len(files)} 之間的數字")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ 操作取消")
            return None


def read_excel_updates(xlsx_path: Path, config) -> dict:
    """讀取 Excel 檔案中的更新資料 - 自動處理所有有替換結果的業態"""
    try:
        print(f"📖 讀取 Excel 檔案：{xlsx_path.name}")
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        
        header_row = list(ws[1])
        header = {cell.value: idx for idx, cell in enumerate(header_row) if cell.value}
        
        # 基本欄位檢查
        required_columns = ["檔案類型", "項目ID", "項目內容"]
        missing_columns = []
        
        for col in required_columns:
            if col not in header:
                missing_columns.append(col)
        
        if missing_columns:
            print(f"❌ Excel 缺少必要欄位：{missing_columns}")
            return {}
        
        # 自動檢測所有業態的替換結果欄位
        business_types = config.get_business_types()
        available_business_types = []
        
        for bt_code, bt_config in business_types.items():
            display_name = bt_config['display_name']
            result_col_name = f"{display_name}_替換結果"
            if result_col_name in header:
                available_business_types.append(bt_code)
        
        if not available_business_types:
            print("❌ 未找到任何業態的替換結果欄位")
            return {}
        
        print(f"   📋 檢測到業態：{', '.join([business_types[bt]['display_name'] for bt in available_business_types])}")
        
        # 解析更新資料
        updates = {bt_code: {"po": [], "json": []} for bt_code in available_business_types}
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or len(row) <= max(header.values()):
                continue
            
            try:
                file_type = row[header["檔案類型"]]
                entry_id = row[header["項目ID"]]
                original_text = row[header["項目內容"]]
                
                if not file_type or not entry_id:
                    continue
                
                file_type = str(file_type).lower()
                
                # 處理每個可用的業態
                for bt_code in available_business_types:
                    display_name = business_types[bt_code]['display_name']
                    result_col_name = f"{display_name}_替換結果"
                    
                    new_value = row[header[result_col_name]]
                    
                    # 跳過空值和與原文相同的值
                    if not new_value or not str(new_value).strip():
                        continue
                    
                    new_value = str(new_value).strip()
                    
                    if original_text and str(original_text).strip() == new_value:
                        continue
                    
                    # 創建更新記錄
                    update_record = (str(entry_id), new_value)
                    
                    if file_type == "po":
                        updates[bt_code]["po"].append(update_record)
                    elif file_type == "json":
                        updates[bt_code]["json"].append(update_record)
            
            except Exception as e:
                print(f"⚠️  第 {row_num} 行處理失敗: {e}")
                continue
        
        # 統計有效更新
        total_updates = 0
        for bt_code in available_business_types:
            bt_updates = len(updates[bt_code]["po"]) + len(updates[bt_code]["json"])
            total_updates += bt_updates
            if bt_updates > 0:
                print(f"     {business_types[bt_code]['display_name']}: {bt_updates} 個更新")
        
        print(f"   📊 總計：{total_updates} 個有效更新")
        return updates
        
    except Exception as e:
        print(f"❌ 讀取 Excel 檔案失敗：{e}")
        return {}


def combine_po_files(updates_list: list, target_po_path: Path, output_po_path: Path) -> dict:
    """合併 PO 檔案"""
    result = {
        "success": False,
        "merged": 0,
        "skipped": 0,
        "conflicts": [],
        "errors": []
    }
    
    if not updates_list:
        result["success"] = True
        return result
    
    try:
        # 載入目標 PO 檔案
        if not target_po_path.exists():
            result["errors"].append(f"目標 PO 檔案不存在：{target_po_path}")
            return result
        
        target_po = polib.pofile(str(target_po_path))
        print(f"   📄 載入目標 PO 檔案：{target_po_path.name}，共 {len(target_po)} 個條目")
        
        conflicts = []
        
        # 處理更新
        for msgid, new_msgstr in updates_list:
            target_entry = target_po.find(msgid)
            
            if target_entry:
                # 檢查是否有衝突
                if target_entry.msgstr and target_entry.msgstr.strip():
                    if target_entry.msgstr != new_msgstr:
                        # 發現衝突
                        conflict_info = {
                            'msgid': msgid,
                            'existing_value': target_entry.msgstr,
                            'new_value': new_msgstr,
                            'file_type': 'po'
                        }
                        conflicts.append(conflict_info)
                        continue
                    else:
                        # 值相同，跳過
                        result["skipped"] += 1
                        continue
                
                # 應用更新
                target_entry.msgstr = new_msgstr
                result["merged"] += 1
            else:
                # 目標檔案中沒有此條目，添加新條目
                new_entry = polib.POEntry(
                    msgid=msgid,
                    msgstr=new_msgstr
                )
                target_po.append(new_entry)
                result["merged"] += 1
        
        # 如果有衝突，記錄但不儲存
        if conflicts:
            result["conflicts"] = conflicts
            result["success"] = False
            return result
        
        # 保存合併後的檔案
        output_po_path.parent.mkdir(parents=True, exist_ok=True)
        target_po.save(str(output_po_path))
        
        result["success"] = True
        
    except Exception as e:
        result["errors"].append(f"PO 檔案合併失敗：{e}")
    
    return result


def combine_json_files(updates_list: list, target_json_path: Path, output_json_path: Path) -> dict:
    """合併 JSON 檔案"""
    result = {
        "success": False,
        "merged": 0,
        "skipped": 0,
        "conflicts": [],
        "errors": []
    }
    
    if not updates_list:
        result["success"] = True
        return result
    
    try:
        # 載入目標 JSON 檔案
        if not target_json_path.exists():
            result["errors"].append(f"目標 JSON 檔案不存在：{target_json_path}")
            return result
        
        target_data = json.loads(target_json_path.read_text(encoding="utf-8"))
        print(f"   📄 載入目標 JSON 檔案：{target_json_path.name}")
        
        conflicts = []
        
        # 處理更新
        for json_path_str, new_value in updates_list:
            # 獲取現有值
            existing_value = get_json_value_by_path(target_data, json_path_str)
            
            if existing_value is not None:
                # 檢查是否有衝突
                if str(existing_value).strip() != str(new_value).strip():
                    # 發現衝突
                    conflict_info = {
                        'path': json_path_str,
                        'existing_value': existing_value,
                        'new_value': new_value,
                        'file_type': 'json'
                    }
                    conflicts.append(conflict_info)
                    continue
                else:
                    # 值相同，跳過
                    result["skipped"] += 1
                    continue
            
            # 應用更新
            if set_json_value_by_path(target_data, json_path_str, new_value):
                result["merged"] += 1
            else:
                result["errors"].append(f"無法設置 JSON 路徑：{json_path_str}")
        
        # 如果有衝突，記錄但不儲存
        if conflicts:
            result["conflicts"] = conflicts
            result["success"] = False
            return result
        
        # 保存合併後的檔案
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        
        json_content = json.dumps(target_data, ensure_ascii=False, indent=2)
        output_json_path.write_text(json_content, encoding="utf-8")
        
        result["success"] = True
        
    except json.JSONDecodeError as e:
        result["errors"].append(f"JSON 格式錯誤：{e}")
    except Exception as e:
        result["errors"].append(f"JSON 檔案合併失敗：{e}")
    
    return result


def get_json_value_by_path(data: dict, path: str):
    """按路徑獲取 JSON 值"""
    try:
        path_parts = parse_json_path(path)
        current = data
        
        for part_type, part_value in path_parts:
            if part_type == 'key':
                if part_value not in current:
                    return None
                current = current[part_value]
            elif part_type == 'index':
                if not isinstance(current, list) or len(current) <= part_value:
                    return None
                current = current[part_value]
        
        return current
        
    except Exception:
        return None


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


def choose_business_types(config) -> list:
    """選擇要處理的業態 - 已移除，改為自動處理所有有替換結果的業態"""
    # 此函數已不再使用，保留以維持相容性
    business_types = config.get_business_types()
    return list(business_types.keys())


def main():
    """主執行函數"""
    print("🚀 開始檔案合併處理 (v1.0)")
    
    # 載入配置
    config = get_config()
    
    # 檢測可用的 tobemodified 檔案
    available_files = detect_tobemodified_files(config)
    
    if not available_files:
        print("❌ 未找到任何 tobemodified 檔案")
        print("請先執行 script_01_generate_xlsx.py 生成檔案")
        sys.exit(1)
    
    # 步驟1：選擇 tobemodified 檔案
    language, tobemodified_path = choose_tobemodified_file(available_files)
    if not language:
        sys.exit(1)
    
    # 檢查 i18n_combine 目錄
    combine_dir = Path("i18n_combine")
    
    if not combine_dir.exists():
        print(f"❌ 合併目錄不存在：{combine_dir}")
        print(f"請創建目錄並放入要合併的檔案")
        sys.exit(1)
    
    print(f"📁 掃描合併目錄：{combine_dir}")
    
    # 掃描 combine 目錄中的檔案
    combine_files = scan_combine_directory(combine_dir)
    
    # 步驟2：選擇要合併的 JSON 檔案
    target_json_path = choose_combine_file(combine_files['json'], 'json')
    
    # 步驟3：選擇要合併的 PO 檔案
    target_po_path = choose_combine_file(combine_files['po'], 'po')
    
    # 檢查是否至少選擇了一個檔案
    if not target_json_path and not target_po_path:
        print("❌ 必須至少選擇一個檔案進行合併")
        sys.exit(1)
    
    # 讀取 Excel 更新資料（自動檢測所有業態）
    updates = read_excel_updates(tobemodified_path, config)
    if not updates:
        print("❌ 讀取 Excel 檔案失敗或沒有有效的更新")
        sys.exit(1)
    
    # 獲取實際有更新的業態
    target_business_types = [bt_code for bt_code, bt_updates in updates.items() 
                            if bt_updates['po'] or bt_updates['json']]
    
    if not target_business_types:
        print("❌ 沒有找到任何有效的業態更新")
        sys.exit(1)
    
    print(f"\n📋 合併設定：")
    print(f"   來源檔案：{tobemodified_path.name}")
    if target_json_path:
        print(f"   JSON 檔案：{target_json_path.relative_to(combine_dir)}")
    if target_po_path:
        print(f"   PO 檔案：{target_po_path.relative_to(combine_dir)}")
    print(f"   目標業態：{', '.join([config.get_business_types()[bt]['display_name'] for bt in target_business_types])}")
    
    # 建立輸出目錄
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dirs = config.get_directories()
    output_dir = Path(dirs['output_dir']) / f"{language}_{timestamp}_combined"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 設置日誌
    log_file = output_dir / f"combine_{timestamp}.log"
    
    def log_detail(message: str):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n")
    
    log_detail(f"開始合併處理")
    log_detail(f"語言：{language}")
    log_detail(f"來源檔案：{tobemodified_path}")
    log_detail(f"目標業態：{', '.join(target_business_types)}")
    
    # 處理每個業態
    business_types = config.get_business_types()
    all_results = {}
    has_conflicts = False
    
    for bt_code in target_business_types:
        bt_config = business_types[bt_code]
        display_name = bt_config['display_name']
        suffix = bt_config['suffix']
        
        print(f"\n📝 處理 {display_name}...")
        log_detail(f"開始處理業態：{display_name}")
        
        results = {}
        
        # 處理 PO 檔案
        if target_po_path and updates[bt_code]['po']:
            output_po_path = output_dir / f"{target_po_path.stem}{suffix}_combined.po"
            po_result = combine_po_files(
                updates[bt_code]['po'],
                target_po_path,
                output_po_path
            )
            results['po_result'] = po_result
            
            if po_result['conflicts']:
                has_conflicts = True
                print(f"     ❌ PO 檔案發現 {len(po_result['conflicts'])} 個衝突")
                for conflict in po_result['conflicts']:
                    print(f"       衝突 msgid: '{conflict['msgid']}'")
                    print(f"         現有值: '{conflict['existing_value']}'")
                    print(f"         新值: '{conflict['new_value']}'")
        else:
            # 即使沒有更新也複製原檔案
            if target_po_path:
                output_po_path = output_dir / f"{target_po_path.stem}{suffix}_combined.po"
                output_po_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_po_path, output_po_path)
                print(f"     📄 複製 PO 檔案（無更新）")
        
        # 處理 JSON 檔案
        if target_json_path and updates[bt_code]['json']:
            output_json_path = output_dir / f"{target_json_path.stem}{suffix}_combined.json"
            json_result = combine_json_files(
                updates[bt_code]['json'],
                target_json_path,
                output_json_path
            )
            results['json_result'] = json_result
            
            if json_result['conflicts']:
                has_conflicts = True
                print(f"     ❌ JSON 檔案發現 {len(json_result['conflicts'])} 個衝突")
                for conflict in json_result['conflicts']:
                    print(f"       衝突路徑: '{conflict['path']}'")
                    print(f"         現有值: '{conflict['existing_value']}'")
                    print(f"         新值: '{conflict['new_value']}'")
        else:
            # 即使沒有更新也複製原檔案
            if target_json_path:
                output_json_path = output_dir / f"{target_json_path.stem}{suffix}_combined.json"
                output_json_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_json_path, output_json_path)
        
        all_results[bt_code] = results
        
        # 統計結果
        total_merged = 0
        total_skipped = 0
        
        for result in results.values():
            total_merged += result.get('merged', 0)
            total_skipped += result.get('skipped', 0)
        
        if not has_conflicts:
            print(f"     ✅ 完成 - 合併: {total_merged} 個, 跳過: {total_skipped} 個")
        
        log_detail(f"{display_name} 處理完成：合併 {total_merged} 個，跳過 {total_skipped} 個")"         現有值: '{conflict['existing_value']}'")
                    print(f"         新值: '{conflict['new_value']}'")
        else:
            # 即使沒有更新也複製原檔案
            if target_json_path:
                output_json_path = output_dir / f"{target_json_path.stem}{suffix}.json"
                output_json_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_json_path, output_json_path)
                print(f"     📄 複製 JSON 檔案（無更新）")
        
        all_results[bt_code] = results
        
        # 統計結果
        total_merged = 0
        total_skipped = 0
        
        for result in results.values():
            total_merged += result.get('merged', 0)
            total_skipped += result.get('skipped', 0)
        
        if not has_conflicts:
            print(f"     ✅ 完成 - 合併: {total_merged} 個, 跳過: {total_skipped} 個")
        
        log_detail(f"{display_name} 處理完成：合併 {total_merged} 個，跳過 {total_skipped} 個")
    
    # 如果有衝突，終止操作
    if has_conflicts:
        print(f"\n❌ 發現衝突，操作已終止")
        print(f"請檢查並解決衝突後重新執行")
        log_detail(f"處理因衝突而終止")
        sys.exit(1)
    
    # 生成最終報告
    total_merged = sum(
        sum(result.get('merged', 0) for result in results.values())
        for results in all_results.values()
    )
    total_skipped = sum(
        sum(result.get('skipped', 0) for result in results.values())
        for results in all_results.values()
    )
    
    print(f"\n🎉 合併處理完成！")
    print(f"📊 處理結果：合併 {total_merged} 個項目，跳過 {total_skipped} 個項目")
    print(f"📁 輸出目錄：{output_dir}")
    
    # 生成處理摘要
    generate_combine_summary_report(all_results, output_dir, timestamp, target_json_path, target_po_path, log_detail)


def generate_combine_summary_report(results: dict, output_dir: Path, timestamp: str, 
                                   target_json_path: Path, target_po_path: Path, log_detail):
    """生成合併處理摘要報告"""
    summary_file = output_dir / f"combine_summary_{timestamp}.txt"
    
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"檔案合併處理摘要報告\n")
            f.write(f"生成時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*50}\n\n")
            
            f.write(f"目標檔案：\n")
            if target_json_path:
                f.write(f"  JSON: {target_json_path}\n")
            if target_po_path:
                f.write(f"  PO: {target_po_path}\n")
            f.write(f"\n")
            
            total_merged = 0
            total_skipped = 0
            successful_business_types = []
            failed_business_types = []
            
            for bt_code, bt_results in results.items():
                f.write(f"業態：{bt_code}\n")
                
                bt_merged = sum(result.get('merged', 0) for result in bt_results.values())
                bt_skipped = sum(result.get('skipped', 0) for result in bt_results.values())
                bt_errors = []
                for result in bt_results.values():
                    bt_errors.extend(result.get('errors', []))
                
                f.write(f"合併數量：{bt_merged}\n")
                f.write(f"跳過數量：{bt_skipped}\n")
                
                if bt_errors:
                    f.write(f"錯誤：\n")
                    for error in bt_errors:
                        f.write(f"  - {error}\n")
                    failed_business_types.append(bt_code)
                else:
                    successful_business_types.append(bt_code)
                    total_merged += bt_merged
                    total_skipped += bt_skipped
                
                f.write(f"\n{'-'*30}\n\n")
            
            # 總計統計
            f.write(f"處理總結：\n")
            f.write(f"成功業態：{len(successful_business_types)}\n")
            f.write(f"失敗業態：{len(failed_business_types)}\n")
            f.write(f"總合併項目：{total_merged}\n")
            f.write(f"總跳過項目：{total_skipped}\n")
            
            if successful_business_types:
                f.write(f"\n成功的業態：{', '.join(successful_business_types)}\n")
            
            if failed_business_types:
                f.write(f"失敗的業態：{', '.join(failed_business_types)}\n")
            
            f.write(f"\n合併說明：\n")
            f.write(f"- 本次處理將 tobemodified 中的替換結果合併到指定檔案\n")
            f.write(f"- 相同 key 且相同 value 的項目會自動跳過\n")
            f.write(f"- 相同 key 但不同 value 的項目會產生衝突並中斷操作\n")
            f.write(f"- 合併成功的檔案保存在帶時間戳的目錄中\n")
            
            f.write(f"\n使用建議：\n")
            f.write(f"- 如發現衝突，請檢查並手動解決後重新執行\n")
            f.write(f"- 合併前建議備份原始檔案\n")
            f.write(f"- 合併後請測試翻譯檔案的正確性\n")
        
        log_detail(f"合併摘要報告已生成：{summary_file}")
        
    except Exception as e:
        log_detail(f"生成合併摘要報告失敗：{e}")


if __name__ == "__main__":
    main()