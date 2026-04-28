先做，不要講廢話。
不要先分析一大段才開始。
不要只列計畫。
我要的是完整專案實作，不是建議。
若需求有模糊處，請採用最保守且可執行的工程定義，並寫進 README，但不要停在討論。

在開始任何工作前，必須先閱讀並遵守：
1. `god_rule.md`
2. `db_util.py`

其中 `god_rule.md` 是本專案最高憲法，優先級高於其他子規則。
若本 prompt 與 `god_rule.md` 有衝突，必須以 `god_rule.md` 為準，並在 `HANDOFF.md` 以 `[EXCEPTION]` 記錄例外原因、影響與預計恢復時間。

補充說明：
- 本任務依使用者要求採一次性完整交付。
- 若這與 `god_rule.md` 中的 MVP First 原則存在張力，必須在 `HANDOFF.md` 以 `[EXCEPTION]` 記錄，但仍須遵守其餘規則：不可無限重試、不可覆蓋歷史資料、需自我驗證、需留下 handoff。
- 本次目標不是再優化策略，而是讓系統盡快可小額正式盤上線。
- 請優先補齊正式盤必要能力：Telegram 通知、啟動風險告警、entry/stop/fallback 的完整觀測性。

以下規則為使用者已明確指定，不可自行更改：

1. 本策略必須使用 1 分鐘與 3 分鐘 K bar 搭配判斷進場訊號。
2. 止損價來源固定為「入場當下最新的 1 分鐘 K bar low」。
3. 這裡的「最新 1 分鐘 K bar low」明確定義為：入場當下正在形成中的（in-progress）最新 1m K bar 的即時 low，而不是最後一根已收盤 finalized 1m K bar 的 low。
4. 即使 3 分鐘 K bar 參與訊號判斷，止損 low 仍不可改用 3 分鐘。
5. 預設目標持倉名目為 300 USDT。
6. 若帳戶剩餘可用保證金足夠，則以接近 300 USDT 為目標進場。
7. 若帳戶剩餘可用保證金不足，仍必須無條件進場，並在符合交易所最小下單與精度限制的前提下，使用剩餘可用保證金可支撐的最大合法倉位進場。
8. 不可因資金不足而跳過訊號，除非連最小合法下單都無法成立。
9. 這裡所稱「剩餘可用保證金」，預設以 Binance Futures 帳戶資訊中的 `availableBalance` 為準；若官方接口更新或欄位調整，需在 README 明確記錄替代定義。
10. 止損單類型必須是觸發後市價止損，不可改成限價止損。
11. 交易所止損單預設對應 Binance Futures 的 `STOP_MARKET` 類型；若官方 API 變更，需使用其當前等價實作。
12. 止損單的 `workingType` 必須明確實作為可配置參數，並在 README 說明預設值與差異，不可省略。
13. 若交易所止損單失敗，至少 retry 3 次；若仍失敗，必須寫入本地 CSV 並啟動本地備援止損監控。
14. 本機時間與 Binance server time offset 必須校正，不可直接使用未校正本機時間送出需要 timestamp 的請求。
15. PostgreSQL schema 與資料表已由使用者建立完成，必須沿用既有表，不可自行改表名、改 schema、改欄位設計。
16. 必須自動抓取 Binance USDT 永續合約全部交易對，一個都不能漏。
17. 歷史 K 線只需要抓最近 90 天。
18. 1m 資料存入 `public.semi_auto_price_future_1m`；3m 資料存入 `public.semi_auto_price_future_3m`。
19. 專案內已提供 `db_util.py`，若其能力足夠，必須優先重用，不要重寫另一套不必要的 DB 基礎工具。
20. DB 目標資料庫為 `daily`。
21. 若需 DB 連線設定，請用 `.env` 與 `db_util.py` 相容的變數名稱，不可把密碼硬寫進程式碼、log、handoff、README 或輸出內容。
22. 專案結束前必須更新 `HANDOFF.md`，並回報任務耗時 / token 估算 / 狀態。
23. PostgreSQL 只可存放完整結束、已收盤的 K bar。
24. 未完整、未收盤的 1m / 3m K bar，不可寫入 DB。
25. 所有未收盤 K bar 必須暫存在專案內的 CSV。
26. fallback 止損狀態 CSV 與未收盤 K bar 暫存 CSV 必須分開，不可混在同一份檔案。
27. 3m K bar 的正式資料來源必須全專案一致，不可一部分直接用 Binance 3m，一部分又由 1m 本地聚合。
28. 本專案預設 3m K bar 正式資料來源直接使用 Binance 提供的 3m K bar；若因技術原因改為由 1m 本地聚合，必須在 README 與 HANDOFF 明確記錄，且全專案一致，不可混用。
29. 「最近 90 天」的定義，預設以 Binance / UTC 時間基準往回推算 90*24 小時，不使用本地時區日界切分；若採其他定義，必須在 README 明確說明。
30. fallback 市價平倉若交易所接口支援，必須優先使用 reduceOnly 語意，確保該單僅用於平倉，不可意外反手開新倉。
31. 本專案必須先完整實作全架構，不可因最終首次實盤只測 BTCUSDT，就做成單一標的簡化版。
32. 系統仍需完整支援：
   - Binance USDT 永續全部交易對資料抓取
   - 1m / 3m K bar
   - finalized / in-progress 分流
   - PostgreSQL finalized bar 寫入
   - 市價入場
   - 原生止損
   - fallback stop
   - Telegram 通知
   - server time sync
   - rate limit/backoff
