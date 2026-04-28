# BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

## 專案檔案樹

```text
Auto_buy_Crypto/
├── .env.example
├── .gitignore
├── HANDOFF.md
├── README.md
├── config.py
├── db_util.py
├── god_rule.md
├── main.py
├── requirements.txt
├── data/
│   ├── fallback_stop_state.csv
│   └── inprogress_<STRATEGY_INTERVAL>.csv
├── logs/
│   └── app.log
├── pump_system/
│   ├── app.py
│   ├── models.py
│   ├── cache/staging_store.py
│   ├── db/repository.py
│   ├── exchange/binance_client.py
│   ├── exchange/symbol_registry.py
│   ├── execution/order_service.py
│   ├── execution/sizing.py
│   ├── fallback_stop/manager.py
│   ├── market_data/backfill.py
│   ├── market_data/websocket_manager.py
│   ├── notify/telegram_notifier.py
│   ├── state/csv_state.py
│   ├── state/position_state.py
│   ├── strategy/signal_engine.py
│   └── utils/
└── tests/
    ├── test_signal_engine.py
    ├── test_sizing.py
    ├── test_symbol_registry.py
    └── test_telegram_notifier.py
```

## 規則繼承與 `db_util.py` 重用

### `god_rule.md` 繼承方式

- 已先建立 `snapshots/` 快照後才修改專案。
- Python 全程使用專案內 `.venv`，不污染 global 環境。
- 自動重試全部限制最多 3 次，超過後記錄 `[BLOCKED]`。
- PostgreSQL 歷史 K 線固定採 `INSERT ... ON CONFLICT DO NOTHING`，不覆蓋歷史資料。
- 任務完成前必須自我驗證、保留 `HANDOFF.md`、回報資源耗時。
- [EXCEPTION] 本任務依使用者要求一次性交付完整可測專案，與 `MVP First` 有張力，已記錄於 `HANDOFF.md`。

### `db_util.py` 重用方式

- 直接重用：
  - `.env` 載入方式
  - `DB_HOST / DB_PORT / DB_USER / DB_PASS`
  - `getconn()` connection pool
  - `db99fetchall()` / `db99fetchall_dict()`
- 額外補一層 adapter：`pump_system/db/repository.py`
  - 原因：`db99exec()` 不適合高效率 parameterized bulk insert。
  - 職責：only finalized K 線批量寫入、最近 K 線讀取、最新時間查詢。
  - 相容性：底層仍直接用 `db_util.getconn('daily')`，沒有重寫平行 DB 系統。

## 安裝方式與 `.venv`

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## `.env` 設定方式

最少需要：

```dotenv
API_KEY=***
API_SECRET=***
TESTNET=true
ENABLE_LIVE_TRADING=false
FUNCTION_TEST_MODE=true
FUNCTION_TEST_SYMBOL=BTCUSDT
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=***
DB_PASS=***
DB_NAME=daily
```

### 核心參數說明

- `TESTNET`
  - `true` 走 Binance Futures Testnet。
  - `false` 走正式盤。
- `ENABLE_LIVE_TRADING`
  - `false` 時仍會做資料同步、訊號判斷、size 計算、下單前檢查與 Telegram/log，但不送真單。
- `FUNCTION_TEST_MODE`
  - `true` 時系統仍抓全部資料、跑全部訊號。
  - 但只有 `FUNCTION_TEST_SYMBOL` 允許真實下單。
- `FUNCTION_TEST_SYMBOL`
  - 預設 `BTCUSDT`。
  - 即使它在大幣排除清單內，function test mode 仍會把它加入 execution evaluation set。
- `STRATEGY_INTERVAL`
  - 預設 `15m`；支援 `3m` 或 `15m`。
  - 切到 `15m` 時，REST backfill、WebSocket、DB seed、in-progress CSV、訊號評估與 fallback contract trigger 都會使用 `15m`。
  - 修改後必須重啟程式；正式盤切換前需確認對應資料表已補齊。
