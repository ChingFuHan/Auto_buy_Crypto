## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM 熱區

更新時間：2026-05-08 05:49 +08:00
整理快照：`git HEAD=d7a8c0e`

### 本次完成事項
- 2026-05-08（本輪）：依使用者要求實作第 1 層 `Signal Decision Audit`，用 append-only JSONL 保留每次已評估候選 symbol 的訊號判斷快照。新增 `pump_system/audit/signal_decision_audit.py` 與 `pump_system/audit/__init__.py`；`TradingApplication` 建立 `SignalDecisionAuditWriter`；`OrderService._evaluate_symbol()` 每次 `SignalEngine.evaluate()` 後寫入 `SIGNAL_DECISION`，即使 `triggered=False` 也會保存。另記錄幾個後續 order gate：duplicate bar、已有倉、達持倉上限、symbol info 缺失、order type 缺失、private API unavailable、min legal order、function test 擋單、live disabled simulated、server time unhealthy、margin/leverage/entry failure、entry success。輸出路徑：`data/audit/signal_decisions/signal_decisions_<interval>_<YYYYMMDD>.jsonl`。
- 2026-05-08（本輪）：釐清第 2 層設計風險：若只記 near-miss，確實可能漏掉 `DOGSUSDT` 這類「有被評估但離門檻很遠」的 symbol；若只記 candidate，則 `DOGSUSDT` 在目前設定下會被記到，但未來若被 blacklist / whitelist / excluded 或 universe 異常排除，仍會缺席。建議第 2 層至少記「所有已評估 candidate 的 in-progress update」，near-miss 只作額外標記或延長保留，不作唯一資料來源。
- 2026-05-08（本輪）：依使用者要求巡查 `JTOUSDT` / `DOGSUSDT` 目前無倉位原因。唯讀查 `god_rule.md`、`README.md`、`HANDOFF.md`、`logs/app.log*`、`data/inprogress_15m.csv`、`config.py` 與訊號/下單流程。結論：兩者都有進入 15m 候選池並被評估，未在黑名單/白名單排除，也非 function test 擋單；但 live log 於 03:48 +08 顯示兩者皆 `triggered=False`，原因共同包含 `15m_not_compressed,15m_volume_too_low,15m_push_too_small,15m_not_breakout,already_extended`，因此流程在訊號層返回，沒有進入 `SIGNAL_TRIGGERED` / 持倉刷新 / 下單流程。
- 2026-05-07（本輪）：`SERVER_TIME_OFFSET_BLOCKED` 常態發生根因分析與修復。兩個 commit：1) `f789af4`（Claude Haiku）：`config.py` 預設 `SERVER_TIME_RESYNC_INTERVAL_SECONDS` 300s→60s；`ensure_time_sync()` 加入 `approaching_threshold`（80% 閾值觸發預先 sync）、`consecutive_sync_failures` 連續失敗計數與 try/except 保護。2) `d7a8c0e`（本輪 Copilot）：`_request` retry handler 在 `ensure_time_sync` 後正確重新產生 `timestamp` + `signature`（pop 舊 sig → 重算 timestamp with fresh offset → 重簽）；移除 `BINANCE_API_RETRY` Telegram 通知（降噪，與 HANDOFF 記載對齊）。測試結果：`41 passed, 1 xfailed`。
- 2026-05-07（本輪）：確認 OS 層修復（chrony）需要 sudo 密碼，**已提供指令但未執行**，待使用者手動完成：`sudo apt install chrony && sudo systemctl enable --now chrony && chronyc tracking`。
- 2026-05-07：完成並驗證兩個 live-safe 修復。1) `pump_system/exchange/binance_client.py`：signed request 會在**每次 retry 前重新產生** `timestamp` / `signature`；遇到 Binance `code=-1021` 會先 `ensure_time_sync(force=True)` 後再以短延遲重試；中間態 `BINANCE_API_RETRY` 不再送 Telegram，只保留 final blocked/error 類事件。2) `pump_system/notify/telegram_notifier.py`：加入全域節流（最小發送間隔、每分鐘上限）、Telegram 429 `retry_after` flood-wait、低優先級訊息丟棄、同 symbol 同 bar 的 `SIGNAL_TRIGGERED` 去重，以及 flood-wait 結束後自動補送 deferred 高優先級事件。另在 `pump_system/execution/order_service.py` 的 `SIGNAL_TRIGGERED` 詳情新增 `bar_key`，讓 notifier 去重真正生效。新增/更新測試：`tests/test_binance_client.py`、`tests/test_telegram_notifier.py`、`tests/test_order_service_signal_notifications.py`；`python3 -m pytest -q` 結果為 `41 passed, 1 xfailed`。
- 2026-05-07：依使用者要求驗證 Claude 已處理的 VM 時間同步問題。`timedatectl status` 顯示 `System clock synchronized: yes`、`NTP service: active`；`systemd-timesyncd` 於 00:17:30 +08 重啟，00:18:01 +08 已聯到 `ntp.ubuntu.com` 完成 initial clock synchronization。執行 `python3 time_sync_diagnostic.py --repeat 3`，Binance offset 三次為 `+236 ms / +70 ms / +52 ms`，平均 `+119 ms`，低於 `threshold_ms=5000`；結論：VM / Binance server time offset 已恢復正常範圍。
- 2026-05-07：解析使用者貼上的 live Telegram 訊息。結論：`HOMEUSDT` 15m 訊號條件通過並重複送出 `SIGNAL_TRIGGERED`，但 private/signed Binance 流程因 `SERVER_TIME_OFFSET_BLOCKED` 被擋；`offset_ms=-13776` 超過 `threshold_ms=5000`，後續 `position_state.refresh_symbol()` / signed request 丟出 `timestamp_unhealthy`，形成 `SYMBOL_EVALUATION_BLOCKED`。貼文片段未出現 `ENTRY_ORDER_SUCCESS` 或 `STOP_ORDER_SUCCESS`，因此不能判定有下單成功。
- 2026-05-04：依 `god_rule.md` RULE 01 將過長的 `HANDOFF.md` 瘦身為熱區版本。
- 整理前 `HANDOFF.md` 完整原文已先附加到 `HANDOFF_ARCHIVE.md` 末尾；原始行數 822，SHA256 已記錄於 archive 搬遷段。
- 2026-05-04 那輪只修改 `HANDOFF.md` 與 `HANDOFF_ARCHIVE.md`；未改程式碼、未改 `.env`、未跑測試、未連 API、未查帳戶、未查/寫 DB。