33. 不要預設依賴 `SYMBOL_WHITELIST`。
34. 但必須提供一個獨立的功能測試模式，讓首次正式盤只對單一指定標的啟用真實下單。
35. 當 `FUNCTION_TEST_MODE=true` 時：
   - 系統仍照完整架構跑
   - 仍可抓全部資料與跑完整訊號流程
   - 但只允許 `FUNCTION_TEST_SYMBOL` 真實下單
   - 其他 symbol 不可真實下單，只能記錄 log / Telegram
36. 首次正式盤功能測試預設：
   - `FUNCTION_TEST_MODE=true`
   - `FUNCTION_TEST_SYMBOL=BTCUSDT`
37. 這次 BTCUSDT 測試的目的是驗證 execution flow，不是驗證策略績效。
38. 不得因為 BTCUSDT 不屬於小幣，而跳過此功能測試要求。
39. 本次 BTCUSDT 功能測試至少要驗證：
   - 是否真的送出市價單
   - 是否真的依規則設定止損
   - 若原生止損單失敗，是否真的啟動 fallback stop
   - 是否正確發送 Telegram 通知

# BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

你現在是資深 Python 量化交易工程師 + 交易系統工程師。
你的任務不是討論策略，而是直接在本機專案中實作一套「Binance USDⓈ-M Futures 小幣第一波爆量啟動自動入場 + 止損保護系統」。

你的交付目標不是提案，不是偽代碼，不是研究報告，而是完整可執行 Python 專案。

--------------------------------------------------
一、先做的事
--------------------------------------------------

在真正開始實作前，必須先做以下事情：

1. 閱讀 `god_rule.md`
2. 閱讀 `db_util.py`
3. 判斷哪些規則必須直接繼承到本專案
4. 判斷 `db_util.py` 內哪些函式可直接重用
5. 在開始破壞性操作前建立快照或 rollback 方案
6. 確保 Python 只在專案內 `.venv` 執行，不污染 global 環境

--------------------------------------------------
二、系統定位
--------------------------------------------------

這不是全自動交易系統。
這是一套「自動入場 + 自動止損保護」工具。

程式只負責：
1. 偵測進場訊號
2. 市價單自動入場
3. 入場後立即設定止損
4. 若交易所止損單設定失敗，啟動本地備援止損監控
5. 若價格跌破原定止損價，無條件市價平倉
6. 發送 Telegram 交易與風險通知

程式不負責：
1. 固定止盈
2. 移動止損
3. 追蹤停利
4. 分批出場
5. 自動加碼
6. 自動攤平
7. 自動續抱管理
8. 其他非止損型出場管理

也就是說：
- 入場由程式處理
- 止損保護由程式處理
- 通知由程式處理
- 其餘持倉管理由人工自行決定

--------------------------------------------------
三、交易市場與方向
--------------------------------------------------

1. 市場：
   Binance USDⓈ-M Futures

2. 合約：
   只做 USDT 永續合約

3. 方向：
   只做多，不做空

4. 標的：
   策略目標是小幣，但系統必須完整支援全部 USDT 永續資料抓取

5. 持倉去重規則：
   若某幣種當前已有持倉，該幣種直接跳過，不可重複下單
   - 不加碼
   - 不攤平
   - 不重複進場

--------------------------------------------------
四、小幣定義
--------------------------------------------------

1. 預設排除主流大幣，例如：
   BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT

2. 其餘 USDT 永續視為候選池

3. 必須支援：
   - blacklist
   - whitelist
   - 預設排除大幣清單可於 .env 設定

4. 候選池在程式啟動時載入。
   若程式為長時間常駐執行，需支援定期刷新候選池，以處理新上線 / 下架 / 狀態改變的合約。