- `STOP_WORKING_TYPE`
  - `CONTRACT_PRICE`：原生止損以合約價格觸發；fallback 監控使用目前 `STRATEGY_INTERVAL` 的 in-progress low。
  - `MARK_PRICE`：原生止損以標記價格觸發；fallback 監控改查 mark price。
- `STOP_PRICE_MODE`
  - `IN_PROGRESS_INTERVAL_LOW`：止損價使用入場當下目前 `STRATEGY_INTERVAL` kline 的即時 `low`。
  - `IN_PROGRESS_3M_LOW` / `IN_PROGRESS_15M_LOW`：相容舊設定，實際仍取目前策略週期的 signal low。
  - `NOTIONAL_RISK_PCT`：止損價使用成交均價依名目風險比例計算。
- `STOP_NOTIONAL_RISK_PCT`
  - 預設 `0.50`，只在 `STOP_PRICE_MODE=NOTIONAL_RISK_PCT` 時生效。
  - 做多時計算式：`stop = filled_avg_entry_price * (1 - STOP_NOTIONAL_RISK_PCT)`，再依 tick size 向下合法化。
- `TARGET_NOTIONAL_USDT`
  - 預設 300；在 `POSITION_SIZING_MODE=FIXED_NOTIONAL` 時，代表每筆目標名目。
- `MAX_CONCURRENT_POSITIONS`
  - 已持倉達上限時，新訊號直接丟棄，不排隊。
- `POSITION_SIZING_MODE`
  - `FIXED_NOTIONAL`：每筆優先使用 `TARGET_NOTIONAL_USDT`。
  - `BALANCE_SPLIT`：每筆用 `availableBalance * 該幣最大槓桿 / 剩餘可開倉位數`，適合 `MAX_CONCURRENT_POSITIONS=5` 時盡量把保證金分配到最多 5 個幣。
- `API_RETRY_MAX_ATTEMPTS`
  - 預設 3，遵守 `god_rule.md`。

## Telegram Bot 設定方式

1. 在 Telegram 用 `@BotFather` 建立 bot，拿到 bot token。
2. 將 bot 加入要接收通知的 chat 或直接私訊 bot。
3. 對 bot 發一則訊息後，用下列方式取得 chat id：
   - `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 將 `.env` 設定成：

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=***
TELEGRAM_CHAT_ID=***
```

工程定義：

- Telegram 功能集中在 `pump_system/notify/telegram_notifier.py`。
- 主交易流程不直接散落 HTTP request。
- Telegram 發送失敗只記 log，不中斷交易主流程。

### 已實作的 Telegram 通知類型

- 程式啟動成功、程式關閉、模式摘要
- 正式盤真實下單模式風險告警
- backfill 開始 / 完成
- server time sync 成功 / offset 異常 / resync 失敗
- WebSocket 重連中 / 重連成功 / 重連補資料完成 / 重連失敗
- 訊號觸發
- 因已有持倉跳過
- 因持倉上限跳過
- 因最小合法下單不足跳過
- 因 function test mode 被攔下真實下單
- entry 成功 / entry 失敗
- 原生 stop 掛單成功 / 原生 stop 觸發平倉 / 原生 stop 遺失 / stop 失敗
- fallback stop 啟動 / 觸發 / 平倉成功 / 平倉失敗 / blocked
- DB 寫入失敗
- Binance API retry / blocked
- 無法取得 `availableBalance`
- 無法設定 cross
- 無法設定 leverage
- 任一子流程進入 `[BLOCKED]`

每則通知至少會帶：

- `event type`
- `timestamp`
- `symbol`
- `side`
- `quantity`
- `entry price`
- `stop price`
- `workingType`
- `order id`
- `error message`

## 啟動方式

```powershell
.venv\Scripts\python main.py run
```

其他指令：

```powershell
.venv\Scripts\python main.py backfill
.venv\Scripts\python main.py validate
```

## PostgreSQL 連線方式

- 目標 DB 預設 `daily`。
- 連線資訊完全由 `.env` 控制。
- 正式主線依 `STRATEGY_INTERVAL` 選擇 `public.semi_auto_price_future_3m` 或 `public.semi_auto_price_future_15m`。
- `public.semi_auto_price_future_1m` 屬舊版/歷史相容表，主線不再寫入。

