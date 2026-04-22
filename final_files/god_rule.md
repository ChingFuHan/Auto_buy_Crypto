# GOD RULE - 最高憲法

- **適用範圍：** 所有專案、所有 Agent、所有協作者
- **優先級：** 本文件凌駕於任何子專案規範之上
- **版本：** v1.3.1
- **最後更新：** 2026-04-17

---

## 規則優先級與衝突處理

在規則衝突時，依下列優先級處理：

| 優先級 | 說明 |
|---|---|
| P0 - 絕對禁止 | 機密外洩、無限重試、未留快照就做破壞性操作、覆蓋歷史結果 |
| P1 - 高度重要 | Handoff、Local-first、版本快照、明確風險標示、自我驗證 |
| P2 - 建議遵守 | 其餘工程慣例與專案最佳實踐 |

**衝突處理原則**
1. 下層規則不得違反上層規則。
2. 若需例外，必須在 `HANDOFF.md` 以 `[EXCEPTION]` 記錄原因、影響與預計恢復時間。
3. 未記錄的例外，視為違規。

---

## RULE 01 | 智慧傳承與脈絡管理 - Handoff Protocol

每次任務結束，都必須留下可直接接手的交接資訊。

### 標準格式

```markdown
## HANDOFF - [任務名稱]

### 本次完成事項
- ...

### 進行中 / 尚未完成
- ...

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| path/to/file | 說明 |

### 注意事項 / 已知風險
- ...

### 下一步建議
- ...

### 關鍵決策紀錄
- ...
```

### 簡化版

```markdown
## HANDOFF - [任務名稱]
完成：...
注意：...
下步：...
```

### 壓縮規定

- `HANDOFF.md` 不可無限堆疊歷史。
- 已解決卡點要刪除或摘要化。
- 建議控制在 100 行內。

---

## RULE 02 | 資源與成本回報 - Resource Accounting

任務完成時，最後必須回報：

```text
⏱️ 任務耗時：XX 分 XX 秒 | 🪙 Tokens (估算): IN XXk / OUT XXk | 💰 狀態: 成功/失敗/阻塞
```

補充規範：

- 若有子任務，分別計時後再加總。
- 若任務中途中斷再續行，需區分本次耗時與累計耗時。
- 長時間任務（> 30 分鐘）每 10 分鐘至少回報一次進度。

---

## RULE 03 | 環境隔離 - Local-First Execution

所有執行與依賴優先放在本專案內，禁止污染 global 環境。

### 強制規範

- Python 使用 `.venv` 或專案專用 conda env。
- Node.js 套件只做 local install，禁止未授權的 global install。
- `.env` 放在專案內，並提供 `.env.example`。
- 禁止修改 shell profile 或系統全域設定。
- 優先使用專案內的 scripts、config、workspace。

### 建議目錄

```text
project_root/
├── .venv/
├── node_modules/
├── .env
├── .env.example
├── HANDOFF.md
├── logs/
└── .gitignore
```

---

## RULE 04 | 版本快照 - State Snapshot

任何重要操作前，必須先建立可還原快照。

### 最低要求

- 記錄當前 `git HEAD`。
- 或輸出 patch 備份。
- 或備份關鍵檔案為 `.bak`。

### 破壞性操作前 Checklist

- [ ] 已建立備份或快照
- [ ] 已記錄 rollback 步驟
- [ ] 已評估影響範圍
- [ ] 已通知相關人員（若有）

---

## RULE 05 | 最小權限與機密保護 - Least Privilege & Secret Masking

嚴禁在任何 log、handoff、對話、報表中明碼輸出下列資訊：

- API key
- token
- password
- private key
- credentials

### 遮罩範例

| 類型 | 範例 |
|---|---|
| API Key | `sk-proj-****1234` |
| Token | `ghp_****xyz` |
| Password | `****` |
| Private Key | `-----BEGIN PRIVATE KEY----- [REDACTED] -----END PRIVATE KEY-----` |

### 建議加入 `.gitignore` 的項目

```text
.env
*.key
*.pem
id_rsa*
*.log
*.tmp
*.cache
credentials.json
secrets.yaml
```

---

## RULE 06 | 明確溝通 - Explicit Communication

不確定、假設、風險、阻塞，不得靜默跳過。

### 強制標籤

| 標籤 | 使用情境 |
|---|---|
| `[ASSUMPTION]` | 做了未經確認的假設 |
| `[RISK]` | 有潛在風險的操作或決策 |
| `[BLOCKED]` | 被阻塞，需要人類介入 |
| `[SKIP]` | 主動略過某項並說明原因 |
| `[TODO]` | 應完成但本次未完成 |
| `[EXCEPTION]` | 申請規則例外並說明理由 |

---

## RULE 07 | 冪等性 - Idempotency

腳本與任務設計必須可安全重複執行。

### 強制規範

- 建立檔案前先檢查是否已存在或內容是否相同。
- 批次任務要避免重複寫入。
- 可重跑不代表可以覆蓋歷史資料。
- 若外部系統支援，優先使用 idempotency key。

---

## RULE 08 | 日誌義務 - Logging Standard

重要操作必須留下可追蹤日誌。

