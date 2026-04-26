## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-27

## 本輪 (2026-04-27) - 進度查詢與 3m-only 改造

- 2026-04-27 03:06 +08:00：依使用者要求查看最新進度；僅讀取 `god_rule.md`、`HANDOFF.md`、`README.md`，未跑測試、未連 Binance、未查 DB、未修改交易邏輯或 `.env`。
- 2026-04-27 本輪補充：使用者貼上另一個 review session 的 A/B/D 選項並要求解釋；本輪讀取 `god_rule.md`、`README.md`、`HANDOFF.md`，並因 B 涉及 `final_files` 補讀 `final_file.md`；僅說明含義與風險，不修改交易邏輯、不跑測試、不連 Binance、不查 DB、不改 `.env`。
- 2026-04-27 本輪策略討論：[TENTATIVE] 使用者表示下一階段先改用 `3m` WebSocket 監控全 USDT 合約以降低複雜度、先求功能上線；本輪僅討論疑慮與策略使用方式，未修改交易程式、未跑測試、未連 Binance、未查 DB、不改 `.env`。
- 2026-04-27 本輪明確決策：使用者要求強制改為 `3m-only`；止損 low 來源同步改為當前 in-progress `3m` low；REST 429 retry 問題先不動、實盤觀察；接受 3m 追高較慢但較穩。
- 2026-04-27 本輪完成：已將正式主線改為 `3m-only`，包含 WebSocket 訂閱、backfill/catch-up、rolling staging、SignalEngine、OrderService manual/evaluation、fallback contract trigger、README 與 `tests/test_signal_engine.py`；未修改 `.env`、未連 Binance、未查/寫 DB、未動 REST 429 retry。
- 驗證：`python3 -m pytest -q` -> `18 passed, 1 xfailed`；`python3 -m compileall config.py main.py pump_system tests` -> pass。Linux 下 `.venv/Scripts/python.exe` 是 Windows PE，無法執行，故用系統 `python3` 做本地驗證。
- 2026-04-27 使用者要求提供 Windows 驗證指令與實盤親自驗證操作手冊；Agent 僅提供指令，不執行、不修改 `.env`、不連 Binance、不查/寫 DB。
- 2026-04-27 使用者回報 Windows PowerShell 驗證：`.venv\Scripts\python.exe --version` -> Python 3.11.9；`compileall` pass；`pytest -q` -> `18 passed, 1 xfailed`；`kline_1m` / `current_1m|finalized_1m|1m_` / `get_klines(symbol, "1m"` 搜尋皆無輸出，`kline_3m` 有輸出，確認 3m-only 主線已落地。
- 2026-04-27 使用者回報正式盤 dry-run：`.env` 為 `TESTNET=false`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`、`FUNCTION_TEST_SYMBOL=BTCUSDT`；`main.py validate` 成功，載入 `data_symbols=535`、`candidate_symbols=528`、seeded rolling history `3m=47610`。`main.py backfill` 開始寫入 3m 增量，多數 symbol inserted=49；途中遇 Binance `/fapi/v1/klines` 429，既有邏輯進入 60 秒等待，尚未判定為失敗。
- 2026-04-27 使用者詢問 `STOP_WORKING_TYPE`、`TARGET_NOTIONAL_USDT`、`MAX_CONCURRENT_POSITIONS`、`STARTUP_BACKFILL_ENABLED` 建議值；Agent 僅提供建議，不修改 `.env`、不執行實盤、不連 Binance。
- [RISK] `god_rule.md` 要求任務完成時更新 `HANDOFF.md`；本專案「查詢進度」段落要求不要修改檔案。此處依上位規則做最小追加，僅保存查詢紀錄。
- 2026-04-27 03:06 +08:00 後續解釋 P1 步驟時，最小範圍讀取 `tests/test_algo_fill_regression.py`、`pump_system/exchange/binance_client.py`、`pump_system/execution/order_service.py`。
- [RISK] `tests/test_algo_fill_regression.py` 的 xfail reason 寫 `GET /fapi/v1/algoOrders`，但 Binance 官方 USDⓈ-M Futures 文件目前列的是 `GET /fapi/v1/algoOrder`（單筆）與 `GET /fapi/v1/allAlgoOrders`（全部）；另有 Algo Trading 產品文件的 `GET /sapi/v1/algo/futures/historicalOrders`，屬不同文件線。P1 實作前必須釐清正式 endpoint 與 response 欄位，不可盲貼測試註解。

## 本輪補充 (2026-04-26 交接 commit)

### 本輪確認
- 使用者已確認「近120資料已補齊」。
- 當前共識下一步：先維持基線驗證，再進入 P1 `algo history fallback` 實作。

### 下一步執行順序（鎖定）
1. 跑 `tests/test_algo_fill_regression.py` 確認基線。
2. 實作 `BinanceClient.get_historical_algo_orders()`。
3. 在 `order_service` native stop reconcile 接入 history fallback。
4. 將 `test_reconcile_triggered_via_algo_history_fallback` 從 `xfail` 推進為 pass。

### 範圍約束
- 本 commit 僅交接紀錄，不修改交易邏輯、`.env`、Binance 帳戶/API、DB 歷史資料表。

### 一句話現況
- 原生止損正式路徑已改為 `/fapi/v1/algoOrder`，2026-04-25 BNBUSDT controlled stop test 已確認 `STOP_ORDER_TRIGGERED`。
- PostgreSQL finalized / in-progress 分流已完成驗證；目前最主要未完項是 algo history fallback。
- 2026-04-26 已完成 `HANDOFF.md` 熱區整理，完整舊內容已搬到 `HANDOFF_ARCHIVE.md`。

### 本次完成事項
- 建立 `HANDOFF_ARCHIVE.md`，完整保存整理前的 `HANDOFF.md` 全文。
- 將 `HANDOFF.md` 重寫為熱區摘要，移除重複段落與過期 metadata。
- 建立整理前快照：`/home/xiaohan/.copilot/session-state/98e3f459-54f5-4a55-a214-f6ba0bb9ca08/files/handoff-backups/HANDOFF.pre-archive.20260426-0500.md`

### 進行中 / 尚未完成
- [TODO] `tests/test_algo_fill_regression.py::test_reconcile_triggered_via_algo_history_fallback` 仍為 `xfail`。
- [TODO] 若實作 P1，需在 `pump_system/exchange/binance_client.py` 新增 `get_historical_algo_orders()`，並在 `pump_system/execution/order_service.py` 的 native stop reconcile 補上 algo history fallback。
- [SKIP] P2 open orders 統一接口屬未來防禦；目前 `PositionState.refresh()` 已正確同時查一般 open orders 與 algo open orders，不是當前 bug。

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `HANDOFF_ARCHIVE.md` | 2026-04-26 前完整交接歷史；整理前全文已封存 |
| `tests/test_algo_fill_regression.py` | algo fill fallback 的 xfail 測試與目標行為 |
| `pump_system/exchange/binance_client.py` | algo order 相關 API wrapper；P1 需補 historical algo query |
| `pump_system/execution/order_service.py` | native stop reconcile 與 `STOP_ORDER_TRIGGERED` 判定 |
| `pump_system/state/position_state.py` | 目前已正確同時查一般 open orders + algo open orders |
| `README.md` | 專案規格與 stop / data flow / Telegram / runbook 說明 |

### 注意事項 / 已知風險
- [RISK] 若 Binance child order 的 `clientOrderId` 不再對齊原始 `clientAlgoId`，目前流程會降級成 `STOP_ORDER_POSITION_CLOSED`；P1 即是針對此情境補強。
- [RISK] `BinanceClient.get_open_orders()` 目前不支援 `symbol` 參數；若之後做 P2，不可直接照舊 handoff 範例貼上。
- [SKIP] 本輪只整理文件與交接，未碰交易邏輯、`.env`、Binance/API、DB。

### 最近已確認基線
- 2026-04-25：`python -m pytest -q` -> `18 passed, 1 xfailed`
- 2026-04-25：BNBUSDT controlled stop test 成功，`MARKET BUY -> /fapi/v1/algoOrder STOP_MARKET -> native stop filled`
- 2026-04-25：PostgreSQL E2E 確認 in-progress 只留 CSV、finalized 1m/3m 才進 DB
- 2026-04-26：靜態核對確認 `PositionState.refresh()` 已同時查一般單與 algo 單，P2 不是當前 bug

### 下一步建議
1. 優先實作 P1 algo history fallback，移除 `xfail`，讓 stop fill 在 child order `clientOrderId` 改變時仍可準確確認。
2. 若要做 P2，先修正 `get_open_orders(symbol=...)` 設計，再補 README 的 unified open-orders 指引。
3. 繼續保留 `/fapi/v1/algoOrder` 與既有 `STOP_ORDER_TRIGGERED` Telegram 行為，不要回退舊路徑。

### 關鍵決策紀錄
- 原生 stop 的正式實作固定走 Binance `/fapi/v1/algoOrder`，不再回退 `/fapi/v1/order`。
- DB 僅保存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`。
- function test mode 仍只允許 `FUNCTION_TEST_SYMBOL` 真實下單，其餘 symbol 只做評估與通知。
- `HANDOFF_ARCHIVE.md` 現在是完整歷史冷區；`HANDOFF.md` 僅保留最新熱區摘要。