### 進行中 / 尚未完成
- [TODO] 上述 notifier / Binance retry 修復目前只在程式碼與測試中完成；若要進入 live process，仍需由使用者明確授權後重啟載入新程式，不能沿用舊進程視為已生效。
- [TODO] 使用者表示不需補單，會自行重啟 bot；重啟後只需觀察 Telegram 是否不再出現 `SERVER_TIME_OFFSET_BLOCKED` / `timestamp_unhealthy`，並確認後續 trade 事件是否正常。
- [TODO] 若要讓 2026-05-02 的槓桿 `-4424` fallback 修正進入 live process，必須先取得明確授權並確認目前是否已有 live bot 在跑；不可自行重啟或開第二個 `main.py run`。
- [TODO] `tests/test_algo_fill_regression.py::test_reconcile_triggered_via_algo_history_fallback` 仍是 P1 未完項；若要處理，需釐清 Binance historical algo endpoint，再在 `BinanceClient` / `OrderService` 接入。
- [TODO] Aggressive / Bucket C 研究目前只能進 shadow / prototype signal spec 設計審查；不可直接部署到主交易邏輯。
- [TODO] `SIGNAL_15M_*` 雖已獨立，但仍需持續觀察與回測校準；不可因單一 near-miss 直接放寬正式盤主策略門檻。

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `HANDOFF.md` | 熱區：目前狀態、風險、下一步 |
| `HANDOFF_ARCHIVE.md` | 冷區：完整歷史紀錄，只增不減 |
| `README.md` | 主線規格、runbook、資料流與風險說明 |
| `config.py` | `.env` 載入、`STRATEGY_INTERVAL`、訊號/止損/下單設定 |
| `main.py` | CLI 入口：`validate` / `backfill` / `run` |
| `pump_system/app.py` | 主流程組裝、背景任務、WebSocket / DB / execution 串接 |
| `pump_system/audit/signal_decision_audit.py` | append-only 訊號決策 audit JSONL writer |
| `pump_system/strategy/signal_engine.py` | 主策略訊號條件與 fail reasons |
| `pump_system/execution/order_service.py` | 下單、槓桿設定、native stop、fallback 觸發入口 |
| `pump_system/notify/telegram_notifier.py` | Telegram flood-wait / 節流 / 高低優先級 / signal 去重 |
| `pump_system/execution/sizing.py` | quantity / notional / leverage sizing |
| `pump_system/exchange/binance_client.py` | Binance public/private wrapper；P1 algo history 會動到這裡 |
| `tests/test_telegram_notifier.py` | notifier flood-wait / 去重測試 |
| `tests/test_binance_client.py` | signed retry 重簽 / -1021 測試 |
| `tests/test_order_service_signal_notifications.py` | `SIGNAL_TRIGGERED` 是否附帶 `bar_key` 測試 |
| `pump_system/db/repository.py` | finalized K 線 DB 寫入/讀取；歷史資料不可覆蓋 |
| `reports/aggressive_backtest_audit_20260430.py` | aggressive audit / live-safe audit 腳本 |
| `reports/aggressive_backtest_audit_live_safe_20260502.md` | 修正版 live-safe audit 報告 |
| `reports/aggressive_backtest_live_safe_stability_20260502.md` | Bucket C 穩健性補充報告 |