5. 雖然策略只做小幣，但資料抓取層必須抓 Binance USDT 永續全部交易對，不可只抓小幣池。
   策略層再根據 blacklist / whitelist / 排除大幣規則過濾。

--------------------------------------------------
五、資料庫與資料表要求
--------------------------------------------------

PostgreSQL schema 與資料表已存在，必須直接沿用，禁止擅自改名或重建成其他格式。

使用者已建立以下兩張表：

1. `public.semi_auto_price_future_1m`
2. `public.semi_auto_price_future_3m`

欄位結構如下：

### Table: public.semi_auto_price_future_1m

CREATE TABLE IF NOT EXISTS public.semi_auto_price_future_1m
(
    da timestamp without time zone NOT NULL,
    code character varying(50) NOT NULL,
    cl double precision,
    hi double precision,
    lo double precision,
    op double precision,
    vol double precision,
    CONSTRAINT semi_auto_price_future_1m_pkey PRIMARY KEY (code, da)
);

### Table: public.semi_auto_price_future_3m

CREATE TABLE IF NOT EXISTS public.semi_auto_price_future_3m
(
    da timestamp without time zone NOT NULL,
    code character varying(50) NOT NULL,
    cl double precision,
    hi double precision,
    lo double precision,
    op double precision,
    vol double precision,
    CONSTRAINT semi_auto_price_future_3m_pkey PRIMARY KEY (code, da)
);

資料寫入要求：

1. 1m K 線資料寫入 `public.semi_auto_price_future_1m`
2. 3m K 線資料寫入 `public.semi_auto_price_future_3m`
3. `code` 欄位存 Binance symbol，例如 `BTCUSDT`
4. `da` 欄位存 K bar 對應時間戳
5. 若資料已存在，不可重複插入造成衝突
6. 必須使用符合 PostgreSQL 的 conflict-safe 寫法
7. 依 `god_rule.md`，歷史資料不可默默覆蓋，優先使用：
   - `INSERT ... ON CONFLICT DO NOTHING`
   - 禁止對歷史 K 線資料默默做 `ON CONFLICT DO UPDATE` 覆蓋
8. 不可自行發明新的資料表替代
9. 不可改成 SQLite / CSV 取代主 K 線資料庫
10. 本地 CSV 僅可用於 fallback 止損狀態保存與未收盤 K bar 暫存，不可取代主行情資料庫

11. K bar 完整性要求：
   - PostgreSQL 只允許存放「已完整結束、已收盤」的 K bar
   - 未完整、尚未收盤中的 K bar，不可寫入 `public.semi_auto_price_future_1m` 或 `public.semi_auto_price_future_3m`
   - 1m bar 只有在該 1m 週期正式結束後，才能寫入 `public.semi_auto_price_future_1m`
   - 3m bar 只有在該 3m 週期正式結束後，才能寫入 `public.semi_auto_price_future_3m`
   - 禁止把 WebSocket 推送中的未完成 K bar 當成正式歷史資料寫入 DB
   - DB 內資料必須是可重用、可回測、可重跑的一致歷史資料，不可混入即時浮動中的半成品 K bar

--------------------------------------------------
六、DB 工具重用要求
--------------------------------------------------

專案內已提供 `db_util.py`。

你必須先檢查是否可直接重用以下能力：
- connection pool
- `db99exec`
- `db99fetchall`
- `db99fetchall_dict`
- 其他必要查詢能力

重用原則：

1. 若 `db_util.py` 已可滿足本專案 DB 存取需求，優先直接重用
2. 若不足，可在不破壞原檔的前提下額外封裝一層 adapter / repository
3. 不要無故重寫另一套完全平行的 DB 工具
4. 若決定不直接使用某些函式，必須在 README 或 HANDOFF 說明原因
5. 資料庫目標為 `daily`
6. `.env` 變數命名需與 `db_util.py` 相容，優先使用：
   - `DB_HOST`
   - `DB_PORT`
   - `DB_USER`
   - `DB_PASS`
7. 連線資訊不得硬寫進程式碼
8. 即使使用者已提供本機資料庫帳號資訊，也只可放進 `.env`，不可出現在 log、handoff、README、輸出內容或版本控制中
9. `db_util.py` 若不足以支援高效率批量 K bar 寫入，允許在不修改原檔核心行為的前提下，額外封裝專案內 adapter / repository 層，用於批量寫入；但仍須沿用 `db_util.py` 的連線設定與既有 DB 存取方式。
10. 若需批量寫入 finalized K bar，優先考慮高效率批量插入方案；不可退化成對數百個 symbol 逐筆低效率 round-trip 寫入。
11. 若採用額外 bulk insert adapter，必須在 README 與 HANDOFF 說明：
   - 為何 `db_util.py` 原始函式不足
   - 額外 adapter 的責任範圍
   - 它如何仍與既有 `db_util.py` 相容