寫入規則：

- `3m` finalized bars -> `public.semi_auto_price_future_3m`
- `15m` finalized bars -> `public.semi_auto_price_future_15m`
- `code` = Binance symbol
- `da` = bar open time
- conflict-safe 寫法固定 `ON CONFLICT (code, da) DO NOTHING`
- 未收盤 bar 一律禁止進 DB

## 全體交易對資料抓取

「全部交易對」的工程定義：

- `quoteAsset=USDT`
- `contractType=PERPETUAL`
- `status=TRADING`

資料層一定抓全部 USDT 永續；策略層才再用：

- `EXCLUDED_BIG_CAPS`
- `SYMBOL_BLACKLIST`
- `SYMBOL_WHITELIST`

做候選池過濾。

## 90 天歷史資料初始化流程

1. 啟動先校時。
2. 抓 `exchangeInfo`，建立全部 USDT 永續 universe。
3. 對每個 symbol 回補 `STRATEGY_INTERVAL`
4. 「最近 90 天」定義：
   - Binance server time / UTC 往回推 `90 * 24` 小時
   - 不用本地時區日界切分
5. 若 DB 已有資料：
   - 從該 symbol 最新 `da + interval` 做增量補齊
6. 當前尚未收盤 bar 不寫 DB。

## 增量更新流程

- WebSocket 只接 Binance 原生 `STRATEGY_INTERVAL` kline stream。
- `x=false` 的 in-progress bar 只留在 staging / CSV。
- `x=true` 的 finalized bar 才進 DB batch writer。
- WebSocket 重連後：
  - 自動重新訂閱
  - 用 REST catch-up 補回遺漏 finalized bar
- 週期性 symbol refresh 發現新合約時：
  - 先 backfill
  - 再重建 websocket 訂閱

## finalized bars 與 in-progress bars 分流

- PostgreSQL：
  - 只存 finalized `STRATEGY_INTERVAL`
- `data/inprogress_<STRATEGY_INTERVAL>.csv`
  - 只存未收盤 `STRATEGY_INTERVAL`
- `data/fallback_stop_state.csv`
  - 只存 fallback stop 狀態

### 未收盤 K bar 暫存 CSV 如何更新與清理

- 收到 websocket in-progress 更新時，先寫入 staging memory。
- staging CSV 每 `STAGING_FLUSH_INTERVAL_SECONDS` 秒 flush。
- 某根 bar 收盤後：
  - 從 in-progress staging 移除
  - 立即 flush CSV
  - 將 finalized bar 加入 DB flush batch

## 主策略週期資料來源

- 全專案固定直接使用 Binance 原生 `STRATEGY_INTERVAL` REST / WebSocket。
- 目前支援 `3m` 與 `15m`，不做 1m 本地聚合。
- 因此不存在正式資料來源混用。

## 主策略週期訊號說明

### STRATEGY_INTERVAL 的用途

- 偵測第一波啟動的即時爆量與短時間拉升。
- 做較大週期確認，降低短週期假突破噪音。
- 提供 `STOP_PRICE_MODE=IN_PROGRESS_INTERVAL_LOW` 時的止損 low 來源。

### 最終進場訊號工程定義

1. 主週期壓縮背景成立：
   - `STRATEGY_INTERVAL=3m` 時讀 `SIGNAL_3M_LOOKBACK` / `SIGNAL_3M_COMPRESSION_*`
   - `STRATEGY_INTERVAL=15m` 時讀 `SIGNAL_15M_LOOKBACK` / `SIGNAL_15M_COMPRESSION_*`
2. 主週期爆量成立：
   - 當前 in-progress 主週期 volume / 最近 finalized 主週期平均 volume >= 對應週期的 `SIGNAL_<週期>_VOLUME_MULTIPLE`
3. 主週期上拉與突破成立：
   - 當前 in-progress 主週期報酬 >= 對應週期的 `SIGNAL_<週期>_RETURN_PCT_MIN`
   - 且高點突破最近 `SIGNAL_<週期>_BREAKOUT_LOOKBACK` finalized 主週期高點
