#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script_02_apply_fixes.py (v2.0)

依據 tobemodified.xlsx，把「修正結果」寫回翻譯檔。
支援多語言和可配置的業態類型。

更新內容：
- 支援 config.yaml 配置
- 支援多語言選擇
- 支援可擴充的業態類型
- 自動檢測 tobemodified 檔案語言
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
    print("🚀 開始套用修正結果 (v2.0)")
    
    # 載入配置
    config = get_config()
    config.print_config_summary()
    
    # 設置備份目錄
    backup_dir = Path(config.get_base_files()['backup_dir'])
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
    def detect_or_choose_