--------------------------------------------------
七、CSV 與暫存資料要求
--------------------------------------------------

CSV 用途區分要求：

1. 本專案內的 CSV 至少分為三類：
   - fallback 止損狀態 CSV
   - 未收盤 K bar 暫存 CSV
   - 其他必要 runtime state CSV（若有）
2. 不可把不同用途混在同一份 CSV
3. fallback 止損狀態 CSV 用於記錄：
   - 止損單失敗後的備援監控狀態
4. 未收盤 K bar 暫存 CSV 用於記錄：
   - 當前尚未收盤的 1m / 3m K bar 狀態
5. 正式歷史資料仍以 PostgreSQL 為唯一正式來源
6. CSV 只是專案內暫存與保護機制，不可取代正式 K 線資料表

未收盤 K bar 暫存要求：

1. 所有未完整結束的即時 K bar，必須暫存在專案內 CSV 或其他本地暫存檔
2. 該暫存資料僅用於：
   - 即時訊號判斷
   - 入場當下止損價來源判斷
   - fallback 止損監控所需的最新價格 / 最新 K bar 狀態
3. 未收盤 K bar 暫存資料不可直接視為正式歷史資料
4. 一旦該 K bar 正式收盤，才可將其寫入 PostgreSQL 正式表，並同步更新 / 清理本地暫存狀態
5. 必須明確區分：
   - finalized bars（正式收盤 K bar）
   - in-progress bars（尚未收盤 K bar）
6. README 必須說明：
   - 哪些資料進 DB
   - 哪些資料只留在本地暫存
   - 暫存檔如何更新與清理

--------------------------------------------------
八、歷史資料抓取要求
--------------------------------------------------

1. 系統必須自動向 Binance 抓取 USDT 永續合約全部交易對的 K 線資料
2. 一個交易對都不能漏
3. 只需要抓最近 90 天資料
4. 必須同時抓：
   - 1m
   - 3m
5. 抓完後寫入 PostgreSQL 對應資料表
6. 啟動時若資料不足，需先補齊後再進入正式監控
7. 若資料表已有部分資料，需支援增量補齊，不可每次都粗暴重灌
8. 必須處理：
   - API 分頁 / 批次抓取
   - 429 / rate limit
   - 中斷後續抓
   - 已存在資料跳過或安全寫入
9. 必須提供一個明確的資料初始化 / backfill 模組
10. 3m K bar 的正式資料來源必須全專案一致。
11. 本專案預設 3m K bar 正式資料來源直接使用 Binance 提供的 3m K bar。
12. 若因技術原因改為由 1m 本地聚合產生 3m，必須在 README 與 HANDOFF 明確記錄，且全專案一致，不可混用。
13. 「最近 90 天」的定義，預設以 Binance / UTC 時間基準往回推算 90*24 小時，不使用本地時區日界切分；若採其他定義，必須在 README 明確說明。
14. README 必須說明：
   - 如何初始化 90 天歷史資料
   - 如何日後增量更新
   - 如何避免重複寫入

--------------------------------------------------
九、策略核心：抓第一波爆量往上
--------------------------------------------------

這套策略要抓的是：

「平時沒什麼波動，突然爆量好幾倍，價格快速往上拉，且屬於第一波啟動」的小幣永續。

注意：
這句本身是模糊敘述，所以你必須把它工程化，轉成可配置、可運算、可記錄 log 的條件，但不能偏離原意。

策略週期要求：

1. 本策略必須使用 1 分鐘與 3 分鐘 K bar 搭配判斷訊號
2. 1m 與 3m 都屬於主判斷依據，不可只做單一週期簡化版
3. 你必須在 README 中明確說明：
   - 1m 在策略中的用途
   - 3m 在策略中的用途
   - 兩者如何共同組成最終進場訊號
4. 若 1m 與 3m 訊號不同步，需採用明確且固定的工程定義，不可模糊處理

你必須至少用以下概念做成訊號引擎：

1. 平時沒什麼波動
   - 要有觀察窗
   - 可用以下一種或多種方式量化：
     - ATR%
     - 報酬率標準差
     - 高低區間壓縮
     - 最近 N 根 K 線波動範圍

2. 突然爆量好幾倍
   - 當前成交量 / 過去平均成交量 >= 可配置倍數
   - 倍數門檻必須可調
   - 預設偏激進

3. 往上拉
   - 短時間內累積漲幅達門檻
   - 且突破近端局部高點

