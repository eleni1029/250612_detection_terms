2025-06-10 詞彙檢測與替換專案 Version 2.0
-------------------------

一個支援多語言和可配置業態的敏感詞檢測與替換系統。

## 🆕 v2.0 更新內容

- ✅ **多語言支援**：可處理不同語言的翻譯檔案
- ✅ **可配置業態**：支援任意數量的業態類型
- ✅ **配置檔案驅動**：透過 `config.yaml` 集中管理設定
- ✅ **自動檢測**：智能檢測語言和檔案類型
- ✅ **向下相容**：保持與 v1.0 的相容性

## 📁 檔案結構

```
250609_detection_terms/
├── config.yaml                          # 系統配置檔案
├── config_loader.py                     # 配置載入器
├── detection_terms.py                   # 基礎敏感詞字典
├── detection_terms_enterprises.py       # 企業方案字典
├── detection_terms_public_sector.py     # 公部門方案字典
├── detection_terms_training_institutions.py  # 培訓機構方案字典
├── phrase_update.py                     # Excel → Python 字典轉換
├── phrase_comparison.py                 # 生成對照 Excel
├── script_01_generate_xlsx.py           # 掃描翻譯檔案生成問題列表
├── script_02_apply_fixes.py             # 套用修正結果
├── messages.po                          # PO 翻譯檔案
├── zh-TW.json                          # JSON 翻譯檔案
├── phrase_comparison.xlsx               # 敏感詞對照表
├── tobemodified_zh-TW.xlsx             # 待修正項目列表
└── backup/                             # 備份目錄
    ├── apply_fixes_YYYYMMDD_HHMMSS.log
    └── ...
```

## ⚙️ 配置說明

### config.yaml 結構

```yaml
# 語言配置
languages:
  zh-TW:
    po_file: "messages.po"
    json_file: "zh-TW.json"
    description: "繁體中文"
  # 可添加更多語言...

# 業態配置 (可擴充)
business_types:
  enterprises:
    suffix: "_enterprises"
    display_name: "企業"
    description: "企業客戶適用的敏感詞解決方案"
  
  public_sector:
    suffix: "_public_sector"
    display_name: "公部門"
    description: "政府機關與公部門適用的敏感詞解決方案"
  
  training_institutions:
    suffix: "_training_institutions"
    display_name: "培訓機構"
    description: "教育訓練機構適用的敏感詞解決方案"
  
  # 可添加更多業態...
```

### 新增語言

1. 在 `config.yaml` 的 `languages` 區段添加新語言：
```yaml
languages:
  en:
    po_file: "messages_en.po"
    json_file: "en.json"
    description: "English"
```

2. 準備對應的翻譯檔案：
   - `messages_en.po`
   - `en.json`

### 新增業態

1. 在 `config.yaml` 的 `business_types` 區段添加新業態：
```yaml
business_types:
  healthcare:
    suffix: "_healthcare"
    display_name: "醫療機構"
    description: "醫療保健機構適用的敏感詞解決方案"
```

2. 系統會自動生成對應的檔案：
   - `detection_terms_healthcare.py`

## 🚀 使用流程

### 1. 建立敏感詞對照表

```bash
python phrase_comparison.py
```

**功能**：
- 讀取所有 `detection_terms_*.py` 檔案
- 生成 `phrase_comparison.xlsx` 對照表
- 顯示敏感詞與各業態解決方案的對應關係

### 2. 更新敏感詞字典

編輯 `phrase_comparison.xlsx` 後：

```bash
python phrase_update.py
```

**功能**：
- 讀取修改後的 `phrase_comparison.xlsx`
- 重新生成所有 `detection_terms_*.py` 檔案
- 自動備份原始檔案到 `backup/`

### 3. 掃描翻譯檔案

```bash
# 掃描預設語言 (zh-TW)
python script_01_generate_xlsx.py

# 掃描指定語言
python script_01_generate_xlsx.py --language en

# 顯示說明
python script_01_generate_xlsx.py --help
```

**功能**：
- 掃描指定語言的 PO 和 JSON 檔案
- 偵測敏感詞並生成修正建議
- 輸出 `tobemodified_語言.xlsx`

### 4. 套用修正結果

