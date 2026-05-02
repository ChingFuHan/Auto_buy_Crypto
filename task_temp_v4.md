# Claude Task v4: 歷史資料補齊 + Aggressive Breakout 可審核回測

請依本專案規則執行一個「歷史資料補齊 + aggressive breakout 可審核回測」長任務。

本 v4 任務稿是在 `task_temp_v3.md` 基礎上補強：Phase 8 多切片量化門檻、token budget、dry-run 硬上限觸發語意、Layer 2 stop floor 二選一、schema dump 原始格式、sanity sample 自動化輸出、SignalEngine 函數名以實際 source 為準。

## 任務背景

目前 `SOLVUSDT` 2026-04-29 17:00 沒入場，已確認是被 `15m_not_compressed` 與 `15m_overheated` 擋下。先前 Layer 1 回測報告 `reports/aggressive_backtest_20260430.md` 被審核指出不可直接採信，原因包含：

1. 可能漏掉 ATR 條件。
2. `SOLVUSDT` future-bar 對齊結果明顯有 bug。
3. finalized close entry 的偏差方向是 mixed，不可直接 kill 或放行。
4. 回測腳本不可重現。

## 本次目標

1. 在不違反專案規則的前提下，補齊更多歷史 K 線資料。
2. 僅允許寫入 `public.semi_auto_price_future_*` 這類 `semi` 開頭歷史價格表。
3. 用可重現腳本做嚴格回測 audit，再決定是否值得新增 aggressive 分支。
4. 不修改正式交易邏輯，不修改 `.env`，不下單，不查/改交易所帳戶。

## 授權範圍

- 允許讀取 `god_rule.md`、`AGENTS.md`（若存在）、`README.md`、`HANDOFF.md`、`config.py`、`db_util.py`、`pump_system/strategy/signal_engine.py`、backfill 相關程式與測試。
- 允許使用既有 `.env` 的 DB 連線資訊，但不得輸出任何 secret。
- 允許 DB 唯讀查詢所有需要的 metadata、row count、min/max date、schema。
- 允許向 Binance public market data endpoint 讀取歷史 K 線資料。
- 允許只對以下表做 append-only 寫入：
  - `public.semi_auto_price_future_15m`
  - `public.semi_auto_price_future_3m`
  - 如程式已有支援且需要，也可包含 `public.semi_auto_price_future_1m`
- 寫入規則必須是：
  - `INSERT ... ON CONFLICT (code, da) DO NOTHING`
  - 禁止 `UPDATE`
  - 禁止 `DELETE`
  - 禁止 `TRUNCATE`
  - 禁止覆蓋歷史資料
  - 禁止改 schema
- 允許建立可重現的本地分析腳本與報告，例如：
  - `reports/aggressive_backtest_audit_YYYYMMDD.py`
  - `reports/aggressive_backtest_audit_YYYYMMDD.md`
  - `reports/aggressive_backtest_candidates_YYYYMMDD.csv`
  - `reports/aggressive_backtest_sanity_samples_YYYYMMDD.csv`
- 允許更新 `HANDOFF.md` 記錄進度與結論。

## 禁止事項

- 不得修改 `.env`。
- 不得切換 live/testnet。
- 不得建立新 API key。
- 不得呼叫交易所 private/account/order API。
- 不得下單。
- 不得啟動 `main.py run`。
- 不得停止現有交易程式，除非使用者另行明確要求。
- 不得修改交易策略正式程式碼。
- 不得用 `pip install --break-system-packages` 或污染 global 環境。
- 不得把腳本只放 `/tmp` 後刪掉；所有回測必須可重現。
- 若 local env 缺依賴且無法用專案 `.venv`，先停下回報，不要硬裝 global package。

## Phase 0：進場與安全確認

1. 先讀：
   - `god_rule.md`
   - `AGENTS.md`（若專案根目錄存在；其優先級低於 `god_rule.md`）
   - `README.md`
   - `HANDOFF.md`
2. 若本任務與上述規則衝突，先列出衝突，不要執行。
3. 明確列出本任務會觸碰的高風險規則與對應授權，例如 DB append-only 寫入、Binance public data 讀取、報告檔案建立；若有任何不確定是否越界，先停下回報。
4. 記錄 git HEAD。
5. 檢查工作區狀態，但不要 revert 任何既有變更。
6. 在 `HANDOFF.md` 先追加本任務開始紀錄，標明授權範圍與禁止事項。

## Phase 1：DB 與歷史資料盤點

