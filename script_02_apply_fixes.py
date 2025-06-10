#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_02_apply_fixes.py

依據 tobemodified.xlsx，把「修正結果」寫回翻譯檔。
改進點：修正檔名後綴一致性、增加日誌記錄、簡化終端輸出
"""

from pathlib import Path
import json
import sys
import shutil
import re
import datetime
from collections import defaultdict

try:
    import openpyxl
    import polib
except ImportError as e:
    print(f"❌ 缺少必要套件：{e}")
    print("請執行：pip install openpyxl polib")
    sys.exit(1)


def main():
    print("🚀 開始套用修正結果")
    
    backup_dir = Path("backup")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = backup_dir / f"apply_fixes_{timestamp}.log"
    
    def log_detail(message: str):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n")

    ORIG_PO = Path("messages.po")
    ORIG_JSON = Path("zh-TW.json")
    XLSX = Path("tobemodified.xlsx")
    
    missing_files = []
    if not ORIG_PO.exists():
        missing_files.append(str(ORIG_PO))
    if not ORIG_JSON.exists():
        missing_files.append(str(ORIG_JSON))
    if not XLSX.exists():
        missing_files.append(str(XLSX))
    
    if missing_files:
        print(f"❌ 找不到必要檔案：{', '.join(missing_files)}")
        if str(XLSX) in missing_files:
            print("請先執行 script_01_generate_xlsx.py 生成 tobemodified.xlsx")
        sys.exit(1)

    DOMAINS = {
        "企業": {
            "suffix": "_enterprises",
            "xlsx_col": "修正結果(企業)",
        },
        "公部門": {
            "suffix": "_public_sector",
            "xlsx_col": "修正結果(公部門)",
        },
        "培訓機構": {
            "suffix": "_training_institutions",
            "xlsx_col": "修正結果(培訓機構)",
        },
    }

    def choose_domain() -> list[str]:
        cli_arg = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
        
        if cli_arg:
            if cli_arg == "全部":
                return list(DOMAINS.keys())
            if cli_arg in DOMAINS:
                return [cli_arg]
            print(f"❌ 無效的參數：{cli_arg}")
            print("有效參數：企業 / 公部門 / 培訓機構 / 全部")
            sys.exit(1)
        
        print("\n請選擇要套用修正的業態：")
        print("  1) 企業")
        print("  2) 公部門") 
        print("  3) 培訓機構")
        print("  4) 全部")
        
        mapping = {"1": "企業", "2": "公部門", "3": "培訓機構", "4": "全部"}
        
        while True:
            try:
                opt = input("\n輸入選項 (1-4)：").strip()
                if opt in mapping:
                    selected = mapping[opt]
                    if selected == "全部":
                        return list(DOMAINS.keys())
                    return [selected]
                print("⚠️  請輸入 1-4 之間的數字")
            except KeyboardInterrupt:
                print("\n❌ 使用者取消操作")
                sys.exit(0)

    targets = choose_domain()
    print(f"\n👉 將套用至：{', '.join(targets)}")

    # 預先備份現有的目標檔案
    def backup_existing_files():
        print(f"🔍 檢查並備份現有檔案...")
        backup_count = 0
        
        for domain in targets:
            suffix = DOMAINS[domain]["suffix"]
            po_target = ORIG_PO.with_name(f"{ORIG_PO.stem}{suffix}.po")
            json_target = ORIG_JSON.with_name(f"{ORIG_JSON.stem}{suffix}.json")
            
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
            
            for domain in targets:
                col_name = DOMAINS[domain]["xlsx_col"]
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

    print(f"🔍 解析修正資料...")
    log_detail("開始解析 Excel 修正資料")
    updates = {domain: {"po": [], "json": []} for domain in targets}
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
            
            for domain in targets:
                col_name = DOMAINS[domain]["xlsx_col"]
                new_value = row[get_column_index(col_name)]
                
                if not (isinstance(new_value, str) and new_value.strip()):
                    continue
                
                new_value = new_value.strip()
                stats[f'{domain}_updates'] += 1
                
                if source == "po":
                    updates[domain]["po"].append((key, new_value))
                    log_detail(f"PO 更新 - {domain}: {key} → {new_value}")
                elif source == "json":
                    updates[domain]["json"].append((key, new_value))
                    log_detail(f"JSON 更新 - {domain}: {key} → {new_value}")
                else:
                    log_detail(f"警告: 第 {row_num} 行未知的 source 類型 '{source}'")
            
        except Exception as e:
            log_detail(f"錯誤: 第 {row_num} 行處理失敗: {e}")
            continue

    print(f"✅ 解析完成 - 總行數: {stats['total_rows']}")
    for domain in targets:
        update_count = stats[f'{domain}_updates']
        print(f"   {domain}: {update_count} 個更新")
    
    log_detail(f"解析完成統計: {dict(stats)}")

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

    results = {}
    
    for domain in targets:
        suffix = DOMAINS[domain]["suffix"]
        po_dest = ORIG_PO.with_name(f"{ORIG_PO.stem}{suffix}.po")
        json_dest = ORIG_JSON.with_name(f"{ORIG_JSON.stem}{suffix}.json")

        print(f"\n📝 處理 {domain}...")
        log_detail(f"開始處理業態: {domain}")
        
        domain_result = {
            "po_file": str(po_dest),
            "json_file": str(json_dest),
            "po_result": {"success": False, "updated": 0, "errors": []},
            "json_result": {"success": False, "updated": 0, "errors": []}
        }
        
        po_copy_success = create_backup_and_copy(ORIG_PO, po_dest)
        json_copy_success = create_backup_and_copy(ORIG_JSON, json_dest)
        
        if not (po_copy_success and json_copy_success):
            error_msg = f"{domain} 檔案複製失敗，跳過處理"
            print(f"  ❌ {error_msg}")
            log_detail(f"錯誤: {error_msg}")
            results[domain] = domain_result
            continue
        
        domain_result["po_result"] = update_po_file(po_dest, updates[domain]["po"])
        domain_result["json_result"] = update_json_file(json_dest, updates[domain]["json"])
        
        results[domain] = domain_result
        
        print(f"  ✅ 完成 - PO: {domain_result['po_result']['updated']} 個, JSON: {domain_result['json_result']['updated']} 個")
        
        log_detail(f"{domain} 處理完成: PO 更新 {domain_result['po_result']['updated']} 個, JSON 更新 {domain_result['json_result']['updated']} 個")

    print(f"\n🎉 處理完畢！")
    
    all_success = True
    total_updates = 0
    
    for domain, result in results.items():
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
        print(f"{status_icon} {domain}: {domain_total} 個更新 ({result['po_file']}, {result['json_file']})")
        
        log_detail(f"最終結果 - {domain}: PO={po_updated}, JSON={json_updated}, 成功={domain_success}")
        
        all_errors = result["po_result"]["errors"] + result["json_result"]["errors"]
        if all_errors:
            for error in all_errors:
                log_detail(f"錯誤詳情 - {domain}: {error}")
    
    print(f"\n📊 總計: {total_updates} 個更新，狀態: {'✅ 成功' if all_success else '⚠️ 部分失敗'}")
    print(f"📄 詳細日誌: {log_file}")
    
    log_detail(f"處理完成 - 總更新: {total_updates}, 整體成功: {all_success}")
    
    if not all_success:
        sys.exit(1)


if __name__ == "__main__":
    main()