### 資源回報
- ⏱️ 任務耗時：估算 20 分鐘（文件整理 / 歸檔 / 熱區重寫）
- 🪙 Tokens (估算)：平台未提供
- 💰 狀態：成功

---

## 本輪 (2026-04-26) - Handoff 歸檔嚴格確認

### 確認結論
- 已靜態核對 `HANDOFF.md` / `HANDOFF_ARCHIVE.md` / pre-archive 快照 / P1 相關程式與測試；未跑 pytest、未連 Binance、未查 DB、未改交易邏輯與 `.env`。
- `HANDOFF.md` 追加本段前 55 行，追加後仍低於 100 行，符合熱區摘要用途；`HANDOFF_ARCHIVE.md` 目前 495 行，已建立且包含舊 handoff 主要內容。
- [RISK] `HANDOFF_ARCHIVE.md` 並非整理前快照的 byte-for-byte 原文附加：與 pre-archive 快照相比，多了幾個 Markdown code fence / whitespace 格式調整，舊內容語意大致保留，但嚴格來說不應描述為「完全原樣封存」。
- P1 狀態仍正確：`get_historical_algo_orders()` 尚未在 `BinanceClient` 實作，`test_reconcile_triggered_via_algo_history_fallback` 仍為 strict xfail。
- P2 判斷仍正確：目前 `PositionState.refresh()` 已同時查一般 open orders 與 algo open orders；`BinanceClient.get_open_orders()` 仍不支援 `symbol` 參數。

