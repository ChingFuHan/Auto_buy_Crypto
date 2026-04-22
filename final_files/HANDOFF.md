## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

### 本次完成事項
- 補齊 Telegram bot 通知模組 `pump_system/notify/telegram_notifier.py`
- 新增 `FUNCTION_TEST_MODE` / `FUNCTION_TEST_SYMBOL`，允許只對 `BTCUSDT` 做首次正式盤 execution function test
- 把 function test symbol 納入 execution evaluation set，不受大幣排除清單限制
- 補齊正式盤必要觀測性：startup / mode summary / signal / entry / stop / fallback / websocket / server time / DB write / API retry 通知
- 更新 `.env.example`、`README.md`、`HANDOFF.md`
- 新增 `test_symbol_registry.py`、`test_telegram_notifier.py`

### 進行中 / 尚未完成
- [TODO] 尚未使用真實 Binance API / PostgreSQL / Telegram 憑證做端到端整合測試
- [TODO] `FUNCTION_TEST_MODE` 目前是 execution gating，不會主動強制產生 BTCUSDT 訊號；若要加快驗證，可暫時放寬 `SIGNAL_*` 參數

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `config.py` | 新增 function test mode 與 Telegram 設定 |
| `pump_system/notify/telegram_notifier.py` | 統一 Telegram 通知介面與 queue worker |
| `pump_system/exchange/binance_client.py` | API retry / blocked / server time 異常通知 |
| `pump_system/execution/order_service.py` | function test gating、entry/stop 通知、skip 通知 |
| `pump_system/fallback_stop/manager.py` | fallback 啟動/觸發/平倉通知 |
| `pump_system/app.py` | startup/shutdown/mode summary/DB write 觀測性 |
| `pump_system/exchange/symbol_registry.py` | 讓 function test symbol 可被評估 |
| `README.md` | 正式盤上線、Telegram、BTCUSDT function test 流程 |

### 注意事項 / 已知風險
- [RISK] 尚未做真實 Telegram chat id / bot token 實測
- [RISK] 正式盤 first live test 若 BTCUSDT 遲遲不出現訊號，不會自動送測試單；需放寬訊號參數或等待條件成立
- [RISK] fallback close 若連續 3 次失敗，會標記 `BLOCKED` 並持續以 Telegram 回報，需人工接手
- [ASSUMPTION] function test mode 的「完整架構運行」定義為：資料抓取、DB、訊號、風控檢查、通知完整保留，但非 `FUNCTION_TEST_SYMBOL` 不送真單

### 下一步建議
- 先填 `.env` 的 Telegram / Binance / PostgreSQL
- 跑 `main.py validate`
- 跑 `main.py backfill`
- 用 Testnet 驗證 BTCUSDT function test flow
- 再切正式盤小額驗證

### 關鍵決策紀錄
- 3m 正式資料來源維持 Binance 原生 3m，不改成本地聚合
- DB 僅存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`
- `db_util.py` 仍直接重用 pool / env naming / fetch helpers；bulk insert 仍由 repository adapter 補齊
- function test mode 不依賴 `SYMBOL_WHITELIST`，而是由 `SymbolRegistry.should_evaluate()` 額外納入 `FUNCTION_TEST_SYMBOL`
- Telegram 採 queue worker，避免通知失敗拖垮交易主流程
- [EXCEPTION] 依使用者要求採一次性交付完整專案，未走分階段 MVP；其餘 `god_rule.md` 規則維持遵守。預計恢復時間：下一輪功能擴充時回到迭代式交付

### 驗證紀錄
- `.\.venv\Scripts\python -m compileall .`
- `.\.venv\Scripts\python -m pytest -q`

### 資源回報
- ⏱️ 任務耗時：29 分 12 秒 | Tokens (估算): IN 31k / OUT 24k | 狀態: 成功