```bash
# 互動式選擇
python script_02_apply_fixes.py

# 指定語言和業態
python script_02_apply_fixes.py --language zh-TW --business-types enterprises public_sector

# 套用全部業態
python script_02_apply_fixes.py --business-types all

# 顯示說明
python script_02_apply_fixes.py --help
```

**功能**：
- 讀取 `tobemodified_*.xlsx` 中的修正結果
- 生成各業態的翻譯檔案
- 自動備份原始檔案到 `backup/`

## 📊 檔案命名規則

### 字典檔案
- 基礎敏感詞：`detection_terms.py`
- 業態方案：`detection_terms_{業態後綴}.py`

### 翻譯檔案
- 原始檔案：`messages.po`、`zh-TW.json`
- 業態檔案：`messages_{業態後綴}.po`、`zh-TW_{業態後綴}.json`

### Excel 檔案
- 對照表：`phrase_comparison.xlsx`
- 待修正列表：`tobemodified_{語言}.xlsx`

### 備份檔案
- 位置：`backup/` 目錄
- 格式：`檔名_{時間戳}.副檔名`
- 日誌：`apply_fixes_{時間戳}.log`

## 📋 Excel 檔案格式

### phrase_comparison.xlsx
| 敏感詞類型 | 敏感詞 | 對應方案(企業) | 一對多校驗(企業) | 對應方案(公部門) | 一對多校驗(公部門) | 對應方案(培訓機構) | 一對多校驗(培訓機構) |
|------------|--------|----------------|------------------|------------------|-------------------|-------------------|---------------------|
| 時間相關   | 年度   | 年度報告       |                  | 年度總結         |                   | 年度課程          |                     |

### tobemodified_{語言}.xlsx
| source | key | value | 敏感詞 | 修正方案(企業) | 修正結果(企業) | 修正方案(公部門) | 修正結果(公部門) | 修正方案(培訓機構) | 修正結果(培訓機構) |
|--------|-----|-------|--------|----------------|----------------|------------------|------------------|-------------------|-------------------|
| po     | ... | ...   | 年度   | 年度→年度報告  | ...年度報告... | 年度→年度總結    | ...年度總結...   | 年度→年度課程     | ...年度課程...    |

## 🔧 開發指南

### 新增支援的檔案類型

1. 修改 `script_01_generate_xlsx.py` 中的檔案讀取函數
2. 添加對應的檔案解析邏輯
3. 更新 `script_02_apply_fixes.py` 中的檔案寫入函數

### 擴展檢測邏輯

1. 修改 `script_01_generate_xlsx.py` 中的 `find_keywords()` 函數
2. 調整正則表達式或檢測算法
3. 更新關鍵字匹配邏輯

### 自定義業態邏輯

1. 在 `config.yaml` 中定義新的業態
2. 系統會自動處理檔案生成和映射
3. 可在各腳本中添加特定業態的處理邏輯

## 🐛 故障排除

### 常見問題

**Q: `❌ 找不到配置文件：config.yaml`**
A: 確保 `config.yaml` 檔案存在於執行目錄中

**Q: `❌ 載入 detection_terms_*.py 失敗`**
A: 檢查 Python 檔案語法是否正確，確保包含 `DETECTION_TERMS` 變數

**Q: `❌ Excel 缺少必要欄位`**
A: 確保 Excel 檔案包含所有必要的欄位，可重新生成檔案

**Q: `❌ JSON 格式錯誤`**
A: 檢查 JSON 檔案語法，使用 JSON 驗證工具確認格式正確

### 日誌檢查

詳細的操作日誌儲存在 `backup/apply_fixes_*.log`：
```bash
# 查看最新日誌
ls -la backup/apply_fixes_*.log | tail -1
cat backup/apply_fixes_YYYYMMDD_HHMMSS.log
```

### 備份恢復

如需恢復備份檔案：
```bash
# 查看備份檔案
ls backup/

# 恢復檔案 (範例)
cp backup/detection_terms_20241210_143000.py detection_terms.py
```

## 📚 API 參考

### config_loader.py