4. 第一波
   - 不要追在已經噴太久的末端
   - 需加入過熱排除條件
   - 但不可改成保守等回踩策略

你必須提供一組預設參數，且全部可配置，不可寫死在邏輯裡。

--------------------------------------------------
十、資料與監控方式
--------------------------------------------------

1. 必須優先使用 WebSocket 做即時市場監控
2. 至少要支援：
   - 1m K 線監控
   - 3m K 線監控
   - 啟動時補足 1m 與 3m 歷史 K 線作初始化
3. 啟動時必須：
   - 載入候選 symbol
   - 同步歷史 K 線
   - 同步當前持倉
   - 同步當前掛單狀態（若需要）

4. WebSocket 必須實作：
   - 自動重連
   - 心跳 / 健康檢查
   - 斷線後重新訂閱
   - 斷線恢復後補回遺漏資料或重新同步關鍵狀態

5. 若候選池 symbol 數量過大，需處理 Binance WebSocket 單連線訂閱上限問題。

6. 啟動初始化與批量查詢時，必須處理 API rate limit / 429。
7. 對 rate limit / 429 / 暫時性交易所錯誤，必須有有限次數 retry + exponential backoff。
8. 不可無限重試；依 `god_rule.md`，同一錯誤自動重試不得超過 3 次，超過後必須標記 `[BLOCKED]` 或停止該子流程。
9. 必須實作與 Binance server time 的時間偏移校正機制。
10. 啟動時必須查詢 server time，計算本機 offset。
11. 後續所有需要 timestamp 的 REST API 請求，都必須使用校正後時間。
12. 系統運行期間必須定期重新校時。
13. 若時間偏移異常已影響關鍵交易流程，必須中止該次交易，不可硬送請求。

14. 新增暫存 / staging 要求：
   - 所有未收盤 1m / 3m K bar，必須先進入本地 staging / cache 層
   - 只有 finalized K bar 才能交給 DB 寫入層
   - 不可讓 DB 寫入層直接接收未完成 K bar

--------------------------------------------------
十一、下單規則（必須嚴格照做）
--------------------------------------------------

1. 槓桿
   - 將該幣種槓桿設到交易所允許的最大值
   - 必須動態查詢該 symbol 可用最大槓桿

2. 保證金模式
   - 使用全倉模式（cross）
   - 若不是 cross，需先切換
   - 若切換失敗，該筆交易直接放棄，不可硬下

3. 名目持倉目標
   - 預設最終持倉名目目標約為 300 USDT
   - 若帳戶剩餘可用保證金足夠，則以接近 300 USDT 為目標計算 quantity
   - 若帳戶剩餘可用保證金不足，則改為使用剩餘可用保證金所能支撐的最大合法倉位進場

4. 資金不足時的強制進場規則
   - 不可因剩餘可用保證金過低就直接跳過訊號
   - 不可預留額外安全餘額
   - 允許帳戶幾乎把剩餘可用保證金全部投入新倉位

5. 下單精度與限制
   - quantity 必須符合交易所規則
   - 必須處理：
     - stepSize
     - minQty
     - minNotional
     - market order 相關限制
     - quantity rounding
   - 必須實作：
     - target notional -> 合法 quantity
     - available margin -> 最大合法 quantity

6. 用於計算可開倉資金的欄位，預設以 Binance Futures 帳戶資訊中的 `availableBalance` 為準；若官方接口調整，需在 README 記錄替代定義與原因。

7. 入場方式
   - 一律市價單
   - 不做限價
   - 不分批

8. 功能測試模式要求
   - 當 `FUNCTION_TEST_MODE=true` 時，系統仍照完整架構運行
   - 仍抓全部資料、跑完整訊號流程
   - 但只允許 `FUNCTION_TEST_SYMBOL` 真實下單
   - 其他 symbol 即使觸發訊號，只能記錄 log / Telegram，不可真實下單
   - 首次正式盤功能測試預設 `FUNCTION_TEST_SYMBOL=BTCUSDT`
   - 這屬於 execution function test，不屬於策略績效測試

--------------------------------------------------
十二、止損規則（核心要求）
--------------------------------------------------

1. 入場後必須立即設定止損
2. 止損單類型必須明確使用 Binance Futures 的 `STOP_MARKET` 或其官方當前等價實作
3. `workingType` 必須做成可配置參數，並在 README 說明預設值與差異
4. 止損價定義：
   - 止損價一律取「入場當下正在形成中的（in-progress）最新 1 分鐘 K bar 的即時 low」
   - 即使策略訊號同時參考 1m 與 3m，止損 low 的來源仍固定只看 1m in-progress bar
   - 不可改用 finalized 1m bar
   - 不可改用 3m low
   - 不可改用前一根已收盤 1m
   - 不可改用其他自定義止損來源