1. 查詢 `public.semi_auto_price_future_15m`、`3m`、必要時 `1m`：
   - row count
   - distinct code count
   - min(da)
   - max(da)
   - 每個 symbol 的 min/max/count 分佈
2. 驗證每張目標表的 schema、欄位型別、primary key / unique constraints / indexes。報告中必須貼出 `\d public.semi_auto_price_future_15m` 等指令的原始輸出（或等價 `information_schema` 查詢的 raw rows），不得只用文字摘要描述欄位。
3. 在確認 `ON CONFLICT (code, da)` 對應實際 unique constraint 前，不得執行任何 DB 寫入；若 constraint 不存在或欄位名稱不符，先停下回報。
4. 檢查是否有近期資料缺口。
5. 檢查資料是否只包含目前仍交易 symbol，並在報告標註 survivor bias 風險。
6. 不得用「DB 內所有 symbol 近 7 天都有資料」推論「無 delisted bias」。只能說 DB 內現有 symbols 近期仍有資料；歷史已下架 symbols 是否缺失仍需標註為 survivor bias。
7. 輸出盤點摘要到報告，不要只在 terminal 顯示。

## Phase 2：補齊更多歷史資料

1. 使用專案既有 backfill / repository 寫入邏輯優先，不要重造一套 DB writer。
2. 只補 `semi_auto_price_future_*` 表。
3. 補資料前必須先做 dry-run estimate：
   - 預估 symbol 數
   - 預估 API calls
   - 預估新增 rows
   - 預估耗時
   - 預估 DB 寫入量
4. dry-run 硬上限（**以下任一條件觸發即停下回報，不得繼續執行**）：
   - 預估 API calls > 50,000。
   - 預估新增 rows > 2,000,000。
   - 預估 wall-clock > 2 小時。
   - 任一單表預估新增 rows > 該表現有 rows 的 50%。
   - 無法可靠估算上述任一項。
5. 優先補：
   - 15m：盡可能補到 Binance 可取得範圍或專案設定允許的最大範圍，但必須受 dry-run estimate 約束。
   - 3m：至少覆蓋 15m 回測所需期間，用於 Layer 2 in-progress approximation。
6. 每批寫入都必須使用 `ON CONFLICT DO NOTHING`。
7. 寫入前必須先記錄每張目標表的可審核快照，並寫入報告：
   - table
   - before row count
   - before min/max da
   - before distinct code count
8. 寫入後必須記錄：
   - table
   - after row count
   - inserted count
   - after min/max da
   - after distinct code count
9. 若遇到 Binance 429 或 API limit：
   - 最多依專案 retry 規則重試。
   - 超過就停下，標 `[BLOCKED]`，不要無限重試。

## Phase 3：建立可重現回測 audit 腳本

建立一個可重現腳本，放在 `reports/` 或明確的分析目錄，不要放 `/tmp`。

腳本要求：

1. 完全複製 `SignalEngine` 的指標邏輯：
   - lookback = 20
   - breakout_lookback = 12
   - atr_pct = avg((hi-lo)/cl) over previous finalized 20 bars；這是 percent ATR，不是標準 ATR。`cl` 必須使用該 finalized bar 自己的 close。
   - range = (max_hi - min_lo) / min_lo over previous finalized 20 bars
   - vol_ratio = current_bar.vol / avg(previous finalized 20 vol)
   - ret = (current_bar.cl - previous_close) / previous_close；`previous_close` 是 current bar 前一根 finalized 15m close。
   - breakout = current_bar.hi > max(previous finalized 12 hi)
   - prior_runup = range over previous finalized 5 bars
   - recent_green = consecutive green bars ending at previous finalized bar；green 定義必須是 `close_price > open_price`，不包含 current bar。
2. 報告必須包含 `SignalEngine` source 與回測腳本實作的 side-by-side 對照，至少覆蓋 atr_pct、range、vol_ratio、ret、breakout、prior_runup、recent_green。對照所引用的 SignalEngine 函數名稱以實際 source 為準（`pump_system/strategy/signal_engine.py` 中對應函數），不得依賴本任務稿中的猜測名。
3. Universal base filter 必須包含：
   - `ret >= 0.017`
   - `vol_ratio >= 2.0`
   - `breakout = True`
   - `prior_runup <= 0.040`
   - `recent_green <= 3`
   - `atr <= 0.015`
4. Bucket 定義：
   - Baseline：`range <= 0.035` 且 `ret <= 0.060`
   - A：`range > 0.035` 且 `ret <= 0.060`
   - B：`range <= 0.035` 且 `ret > 0.060`
   - C：`range > 0.035` 且 `ret > 0.060`