```python
from config_loader import get_config

config = get_config()

# 獲取語言配置
languages = config.get_languages()
default_lang = config.get_default_language()
lang_files = config.get_language_files('zh-TW')

# 獲取業態配置
business_types = config.get_business_types()
choices = config.get_business_type_choices()

# 獲取檔案路徑
detection_files = config.get_detection_terms_files()
output_files = config.get_output_files('zh-TW')
```

### 命令列參數

#### script_01_generate_xlsx.py
```bash
python script_01_generate_xlsx.py [選項]

選項:
  -l, --language {zh-TW,en,...}  指定要處理的語言
  -h, --help                     顯示說明並退出
```

#### script_02_apply_fixes.py
```bash
python script_02_apply_fixes.py [選項]

選項:
  -l, --language {zh-TW,en,...}           指定要處理的語言
  -b, --business-types {業態1,業態2,all}  指定要處理的業態
  -h, --help                              顯示說明並退出
```

## 📈 效能優化

### 大型檔案處理
- 對於大型翻譯檔案，考慮分批處理
- 使用 `--business-types` 參數只處理必要的業態

### 記憶體使用
- 系統會將整個檔案載入記憶體
- 對於非常大的檔案，可能需要修改為串流處理

### 處理速度
- Excel 檔案操作是瓶頸
- 考慮使用 pandas 替代 openpyxl 處理大型資料

## 🔐 安全注意事項

- 備份檔案包含敏感資料，注意存取權限
- 配置檔案可能包含路徑資訊，避免暴露
- 日誌檔案記錄詳細操作，定期清理

## 📄 授權

本專案遵循 MIT 授權條款。

## 🤝 貢獻指南

1. Fork 本專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📞 技術支援

如有問題或建議，請：
1. 查看本 README 的故障排除區段
2. 檢查 GitHub Issues
3. 創建新的 Issue 描述問題

---

**版本**: v2.0  
**更新日期**: 2024-12-10  
**維護者**: [您的名稱]






2025-06-10 Version 1.0
-------------------------
資料夾：
1. Ori: 手動備份文件，在專案中不會用到。
2. backup：在更新 py, po, json 時，會保存 backup 文件在裡頭，並加上時間戳。
3. __pycache__：我也不知道是啥，Claude 很開心寫的。

檔案，此處僅引用繁體中文的版本：
1. zh-TW.json - 前端文件（內部稱呼）
2. messages.po - 後端文件（內部稱呼）

-
操作流程：
這個專案包含兩套操作，
  1. 敏感詞彙的確認與調整
    1-1. 用戶編輯 phrase_comparison.xlsx，確認後保存。
    1-2. 執行 “phrase_update.py”，會輸入 phrase_comparison.xlsx,
      存在變更時會先備份原本的py文件，然後將新的內容分別寫入
      detection_terms.py,（教育機構）
      detection_terms_enterprises.py,（企業）
      detection_terms_public_sector.py,（公部門）
      detection_terms_training_institutions.py.(培訓機構）
 （*備註：
    這個步驟是可逆的，如果四個py是另外生成的，也可以根據py的內容生成phrase_comparison.xlsx：
    在已經存在這幾個py的情況下，執行"phrase_comparison.py",即可生成 phrase_comparison.xlsx。）

  2. 具體替換敏感詞彙並確認寫入，生成新版本的 json 與 po 文件。
    2-1. 執行整體比對，執行 "script_01_generate_xlsx.py"
      輸出 tobemodified.xlsx 內容會包含如下 
      對比 messages.po, zh-TW.json, 列出內容包含敏感詞彙的 key 與 value
      並且展示對應在企業、公部門、培訓機構的 value 對照，並顯示替換後的 value 值。
    2-2. 用戶確認是否調整（不調整可以將內容改為空），或是整體用另外的方式修改。
      用戶調整完成後，執行 "script_02_apply_fixes.py"
      會將有修改的文件保存到 bakcup 中，並且生成新的對應 po 與 json 文件：
      zh-TW.json
      zh-TW_enterprises.json
      zh-TW_public_sector.json
      zh-TW_training_institutions.json
      messages.po
      messages_enterprises.po
      messages_public_sector.po
      messages_training_institutions.po

  3. 截至 2025-06-10，目前尚未加入其他語言或是其他前後端文件的功能。