5. 若止損距離極小：
   - 不得自行更改止損來源
   - 只能照規則設定止損
   - 必須記 log

--------------------------------------------------
十三、交易所止損單失敗時的處理
--------------------------------------------------

1. 市價單入場成功後，必須立即送出交易所原生止損單
2. 若止損單送出失敗：
   - 至少 retry 3 次
   - 每次 retry 要記錄 log
   - 不可無限重試
3. 若 retry 3 次後仍失敗：
   - 必須立刻啟動本地備援止損監控
4. 本地備援止損監控要求：
   - 將持倉止損資訊記錄到專案內 fallback CSV
   - 持續即時監控該幣種價格
   - 一旦價格跌破原本止損價，必須無條件送出市價平倉單
5. fallback 市價平倉若交易所接口支援，必須優先使用 reduceOnly 語意，確保該單僅用於平倉，不可意外反手開新倉。
6. 程式重啟後：
   - 必須重新讀取 fallback CSV
   - 恢復所有 fallback_stop_active=true 的監控狀態
7. CSV 寫入必須考慮並發安全
8. fallback 平倉成功後，必須更新 CSV 狀態，不可重啟後誤判

--------------------------------------------------
十四、Telegram bot 通知要求
--------------------------------------------------

新增 Telegram bot 通知功能，這是正式盤必要功能，不是可選項。

一、整合目標
1. 本專案必須整合 Telegram bot。
2. 所有關鍵事件都必須主動推送通知到指定 chat。
3. Telegram 通知必須支援正式盤模式，不可只做測試用假通知。
4. 若 Telegram 發送失敗，必須記錄 log，但不可因此中斷主交易流程。

二、設定方式
1. `.env.example` 必須新增：
   - TELEGRAM_ENABLED=true
   - TELEGRAM_BOT_TOKEN=
   - TELEGRAM_CHAT_ID=
2. 不可把 bot token 或 chat id 寫死在程式碼。
3. README 必須說明如何建立 Telegram bot 與取得 chat id。

三、至少必須通知的事件
1. 程式啟動成功
2. 程式關閉
3. 當前模式摘要：
   - TESTNET
   - ENABLE_LIVE_TRADING
   - FUNCTION_TEST_MODE
   - FUNCTION_TEST_SYMBOL
   - STOP_WORKING_TYPE
   - MAX_CONCURRENT_POSITIONS
   - TARGET_NOTIONAL_USDT
4. backfill 開始 / 完成
5. server time sync 成功 / offset 異常
6. WebSocket 重連 / 重連失敗
7. 訊號觸發
8. 因已有持倉跳過
9. 因持倉上限跳過
10. 因最小合法下單不足跳過
11. 因功能測試模式而跳過真實下單
12. 市價單入場成功
13. 原生止損單送出成功
14. 原生止損單送出失敗
15. 原生止損單 retry 過程
16. 原生止損單最終失敗並啟動 fallback stop
17. fallback stop 觸發平倉
18. fallback 平倉成功
19. fallback 平倉失敗
20. 任一子流程進入 [BLOCKED]
21. DB 寫入失敗
22. Binance API 429 / 5xx 過多
23. 無法取得 availableBalance
24. 無法設定 cross
25. 無法設定 leverage
26. 無法送 entry order
27. 無法送 stop order

四、通知內容要求
1. 每則通知至少要包含：
   - event type
   - symbol（若有）
   - side（若有）
   - quantity（若有）
   - entry price（若有）
   - stop price（若有）
   - workingType（若有）
   - order id（若有）
   - error message（若有）
   - timestamp
2. 內容必須簡潔但可直接判讀，不要只傳「error」這種沒資訊的字串。

五、正式盤安全要求
1. 程式啟動時必須先主動發送一則「正式盤啟動通知」。
2. 若 `TESTNET=false` 且 `ENABLE_LIVE_TRADING=true`，通知內容必須明確標示：
   - 目前為正式盤真實下單模式
3. fallback stop 啟動時，必須發送高優先級風險通知。
4. fallback 平倉失敗時，必須重複通知，不可只通知一次後沉默。

六、工程要求
1. Telegram 功能必須獨立成單一模組，例如：
   - `pump_system/notify/telegram_notifier.py`
2. 交易主流程不可直接散落寫 HTTP request，必須透過 notifier 模組統一發送。
3. 需提供：
   - `send_info(...)`
   - `send_warning(...)`
   - `send_error(...)`
   - `send_trade(...)`
   之類的清楚接口