5. 每個 bucket 要輸出：
   - sample N
   - win rate
   - mean return after cost
   - median return
   - std
   - expectancy
   - MFE median / p90
   - MAE median / p10
   - -3% stop hit rate
   - -5% stop hit rate
   - bar-low stop hit rate
   - false stop rate
   - rough Sharpe
6. horizons：
   - 4 bars
   - 16 bars
   - 96 bars
7. 成本假設：
   - entry + exit + slippage 總扣 0.6%
   - 在報告中明確標示。

## Phase 4：Sanity Cases

腳本必須內建 sanity checks，至少包含：

1. `SOLVUSDT` 2026-04-29 17:00：
   - 必須歸類為 Bucket C。
   - 必須重算出：
     - ret 約 9.897%
     - range 約 5.843%
     - vol_ratio 約 77x
     - breakout=True
     - reason 應包含 range / overheat 類問題。
   - 上述 sanity 數值必須有量化容差：ret / range 誤差不得超過 0.05 個百分點，vol_ratio 相對誤差不得超過 1%，breakout 必須完全一致；超過即視為 sanity 失敗。
   - 必須能算出 4-bar future metrics，不可出現「不足 4 bars」錯誤，除非 DB 補齊後真的沒有資料。
2. 隨機抽樣 5-10 筆 candidate，由腳本自動將其前 20 bars 與後 4 bars dump 至 `reports/aggressive_backtest_sanity_samples_YYYYMMDD.csv`（或報告附錄表），含 symbol、bar open time、ohlcv、是否屬 lookback / future 區段；不得只在 terminal 顯示。
3. 若 sanity check 失敗，立刻停下，不產生最終策略結論。

## Phase 5：Layer 1 / Layer 1.5 / Layer 2

請不要只做單一 close-entry 回測。

至少做三種版本：

### Layer 1：15m finalized close 入場

- 這不是 optimistic upper bound，只是 close-entry baseline。
- 報告中禁止寫「Layer 1 負就直接 kill」。

### Layer 1.5：threshold-entry approximation

- entry price 用 `prev_close * (1 + 0.017)` 作樂觀近似。
- 必須標註這是 optimistic approximation，因為 volume / breakout 未必在該價格同時成立。
- optimistic approximation 不可單獨作為放行 aggressive 分支的依據。

### Layer 2：3m 子K approximation

- 用 `semi_auto_price_future_3m` 重建每根 15m 內的 3m 子K。
- 對每根 15m candidate，找出第一根 3m 子K，使得：
  - 3m 子K 的 high 或 close 已使 15m in-progress ret >= 0.017
  - 15m in-progress high 已 breakout
  - 15m in-progress 累積 volume / previous 20 finalized 15m avg volume >= 2.0
  - 其他 finalized-history 條件已過
- Layer 2 至少輸出兩種 entry 模式：
  - optimistic：3m high 觸及條件時，以 trigger threshold price 入場。
  - conservative：3m close 已滿足條件時，以 3m close 或 3m high 入場。
- 若 3m high 觸及條件但 3m close 掉回門檻以下，必須在報告中單獨統計，不能與 close-confirm 訊號混在一起。
- Layer 2 不可直接使用完整 15m finalized low 作為 `stop_reference_low`。
- Layer 2 的 stop reference 必須使用觸發當下之前已形成的 3m cumulative low（從 15m bar open 起到 trigger 3m bar 之前所有 3m bars 的 min low）；若做不到，需標示為 lookahead-biased stop，不可用於正式決策。
- 第一根 3m 子K 即觸發、無更早 in-progress low 可參照時，stop reference 預設使用 **trigger 3m bar 的 open** 作為 floor（保守口徑），並在報告中明確列出此 fallback；同時可額外輸出以 trigger 3m bar low 為 floor 的次要欄位作對照，但兩者不得混為同一統計。任何情況下不得產生 stop distance = 0 的假訊號。
- Layer 2 的 4 / 16 / 96 horizon 必須明確定義：
  - 從 trigger 之後開始計算，或
  - 從該 15m bar close 後開始計算。
  兩者不可混用；若兩者都輸出，必須清楚分表。
- 若 3m 無法精準重建累積 15m volume，要明確說明 approximation 方式。
- 若 3m volume 無法精準對齊 15m cumulative volume，Layer 2 結果只能標為 approximate，不可作 Phase 8 唯一依據。
- Layer 2 結果才可作為是否值得進一步設計 aggressive 分支的主要依據。

## Phase 6：主策略 Baseline 對照