4. 第一波過熱排除：
   - 最近 5 根 finalized 主週期的總 range% <= `SIGNAL_PRIOR_RUNUP_LIMIT_PCT`
   - 當前 in-progress 主週期報酬 <= 對應週期的 `SIGNAL_<週期>_OVERHEAT_LIMIT_PCT`
   - 連續上漲 finalized 主週期根數 <= `SIGNAL_MAX_RECENT_GREEN_BARS`

對應關係：

- `STRATEGY_INTERVAL=3m`：讀 `SIGNAL_3M_*`
- `STRATEGY_INTERVAL=15m`：讀 `SIGNAL_15M_*`

兩組門檻彼此獨立；改 `SIGNAL_3M_*` 不會影響 15m，改 `SIGNAL_15M_*` 也不會影響 3m。

## 下單規則

- 只做多，不做空。
- 已有持倉的 symbol 直接跳過。
- 活躍持倉數 >= `MAX_CONCURRENT_POSITIONS` 直接丟棄新訊號。
- 先查 Binance 該 symbol 最大初始槓桿。
- 保證金模式固定切 `CROSSED`。
- 入場方式固定 `MARKET`。

### 固定名目與資金分配進場

- 先計算 `availableBalance * max_leverage`。
- `POSITION_SIZING_MODE=FIXED_NOTIONAL`：
  - 若足夠，目標名目用 `TARGET_NOTIONAL_USDT`。
  - 若不足，直接把剩餘可用保證金可支撐的最大名目全部用上，不預留額外安全餘額。
- `POSITION_SIZING_MODE=BALANCE_SPLIT`：
  - 目標名目用 `availableBalance * max_leverage / remaining_position_slots`。
  - `remaining_position_slots = MAX_CONCURRENT_POSITIONS - active_position_count`，最小視為 1。
  - 例：`MAX_CONCURRENT_POSITIONS=5`、目前 0 倉、可用保證金 100 USDT、該幣最大槓桿 10x，第一筆目標名目為 `100 * 10 / 5 = 200 USDT`。
- 再依 `MARKET_LOT_SIZE / LOT_SIZE / MIN_NOTIONAL` 做 quantity 合法化。
- 只有在「連最小合法下單都不成立」時才跳過。

### `availableBalance` 定義

- 優先取 `/fapi/v2/account` top-level `availableBalance`
- 若缺少，退回 `assets[].availableBalance` 內的 `USDT`
- 若 Binance 未來變更欄位，請同步修改 `OrderService._extract_available_balance()`

## Function Test Mode 用途與限制

這是這次新增的正式盤上線保護機制。

### 工程定義

- `FUNCTION_TEST_MODE=true` 時：
  - 系統仍抓全部資料
  - 仍跑完整主週期訊號
  - 仍寫 DB finalized bars
  - 仍維持 fallback / Telegram / time sync / reconnect
  - 但只有 `FUNCTION_TEST_SYMBOL` 可以真的送 entry / stop / fallback close
- 其他 symbol 若觸發：
  - 只記 log / Telegram
  - 不送真實下單

### 為何 BTCUSDT 仍會被評估

- 雖然 BTCUSDT 預設不在小幣候選池，但 function test mode 會把 `FUNCTION_TEST_SYMBOL` 加入 execution evaluation set。
- 這是 execution flow test，不是策略績效 test。

## 止損與 fallback 說明

### 原生止損

- 類型固定 `STOP_MARKET`
- Binance 目前官方等價實作為 `POST /fapi/v1/algoOrder`
  - `algoType=CONDITIONAL`
  - `type=STOP_MARKET`
  - `triggerPrice=<low price>`
  - `closePosition=true`
- `workingType` 可配置，預設 `CONTRACT_PRICE`
- 止損價由 `.env` 的 `STOP_PRICE_MODE` 決定：
  - `IN_PROGRESS_INTERVAL_LOW`：使用入場當下 in-progress 最新主週期 kline 的即時 `low`。
  - `NOTIONAL_RISK_PCT`：使用成交均價按 `STOP_NOTIONAL_RISK_PCT` 換算；例如 `0.50` 代表止損距離約等於名目持倉金額的 50%，止損價約為成交均價的 50%。