4. 若 Telegram 關閉，系統仍需可正常運作。
5. 若 Telegram 發送失敗，只能記錄 log，不可讓交易主流程崩潰。

--------------------------------------------------
十五、已有持倉跳過規則
--------------------------------------------------

1. 啟動時要同步帳戶持倉
2. 每次訊號觸發前也要再次確認該 symbol 是否已有持倉
3. 若已有持倉：
   - 直接跳過
   - 不可重複下單
   - 不可加碼
   - 不可補倉

4. 若同時持倉數已達 `MAX_CONCURRENT_POSITIONS`：
   - 直接丟棄新的進場訊號
   - 不排隊
   - 必須記 log / Telegram

--------------------------------------------------
十六、系統模組要求
--------------------------------------------------

你必須以模組化方式實作，至少拆成以下層次：

1. config
2. db
3. market_data
4. exchange
5. strategy
6. execution
7. fallback_stop
8. notify
9. cache 或 staging
10. state
11. utils

其中：
- `db` 層要優先重用 `db_util.py`
- `notify` 層要統一處理 Telegram
- `cache / staging` 層要管理未收盤 1m / 3m K bar 的本地暫存
- finalized K bar 才能進 DB
- 不要把 DB 寫入邏輯和策略判斷混在一起
- 不要把策略邏輯和交易所 API 呼叫混在一起
- 不要把 Telegram HTTP 呼叫散落在主流程裡

--------------------------------------------------
十七、日誌與審計要求
--------------------------------------------------

至少要記錄：
1. 每次訊號檢查結果
2. 為何未觸發 / 為何觸發
3. 1m / 3m 訊號判斷結果
4. quantity 計算過程
5. leverage / margin type 設定結果
6. 市價單結果
7. 止損價來源 K bar
8. 交易所止損單送單結果
9. retry 次數與結果
10. fallback CSV 寫入結果
11. fallback 平倉結果
12. WebSocket 斷線 / 重連 / 重新同步結果
13. server time offset 計算結果
14. rate limit / 429 / backoff / retry 紀錄
15. backfill / 增量更新結果
16. 是否因資金不足而改用「剩餘資金最大化進場模式」
17. 未收盤 K bar 暫存更新結果
18. K bar 收盤並寫入 DB 的結果
19. 哪些 K bar 因尚未收盤而被禁止寫入 DB
20. 本地暫存 CSV 更新 / 清理結果
21. Telegram 通知發送結果
22. 因功能測試模式而被攔下的真實下單事件

重要：
- log 不可明碼輸出 password / API key / secret / bot token / chat id
- 必須符合 `god_rule.md` 的 logging standard

--------------------------------------------------
十八、專案輸出要求
--------------------------------------------------

你必須直接交付完整專案，至少包含：

1. README.md
2. requirements.txt
3. .env.example
4. main.py
5. config.py
6. HANDOFF.md
7. 專案模組資料夾
8. logs/
9. data/ 或 state/（用來放 fallback CSV）
10. data/ 或 state/（用來放未收盤 K bar 暫存 CSV）

README 必須包含：
1. 安裝方式
2. `.venv` 使用方式
3. Testnet / 正式盤切換方式
4. 啟動方式
5. 參數說明
6. fallback 止損說明
7. Telegram bot 設定方式
8. WebSocket 重連與恢復說明
9. server time offset 校正說明
10. rate limit / retry / backoff 說明
11. 1m / 3m 訊號搭配說明
12. 資金不足時的最大化進場邏輯說明
13. PostgreSQL 表結構使用方式
14. `db_util.py` 如何被重用
15. 若額外新增 bulk insert adapter，需說明原因與範圍
16. 90 天歷史資料初始化 / 增量同步方式
17. 3m K bar 正式來源（直接 Binance 3m 或本地聚合）必須明確說明
18. finalized bars 與 in-progress bars 的分流方式
19. 未收盤 K bar 暫存 CSV 如何更新與清理
20. 功能測試模式用途與限制
21. 首次正式盤 BTCUSDT 功能測試流程
22. 風險警告
23. 所有模糊但重要處的最終工程定義