1. Baseline 不能只當對照組，必須獨立報告。
2. 若 Baseline 在 conservative Layer 2 後仍為負，要明確標 `[RISK] 主策略可能沒有 edge`。
3. 若沒有 live trade history 表，明確說明無法做 live PnL 對比。
4. 不得把 `crypto_signal` 誤當成本 bot 的 trade history，除非先證明 schema 與本 bot 相關。

## Phase 7：報告輸出

寫入：

```text
reports/aggressive_backtest_audit_YYYYMMDD.md
reports/aggressive_backtest_candidates_YYYYMMDD.csv
reports/aggressive_backtest_sanity_samples_YYYYMMDD.csv
```

Markdown 報告必須包含：

1. 執行摘要。
2. 本次授權範圍與未做事項。
3. 歷史資料補齊狀態。
4. dry-run estimate 與實際寫入量對照。
5. DB 表 row count before/after 與 schema raw dump。
6. 資料範圍與 survivor bias 風險。
7. SignalEngine 等價性說明（含 side-by-side 對照）。
8. Sanity checks 與 sample CSV 連結。
9. Layer 1 / 1.5 / 2 結果表。
10. Baseline vs A/B/C 比較。
11. 對 `SOLVUSDT` 2026-04-29 17:00 的單獨案例分析。
12. 明確決策：
    - 不足以新增 aggressive 分支
    - 或值得做小倉位 aggressive prototype
    - 或主策略本身需優先 audit
13. 明確禁止把暫定結果直接上正式交易。

Candidate-level CSV 必須至少包含：

- symbol
- bar open time
- bucket
- atr
- range
- ret
- vol_ratio
- breakout
- prior_runup
- recent_green
- layer
- entry mode
- trigger_3m_open_time
- trigger_offset_in_bar_minutes
- entry price
- stop reference
- horizon
- exit price
- return after cost
- MFE
- MAE
- stop hit flags
- false stop flags

## Phase 8：決策規則

只有在以下條件同時滿足時，才可建議未來新增 aggressive 分支：

1. Bucket C 在 conservative Layer 2 entry 模式的成本後 expectancy > 0。
2. Bucket C 樣本數足夠，至少 N >= 100。
3. Bucket C 的 median return after cost >= 0，且不得低於 Baseline median。
4. -3% / -5% stop false stop rate 可接受。
5. Bucket C 不明顯劣於 Baseline。
6. `SOLVUSDT` sanity case 正常。
7. 回測腳本可重現，且沒有已知對齊 bug。
8. 多切片穩定性（量化門檻）：在 Bucket C × conservative entry mode 下，**4-bar 與 16-bar 兩個 horizon 必須同時 expectancy > 0**；且整體 A/B/C/Baseline × {4,16,96} bars × {optimistic, conservative} 共 24 個切片中，Bucket C 為正的切片數需 ≥ 3，否則視為證據不足。

補充規則：

- optimistic Layer 2 只能當上界，不可單獨作為放行依據。
- 如果只有 optimistic 為正、conservative 為負，結論應是「證據不足，不新增 aggressive 分支」。

否則結論應是：

- 不新增 aggressive 分支。
- 保持主策略不動。
- 或優先 audit 主策略 baseline。

## Phase 9：收尾

1. 更新 `HANDOFF.md`，記錄：
   - 做了哪些查詢與寫入
   - 補了哪些 semi 表
   - 寫入筆數
   - Phase 7 報告位置與 CSV 明細位置（以連結方式引用，不再重列 Phase 7 內容）
   - 結論
   - 風險與下一步
2. 不要 commit，除非使用者另行要求。
3. 最後回報：
   - 改了哪些檔案
   - 寫了哪些 DB 表
   - 沒碰哪些敏感項
   - 結論是否足以改策略
   - 資源耗時與 token 狀態

## 嚴格要求

- 先理解，再執行。
- 若任何規則衝突，先停下回報。
- 不要為了完成任務而放寬安全限制。
- 最重要的是：先 dry-run estimate，再補資料，再做可重現 audit，不直接 Layer 2 下結論。
- 如果直接說「預期 Bucket C +5%」或「直接 KILL」，就是跳結論，必須撤回。
- 預算上限（任一觸發即停下回報目前完成狀態、阻塞點與下一步，不得繼續長時間無回報執行）：
  - wall-clock 累計超過 2 小時仍未完成 Phase 7 報告。
  - token / context 使用接近模型上限（例如剩餘 context < 20%）。
  - 任務明顯超出可控成本或重複失敗無進展。