- 修改 `.env` 後必須重啟程式，新設定才會生效。
- Telegram 會回報：
  - `STOP_ORDER_SUCCESS`：原生 stop 掛單成功
  - `STOP_ORDER_TRIGGERED`：原生 stop 觸發並完成平倉
  - `STOP_ORDER_POSITION_CLOSED`：倉位已關閉，但這次沒有確認到 native stop fill
- 明確禁止：
  - finalized 主週期 low
  - 前一根主週期 low
  - 1m low

### fallback 止損

1. entry 成功後立即送原生 `STOP_MARKET`
2. 若 stop order 連續 3 次失敗：
   - 寫入 `data/fallback_stop_state.csv`
   - 啟動 fallback monitor
3. fallback monitor：
   - `CONTRACT_PRICE`：看 staging 中最新 in-progress 主週期 low
   - `MARK_PRICE`：查 Binance mark price
4. 一旦價格跌破 stop：
   - 送 `MARKET SELL` + `positionSide=LONG`
5. fallback close 若失敗：
   - 每次 retry 都發 Telegram
   - 最終標記 `BLOCKED`
6. 重啟後：
   - 重新讀 CSV
   - 恢復 active fallback stop

## WebSocket 重連與恢復說明

- 使用 combined streams。
- `WS_MAX_STREAMS_PER_CONNECTION` 預設 200，保守低於官方 1024 streams 上限。
- 重連策略：
  - 最多 3 次
  - exponential backoff
  - 成功後重新訂閱並執行 REST catch-up
- 相關事件會推送 Telegram。

## Server Time Offset 校正說明

- 啟動時呼叫 `/fapi/v1/time`
- 用 local request midpoint 與 Binance server time 計算 offset
- 所有 signed request 都用校正後 timestamp
- 執行中每 `SERVER_TIME_RESYNC_INTERVAL_SECONDS` 秒重校
- 若 `abs(offset_ms) > MAX_SERVER_TIME_OFFSET_MS`：
  - 關鍵交易流程直接中止
  - 發送 Telegram 風險告警

## Rate Limit / Retry / Backoff 說明

- REST retry 上限：`API_RETRY_MAX_ATTEMPTS=3`
- backoff：exponential backoff
- 429 / 418 / 5xx / 常見暫時性 futures error code 會重試
- 第 3 次仍失敗：
  - 記錄 `[BLOCKED]`
  - 發 Telegram
- Telegram 自身發送失敗不會中斷交易主流程

## Testnet / 正式盤切換方式

- `TESTNET=true` + `ENABLE_LIVE_TRADING=false`
  - 最安全 dry-run
- `TESTNET=true` + `ENABLE_LIVE_TRADING=true`
  - Testnet 真實送測試單
- `TESTNET=false` + `ENABLE_LIVE_TRADING=false`
  - 讀正式盤資料但不下單
- `TESTNET=false` + `ENABLE_LIVE_TRADING=true`
  - 正式盤真單模式
  - 啟動時會發 `LIVE_PRODUCTION_MODE` Telegram 風險告警

## Testnet 測試流程

1. `.env` 設：
   - `TESTNET=true`
   - `ENABLE_LIVE_TRADING=true`
   - `FUNCTION_TEST_MODE=true`
   - `FUNCTION_TEST_SYMBOL=BTCUSDT`
2. 先跑：

```powershell
.venv\Scripts\python main.py backfill
.venv\Scripts\python main.py run
```

3. 確認 Telegram 能收到：
   - 啟動成功
   - 模式摘要
   - backfill 開始 / 完成
   - signal / skip / entry / stop / fallback 類事件

## 首次正式盤 BTCUSDT 功能測試流程

1. 保持：
   - `FUNCTION_TEST_MODE=true`
   - `FUNCTION_TEST_SYMBOL=BTCUSDT`
2. 先用正式盤但不下單：
   - `TESTNET=false`
   - `ENABLE_LIVE_TRADING=false`
   - 確認 DB、WebSocket、Telegram、time sync 都正常