### 格式

```text
[YYYY-MM-DD HH:MM:SS] [LEVEL] [MODULE] Message
```

### Log Level

| Level | 用途 |
|---|---|
| INFO | 正常執行流程 |
| WARN | 非預期但不中斷流程 |
| ERROR | 需要處理的錯誤 |
| DEBUG | 開發除錯用，正式環境預設關閉 |

### 保留原則

- 單一日誌檔案不超過 100MB。
- 開發環境可短期保留，正式環境需有輪替策略。
- 重要失敗必須能對應到任務、模組與時間點。

---

## RULE 09 | 防卡死與重試限制 - Infinite Loop Prevention

同一個錯誤或卡點，自動重試不得超過 3 次。

### 決策規則

1. 第 1 至 2 次失敗：可在有新資訊或修正條件下重試。
2. 第 3 次失敗：必須標記 `[BLOCKED]`，停止該子任務。
3. 保留錯誤現場與必要 log，等待人類或上層 Agent 處理。

---

## RULE 10 | 自我驗證義務 - Self-Validation Requirement

未經驗證，不得宣稱完成。

### 基本驗證順序

1. 編譯或建置成功
2. Lint / 語法檢查通過
3. 單元測試通過
4. 整合測試通過（若有）
5. 手動驗證關鍵流程

### 變更類型對應驗證

| 變更類型 | 必要驗證 |
|---|---|
| UI | 視覺檢查、互動流程、響應式檢查 |
| API | 端點測試、錯誤處理、文件同步 |
| 資料庫 | 資料完整性、rollback、效能影響 |
| 設定 | 語法檢查、影響範圍確認 |
| 相依性更新 | 建置成功、相關測試通過 |

---

## RULE 11 | 資料流優先繼承 - Data Pipeline Reuse First

若專案已有既有資料流或資料工程基底，必須先檢查能否重用。

### 本專案硬規則

若使用者已指定資料流路徑，例如：

```text
C:\Users\User\Documents\data_pipeline
```

則必須先：

1. 掃描該路徑。
2. 找出可重用模組。
3. 優先複製必要元件到本專案內。

### 禁止事項

- 未檢查就假設資料格式。
- 繞過既有資料讀取邏輯重寫一套。
- 直接修改原始 `data_pipeline`，除非任務明確要求。

---

## RULE 12 | PostgreSQL 歷史資料保護 - History Must Not Be Overwritten

凡屬歷史結果、策略紀錄、投組快照、訊號快照之資料表，不得默默覆蓋舊資料。

### 強制規範

- 優先使用 `INSERT ... ON CONFLICT DO NOTHING`。
- 禁止 `ON CONFLICT DO UPDATE` 直接覆寫歷史結果。

### 若需修正舊資料，只能二選一

1. 使用新的 `strategy_name` 或版本名稱重新寫入。
2. 人工明確 `DELETE` 後，再重新 `INSERT`。

---

## RULE 13 | 先做最小可行版 - MVP First

禁止一開始就過度複雜化。

### 建議順序

1. 先讓資料能正確讀進來。
2. 先讓回測主流程能跑完。
3. 先產出第一版結果。
4. 再做參數掃描、風控擴充、報表美化。

---

## RULE 14 | 結果真實性優先 - No Cosmetic Research

研究結果必須誠實呈現，不得為了好看而調整敘事。

### 強制規範

- 若策略結果差，就直接說差。
- 若 turnover 太高，就直接說不可交易。
- 若 funding 或成本吃光 edge，就直接說沒有研究價值。

### 禁止事項

- 偷改 universe 美化結果。
- 選擇性只展示好看的參數。
- 忽略成本。
- 隱藏失敗實驗。

---

## Agent 任務完成 Checklist

- [ ] 已更新 `HANDOFF.md`
- [ ] 已回報耗時與資源估算
- [ ] 未污染 global 環境
- [ ] 已建立快照或可回滾方案
- [ ] 無機密外洩
- [ ] 風險與假設已標示
- [ ] 任務可重跑
- [ ] 已留下必要日誌
- [ ] 未超限重試
- [ ] 已完成自我驗證
- [ ] 已檢查既有 data pipeline 是否可重用
- [ ] PostgreSQL 歷史表未被覆蓋
- [ ] 已誠實揭露策略真實表現

---

## 版本紀錄

| 版本 | 日期 | 變更說明 |
|---|---|---|
| v1.0.0 | 2026-04-14 | 初始版本，建立核心規則 |
| v1.1.0 | 2026-04-14 | 新增資源回報、防卡死、自我驗證、強化交接與機密保護 |
| v1.2.0 | 2026-04-15 | 新增規則優先級、例外處理、協作與持續改進內容 |
| v1.2.1 | 2026-04-16 | 修正繁簡混用、錯字與重複條目 |
| v1.3.0 | 2026-04-17 | 新增 data pipeline reuse、歷史資料保護、MVP first、結果真實性優先 |
| v1.3.1 | 2026-04-17 | 整併 v1.2.1 與 v1.3.0，移除重複內容，修正 Markdown 結構與用詞一致性 |

---

本文件由 **作者** 定義，適用於 AI_Team 所有子專案。