### 注意事項 / 已知風險
- [RISK] `SignalDecisionAuditWriter` 會對每次已評估 candidate 訊號判斷寫一行 JSONL，能解決事後缺 in-progress 決策快照的問題，但會增加本地磁碟 I/O 與 `data/audit/signal_decisions/` 檔案量；目前未做 retention / compression。若 live 後檔案增長過快，下一步應加輪替、壓縮或保留天數設定。
- [RISK] 第 2 層若只做 near-miss symbols 會漏掉非 near-miss 的 DOGS 類案例；不建議 near-miss 作唯一記錄範圍。
- [RISK] 2026-05-08 JTO/DOGS 巡查未連 private/account/order API、未查帳戶、未查/寫 DB；「無倉位原因」是基於本地 live log 與流程碼判讀：系統未產生 JTO/DOGS 入場訊號，因此未嘗試開倉。
- [RISK] `SIGNAL_TRIGGERED` 仍在 `position_state.refresh_symbol()` 之前送出；雖然 notifier 現已用 `bar_key` 去重同 symbol 同 bar 的重複 Telegram，但若 live process 尚未重啟載入新版程式，舊進程仍可能重複推播。
- [RISK] `TIME_SYNC_TROUBLESHOOT.md` 對 offset 正負號的文字說明疑似與程式實作不一致；程式實作為 `server_time - local_midpoint`，因此 `offset_ms=-13776` 代表本機 midpoint 約快於 Binance server 13.776 秒。未經使用者要求，本輪不修改文件。
- [RISK] 本專案是交易系統；未經明確要求，不可修改交易邏輯、切換 live/testnet、建立憑證、修改 `.env`、連交易所帳戶/API、查帳戶或寫 DB。
- [RISK] `HANDOFF_ARCHIVE.md` 是永久冷區，只可附加不可刪改；若未來再瘦身，仍需先完整附加原文再移除熱區段落。
- [RISK] 2026-05-02 記錄顯示 live process 可能尚未載入 `-4424` fallback 整合 commit；下次處理 live 前必須重新確認，不可沿用舊 PID 當現況事實。
- [RISK] 目前主線方向不是把正式策略從 15m 改回 3m；3m 在 aggressive audit 中主要是 Layer 2 重建粒度。
- [RISK] Aggressive 回測修正後 Bucket C conservative 仍有正 expectancy，但 96bar median 為負，且 2026-04 stop 行為惡化；只可作研究/設計輸入，不可直接部署。
- [RISK] `return_pct_min` 曾於 2026-04-29 調到 `0.017`；若任務依賴實際執行門檻，需讀當前程式與 `.env`（不可輸出 secrets）重新確認。
- [SKIP] 本次 handoff 整理與資料流重用、PostgreSQL 寫入保護、策略績效驗證無直接關係；本輪沒有碰資料流、DB 或交易邏輯。

### 下一步建議
1. 若要讓本輪修復進入 live，先確認目前是否已有 `main.py run` 進程，再由使用者明確授權後重啟載入新版程式；本輪未代替使用者重啟。
2. 重啟後優先觀察 Telegram 是否不再長時間 429、`SIGNAL_TRIGGERED` 是否不再同 bar 連發、以及 `code=-1021` 是否消失或顯著下降。
3. 若下一個任務是 P1 algo history fallback，先只讀核對 Binance endpoint 與現有 xfail 測試，再做最小改動與測試。
4. 若下一個任務是 aggressive 分支，先做 shadow signal spec / 紙上交易設計，不要改主交易流程。
5. 若只是查歷史脈絡，優先在 `HANDOFF_ARCHIVE.md` 查 2026-05-04 搬遷段；不要把 `HANDOFF.md` 再膨脹成完整歷史。

