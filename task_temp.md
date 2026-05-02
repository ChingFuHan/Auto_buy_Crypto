# Claude Task: 歷史資料補齊 + Aggressive Breakout 可審核回測

請依本專案規則執行一個「歷史資料補齊 + aggressive breakout 可審核回測」長任務。

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

- 允許讀取 `god_rule.md`、`README.md`、`HANDOFF.md`、`config.py`、`db_util.py`、`pump_system/strategy/signal_engine.py`、backfill 相關程式與測試。
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
- 允許建立可重現的本地分析腳本，例如：
  - `reports/aggressive_backtest_audit_YYYYMMDD.py`
  - `reports/aggressive_backtest_audit_YYYYMMDD.md`
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
   - `README.md`
   - `HANDOFF.md`
2. 若本任務與上述規則衝突，先列出衝突，不要執行。
3. 記錄 git HEAD。
4. 檢查工作區狀態，但不要 revert 任何既有變更。
5. 在 `HANDOFF.md` 先追加本任務開始紀錄，標明授權範圍與禁止事項。

## Phase 1：DB 與歷史資料盤點

1. 查詢 `public.semi_auto_price_future_15m`、`3m`、必要時 `1m`：
   - row count
   - distinct code count
   - min(da)
   - max(da)
   - 每個 symbol 的 min/max/count 分佈
2. 檢查是否有近期資料缺口。
3. 檢查資料是否只包含目前仍交易 symbol，並在報告標註 survivor bias 風險。
4. 輸出盤點摘要到報告，不要只在 terminal 顯示。

## Phase 2：補齊更多歷史資料

1. 使用專案既有 backfill / repository 寫入邏輯優先，不要重造一套 DB writer。
2. 只補 `semi_auto_price_future_*` 表。
3. 優先補：
   - 15m：盡可能補到 Binance 可取得範圍或專案設定允許的最大範圍。
   - 3m：至少覆蓋 15m 回測所需期間，用於 Layer 2 in-progress approximation。
4. 每批寫入都必須使用 `ON CONFLICT DO NOTHING`。
5. 寫入前後記錄：
   - table
   - before row count
   - after row count
   - inserted count
   - min/max date
   - symbol count
6. 若遇到 Binance 429 或 API limit：
   - 最多依專案 retry 規則重試。
   - 超過就停下，標 `[BLOCKED]`，不要無限重試。

## Phase 3：建立可重現回測 audit 腳本

建立一個可重現腳本，放在 `reports/` 或明確的分析目錄，不要放 `/tmp`。

腳本要求：

1. 完全複製 `SignalEngine` 的指標邏輯：
   - lookback = 20
   - breakout_lookback = 12
   - ATR = avg((hi-lo)/cl) over previous finalized 20 bars
   - range = (max_hi - min_lo) / min_lo over previous finalized 20 bars
   - vol_ratio = current_bar.vol / avg(previous finalized 20 vol)
   - ret = (current_bar.cl - previous_close) / previous_close
   - breakout = current_bar.hi > max(previous finalized 12 hi)
   - prior_runup = range over previous finalized 5 bars
   - recent_green = consecutive green bars ending at previous finalized bar
2. Universal base filter 必須包含：
   - `ret >= 0.017`
   - `vol_ratio >= 2.0`
   - `breakout = True`
   - `prior_runup <= 0.040`
   - `recent_green <= 3`
   - `atr <= 0.015`
3. Bucket 定義：
   - Baseline：`range <= 0.035` 且 `ret <= 0.060`
   - A：`range > 0.035` 且 `ret <= 0.060`
   - B：`range <= 0.035` 且 `ret > 0.060`
   - C：`range > 0.035` 且 `ret > 0.060`
4. 每個 bucket 要輸出：
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
5. horizons：
   - 4 bars
   - 16 bars
   - 96 bars
6. 成本假設：
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
   - 必須能算出 4-bar future metrics，不可出現「不足 4 bars」錯誤，除非 DB 補齊後真的沒有資料。