3. 再切：
   - `TESTNET=false`
   - `ENABLE_LIVE_TRADING=true`
4. 這時系統仍會跑全部 symbol，但只有 BTCUSDT 允許真實下單。
5. [ASSUMPTION] 若要加快 execution flow 驗證，可暫時放寬 `SIGNAL_*` 門檻，讓 BTCUSDT 更容易觸發；驗證完成後恢復預設值。
6. 本次至少驗證：
   - 是否真的送出市價單
   - 是否真的依規則送出 `STOP_MARKET`
   - stop 失敗時是否真的啟動 fallback
   - Telegram 是否完整通知

## fallback 止損驗證方式

1. `ENABLE_LIVE_TRADING=false` 先看 simulated fallback trigger log / Telegram
2. Testnet 開啟 live trading
3. 人工讓 stop order 參數失敗或暫時破壞 stop request，確認：
   - `data/fallback_stop_state.csv` 出現 active record
   - Telegram 收到 `FALLBACK_STOP_ACTIVATED`
4. 價格跌破 stop 時確認：
   - 送出 reduceOnly market close
   - CSV 狀態更新為 `CLOSED` 或 `BLOCKED`

## 未收盤 K bar 暫存驗證方式

1. 啟動系統
2. 觀察 `data/inprogress_<STRATEGY_INTERVAL>.csv`
3. 未收盤 bar 應持續更新 high / low / close / volume
4. bar 收盤後：
   - staging CSV 該列消失
   - PostgreSQL 新增 finalized row

## 正式盤啟用前檢查清單

- `.env` 已填正式 API / DB / Telegram
- `TESTNET=false`
- `ENABLE_LIVE_TRADING=true`
- `FUNCTION_TEST_MODE=true`
- `FUNCTION_TEST_SYMBOL=BTCUSDT`
- `daily` DB 可連線
- `STRATEGY_INTERVAL` 已確認為 `3m` 或 `15m`
- 對應資料表 `public.semi_auto_price_future_<STRATEGY_INTERVAL>` 已存在且已補齊
- 已完成至少一次 `main.py backfill`
- 已在 Testnet 驗證 entry / stop / fallback / Telegram
- `STOP_WORKING_TYPE` 已確認
- `STOP_PRICE_MODE` / `STOP_NOTIONAL_RISK_PCT` 已確認
- `POSITION_SIZING_MODE` 已確認
- `MAX_CONCURRENT_POSITIONS` 已確認
- `TARGET_NOTIONAL_USDT` 已確認

## 本地自我驗證

```powershell
.venv\Scripts\python -m compileall .
.venv\Scripts\python -m pytest -q
```

## 風險警告

- 這是自動入場 + 自動止損保護系統，不含止盈與續抱管理。
- 小幣永續可能出現滑價、流動性真空、下市、標記價格偏移。
- 原生 stop 與 fallback 都失敗時會標記 `[BLOCKED]`，需人工處理。
- function test mode 只保護「只有指定 symbol 可真下單」，不保證該 symbol 一定很快出現策略訊號。

## 參考官方文件

- Binance USDⓈ-M Futures New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
- Binance USDⓈ-M Futures Account Information V2: https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Account-Information-V2
- Binance USDⓈ-M Futures Exchange Information: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Binance USDⓈ-M Futures Kline Data: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
- Binance USDⓈ-M Futures Check Server Time: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Check-Server-Time
- Binance USDⓈ-M Futures Kline Streams: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- Binance USDⓈ-M Futures WebSocket Connect: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Connect
- Binance USDⓈ-M Futures Leverage Brackets: https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Notional-and-Leverage-Brackets
- Binance USDⓈ-M Futures Change Leverage: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Change-Initial-Leverage
- Binance USDⓈ-M Futures Change Margin Type: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Change-Margin-Type
- Binance USDⓈ-M Futures Position Risk: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Position-Information-V2
- Binance USDⓈ-M Futures Mark Price: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price
- Telegram Bot API `sendMessage`: https://core.telegram.org/bots/api#sendmessage