### 關鍵決策紀錄
- 2026-05-07：依使用者授權繼續處理「5 / 6」兩個工程修復，範圍限定為 notifier 降噪/429 處理與 Binance signed retry 重簽；不改 `.env`、不重啟 live bot、不碰交易策略。
- 2026-05-07：VM 時間同步問題已驗證修復；使用者明確表示「不用補單，我自行重啟 bot」。後續不可代替使用者補單或重啟，除非取得新的明確授權。
- 2026-05-07 live Telegram 解析採程式實作為準：`SERVER_TIME_OFFSET_BLOCKED` 是 signed request 前的安全擋板；看到 `SIGNAL_TRIGGERED` 不等於已送單，需以 `ENTRY_ORDER_SUCCESS` / `STOP_ORDER_SUCCESS` 等 trade 事件判斷下單與止損是否成功。
- `god_rule.md v1.5.0` 優先於所有下位文件；有衝突時先列衝突，再以 `god_rule.md` 為準。
- `HANDOFF.md` 保持熱區；完整歷史保存在 `HANDOFF_ARCHIVE.md`。
- 正式主線支援 `STRATEGY_INTERVAL=3m|15m`，目前 README/交接脈絡以 15m 為主；切換需重啟且不得自行改 `.env`。
- finalized bars 才寫 PostgreSQL；in-progress bars 留 staging / `data/inprogress_<STRATEGY_INTERVAL>.csv`。
- 原生止損正式路徑固定為 Binance `/fapi/v1/algoOrder` 的 `STOP_MARKET`；fallback stop 只在 native stop 失敗後監控並市價平倉，不是重新掛 stop。
- Function test mode 開啟時，只有 `FUNCTION_TEST_SYMBOL` 可真實下單；其他 symbol 只評估與通知。
- DAMUSDT / SOLVUSDT 等歷史案例目前屬策略取捨與回測研究脈絡，不是已確認的候選池漏單 bug。

### 資源回報
- 2026-05-08 本輪類型：Signal Decision Audit 實作、測試與 handoff 更新。
- 2026-05-08 驗證方式：`python3 -m py_compile pump_system/audit/signal_decision_audit.py pump_system/app.py pump_system/execution/order_service.py tests/test_signal_decision_audit.py tests/test_order_service_signal_notifications.py`；`python3 -m pytest -q tests/test_signal_decision_audit.py tests/test_order_service_signal_notifications.py`；`python3 -m pytest -q tests/test_order_service_stop.py tests/test_signal_decision_audit.py tests/test_order_service_signal_notifications.py`；`python3 -m pytest -q` 結果 `43 passed, 1 xfailed`。未改 `.env`、未重啟 bot、未連 private/account/order API、未查帳戶、未查/寫 DB、未改訊號門檻或下單判斷。
- 2026-05-08 本輪類型：`JTOUSDT` / `DOGSUSDT` 無倉位原因巡查與 handoff 更新。
- 2026-05-08 驗證方式：讀 `god_rule.md`、`README.md`、`HANDOFF.md`；查 `logs/app.log*`、`data/inprogress_15m.csv`、`config.py`、`pump_system/execution/order_service.py`、`pump_system/strategy/signal_engine.py`、`pump_system/exchange/symbol_registry.py`；用 `python3` 只輸出非機密設定。未改 `.env`、未重啟 bot、未連 private/account/order API、未查帳戶、未查/寫 DB、未改交易邏輯。
- 2026-05-07 本輪類型：Telegram flood-wait / Binance retry 工程修復、測試與 handoff 更新。
- 2026-05-07 驗證方式：`python3 -m pytest -q tests/test_telegram_notifier.py tests/test_binance_client.py tests/test_order_service_signal_notifications.py tests/test_order_service_stop.py` 與 `python3 -m pytest -q`；未改 `.env`、未重啟 bot、未連 private/account/order API、未查帳戶、未查/寫 DB。
- 2026-05-07 本輪類型：VM / Binance time offset 驗證與 handoff 更新。
- 2026-05-07 驗證方式：`timedatectl status`、`systemctl status systemd-timesyncd`、`python3 time_sync_diagnostic.py --repeat 3`；未改程式碼、未改 `.env`、未重啟 bot、未查帳戶、未查/寫 DB。
- 2026-05-07 本輪類型：live Telegram 訊息解析 / 程式碼唯讀核對 / handoff 更新。
- 2026-05-07 驗證方式：讀 `god_rule.md`、`README.md`、`HANDOFF.md` 與最小相關程式碼；未跑測試、未連 API、未查帳戶、未查/寫 DB；只修改 `HANDOFF.md`。
- 本輪類型：文件整理 / handoff 歸檔。
- 驗證方式：唯讀檢查行數、archive marker / hash、檔案差異；未跑測試。