2. 隨機抽樣 5-10 筆 candidate，人工列出其前 20 bars 與後 4 bars，供審核。
3. 若 sanity check 失敗，立刻停下，不產生最終策略結論。

## Phase 5：Layer 1 / Layer 1.5 / Layer 2

請不要只做單一 close-entry 回測。

至少做三種版本：

1. Layer 1：15m finalized close 入場
   - 這不是 optimistic upper bound，只是 close-entry baseline。
   - 報告中禁止寫「Layer 1 負就直接 kill」。
2. Layer 1.5：threshold-entry approximation
   - entry price 用 `prev_close * (1 + 0.017)` 作樂觀近似。
   - 但必須標註這是 optimistic approximation，因為 volume / breakout 未必在該價格同時成立。
3. Layer 2：3m 子K approximation
   - 用 `semi_auto_price_future_3m` 重建每根 15m 內的 3m 子K。
   - 對每根 15m candidate，找出第一根 3m 子K，使得：
     - 3m 子K 的 high/close 已使 15m in-progress ret >= 0.017
     - 15m in-progress high 已 breakout
     - 15m in-progress 累積 volume / previous 20 finalized 15m avg volume >= 2.0
     - 其他 finalized-history 條件已過
   - entry price 可用該 3m close，或保守用該 3m high，兩者都輸出。
   - 若 3m 無法精準重建累積 15m volume，要明確說明 approximation 方式。
   - Layer 2 結果才可作為是否值得進一步設計 aggressive 分支的主要依據。

## Phase 6：主策略 Baseline 對照

1. Baseline 不能只當對照組，必須獨立報告。
2. 若 Baseline 在 Layer 2 後仍為負，要明確標 `[RISK] 主策略可能沒有 edge`。
3. 若沒有 live trade history 表，明確說明無法做 live PnL 對比。
4. 不得把 `crypto_signal` 誤當成本 bot 的 trade history，除非先證明 schema 與本 bot 相關。

## Phase 7：報告輸出

寫入：

```text
reports/aggressive_backtest_audit_YYYYMMDD.md
```

報告必須包含：

1. 執行摘要。
2. 本次授權範圍與未做事項。
3. 歷史資料補齊狀態。
4. DB 表 row count before/after。
5. 資料範圍與 survivor bias 風險。
6. SignalEngine 等價性說明。
7. Sanity checks。
8. Layer 1 / 1.5 / 2 結果表。
9. Baseline vs A/B/C 比較。
10. 對 `SOLVUSDT` 2026-04-29 17:00 的單獨案例分析。
11. 明確決策：
    - 不足以新增 aggressive 分支
    - 或值得做小倉位 aggressive prototype
    - 或主策略本身需優先 audit
12. 明確禁止把暫定結果直接上正式交易。

## Phase 8：決策規則

只有在以下條件同時滿足時，才可建議未來新增 aggressive 分支：

1. Bucket C 在 Layer 2 的成本後 expectancy > 0。
2. Bucket C 樣本數足夠，至少 N >= 100。
3. Bucket C 的 median return 不可明顯為負。
4. -3% / -5% stop false stop rate 可接受。
5. Bucket C 不明顯劣於 Baseline。
6. `SOLVUSDT` sanity case 正常。
7. 回測腳本可重現，且沒有已知對齊 bug。

否則結論應是：

- 不新增 aggressive 分支。
- 保持主策略不動。
- 或優先 audit 主策略 baseline。

## Phase 9：收尾

1. 更新 `HANDOFF.md`，記錄：
   - 做了哪些查詢與寫入
   - 補了哪些 semi 表
   - 寫入筆數
   - 報告位置
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
- 最重要的是：先補資料，再做可重現 audit，不直接 Layer 2 下結論。
- 如果直接說「預期 Bucket C +5%」或「直接 KILL」，就是跳結論，必須撤回。