## 本輪 (2026-04-27) - Handoff 遇到爆 context
 [2026-04-27 04:37:57,282] [INFO] [execution.order] signal check symbol=THETAUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001728839211999714523754587942', 'range_3m_pct': '0.008442776735459662288930581614', 'vol_ratio_3m': '0.4344012084232175088401994986', 'ret_3m_pct': '-0.0004655493482309124767225325885',
  'prior_runup_3m_pct': '0.003266448903406439570695286981', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,318] [INFO] [app] staging updated symbol=SOONUSDT interval=3m
  [2026-04-27 04:37:57,319] [INFO] [execution.order] signal check symbol=SOONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.0052504219845369976174380235', 'range_3m_pct': '0.03345925526173772261198057205', 'vol_ratio_3m': '0.3205692224015407523650727132', 'ret_3m_pct': '-0.003727369542066027689030883919',
  'prior_runup_3m_pct': '0.01173333333333333333333333333', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,339] [INFO] [app] staging updated symbol=SPKUSDT interval=3m
  [2026-04-27 04:37:57,339] [INFO] [execution.order] signal check symbol=SPKUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.003124468830951487391091801051', 'range_3m_pct': '0.01352785145888594164456233422', 'vol_ratio_3m': '0.2985705522553241923420039816', 'ret_3m_pct': '-0.0007936507936507936507936507937',
  'prior_runup_3m_pct': '0.008474576271186440677966101695', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,352] [INFO] [app] staging updated symbol=SLPUSDT interval=3m
  [2026-04-27 04:37:57,352] [INFO] [execution.order] signal check symbol=SLPUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002937875020769375763324694189', 'range_3m_pct': '0.01937282229965156794425087108', 'vol_ratio_3m': '0.1207931955828651561712371627', 'ret_3m_pct': '-0.0006912760956726116410894511268',
  'prior_runup_3m_pct': '0.005281445448227936066712995136', 'recent_green_3m_bars': '2', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,352] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,352] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8003460257139032474727799845', 'ret_3m_pct':
  '0.004159387738124948007653273438', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,481] [INFO] [app] staging updated symbol=USUSDT interval=3m
  [2026-04-27 04:37:57,482] [INFO] [execution.order] signal check symbol=USUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002466212044035474542269447318', 'range_3m_pct': '0.01371774006045105789351313648', 'vol_ratio_3m': '0.3495803888069167249100463358', 'ret_3m_pct': '-0.001613646841862609497464269249',
  'prior_runup_3m_pct': '0.004847645429362880886426592798', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,538] [INFO] [app] staging updated symbol=SKYAIUSDT interval=3m
  [2026-04-27 04:37:57,539] [INFO] [execution.order] signal check symbol=SKYAIUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002666407490457371617132293542', 'range_3m_pct': '0.01310630069291507761723156255', 'vol_ratio_3m': '0.7897034469931703386891501055', 'ret_3m_pct': '-0.002129925452609158679446219382',
  'prior_runup_3m_pct': '0.004110174015159602861108145618', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,577] [INFO] [app] staging updated symbol=USDCUSDT interval=3m
  [2026-04-27 04:37:57,578] [INFO] [execution.order] signal check symbol=USDCUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.000001000820021885159478750268951', 'range_3m_pct': '0.000001000820672951820492804099361', 'vol_ratio_3m': '0.2788183666916408005993792144', 'ret_3m_pct': '0', 'prior_runup_3m_pct':
  '0.000001000820672951820492804099361', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,608] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  [2026-04-27 04:37:57,609] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,609] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8013171717540709228071278740', 'ret_3m_pct':
  '0.004492138757174943848265535313', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,641] [INFO] [app] staging updated symbol=ZILUSDT interval=3m
  [2026-04-27 04:37:57,641] [INFO] [execution.order] signal check symbol=ZILUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002878282578206849316277563154', 'range_3m_pct': '0.007211538461538461538461538462', 'vol_ratio_3m': '0.1662373846383533140563870289', 'ret_3m_pct': '0', 'prior_runup_3m_pct':
  '0.004807692307692307692307692308', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,648] [INFO] [app] staging updated symbol=TAOUSDT interval=3m
  [2026-04-27 04:37:57,650] [INFO] [execution.order] signal check symbol=TAOUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002114259907946179934065428200', 'range_3m_pct': '0.009314039015030380556443875919', 'vol_ratio_3m': '1.825194860171422692669115891', 'ret_3m_pct': '-0.002030335602531947927863370357',
  'prior_runup_3m_pct': '0.004196139551612516484833952763', 'recent_green_3m_bars': '3', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,656] [INFO] [app] staging updated symbol=ZECUSDT interval=3m
  [2026-04-27 04:37:57,656] [INFO] [execution.order] signal check symbol=ZECUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002710257699817798386467790478', 'range_3m_pct': '0.01534232743387653212913359325', 'vol_ratio_3m': '1.228931732431396931458051368', 'ret_3m_pct': '0.001167152980408503543142976240',
  'prior_runup_3m_pct': '0.01018557276405748569833961211', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,671] [INFO] [app] staging updated symbol=STOUSDT interval=3m
  [2026-04-27 04:37:57,672] [INFO] [execution.order] signal check symbol=STOUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.004743916714474239252096605917', 'range_3m_pct': '0.03988637708604568587998579714', 'vol_ratio_3m': '0.2118834030701181329449743307', 'ret_3m_pct': '-0.0003437213565536205316223648029',
  'prior_runup_3m_pct': '0.005288572085536905035640377098', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,807] [INFO] [app] staging updated symbol=STABLEUSDT interval=3m
  [2026-04-27 04:37:57,807] [INFO] [execution.order] signal check symbol=STABLEUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00524704576725226848430468031', 'range_3m_pct': '0.02424600827912477823772915435', 'vol_ratio_3m': '0.6786451621630939045214354819', 'ret_3m_pct': '-0.002660360626662725391664203370',
  'prior_runup_3m_pct': '0.02424600827912477823772915435', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,820] [INFO] [app] staging updated symbol=XPLUSDT interval=3m
  [2026-04-27 04:37:57,820] [INFO] [execution.order] signal check symbol=XPLUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002734692014594367200524026220', 'range_3m_pct': '0.008991008991008991008991008991', 'vol_ratio_3m': '0.2099808215288020147245548971', 'ret_3m_pct': '-0.0009930486593843098311817279047',
  'prior_runup_3m_pct': '0.005976095617529880478087649402', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,859] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,859] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8026375523069801611935843233', 'ret_3m_pct':
  '0.004616920389318692288495133516', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,910] [INFO] [app] staging updated symbol=SPACEUSDT interval=3m
  [2026-04-27 04:37:57,910] [INFO] [execution.order] signal check symbol=SPACEUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.01035332471533064435826892542', 'range_3m_pct': '0.05794701986754966887417218543', 'vol_ratio_3m': '0.6248071000955163427583458635', 'ret_3m_pct': '-0.002908514013749338974087784241',
  'prior_runup_3m_pct': '0.01900332225913621262458471761', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,931] [INFO] [app] staging updated symbol=UBUSDT interval=3m
  [2026-04-27 04:37:57,931] [INFO] [execution.order] signal check symbol=UBUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.01532133149738378514049966226', 'range_3m_pct': '0.06798640271945610877824435113', 'vol_ratio_3m': '0.3865746778493327994259270825', 'ret_3m_pct': '0.001548586914440572977158343012',
  'prior_runup_3m_pct': '0.02049664958612534489554592038', 'recent_green_3m_bars': '2', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,059] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  [2026-04-27 04:37:58,110] [INFO] [app] staging updated symbol=VINEUSDT interval=3m
  [2026-04-27 04:37:58,110] [INFO] [execution.order] signal check symbol=VINEUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002075871269922844374300496144', 'range_3m_pct': '0.01282051282051282051282051282', 'vol_ratio_3m': '0.03860052562417871222076215506', 'ret_3m_pct': '-0.0006393861892583120204603580563',
  'prior_runup_3m_pct': '0.001920614596670934699103713188', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,122] [INFO] [app] staging updated symbol=TRADOORUSDT interval=3m
  [2026-04-27 04:37:58,123] [INFO] [execution.order] signal check symbol=TRADOORUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.007410226759688400672730985625', 'range_3m_pct': '0.05793450881612090680100755668', 'vol_ratio_3m': '0.6211209222586745713706107833', 'ret_3m_pct': '0.002389486260454002389486260454',
  'prior_runup_3m_pct': '0.02815177478580171358629130967', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,134] [INFO] [app] staging updated symbol=WLDUSDT interval=3m
  [2026-04-27 04:37:58,134] [INFO] [execution.order] signal check symbol=WLDUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001543844045053831632272931047', 'range_3m_pct': '0.005415860735009671179883945841', 'vol_ratio_3m': '0.7664793309289844344144706461', 'ret_3m_pct': '-0.0007707129094412331406551059730',
  'prior_runup_3m_pct': '0.003862495171881035148706064117', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,160] [INFO] [cache.staging] staging csv flushed interval=3m rows=135
  [2026-04-27 04:37:58,171] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:58,171] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8038419151699326286337719615', 'ret_3m_pct':
  '0.004741702021462440728724731719', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,173] [INFO] [app] staging updated symbol=VVVUSDT interval=3m
  [2026-04-27 04:37:58,173] [INFO] [execution.order] signal check symbol=VVVUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002961579161924753220039140484', 'range_3m_pct': '0.008361558001693480101608806097', 'vol_ratio_3m': '0.5575503317012074576841742091', 'ret_3m_pct': '-0.0005275374551593163114581135261',
  'prior_runup_3m_pct': '0.008361558001693480101608806097', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,209] [INFO] [app] staging updated symbol=SUIUSDT interval=3m
  [2026-04-27 04:37:58,210] [INFO] [execution.order] signal check symbol=SUIUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00105704604515521910516568182', 'range_3m_pct': '0.004765434713544424441385153023', 'vol_ratio_3m': '0.6601917347439124114721395681', 'ret_3m_pct': '-0.001266490765171503957783641161',
  'prior_runup_3m_pct': '0.003490216816499206768905341089', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,223] [INFO] [app] staging updated symbol=币安人生USDT interval=3m
  [2026-04-27 04:37:58,223] [INFO] [execution.order] signal check symbol=币安人生USDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00521444544583858555905680873', 'range_3m_pct': '0.02671972711768050028425241615', 'vol_ratio_3m': '0.3416706492450048299354313895', 'ret_3m_pct': '-0.0009895951142275503279800950011',
  'prior_runup_3m_pct': '0.008953951108584422967595224559', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,231] [INFO] [app] staging updated symbol=TONUSDT interval=3m
  [2026-04-27 04:37:58,231] [INFO] [execution.order] signal check symbol=TONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout,recent_green_stretch metrics={'mode': '3m_only',
  'atr_3m_pct': '0.001216616159334315490796683317', 'range_3m_pct': '0.01145801291910181482620732082', 'vol_ratio_3m': '1.673287709061275598913102514', 'ret_3m_pct': '0.0002283278788340056320876779055',
  'prior_runup_3m_pct': '0.005657924917807171802125544766', 'recent_green_3m_bars': '6', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,241] [INFO] [app] staging updated symbol=XANUSDT interval=3m
  [2026-04-27 04:37:58,241] [INFO] [execution.order] signal check symbol=XANUSDT triggered=False reason=3m_push_too_small metrics={'mode': '3m_only', 'atr_3m_pct': '0.002667729936844493425787988938',
  'range_3m_pct': '0.01197604790419161676646706587', 'vol_ratio_3m': '7.936979216006834399128228371', 'ret_3m_pct': '-0.005562130177514792899408284024', 'prior_runup_3m_pct':
  '0.01064465972969740461667264681', 'recent_green_3m_bars': '1', 'breakout_3m': 'True', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,282] [INFO] [app] staging updated symbol=XMRUSDT interval=3m
  [2026-04-27 04:37:58,282] [INFO] [execution.order] signal check symbol=XMRUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001797374204459753042141610908', 'range_3m_pct': '0.006891622849558425647046811986', 'vol_ratio_3m': '0.3820215804506505871152015233', 'ret_3m_pct': '-0.0007617886798202178715624285823',
  'prior_runup_3m_pct': '0.004916571137434721691504266972', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,334] [INFO] [app] staging updated symbol=龙虾USDT interval=3m
  [2026-04-27 04:37:58,335] [INFO] [execution.order] signal check symbol=龙虾USDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002130853453094351513836082421', 'range_3m_pct': '0.004452054794520547945205479452', 'vol_ratio_3m': '1.300809747705777299704098212', 'ret_3m_pct': '-0.003412581048799908997838698669',
  'prior_runup_3m_pct': '0.003306727480045610034207525656', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,343] [INFO] [app] staging updated symbol=SOONUSDT interval=3m
  [2026-04-27 04:37:58,343] [INFO] [execution.order] signal check symbol=SOONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.0052504219845369976174380235', 'range_3m_pct': '0.03345925526173772261198057205', 'vol_ratio_3m': '0.3215868798278542110628635287', 'ret_3m_pct': '-0.003194888178913738019169329073',
  'prior_runup_3m_pct': '0.01173333333333333333333333333', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,474] [INFO] [app] staging updated symbol=ZECUSDT interval=3m
  [2026-04-27 04:37:58,475] [INFO] [execution.order] signal check symbol=ZECUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002710257699817798386467790478', 'range_3m_pct': '0.01534232743387653212913359325', 'vol_ratio_3m': '1.232335100094479362429928295', 'ret_3m_pct': '0.001167152980408503543142976240',
  'prior_runup_3m_pct': '0.01018557276405748569833961211', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,490] [INFO] [app] staging updated symbol=VVVUSDT interval=3m
  [2026-04-27 04:37:58,491] [INFO] [execution.order] signal check symbol=VVVUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002961579161924753220039140484', 'range_3m_pct': '0.008361558001693480101608806097', 'vol_ratio_3m': '0.5577090619074758632751911576', 'ret_3m_pct': '-0.0004220299641274530491664908208',
  'prior_runup_3m_pct': '0.008361558001693480101608806097', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,491] [INFO] [app] staging updated symbol=VIRTUALUSDT interval=3m
  [2026-04-27 04:37:58,492] [INFO] [execution.order] signal check symbol=VIRTUALUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  [2026-04-27 04:37:58,550] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  Traceback (most recent call last):
    File "C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto\main.py", line 40, in <module>
      main()
    File "C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto\main.py", line 36, in main
      asyncio.run(app.run())
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 190, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 641, in run_until_complete
      self.run_forever()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 321, in run_forever
      super().run_forever()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 608, in run_forever
      self._run_once()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 1898, in _run_once
      event_list = self._selector.select(timeout)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 444, in select
      self._poll(timeout)
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 825, in _poll
      status = _overlapped.GetQueuedCompletionStatus(self._iocp, ms)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 157, in _on_sigint
      raise KeyboardInterrupt()
  KeyboardInterrupt
  PS C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto>