`.env.example` 至少包含：
- API_KEY
- API_SECRET
- TESTNET
- ENABLE_LIVE_TRADING
- FUNCTION_TEST_MODE=true
- FUNCTION_TEST_SYMBOL=BTCUSDT
- TELEGRAM_ENABLED=true
- TELEGRAM_BOT_TOKEN=
- TELEGRAM_CHAT_ID=
- DB_HOST
- DB_PORT
- DB_USER
- DB_PASS
- TARGET_NOTIONAL_USDT=300
- SYMBOL_BLACKLIST
- SYMBOL_WHITELIST
- EXCLUDED_BIG_CAPS
- SIGNAL 相關參數
- MAX_CONCURRENT_POSITIONS
- STOP_ORDER_RETRY_COUNT=3
- SERVER_TIME_SYNC_ENABLED=true
- SERVER_TIME_RESYNC_INTERVAL_SECONDS
- API_RETRY_MAX_ATTEMPTS
- API_RETRY_BACKOFF_BASE_SECONDS
- API_RETRY_BACKOFF_MAX_SECONDS
- RECV_WINDOW
- STOP_WORKING_TYPE
- LOG_LEVEL

--------------------------------------------------
十九、工程要求
--------------------------------------------------

1. 使用 Python
2. 使用 `.venv`
3. API KEY 不可寫死
4. DB 連線資訊不可寫死
5. Telegram bot token / chat id 不可寫死
6. quantity / price 精度建議使用 Decimal
7. 所有關鍵函式要有清楚 docstring
8. 所有模糊但重要的工程定義，要在 README 說明
9. 對 API 失敗要有錯誤處理
10. 不可無限重試
11. 若 `ENABLE_LIVE_TRADING=false`：
    - 系統仍需正常啟動
    - 仍需正常跑資料同步、訊號檢查、quantity 計算、下單前檢查與 log
    - 但不得真的送出任何交易所下單 / 平倉 / 止損單請求
12. `TESTNET=true` 與 `ENABLE_LIVE_TRADING=false` 是兩個不同開關，需分開處理
13. 重要操作前要建立快照或 rollback 方案
14. 任務完成前必須自我驗證，不得未驗證就宣稱完成
15. 若使用者已提供既有工具或資料流，必須優先檢查能否重用
16. 任務完成後必須更新 `HANDOFF.md`
17. 任務完成最後必須回報：
    `⏱️ 任務耗時：XX 分 XX 秒 | 🪙 Tokens (估算): IN XXk / OUT XXk | 💰 狀態: 成功/失敗/阻塞`

--------------------------------------------------
二十、禁止事項
--------------------------------------------------

1. 不要改成半自動人工確認進場
2. 不要加入固定止盈
3. 不要加入移動止損
4. 不要改成限價進場
5. 不要省略 fallback 止損 CSV 機制
6. 不要忽略已有持倉跳過規則
7. 不要只給片段
8. 不要只給偽代碼
9. 不要偷偷修改使用者指定條件
10. 不要假裝功能已完成
11. 不要因可用保證金不足以達到 300 USDT 目標持倉，就直接放棄該筆交易
12. 除非連交易所最小下單限制都無法滿足，否則必須盡可能用剩餘可用資金開出最大合法倉位
13. 不要忽略使用者已提供的 PostgreSQL 表結構
14. 不要自行改成別的表名或 schema
15. 不要只抓部分 USDT 永續交易對
16. 不要漏抓 1m 或 3m 任一個週期
17. 不要在任何 log / handoff / README / 對話輸出中明碼寫出 password / API key / token / secret / bot token / chat id
18. 不要把未收盤中的 K bar 寫入 PostgreSQL 正式表
19. 不要把 fallback CSV 與未收盤 K bar 暫存 CSV 混在一起
20. 不要在同一專案中混用「Binance 3m 直接資料」與「1m 聚合 3m」兩種正式來源
21. 不要因為首次正式盤只測 BTCUSDT，就把整個系統做成 BTCUSDT 專用版
22. 不要因為 BTCUSDT 不屬於小幣，而跳過此次 execution function test

--------------------------------------------------
二十一、交付順序
--------------------------------------------------

請依照以下順序工作，不要跳步：

Step 1
先列出你將建立的專案檔案樹

Step 2
說明 `god_rule.md` 與 `db_util.py` 將如何被本專案繼承 / 重用

Step 3
逐檔輸出完整內容

Step 4
最後補上：
- 啟動步驟
- `.env` 設定方式
- Telegram bot 設定方式
- PostgreSQL 連線方式
- 90 天歷史資料初始化流程
- 增量更新流程
- Testnet 測試流程
- 首次正式盤 BTCUSDT 功能測試流程
- fallback 止損驗證方式
- 未收盤 K bar 暫存驗證方式
- 正式盤啟用前檢查清單
- HANDOFF 摘要
- 資源耗時回報

--------------------------------------------------
二十二、最終目標
--------------------------------------------------

我要的是一套真的可以開始測試的 Python 專案。

不是教學文，
不是策略文章，
不是概念說明，
不是 TODO 清單。

直接交付完整可執行程式。