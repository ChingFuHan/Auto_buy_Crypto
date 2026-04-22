# final_file.md
# 請先閱讀 final_file.md，然後依其中規則整理 final_files。

本文件定義最終交付規則。  
用途：讓 Agent 在**不改動專案原本多層次結構**的前提下，於專案根目錄整理出一份**單層平鋪、方便審閱的最終檔案區**。

---

## 規則目標

專案本體可以維持正常工程結構，例如：

- `src/`
- `config/`
- `outputs/`
- `logs/`
- 其他多層次資料夾

但最終交付時，必須另外整理出一個：

- 容易找到
- 沒有子資料夾
- 不混入暫存垃圾
- 不需要再逐層翻找
- 檔名不衝突

的最終交付區。

---

## 固定名稱

請在**專案根目錄**建立：

`final_files`

這是最終交付區。

---

## 硬規則

### 1. 不得改動專案原本結構
- 專案本身維持原本多層次資料夾結構
- 不要為了交付而重構 repo
- 不要把整個專案改成平鋪

### 2. `final_files` 只能單層平鋪
- `final_files` 內只能有檔案
- 不允許任何子資料夾
- 不允許巢狀路徑

### 3. 只匯出重點檔案
不要整個 repo 原樣複製。  
只匯出必要的審閱檔案，例如：

- `README.md`
- `HANDOFF.md`
- `task.md`
- `god_rule.md`
- `final_review.md`
- `overall_results.csv`
- `param_sensitivity.csv`
- `topk_comparison.csv`
- `rebalance_comparison.csv`
- 其他本次任務必須審閱的關鍵檔案

### 4. 同名檔案必須改名防撞
如果不同來源有同名檔案，匯出到 `final_files` 時必須改名，建議加來源前綴。

例如：

- `outputs\\mvp\\final_review.md` → `mvp_final_review.md`
- `outputs\\scan_grid\\final_review.md` → `scan_grid_final_review.md`
- `config\\mvp.toml` → `config_mvp.toml`

### 5. 必須產出 `MANIFEST.txt`
在 `final_files` 內必須另外建立：

`MANIFEST.txt`

內容至少列出：

- 匯出檔名
- 原始路徑
- 用途

### 6. 禁止使用 temp 當最終交付位置
禁止把最終交付物放在：

- `C:\\temp`
- session-state
- 任何暫存目錄
- 任何短生命週期路徑

最終交付物只能放在：

- 專案根目錄下的 `final_files`

### 7. 舊版本先刪再建
如果專案根目錄已存在舊的 `final_files`：

- 先刪除舊版
- 再重建新版

避免新舊檔案混在一起。

### 8. 完成後回報內容
完成後只回報：

- `final_files` 的最終路徑
- 檔案清單
- 是否已清除舊版本

---

## 建議命名規則

平鋪匯出時，檔名應帶來源前綴。

建議格式：

- `config_mvp.toml`
- `mvp_final_review.md`
- `scan_grid_overall_results.csv`
- `src_pbtr_backtest_ic_analysis.py`

原則：
- 一看就知道來源
- 不會撞名
- 不需要打開後才知道用途

---

## 不應匯出的內容

不要放入 `final_files`：

- `.venv`
- `node_modules`
- `__pycache__`
- cache
- 暫存 log 垃圾
- 大型中間產物
- 不必要的原始資料
- 可由其他檔案推得出的重複檔案

---

## 可直接給 Agent 執行的指令模板

你可以直接把下面這段貼給 Agent：

```text
請保留專案原本的多層次資料夾結構，不要動 repo 本體。

請先閱讀 `final_file.md`，然後依其中規則執行 final files 整理。

規則：
1. 在專案根目錄建立 `final_files` 作為最終交付區。
2. `final_files` 內只能單層平鋪檔案，不允許任何子資料夾。
3. 只匯出重點檔案，不要整個 repo 原樣複製。
4. 若不同來源有同名檔案，匯出時必須改名，建議加來源前綴。
5. 必須產出 `MANIFEST.txt`，列出匯出檔名、原始路徑、用途。
6. 禁止使用 temp、session-state 或其他暫存路徑作為最終交付位置。
7. 若舊的 `final_files` 已存在，先刪除後重建。
8. 完成後只回報：
   - `final_files` 的最終路徑
   - 檔案清單
   - 是否已清除舊版本