■ Error running remote compact task: {
  "error": {
    "message": "Your input exceeds the context window of this model. Please adjust your input and try again.",
    "type": "invalid_request_error",
    "param": "input",
    "code": "context_length_exceeded"
  }
}


› commit


■ Error running remote compact task: {
  "error": {
    "message": "Your input exceeds the context window of this model. Please adjust your input and try again.",
    "type": "invalid_request_error",
    "param": "input",
    "code": "context_length_exceeded"
  }
}


› Find and fix a bug in @filename

  gpt-5.5 xhigh · /media/sf_agent_sanbox_vm/Auto_buy_Crypto

## 本輪 (2026-04-27) - commit 前整理

- 2026-04-27 04:50 +08:00：依使用者要求讀取 `AGENTS.md`、`god_rule.md`、`README.md`、`HANDOFF.md` 後進行 commit。
- 快照：commit 前 `HEAD=eebc4ccabe62676d8d3a7c8f91ee0ebe0bd93fda`。
- 本輪不修改交易邏輯、不修改 `.env`、不連 Binance、不查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `18 passed, 1 xfailed`。
- [SKIP] 未納入 runtime 產物與高風險檔：`*.log`、`*.pid`、`*.out`、`backfill_pid.txt`、`backfill_completion_monitor.sh`（含硬寫 DB password）、會直接操作帳戶/修改 `.env` 的臨時 shell script。
- [RISK] `HANDOFF.md` 目前已超過熱區建議長度，且含上一輪 context 爆量紀錄；本輪為避免擴張 commit 任務，僅補最小交接紀錄，後續應另開任務將完整內容先附加到 `HANDOFF_ARCHIVE.md` 再整理熱區。
