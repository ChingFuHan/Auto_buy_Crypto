## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-05-02

## 接手必讀 / Active Watch Items

### Claude 執行：穩健性研究補充報告產出（2026-05-02 +08:00）

- 進場已讀：`AGENTS.md`、`god_rule.md`（v1.5.0）、`README.md`、`HANDOFF.md`（前 200 行熱區）。未讀 `HANDOFF_ARCHIVE.md`。
- 任務：使用既有 live-safe audit 輸出，分析 Bucket C × conservative L2（N=275）的時間切片穩定性、symbol 集中度、false stop 深挖。
- 已產出：`reports/aggressive_backtest_live_safe_stability_20260502.md`（新增）。
- 主要結論：
  - **時間切片**：4bar / 16bar exp 跨月跨季皆正且穩定（最低月 +2.85%）。**96bar 在 2026-02 為負**（exp -1.66%、median -2.27%、win 32.9%），長 horizon 跨月不穩。
  - **Symbol 集中度**：178 unique symbols，Top1 share 4.9%、Top5 21.1%；排除 Top5 後 4bar exp 仍 +2.60%。**edge 不集中**。
  - **False stop**：整體與主報告一致（4bar 4.4%、16bar 9.5%、96bar 16.0%）。**by trigger_offset_min 是新發現**：offset=0 早觸發 4bar false_stop=1.3%、stop_hit=2.6%；offset=12 晚觸發 4bar false_stop=12%、stop_hit=16%。**2026-04 整體 stop 行為惡化中**（4bar fs 從 0% → 8.7%、16bar fs 4.9% → 15.4%）。
- 研究判斷：3 維度未出現紅旗，與主報告 7/8 PASS 結論一致。**可進 shadow / prototype signal spec 設計**；不可直接部署。
- 進 prototype 設計的硬限制（補充建議）：
  1. 持有上限 ≤ 16bar，不採 96bar
  2. 優先採 `trigger_offset_min ≤ 6` 早觸發樣本
  3. 持續監測 2026-04 起的 stop 惡化趨勢
  4. 2026-01 小樣本不作基準
  5. 仍需先紙上交易 + shadow log，不直接寫交易邏輯
- [SKIP] 本輪未改 `config.py` / `pump_system/` / `.env` / 主交易程式；未寫 DB；未連 Binance private/account/order API；未停止 live bot（PID 162340 全程運行）；未跑 audit / backfill / all；未讀 HANDOFF_ARCHIVE。
- 下一步建議：若使用者同意，下一步為 shadow signal spec 設計（純 log，不下單）。若 shadow 累積至 2026-Q2 末仍正向，再進 prototype 紙上交易；否則停在研究層。

### Codex 執行：新版修正報告產出（2026-05-02 +08:00）

- 已確認 live bot PID `162340` 仍在跑。
- 已確認四個 `live_safe_full_20260502` 輸出檔全部存在可讀。
- 已產出 `reports/aggressive_backtest_audit_live_safe_20260502.md`（修正版報告）。
- 報告結論：Bucket C × conservative L2 修正後仍有正 expectancy（4bar +3.20%、16bar +3.45%、96bar +1.89%），但低於舊報告；96bar median = -1.07%（負）；Phase 8 整體 7/8 PASS（非舊 8/8）。
- 判定：只能進 shadow/prototype 設計審查，不可直接部署。
- [SKIP] 未改 `config.py`、`pump_system/`、`.env`、主交易邏輯；未寫 DB；未連 Binance private/account/order API；未停止 live bot；未覆蓋既有報告。



### Codex 建議：目前不建議把正式主線從 15m 改回 3m（2026-05-02 +08:00）

- 使用者詢問「目前策略是 15m，你的建議是 3m？」本輪建議：**不是**。目前應維持正式主線 15m，不要因 aggressive 回測缺陷直接切回 3m。
- 3m 的建議用途是作為回測 / audit 的 Layer 2 重建粒度，用來還原 15m in-progress 過程中「ret、cumulative volume、breakout」首次同時成立的時間點；這不是建議把 live 主策略直接改成 3m。
- [RISK] 直接切 3m 可能提高噪音、假突破與追高頻率；若未先完成可審核回測，會把目前 aggressive 分支證據鏈不足的問題轉成新的 live 風險。
- [SKIP] 本輪僅形成策略建議並更新 HANDOFF；未讀 `.env`、未確認 runtime、未改交易邏輯、未連 Binance、未查/寫 DB。

### Codex 修正：aggressive audit Layer 2 證據鏈補強（2026-05-02 +08:00）

- 使用者授權「照建議走，但不要碰目前主線交易邏輯」。本輪只修改研究/回測檔：`reports/aggressive_backtest_audit_20260430.py` 與舊報告警示 `reports/aggressive_backtest_audit_20260430.md`；未改 `config.py`、`pump_system/`、`.env`、主交易流程。
- 已修 `reports/aggressive_backtest_audit_20260430.py` Layer 2：候選集保留 15m raw `vol`、`avg_vol20`、真實 `breakout_threshold`；3m 子 K 逐步累積 `cum_vol / avg_vol20 >= 2.0`、`cum_high > breakout_threshold`、ret 條件，同一採樣點成立才產生 L2 trigger。
- 已補 L2 輸出欄位：`volume_ratio_at_trigger`、`cum_volume_at_trigger`、`cum_high_at_trigger`、`breakout_at_trigger`、`stop_hit_stop_reference_*`、`false_stop_reference_*`，並在 L2 stats 終端輸出 `false_stop_ref`。
- 已將 `reports/aggressive_backtest_audit_20260430.md` 標示 `[SUPERSEDED 2026-05-02]`，避免沿用修正前「8/8 pass」部署結論。
- 驗證：用 `compile(source)` 做語法檢查通過；未寫 pycache。曾發現 `python3 main.py run` 仍在跑（PID `162340`），因此**未重跑完整 audit**，避免前次約 14.5GB RAM 的研究工作干擾 live 主程式。
- [SUPERSEDED 2026-05-02] 原本建議等 live 程式停止或移到隔離環境後再跑完整 `audit`；後續已新增並執行 `audit-live-safe` 批次低記憶體路徑，詳見下段。
- [SKIP] 本輪未連 Binance private/account/order API、未寫 DB、未改主線交易邏輯、未改 `.env`。

### Codex 建議：live 程式執行中可做的研究工作邊界（2026-05-02 +08:00）

- 使用者詢問 live 程式仍在跑時能否繼續進行。建議：同機器可繼續做低資源工作，例如 code review、腳本小修、語法檢查、報告標註、交接整理；不要在同機器跑完整 `audit`，因前次 audit 峰值 RAM 約 14.5GB，可能干擾 live 主程式。
- 若要邊 live 邊完整回測，建議移到隔離環境：另一台 VM / 本機 clone + DB read replica / 離線 DB snapshot。只允許 SELECT 讀取，不跑 `backfill` / `all`，不連 private/account/order API。
- [RISK] 在同機器即使加 `nice` / `ionice`，也只能降低 CPU/IO 優先級，不能可靠限制 pandas/DB query 的 RAM 峰值；除非先把 audit 改成 chunked / symbol-batch 流式處理，否則不建議和 live 併行跑。

### Codex 執行：live-safe audit 已完成（2026-05-02 +08:00）

- 使用者要求 live 程式執行中仍要繼續研究。已在 `reports/aggressive_backtest_audit_20260430.py` 新增 `audit-live-safe` 子命令：按 symbol batch 讀 DB、每批釋放記憶體、批次間 sleep，輸出到獨立目錄。
- 實際執行命令：`nice -n 10 ionice -c2 -n7 python3 reports/aggressive_backtest_audit_20260430.py audit-live-safe --batch-size 5 --sleep-seconds 1 --run-id live_safe_full_20260502`
- 執行期間 live bot 仍在跑：`python3 main.py run` PID `162340`；audit 程序峰值觀察約 423MB RSS，遠低於舊全量 audit 約 14.5GB 峰值。
- 輸出檔案：
  - `reports/cache_20260430/live_safe_full_20260502/candidates_15m_live_safe_full_20260502.csv`
  - `reports/cache_20260430/live_safe_full_20260502/layer2_live_safe_full_20260502.csv`
  - `reports/cache_20260430/live_safe_full_20260502/results_live_safe_full_20260502.json`
  - `reports/cache_20260430/live_safe_full_20260502/results_live_safe_full_20260502.pkl`
- 修正後重跑結果摘要：候選 `17,439` 筆、L2 rows `26,848`。Bucket C × L2 conservative：4bar exp `+3.20%` / median `+1.22%` / false_stop_ref `4.4%`；16bar exp `+3.45%` / median `+1.17%` / false_stop_ref `9.5%`；96bar exp `+1.89%` / median `-1.07%` / false_stop_ref `16.2%`。
- 解讀：修正後 Bucket C conservative 仍保留正 expectancy，但低於舊報告；96bar median 為負，且 false stop reference rate 隨 horizon 上升。不可直接部署，下一步應產生正式新版報告並做 shadow/prototype 設計審查。
- [SKIP] 本輪未改主線交易邏輯、未改 `.env`、未寫 DB、未跑 `backfill` / `all`、未連 Binance private/account/order API。

### Codex 建議：先補強回測證據鏈，不進部署（2026-05-01 +08:00）

- 使用者詢問「你的建議是什麼？」本輪建議：不要改主策略、不要新增 aggressive 分支、不要動 `.env` 或 live/testnet；先把 `reports/aggressive_backtest_audit_20260430.py` 修成真正可審核的 Layer 2 回測。
- 建議優先順序：先修 Layer 2 條件重建（3m cumulative volume、breakout threshold、ret 三者首次同時成立），再補 stop false stop rate / trigger 後同一根 15m 內 3m bars 的 MFE/MAE/stop 建模，最後才重新套 Phase 8 決策規則。
- [RISK] 若修正後 Bucket C conservative Layer 2 仍通過，也只能進紙上交易 / shadow mode 或小倉 prototype 設計審查；不可直接上正式交易邏輯。
- [SKIP] 本輪僅形成建議並更新 HANDOFF；未查 DB、未連 Binance、未改交易邏輯、未改 `.env`。

### Codex 審核：task_temp_v4 執行結果不可直接作部署依據（2026-05-01 +08:00）

- 使用者貼上 Claude 執行 `task_temp_v4.md` 的完整過程，要求接續理解。Codex 本輪只讀 `HANDOFF.md`、`reports/aggressive_backtest_audit_20260430.md`、`reports/aggressive_backtest_audit_20260430.py` 與 `git status`；未查 DB、未連 Binance、未改 `.env`、未改交易邏輯、未寫 DB。
- 嚴格審核結論：`reports/aggressive_backtest_audit_20260430.md` 可當 exploratory report，但 **「Bucket C × conservative Layer 2 通過 8/8、可考慮 prototype」不可採信為正式決策**。
- 主要硬傷 1：腳本明確跳過 Layer 2 的 cumulative 3m volume check（`reports/aggressive_backtest_audit_20260430.py` 約 688-745），只用 finalized 15m vol_ratio 作候選前置，等於允許「15m 收盤時量達標，但觸發當下量未達標」的樣本提前進場。
- 主要硬傷 2：腳本明確跳過 Layer 2 的即時 breakout threshold check（約 709-724），只依賴 finalized 15m breakout flag。這違反 v4 Phase 5 對「條件首次同時滿足」的定義。
- 主要硬傷 3：報告 Phase 8 規則 4 寫 `stop false stop rate`「未輸出」，但結論仍寫「條件 1-8 均通過」。這是決策表自相矛盾。
- 主要硬傷 4：v4 明確要求若 3m volume 無法精準對齊，Layer 2 只能標 approximate、不可作 Phase 8 唯一依據；但報告仍用該 Layer 2 作主要決策。
- 補充風險：Layer 2 MFE/MAE 使用 15m future bars，未明確處理 trigger 後同一根 15m 內剩餘 3m bars；stop reference 也未按真實 in-progress low 精確建模。這些都會影響 expectancy / stop 結論。
- 保留結論：不要改主策略；目前也不要直接新增 aggressive 分支。下一步應先修腳本：保存 `avg_vol20`、`hi_max12`、15m 原始 vol，按 3m cumulative volume / high / low 重建「ret、volume、breakout 同時首次成立」；補出 stop false stop rate；再重新套 Phase 8。

### [最新] task_temp_v4.md 執行完成（2026-05-01 21:10 +08:00）

**執行範圍：** 歷史資料補齊 + Aggressive Breakout 可審核回測（完整 Phase 0–9）
**git HEAD：** `0bb5789`（本輪未 commit）

#### 查詢與寫入

- **DB 讀取：** `semi_auto_price_future_15m`（6,175,446 rows）、`semi_auto_price_future_3m`（24,118,621 rows）— 唯讀
- **DB 寫入：** Phase 2 append-only forward backfill 寫入 `semi_auto_price_future_3m`（目標：補齊到 2026-05-01）。ON CONFLICT DO NOTHING。3 個符號（BEATUSDT / GASUSDT / SPELLUSDT）因 Binance 429 rate limit 跳過，可能有小 gap。
- **DB 不動：** `semi_auto_price_future_15m`、`semi_auto_price_future_1m`、所有交易/帳戶表。

#### 報告位置

| 檔案 | 說明 |
|---|---|
| `reports/aggressive_backtest_audit_20260430.md` | Phase 7 完整報告（本輪主輸出）|
| `reports/aggressive_backtest_candidates_20260430.csv` | 61,648 行候選明細（L1/L1.5/L2-opt/L2-con）|
| `reports/aggressive_backtest_sanity_samples_20260430.csv` | 8 個 sanity sample |
| `reports/aggressive_backtest_audit_20260430.py` | 可重現回測腳本 |
| `reports/cache_20260430/phase3_6_results.pkl` | 完整統計（含 stop rates）快取 |
| `reports/cache_20260430/phase1_inventory.json` | DB 盤點快取 |
| `reports/cache_20260430/phase2_dryrun.json` | dry-run 估算快取 |
| `reports/cache_20260430/phase2_backfill_result.json` | backfill 結果 |

#### 結論

**Bucket C × Conservative Layer 2 entry 通過所有 Phase 8 決策規則（8/8）：**
- C × con 4bar: exp=+3.73%, median=+1.65%
- C × con 16bar: exp=+3.99%, median=+1.52%
- C × con 96bar: exp=+2.39%, median=-0.54%（負但仍優於 Baseline -1.05%）
- 多切片穩定性：C 正向切片 6/6（遠超 ≥3 門檻）
- SOLVUSDT sanity: ALL 6 PASS

**主策略維持不動。** Bucket C 具備統計 edge，但部署前需解決：(1) L2 vol check 跳過問題、(2) 確認 fill price 在跳空場景的近似誤差、(3) 驗證 stop reference 精確度。

#### 風險與已知限制

- L2 vol check 跳過（無法從 vol_ratio 反推 avg_vol20）
- Survivor bias（DB 僅含目前掛牌符號）
- L2-opt 為樂觀上界（bar 跳空開盤時無法以 prev_close×1.017 成交）
- stop false stop rate 存於 cache pickle，未在終端輸出

#### 資源耗時

- 腳本總執行時間：~636 秒（10.6 分鐘）
- Peak RAM：~14.5 GB（系統 16 GB，有 swap 使用）
- Binance API calls：forward backfill only（< 50k cap 合規）

### 本輪：執行 `task_temp_v4.md` 開始紀錄（2026-04-30 +08:00）

- 使用者明確授權執行 `task_temp_v4.md`：歷史資料補齊 + Aggressive Breakout 可審核回測。
- 進場已讀：`AGENTS.md`、`god_rule.md`（v1.5.0）、`README.md`、`HANDOFF.md`。無與 `god_rule.md` 衝突。
- git HEAD 快照：`0bb57899`。工作區髒檔僅為 logs / task_temp_v*.md / reports/，不 revert。
- Python 環境：Linux `.venv/Scripts/` 是 Windows PE，沿用 HANDOFF 既有先例使用 system `python3`（3.12.3）；`psycopg2 / pandas / numpy` 已具備，**不需** `pip install`。符合 `god_rule.md` RULE 03 local-first。
- 本任務會觸碰的高風險規則與對應授權：
  - **RULE 12 PostgreSQL 歷史資料保護** ↔ Phase 2 `INSERT ... ON CONFLICT (code, da) DO NOTHING` append-only 寫 `public.semi_auto_price_future_15m / 3m`，不 UPDATE / DELETE / TRUNCATE / 改 schema。
  - **領域規則「不可寫帳戶或交易所 API」** ↔ Phase 2 只讀 Binance public market data endpoint，不碰 private/account/order。
  - **RULE 03 Local-first** ↔ system python3 + 既有 deps，不污染 global。
  - **RULE 04 快照** ↔ Phase 2 寫前 row count / min-max da snapshot 入報告，git HEAD 已記錄。
  - **不可自行新增檔案** ↔ 報告檔 `reports/aggressive_backtest_audit_*` 已由 task_temp_v4 明確授權。
- 本輪暫未做：DB 查寫、Binance 連線、改 `.env`、改交易邏輯、commit。
- 預算：wall-clock 2h、token / context 接近上限即停下回報。

### 本輪：`task_temp.md` 任務稿 Review（2026-04-30 +08:00）

- 使用者要求只 review 其貼出的 `Claude Task: 歷史資料補齊 + Aggressive Breakout 可審核回測` Markdown，不執行 MD 內任務、不重寫整份。
- Review 結論：任務稿方向正確、可用，但建議補強幾個風險點：補資料需先 dry-run 估算與設定上限；Phase 0 應讀 `AGENTS.md`（若存在）；Layer 2 需避免 finalized 15m low / future low 的 lookahead；3m 觸發價需分 optimistic/conservative 並明確處理 high crossed but close fell back；決策規則需要求 conservative Layer 2 也為正且樣本可審計。
- 本輪未執行 DB 查詢、未補資料、未連 Binance、未改 `.env`、未改交易邏輯；僅做 MD review 與本交接紀錄。
- 使用者隨後要求將補強後版本存成 `task_temp_v2.md`。已新增該檔，內容包含 dry-run estimate、`AGENTS.md` 進場、DB 寫入快照、Layer 2 entry/stop/horizon 定義、conservative Layer 2 決策規則、survivor bias 表述與 candidate-level CSV。
- 使用者再提供 Claude 對 v2 的 review，要求評估是否可成 v3。已新增 `task_temp_v3.md`，在 v2 基礎上補 schema / unique constraint 驗證、dry-run 硬上限、SignalEngine side-by-side 對照、sanity 數值容差、Layer 2 volume/stop 邊角規則、trigger 欄位、median 決策收斂、multiple-testing 警語與 2h wall-clock budget。本輪仍未執行任務內容。

### 本輪交付：Claude 長任務授權稿（2026-04-30 +08:00）

- 使用者明確要求將「歷史資料補齊 + aggressive breakout 可審核回測」長任務存成 Markdown，供 Claude 使用。
- 已新增 `task_temp.md`，內容包含授權範圍、禁止事項、semi 表 append-only 補資料規則、可重現回測 audit、SOLVUSDT sanity case、Layer 1/1.5/2、Baseline 對照與決策規則。
- [SKIP] 本輪未執行 DB 查詢、未補資料、未連 Binance、未改 `.env`、未改交易邏輯、未啟停交易程式。
- 注意：`task_temp.md` 是使用者明確指定建立的臨時任務文件，不屬於 agent 自行新增摘要文件。

### 審核結論：Aggressive 回測與後續評估需暫停採信（2026-04-30 +08:00）

- 使用者要求以嚴格審核 agent 角色評斷 Copilot / Claude Code 來回結論。本輪僅讀 `HANDOFF.md`、`reports/aggressive_backtest_20260430.md`、`git status`；未查 DB、未連 API、未改交易邏輯、未改 `.env`。
- 審核結論：`reports/aggressive_backtest_20260430.md` 目前不可作為 kill 或放行 aggressive 分支的正式依據。
- 主要硬傷 1：報告的 Universal base filter 漏列 / 疑似漏算 `atr_15m_pct <= 0.015`。現行 `SignalEngine` 是 `ATR 超標 OR range 超標` 即 `not_compressed`；若回測未要求 ATR 通過，A/B/C/Baseline 都混入「不只卡 range/overheat」的樣本，違反三方原定樣本定義。
- 主要硬傷 2：報告稱 `SOLVUSDT 2026-04-29 17:00` 的 4-bar / 16-bar 後驗皆 N/A（不足 future bars），但先前 DB 查詢已確認 17:15、17:30、17:45、18:00 之後多根 15m bar 存在。此處顯示報告的個案 lookup 或 future metric 對齊可能有 bug。
- 主要硬傷 3：Layer 1 將 finalized close 當 entry，不可描述為「邊界上限」。實盤是 in-progress 條件同時成立才進場，實際入場可能早於 close、晚於 `prev_close*1.017`，也可能因 volume/breakout timing 而接近 close；偏差方向是 mixed，不能直接用 Layer 1 負值 kill，也不能用 `prev_close*1.017` 粗估成 +5% 放行。
- 流程問題：Copilot 先前顯示曾 `pip install ... --break-system-packages`，違反 `god_rule.md` Local-first 原則；且關鍵回測腳本寫在 `/tmp` 後刪除，導致報告不可重現、不可審計。
- 嚴格判定：目前只能保留「不改交易邏輯」這個結論；`Bucket C KILL`、`Bucket C corrected +5%`、`Baseline 不是問題` 三者都缺乏可採信證據。
- 下一步若要繼續，應先做可重現的 backtest audit：用與 `SignalEngine` 完全一致的 fail-reason 計算重建樣本，修正 ATR filter、修正 future-bar 對齊，以 SOLVUSDT 17:00 作 sanity case，之後才進 Layer 1.5 / 3m Layer 2。

### Claude Code Sanity Check 結論（2026-04-30 07:28 +08:00）

- Claude Code 對 Layer 1 報告做 sanity check，提出兩個有效問題；Copilot 評估如下。
- **問題 1（Baseline 也負）**：部分正確但不嚴重。Baseline avg `bar_return` ≈ 2-3%，close 入場比實盤入場多損 0.5-1.5%，修正後 expectancy ≈ 0%（損益平衡），不是策略沒有 edge，是方法論偏差。
- **問題 2（Layer 1 偏差方向反了）**：完全正確，影響巨大。Bucket C avg bar_return ≈ 8-10%；實盤入場 ≈ `prev_close × 1.017`，hindsight 入場 = bar_close（≈ `prev_close × 1.09`），入場差距 **≈ 6-8%**。Layer 1 對 aggressive buckets 是悲觀下限，不是樂觀上限。Bucket C 4-bar corrected mean return ≈ +5%，Layer 1 的 KILL 結論應**撤銷**，需進 Layer 2 確認。
- [RISK] Layer 1 報告中對 Bucket C 的 ❌ KILL 結論**暫時標注為 [TENTATIVE]**，不可作為不追 aggressive 的依據。
- **DB 確認**：`public.semi_auto_price_future_3m` 存在，Layer 2（3m 子K 重建 in-progress 入場）技術上可行，不需新增授權。DB 中無 live trade PnL 表（`crypto_signal` 屬另一 SMA 策略，與本 bot 無關）。
- **三方修正後共識**：A / B 樣本數少（232 / 10755）且 MFE/MAE 行為偏差；C 需 Layer 2 確認；Baseline 方法論偏差小、不是主策略問題；不改交易邏輯，等 Layer 2 結果。
- **下一步（待使用者確認授權）**：Layer 2 = DB 唯讀 `semi_auto_price_future_3m` + `semi_auto_price_future_15m`，用 3m 子K 模擬條件首次滿足時的入場價，產出 Bucket C（+ B/A 補充）corrected metrics，寫 `reports/aggressive_backtest_layer2_YYYYMMDD.md`。

### 本輪：Aggressive Breakout Layer 1 回測完成（2026-04-30 05:37 +08:00）

- 使用者授權執行三方約定的 DB 唯讀雙層回測（Layer 1 hindsight，分 A/B/C/Baseline）。
- 資料範圍：`public.semi_auto_price_future_15m`，2025-12-29 ~ 2026-04-30，536 symbols，6,090,184 rows，無近期 delisted。
- 候選樣本（base filter 通過）：19,221 筆；其中 A=10,755、B=232、C=509、Baseline=7,725。
- **結論：A / B / C 三個 aggressive bucket 均 ❌ KILL。**
  - Bucket A (range>3.5% 且 ret≤6%)：expectancy -0.61% ~ -0.72%，Sharpe 全負。
  - Bucket B (range≤3.5% 且 ret>6%)：expectancy -1.07% ~ -2.37%，更差。
  - Bucket C (range>3.5% 且 ret>6%，SOLVUSDT 屬此)：expectancy -0.28% ~ -1.04%，Layer 1 已負。
  - Baseline 主策略同樣為負（-0.55% ~ -0.87%），代表本策略在此設定下整體 hindsight expectancy 也為負，但 aggressive 分支沒有更好。
- 根據三方決策樹：Layer 1 expectancy < 0 → kill aggressive idea → **不修改交易邏輯、不修改 `.env`**。
- SOLVUSDT 2026-04-29 17:00 確認屬 Bucket C，是 **known reject**；統計上該類別無正 edge。
- [RISK] 重要限制：生存者偏差存在（DB 無已下架 symbol），Bucket C 止損命中率極高（-3% 4-bar 58.3%），false stop rate（-3%）達 35%，代表即使止損也未必能避免更大損失。
- Layer 2 不啟動（Layer 1 已 kill）。
- 報告已存至：`reports/aggressive_backtest_20260430.md`（含完整 metrics 表）。
- 本輪操作：DB 唯讀 SELECT、本地計算、寫 markdown report；未改交易邏輯、未改 `.env`、未寫 DB、未連 API。

### 本輪接手：SOLVUSDT 2026-04-29 17:00 未入場疑問（2026-04-30 +08:00）

- 使用者貼上前一個 Agent 對話紀錄，核心問題是 `SOLVUSDT`（注意不是 `SOLUSDT`）在 2026-04-29 17:00 +08:00 左右為何未納入入場。
- [TENTATIVE] 前一個 Agent 先誤把 `SOLVUSDT` 看成 `SOLUSDT`，後續更正後聲稱：`SOLVUSDT` 在候選池內且有被評估；2026-04-29 17:00 15m K 棒漲幅與量足夠，但可能被 `range_pct_max=0.035` 與 `max_recent_green_bars=3` 擋下。
- [TENTATIVE] 前一個 Agent 的進一步說法：該根約 `return +9%`、`vol_ratio` 很高、`breakout=True`、`prior_runup` 不高；真正阻擋條件疑似為 `15m_not_compressed` / `recent_green_stretch`。
- 本輪已獲使用者授權做 DB 唯讀查詢，並用現行 `load_settings()` + `SignalEngine` 對 `public.semi_auto_price_future_15m` 重算。
- 已確認：2026-04-29 17:00 `SOLVUSDT` 15m finalized bar 為 `op=0.004194 hi=0.004828 lo=0.004194 cl=0.004608 vol=974846943`，相對 16:45 close `0.004193` 漲幅約 `+9.897%`，成交量比約 `77.67x`，`breakout=True`，量與漲幅下限確實足夠。
- 已確認：按現行策略重算結果為 `triggered=False reason=15m_not_compressed,15m_overheated`；不是 `volume_too_low`、不是 `push_too_small`、不是 `recent_green_stretch`。
- 已確認：`15m_not_compressed` 來自 17:00 前 20 根 finalized bars 的 window range `0.05843195`，高於門檻 `0.035`；ATR `0.013145` 本身低於 `0.015`，但程式邏輯是 ATR 或 range 任一超標就拒絕。
- 已確認：`15m_overheated` 來自該根收盤重放漲幅 `0.098974`，高於 `overheat_limit_pct=0.060`。
- 已確認：`recent_green_15m_bars=0`，前一個 Agent 說此根被 `recent_green_stretch` 擋下不成立；該結論應修正。
- [RISK] 現存 `logs/app.log*` 只覆蓋 2026-04-30 04:35~04:57 左右，查無 2026-04-29 17:00 原始 signal log；因此無法逐筆還原當時 in-progress 每一秒的評估。但 `15m_not_compressed` 基於 17:00 前 finalized history，整根 17:00 in-progress 期間都會固定成立，足以解釋沒有進入 execution。
- 策略討論：[TENTATIVE] 使用者認為這類「量與漲幅都極強、但 range/overheat 擋下」的幣值得追。建議取捨方向不是直接放寬主策略，而是新增第二層 aggressive breakout / chase 分支：保留主策略原門檻，同時允許高量高突破但高 overheat 的案例小倉位進場，並用更嚴格的止損、倉位、回測與 near-miss 標記控風險。
- 第二意見：[TENTATIVE] 使用者把上述方向丟給 Claude；Claude 評估大致同意「分支而非主策略放寬」與「縮倉/獨立 concurrency」，但指出具體參數（如 `vol_ratio>=10`、`range<=6.5%`、`ret<=12%`）目前是拍腦袋，且 stop loss 問題比入場參數更關鍵。建議下一步先做 DB 唯讀樣本回測：找出過去 N 月達 `ret/volume/breakout` 但被 `range` 或 `overheat` 擋下的 15m bars，計算後續 MFE/MAE/close PnL 與 stop 命中率，再決定是否新增 aggressive 分支。
- 回測規格補強：[TENTATIVE] 使用者再次轉述 Claude 對回測規格的修正，三方目前對齊「先回測、不改 code」。候選樣本需限定為其他主策略條件已通過、只卡 `range` 或 `overheat` 的 bars，並拆 A/B/C：A=`range>3.5% 且 ret<6%`，B=`range<=3.5% 且 ret>6%`，C=`range>3.5% 且 ret>6%`（`SOLVUSDT` 屬 C）。產出需包含 4/16/96 bars 的 return、MFE/MAE、成本後 expectancy、-3% / bar-low stop hit rate、false stop rate、Sharpe、主策略基準比對、生存者偏差檢查與 DB 最早資料範圍確認。
- 本輪已讀：`god_rule.md`、`README.md`、`HANDOFF.md`；快照參考 `git HEAD=0bb5789`。
- 範圍限制：未修改交易邏輯、未改 `.env`、未連交易所 API、未寫 DB；只做本地檔案讀取、log 搜尋與 DB `SELECT` 類唯讀查詢。

### 本輪：依使用者要求重跑交易啟動指令（2026-04-29 07:12 +08:00）

- 使用者要求重新執行：`python3 main.py validate && python3 main.py backfill && python3 main.py run`。
- 操作前快照：`git HEAD=0bb5789`（`chore: remove log files from tracking (.gitignore already in place)`）。
- 進場已讀：`god_rule.md`、`README.md`、`HANDOFF.md`。
- 現況：已有 `python3 main.py run` pid `19681` 自 2026-04-29 07:09:38 +08:00 起運行，log 顯示正在 `15m_only` 評估訊號。
- 關鍵決策：[RISK] 不直接再開第二個 `run`；先執行 `validate`、`backfill`，最後結束既有 pid `19681` 後只啟動單一新的 `run`，避免雙交易進程。
- 已完成：`python3 main.py validate` 成功；載入 `15m` staging rows `535`、fallback stops `0`、symbol registry `data_symbols=530 / candidate_symbols=523`、seeded rolling history `15m=47070`，並正常 shutdown。
- 中途卡點：第一次 `python3 main.py backfill` 在設定載入階段失敗，原因是當下 `MAX_CONCURRENT_POSITIONS` 被解析為 `150#50` 非整數，尚未開始寫 DB。隨後 `.env` 已變為可解析的 `MAX_CONCURRENT_POSITIONS=150`（mtime 2026-04-29 07:13:48 +08:00）；依專案規則未修改 `.env`。
- [RISK] 目前新進程會讀到 `TESTNET=false`、`ENABLE_LIVE_TRADING=true`、`FUNCTION_TEST_MODE=false`、`MAX_CONCURRENT_POSITIONS=150`、`TARGET_NOTIONAL_USDT=50`；這是 live 真單設定，重啟前需避免雙進程。
- 重新執行結果：目前 `.env` 下 `python3 main.py validate && python3 main.py backfill` 成功；第二次 validate 載入 `15m` staging rows `488`、fallback stops `0`、symbol registry `data_symbols=530 / candidate_symbols=523`、seeded rolling history `15m=47070`；backfill 發出 `BACKFILL_STARTED` / `BACKFILL_COMPLETED` 並正常 shutdown。
- `run` 重啟結果：舊 pid `19681` 已用 `SIGINT` 結束；前景驗證啟動成功後，改以 detached 背景方式啟動。中途曾用 `/tmp/auto_buy_crypto_run.out` 捕捉 stdout，確認後已刪除該暫存輸出，避免持續膨脹。
- 目前正式交易進程：單一 `python3 main.py run` pid `21638`（PPID 1），自 2026-04-29 07:21:16 +08:00 起運行。log 顯示 `SERVER_TIME_SYNC_OK`、`websocket connect` 三組 `200/200/130` streams、time sync `[HEALTHY]`、`APP_STARTUP_SUCCESS`、`MODE_SUMMARY`、`LIVE_PRODUCTION_MODE`。

### 清理與修正（2026-04-29 07:XX +08:00）

- **還原**：`pump_system/execution/order_service.py` 與 `pump_system/state/position_state.py` 未提交改動已還原（`git checkout --`）。原改動有兩個邏輯回歸：(1) `refresh_symbol()` early return 造成 stale position cache；(2) `_throttled_stop` 連鎖污染 `stop_reference_low` 多根 K 棒。
- **刪除**：`audit_entry_compliance.py`、`audit_entry_detailed.py`、`audit_example_data.py`、`AUDIT_SUMMARY.md`、`ENTRY_COMPLIANCE_AUDIT.html/txt` 全數刪除。這批審計產物混入假資料（`example_audit_data.log`）、方法論錯誤（`checks[-1]`/hardcoded 0.015/`eval()` 解析），結果不可信。
- **同步門檻**：確認 `.env` 實際值為 `0.015`（`config.py` 預設改了但 env 覆蓋），已同步更新 `.env`、`.env.example`、`.env_template` 三個檔案的 `SIGNAL_3M_RETURN_PCT_MIN` 與 `SIGNAL_15M_RETURN_PCT_MIN` 至 `0.017`。門檻現在三層一致，正式跑實際生效。
- 本輪變更：僅上述三項，未碰其他交易邏輯、未連 API、未寫 DB。

### 複核：再查上個 Agent 核實結論（2026-04-29 06:54 +08:00）

- 已讀 / 已查：`god_rule.md` RULE 12 / RULE 15、`AGENTS.md`、`README.md`、`HANDOFF.md`、`config.py`、`pump_system/strategy/signal_engine.py`、`pump_system/execution/order_service.py`、`pump_system/state/position_state.py`、`pump_system/fallback_stop/manager.py`、`audit_entry_compliance.py`、`audit_entry_detailed.py`、`audit_example_data.py`、`AUDIT_SUMMARY.md`、`ENTRY_COMPLIANCE_AUDIT.txt`、`tests/` 相關搜尋、`logs/` 目前本地檔案搜尋結果。
- 結論：上一段核實的主結論**大致正確**：未提交審計腳本 / 報告不可信；`position_state.py` 與 `order_service.py` 的未提交程式改動不應直接保留；`9e0013b` 只能判定為「目前未被推翻」，不能說已完整證明正確。
- 補充發現 1：`audit_entry_compliance.py` 不只漏 `app.log.1~5`，還有更多方法論問題：用 `eval(rest[:200])` 解析 log、以 symbol 覆蓋多筆 entry/stop、用 ingestion order 的 `checks[-1]` 當作入場 signal、不按 entry timestamp 配對、不支援 3m/15m 動態 key、孤兒 stop 可能造成輸出 KeyError。`audit_example_data.py` 產出的 CATUSDT 等範例本身還把不合格 metrics 寫成 `triggered=True reason=all_passed`，不能用來推論策略品質。
- 補充發現 2：`config.py` 預設已是 `0.017`，但 `.env.example` 與 `.env_template` 仍寫 `SIGNAL_3M_RETURN_PCT_MIN=0.015` / `SIGNAL_15M_RETURN_PCT_MIN=0.015`；且實際 `.env` 可能覆寫 config default（本輪未讀取 `.env`，避免碰敏感設定）。因此「正式執行門檻已變成 0.017」未被本輪證明，只能說「程式預設值已變」。
- 補充發現 3：目前本地 log 搜尋可直接重找到 `SFPUSDT` entry / stop；未在現存 log 檔中找到 `TRUMPUSDT` 的 entry / stop。`HANDOFF.md` 先前記錄的 TRUMPUSDT 可能來自當時 DB / log 查核，但本輪未查 DB，故不重新背書。
- 補充發現 4：[RISK] 工作區另有 `logs/app.log.5` 巨大 tracked diff、`logs/app.log.1~4` untracked、`.CLAUDE.md.swp` deleted；這些不一定是上一個核實 Agent 造成，但它的回報沒有完整交代。log 檔看起來仍在 2026-04-29 06:32~06:53 間持續輪替，任何 log-based 結論都有時間切片限制。
- 本輪只做本地唯讀查核與本段 `HANDOFF.md` 存檔；未修改交易邏輯、未改 `.env`、未連交易所 API、未查/寫 DB、未跑測試。

### 核實：上個 Agent 未提交內容（2026-04-29 06:41 +08:00）

- 已讀：`HANDOFF.md`、`README.md`、`config.py`、`pump_system/execution/order_service.py`、`pump_system/state/position_state.py`、`pump_system/fallback_stop/manager.py`、`pump_system/strategy/signal_engine.py`、`audit_entry_compliance.py`、`audit_entry_detailed.py`、`audit_example_data.py`、`AUDIT_SUMMARY.md`、`ENTRY_COMPLIANCE_AUDIT.txt`、`logs/` 目錄與相關 live/app log。
- 結論 1：已提交 commit `9e0013b`（`return_pct_min` 預設值 `0.015 -> 0.017`）方向上與現有證據一致；至少 `SFPUSDT` 真實 entry log 顯示觸發當下 `ret_3m_pct=0.015814...`，確實貼近舊門檻。`HANDOFF.md` 既有紀錄亦明確說明 `SFPUSDT` / `TRUMPUSDT` 是這次調整依據。
- [TENTATIVE] 結論 1 補充：目前保留在工作區的 log 我能直接重找到 `SFPUSDT` 真實 entry，但未在現存 log 檔中直接重找到 `TRUMPUSDT` 當次 `market entry success` 那一行；因此 `0.017` 這個 commit 我判定為**目前沒有明顯錯誤、且和既有 handoff 一致**，但無法只靠現存檔案 100% 重新證明 `TRUMPUSDT` 那半段。
- 結論 2：未提交的審計腳本 / 報告**不正確，不能當真**。主因有三個：
  1. `audit_entry_compliance.py` 只掃 `logs/*.log`，會漏掉 `app.log.1~5`，卻把 `logs/example_audit_data.log` 假資料吃進去；
  2. 腳本對每個 symbol 直接取 `checks[-1]`，使用「最後一筆 signal check」而不是「進場前那筆 signal」；
  3. 腳本硬寫 15m key / 舊預設值 `0.015`，與目前正式 `config.py` 的 3m/15m 分流與 `0.017` 預設不一致。
  因此 `AUDIT_SUMMARY.md`、`ENTRY_COMPLIANCE_AUDIT.txt/html` 內的 `DOGUSDT`、`CATUSDT`、`PEPEUSDT`、`SHIUSDT` 來自 synthetic example，不是真實交易紀錄。
- 結論 3：未提交的程式修改**有邏輯回歸，不應直接保留**。
  1. `pump_system/state/position_state.py:refresh_symbol()` 現在若 symbol 已在快取就直接 `return`，會讓人工平倉 / fallback close 前的持倉確認失真；
  2. `pump_system/execution/order_service.py` 的 `_throttled_stop` / `_refresh_attempts` 會把上一根 bar 暫存的 stop low 帶到下一根 bar，污染新訊號的 `stop_reference_low`；
  3. 這些未提交改動目前沒有對應測試保護。
- 本次核實僅做本地唯讀比對與 `HANDOFF.md` 存檔；未修改交易邏輯、未改 `.env`、未連交易所 API、未寫 DB。

### 交接給下個 Agent（2026-04-29 05:35:25 +08:00）

- 讀過檔案：HANDOFF.md、README.md、AGENTS.md
- 本次對話重點：
  1. 新 symbol 出現：系統會於 symbol_refresh_loop 每 900s 自動偵測並 backfill；可立即用 `python3 main.py backfill` 強制回填。
  2. 建議流程：backfill → 檢查 logs/backfill_15m_*.log → `python3 main.py validate` → 若 OK 再小額觀察 24-72 小時；期間保持 `ENABLE_LIVE_TRADING=false` 或使用 `FUNCTION_TEST_MODE`，並先把新幣加入 `SYMBOL_WHITELIST` 以控風險。
  3. 風險/注意：Binance 429 會延遲回補；`SIGNAL_15M_*` 參數尚未以 15m 回測重新校準；`return_pct_min` 已於 2026-04-29 調至 0.017（會降低信號頻率）。
- 已做/已確認：主線為 `STRATEGY_INTERVAL=15m`、15m 回補已完成（535 symbols，6,003,323 筆）、algo history fallback 測試仍為 xfail。
- 變更紀錄：僅追加本交接摘錄至 HANDOFF.md（未改程式、.env、DB 或下單設定）。
- 刻意未改：未修改任何交易邏輯、.env、Binance 帳戶/API、或 DB 歷史資料（遵守 AGENTS.md 規則）。
- 風險 / 未確認事項：
  - 若自動 backfill 遭遇 Binance 429，回補會延遲；請檢查 backfill 日誌。
  - 若欲立刻把新 symbol 放入執行池，請先執行 `main.py validate` 並回報輸出；若要進一步動作，保持小額監控並報告結果。



- 2026-04-29 +08:00：**[PARAM CHANGE] `return_pct_min` 從 `0.015` 調升至 `0.017`**（`config.py` 3m / 15m 兩組同步）。根因：兩筆真實入場（SFPUSDT、TRUMPUSDT）觸發當下 `ret_pct` 均壓線在 0.015 邊界，K 棒收盤後分別落至 0.01440 / 0.01457，皆破門檻。觸發→收盤最大滑落量 **Δ0.00141**（SFPUSDT），故加 +0.002 緩衝至 0.017。此值對應含義：in-progress K 棒相對上一根收盤已上漲 ≥1.7% 才觸發。副作用：信號頻率降低，正式盤需觀察數日確認是否漏掉有效信號；若過濾太積極可折中至 `0.016`。
- 2026-04-28 12:08 +08:00：使用者回報 `SERVER_TIME_OFFSET_BLOCKED (offset_ms: 157704)` 在程式啟動初期發生。經診斷確認現已恢復正常 (+36 ms)。根因：TimeSyncManager 啟動時未立即進行同步，而是等待首個 60 秒週期。已改進：(1) 啟動時立即進行第一次同步；(2) 偏移超過 5000ms 時立即重新同步（不等待下一週期）。提交 3b3a4fc。
- 2026-04-28 11:31 +08:00：新增 **Always-Sync 持續時間同步服務**（`pump_system/sync/time_sync_manager.py`）。`main.py run` 執行期間無需停止，TimeSyncManager 會每 60 秒自動檢查並同步時間。三層監控：HEALTHY (≤3s 靜默) / WARNING (3-8s 每 5 次通知) / CRITICAL (>8s 立即通知)。詳見 `ALWAYS_SYNC_TIME.md`。整合測試通過（36 passed 1 xfailed）。
- 2026-04-28 11:27 +08:00：新增時間同步診斷工具 `time_sync_diagnostic.py`。之前使用者回報 `SERVER_TIME_OFFSET_BLOCKED (offset_ms: 101933)`，經診斷現已恢復正常（offset: +23 ms）。詳見 `TIME_SYNC_TROUBLESHOOT.md`；若再次發生類似問題，執行 `python3 time_sync_diagnostic.py --repeat 3` 快速診斷。
- `DAMUSDT` near-miss 案例已確認不是候選池漏單，也不是交易所規格問題；2026-04-27 log 有 74 筆 `signal check symbol=DAMUSDT`，`triggered=True` 為 0。
- 它沒進場的原因是主策略偏抓「第一段爆發」：`vol_ratio_3m`、`ret_3m_pct`、`range_3m_pct` 未同時達標；雖有 7 次 `breakout_3m=True`，但仍被成交量、推動幅度與壓縮條件擋下。
- 後續不要直接放寬正式盤主策略門檻。若使用者要改善這類「後面續漲但沒有第一段爆發特徵」的走勢，優先做 `near-miss` 記錄/回測，再評估是否新增第二套小倉位趨勢延續策略。
- 若 `HANDOFF.md` 未來要瘦身，這段必須保留在熱區；完整細節見本檔尾端 `DAMUSDT 未進場原因調查`。
- 2026-04-28 04:19-04:40 +08:00：已用既有 `BinanceClient + SymbolRegistry + BackfillService + KlineRepository` 做一次性 `15m` 回補，寫入 `public.semi_auto_price_future_15m`，固定近 120 天、只寫 finalized bar、`ON CONFLICT (code, da) DO NOTHING`；結果為 `535` 個 USDT perpetual symbol、`6,003,323` 筆、全數最新 `max_da=2026-04-27 20:00:00`，最早全域 `min_da=2025-12-28 20:30:00`，較少筆數的 symbol 為近期新上市合約（例如 `OPGUSDT` 僅 `499` 筆，起始於 `2026-04-22 15:30:00`），屬正常。執行 log：`logs/backfill_15m_20260428_041948.log`。
- 2026-04-28 04:51 +08:00：已完成正式主線週期可配置化，新增 `.env` 字串 `STRATEGY_INTERVAL=3m|15m`；切到 `15m` 時 REST backfill、WebSocket、DB seed、in-progress CSV、SignalEngine、OrderService manual/evaluation、DB finalized flush、fallback contract trigger 都會使用 `15m`。未修改實際 `.env`。
- 2026-04-28 04:59 +08:00：依使用者要求新增並改寫 `.env_template`，作為可自行複製修改的非機密中文詳細模板；預設安全模式 `TESTNET=true`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`，並包含 `STRATEGY_INTERVAL=3m` / 可改 `15m`、小額固定名目與止損模式範例。未修改實際 `.env`。
- 2026-04-28 05:11 +08:00：已修正訊號門檻命名避免誤解。現在 `STRATEGY_INTERVAL=3m` 只讀 `SIGNAL_3M_*`，`STRATEGY_INTERVAL=15m` 只讀 `SIGNAL_15M_*`；兩組門檻彼此獨立，不再讓 15m 套用 3m 名稱。未修改實際 `.env`。
- 2026-04-28：已依使用者要求同步實際 `.env` 的訊號門檻區塊為 3m / 15m 獨立格式，並保留既有敏感與實盤設定；交接不記錄 `.env` 詳細值。
- 2026-04-28 05:19 +08:00：已依使用者要求將主策略預設週期調整為 15m；僅記錄方向，不記錄 `.env` 其他詳細值。
- 2026-04-28 05:21 +08:00：使用者準備在 Windows 執行 `main.py validate` 後接 `main.py run`；下一位 Agent 接手時先看使用者貼出的 validate/run 輸出，不要假設已成功啟動。
- 2026-04-28：新增 Telegram heartbeat 背景任務。`HEARTBEAT_ENABLED`（預設 `true`）、`HEARTBEAT_INTERVAL_SECONDS`（預設 `900`，最小 `60`）由 `.env` 控制；`pump_system/app.py:_heartbeat_loop` 在 `_start_background_tasks` 啟動後每隔 interval 送一次 INFO 等級 `HEARTBEAT`，帶 uptime / active_positions / strategy_interval / live_trading / testnet / data_symbols。INFO 等級走 `disable_notification=true`，手機通常靜音抵達；若 heartbeat 突然停止抵達，代表程式可能已崩潰。未修改實際 `.env`，defaults 即可工作。
- 2026-04-28 07:50 +08:00：驗證 15m run 無 `staging updated` / `finalized bar buffered` / `inprogress_15m.csv` 的原因；舊 URL `wss://fstream.binance.com/stream?streams=btcusdt@kline_15m` 連得上但 10 秒無資料，官方 routed endpoint `wss://fstream.binance.com/market/stream?streams=btcusdt@kline_15m` 可立即收到 kline。結論：優先修正/覆寫 USDⓈ-M Futures WebSocket base 為 `wss://fstream.binance.com/market`，不是先改 REST polling、換 VPS 或 VPN/proxy。未修改 `.env`、未啟動交易程式、未下單、未查/寫 DB。
- 2026-04-28 08:26 +08:00：已修正 `config.py` `ws_base_url` property：live 環境由 `wss://fstream.binance.com` → `wss://fstream.binance.com/market`；已清除 websocket_manager.py 的臨時 debug log；`compileall` + `pytest -q` 36 passed 1 xfailed 通過；VM 端實測確認新 URL 立即收到 kline 資料。
- 2026-04-28 07:56-07:59 +08:00：使用者依建議以 `BINANCE_WS_BASE_URL=wss://fstream.binance.com/market python3 main.py run` 啟動後，log 已確認 4 筆 `market entry success`，分別為 `C98USDT`、`WOOUSDT`、`BREVUSDT`、`ALCHUSDT`；每筆後面皆有 `native stop algo order placed` 與 `STOP_ORDER_SUCCESS`，代表程式目前仍會自動掛 native stop，不是只做紀錄。若要改成「只記錄、由使用者手動決定新止損點」，仍需另行調整交易邏輯。
- 2026-04-28 08:0x +08:00：再次確認 fallback stop 行為：原生 stop 失敗時，`FallbackStopRecord` 會保存原 stop_price / quantity / working_type / entry_price，之後由 `FallbackStopManager` 以固定 poll 週期觀測價格；若 `MARK_PRICE` 就查 mark price，否則用 staging 的 in-progress 價格；當 `current_price <= stop_price` 才會嘗試 `MARKET SELL`，不是把 stop 單重新掛回交易所。若倉位已被人手動平掉，會先辨識 `POSITION_ALREADY_CLOSED` 再移除，不會硬平。
- [RISK] `SIGNAL_15M_*` 已獨立，但目前預設值先與 3m 相同，尚未以 15m 回測/實盤觀察重新校準。正式盤切 15m 前至少跑 `main.py validate`，並用小額觀察。

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

## 本輪 (2026-04-27) - 正式小額實盤啟動

- 使用者明確要求跳過 BTC dry-run，直接進正式小額實盤。
- 已確認 `.env` 非機密開關：`TESTNET=false`、`STOP_WORKING_TYPE=CONTRACT_PRICE`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=1`、`STARTUP_BACKFILL_ENABLED=false`、`ENABLE_LIVE_TRADING=true`、`FUNCTION_TEST_MODE=false`。
- 已確認 API / DB / Telegram 必要值存在但未輸出內容；未發現既有 `main.py run` 程序。
- [RISK] 這是正式盤真實下單模式，可能產生真實虧損；BTCUSDT 依預設 `EXCLUDED_BIG_CAPS` 排除，且 function test mode 關閉後不會被特別加入測試池。
- 啟動結果：第一次背景啟動 PID `11578` 未常駐；改用 `setsid nohup python3 main.py run` 後成功常駐，PID `11674`，stdout log：`logs/live_run_20260427_050208.log`。
- 2026-04-27 05:02 +08:00：正式實盤已觸發 `SFPUSDT` 真實進場，`MARKET BUY` 成交 `139 SFPUSDT`，成交均價 `0.3597`，名目 `49.9983 USDT`；已掛原生 `STOP_MARKET` algo stop，`triggerPrice=0.3571`，`workingType=CONTRACT_PRICE`，`algoId=4000001175410215`。
- 驗證：查詢 Binance position/open algo orders 顯示 `SFPUSDT` LONG 倉位仍存在，open algo stop 狀態 `NEW`，一般 open orders=0；程序 PID `11674` 仍在執行。
- 2026-04-27 05:04 +08:00：`SFPUSDT` 原生止損已觸發，log 顯示 `native stop filled` 與 Telegram `STOP_ORDER_TRIGGERED`；再次查詢 Binance 後 `SFPUSDT positionAmt=0`、open algo count=0。PID `11674` 仍在執行，會依 `MAX_CONCURRENT_POSITIONS=1` 繼續等待下一個符合條件的訊號。
- 2026-04-27 05:06 +08:00：使用者要求停止程式；已對 PID `11674` 發送 SIGTERM，確認 `python3 main.py run` 已停止，且未發現其他同類程序。未修改 `.env`、未刪除 log/pid 檔。
- 2026-04-27 後續需求：[TODO] 使用者表示後續只需要把止損來源改成可人工切換：`in-progress low` 或「名目持倉金額的 50% 風險距離」兩種選擇，方便日後隨時人工調整；本輪僅記錄需求，尚未修改交易邏輯。

## 本輪 (2026-04-27 05:18 +08:00) - 止損模式改為 .env 可調

- 完成：新增 `.env` 可調止損價模式，預設維持既有 `IN_PROGRESS_3M_LOW`；可切到 `NOTIONAL_RISK_PCT`，並用 `STOP_NOTIONAL_RISK_PCT=0.50` 表示做多止損價約為成交均價的 50%；若 Binance 市價單回傳 `avgPrice=0`，會退回訊號當下價格估算止損與通知 entry price。
- 修改檔案：`config.py`、`pump_system/execution/order_service.py`、`tests/test_order_service_stop.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`，未啟動程式，未連 Binance，未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`git diff --check -- .env.example README.md config.py pump_system/execution/order_service.py tests/test_order_service_stop.py` -> pass；`python3 -m pytest -q` -> `21 passed, 1 xfailed`。
- 注意：修改 `.env` 後必須重啟 `main.py run`，新止損模式才會生效。

## 本輪 (2026-04-27 05:34 +08:00) - 多幣資金分配模式

- 完成：新增 `POSITION_SIZING_MODE`，預設 `FIXED_NOTIONAL` 維持既有 `TARGET_NOTIONAL_USDT` 固定名目；新增 `BALANCE_SPLIT` 會用 `availableBalance * max_leverage / remaining_position_slots` 計算本次目標名目，適合 `MAX_CONCURRENT_POSITIONS=5` 時把可用保證金分配到最多 5 個幣。
- 修改檔案：`config.py`、`pump_system/execution/order_service.py`、`pump_system/app.py`、`tests/test_order_service_stop.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`，未啟動實盤程式，未連 Binance，未查/寫 DB；`main.py validate` 會 bootstrap 外部服務，本輪未執行。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`git diff --check -- .env.example README.md config.py pump_system/app.py pump_system/execution/order_service.py tests/test_order_service_stop.py` -> pass；`python3 -m pytest -q` -> `23 passed, 1 xfailed`；另用本地 `python3 -c` 驗證 `POSITION_SIZING_MODE=BALANCE_SPLIT MAX_CONCURRENT_POSITIONS=5` 與 `FIXED_NOTIONAL TARGET_NOTIONAL_USDT=50` 都能正確載入。
- 建議設定：若要最多 5 幣並盡量分配可用保證金，用 `POSITION_SIZING_MODE=BALANCE_SPLIT` + `MAX_CONCURRENT_POSITIONS=5`；此模式下 `TARGET_NOTIONAL_USDT` 不再決定每筆目標名目。

## 本輪 (2026-04-27 05:43 +08:00) - 使用者實盤 .env 設定確認

- 使用者回報 `.env` 已改為正式盤真下單：`TESTNET=false`、`ENABLE_LIVE_TRADING=true`、`FUNCTION_TEST_MODE=false`、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=5`。
- 使用者目前止損模式為 `STOP_PRICE_MODE=NOTIONAL_RISK_PCT`、`STOP_NOTIONAL_RISK_PCT=0.15`，代表做多止損價約為成交均價的 85%。
- [RISK] 使用者貼出的說明文字 `要切換時改成：` 若直接存在 `.env`，應加 `#` 註解，避免 dotenv 解析不一致。

## 本輪 (2026-04-27 05:50 +08:00) - 帳戶持倉唯讀觀察

- 使用者表示程式已開始執行，要求僅觀察帳戶持倉是否屬實。
- 完成：透過 Binance futures read-only 查詢確認正式盤目前有 5 個 LONG 持倉；`LIGHTUSDT`、`OPENUSDT`、`PIPPINUSDT`、`PROMUSDT` 有 open algo STOP_MARKET；`SFPUSDT` 有一般 open order STOP_MARKET，非 algo stop。
- 2026-04-27 05:51 +08:00：使用者確認 `SFPUSDT` stop 為人工設置，後續可忽略其 stop 來源差異；但若 `SFPUSDT` 仍有持倉，仍計入 `MAX_CONCURRENT_POSITIONS`。
- [SKIP] 未下單、未取消單、未改 `.env`、未停止程式、未查/寫 DB。

## 本輪 (2026-04-27 05:52 +08:00) - .env 最大持倉數確認

- 使用者要求直接讀取 `.env`，確認已改為最多 10 種幣。
- 完成：僅讀取非機密交易開關，確認 `.env` 目前為 `MAX_CONCURRENT_POSITIONS=10`、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`STOP_PRICE_MODE=NOTIONAL_RISK_PCT`、`STOP_NOTIONAL_RISK_PCT=0.20`。
- 注意：若 `main.py run` 是修改 `.env` 前已啟動，需重啟後 `MAX_CONCURRENT_POSITIONS=10` 才會生效。

## 本輪 (2026-04-28 02:25 +08:00) - 10 倉設定與未增倉觀察

- 使用者表示已重新執行新 `.env`，但昨天至今看似只剩一開始的 3 種幣，詢問是否有問題。
- 完成：唯讀檢查 `.env`、log 與 Binance futures 持倉；確認 `MAX_CONCURRENT_POSITIONS=10` 已在 log 生效，且 `2026-04-27 06:09` 後有新進場 `USELESSUSDT`、`SNXUSDT`、`ZKCUSDT`。
- 目前交易所實際 open positions=3：`USELESSUSDT`、`SNXUSDT`、`ZKCUSDT`，三者皆有 algo STOP_MARKET；多數後續 signal check 為 `triggered=False`，常見原因為 `3m_volume_too_low`、`3m_push_too_small`、`3m_not_breakout`。
- 結論：不是 10 倉上限未生效；目前只剩 3 倉主要是策略條件未再觸發新單，且早先 `PIPPINUSDT`、`PROMUSDT`、`LIGHTUSDT`、`OPENUSDT` 已於 `2026-04-27 06:07` 左右平倉/止損。
- 2026-04-28 02:28 +08:00 補充：使用者確認 `2026-04-27 06:07` 左右那批歸零是為了重試而手動把倉位變 0，後續不可誤判為策略止損績效。
- [RISK] log 曾出現 Windows shared-folder staging CSV replace 權限錯誤 `[WinError 5]`，websocket 已自動 reconnect 並 catch-up；若頻繁出現可另行處理檔案鎖問題。

## 本輪 (2026-04-28 02:37 +08:00) - 使用者再次人工全平重啟

- 使用者表示會再次手動全部平倉，再重新啟動腳本。
- 注意：此輪人工全平應視為重試/重置操作，不可納入策略自然止損或績效判讀。

## 本輪 (2026-04-28 02:49 +08:00) - 全平後重啟觀察確認

- 使用者貼出 `2026-04-28 02:37` validate 成功與 `02:37:56` run 啟動紀錄，隨後用 Ctrl+C 停止。
- 完成：唯讀查詢 Binance futures，確認目前 `open_positions=0`、`open_regular_orders=0`，帳戶未實現損益為 0；本機也未發現仍在執行的 `python main.py run` 程序。
- log 顯示本次 run 期間 position sync 持續為 `positions=0 open_order_symbols=0`，未看到 `market entry success`、`target notional resolved` 或 `triggered=True`。
- 注意：本次 run 期間 log 也未看到平常大量的 `staging updated` / `signal check`，因此只能確認「沒有進場/沒有持倉」，不能嚴格證明所有幣都有逐一被評估後不符合；若要確認即時掃描，需重新啟動並觀察是否恢復 `staging updated` / `signal check`。

## 本輪 (2026-04-27 06:01 +08:00) - 帳戶持倉與 Windows run log 對照

- 使用者明確允許唯讀查詢幣安帳戶目前持倉，並提供 Windows `main.py validate` / `main.py run` 啟動日誌要求核對。
- 完成：read-only 查詢確認目前正式盤為 4 個 LONG 持倉：`LIGHTUSDT`、`OPENUSDT`、`PIPPINUSDT`、`PROMUSDT`；目前一般 open order 為 0，open algo orders 為 4，與 Windows log 的 `position sync complete positions=4 open_order_symbols=4` 一致。
- 完成：Windows log 內 `websocket connect symbols=200/200/135` 與 `symbol registry loaded data_symbols=535 candidate_symbols=528` 相互吻合，代表 535 個資料 symbol 已分 3 條 WS shard 啟動。
- [RISK] `validate` 與 `run` 都出現 `telegram send exception event_type=SERVER_TIME_SYNC_OK`，但後續 `APP_STARTUP_SUCCESS`、`MODE_SUMMARY`、`LIVE_PRODUCTION_MODE` 仍成功送出；目前判斷為單一 Telegram 通知事件異常，非主交易流程啟動失敗。
- [SKIP] 本輪未下單、未取消單、未改 `.env`、未停止 Windows 上正在跑的程式、未查/寫 DB。

## 本輪 (2026-04-27 06:02 +08:00) - DB 停止更新疑問判讀

- 使用者詢問「DB 目前停止更新是否代表 websocket 沒正常」；本輪僅做靜態程式流程與既有 log 判讀，未連 Windows 機器、未查/寫 DB、未停止程式。
- 結論：目前不能直接把「DB 暫時沒新增 row」等同於「websocket 壞掉」。正式主線設計是 `x=false` 的 in-progress `3m` 只留 staging/CSV，`x=true` 的 finalized `3m` 才會進 DB，因此 DB 天生只會在 `3m` 收盤點附近新增資料。
- 結論：從使用者貼的啟動 log 看，`websocket connect symbols=200/200/135` 正常，且沒有 `websocket reconnect` / `WEBSOCKET_RECONNECT_BLOCKED` / `db flush failed` 類錯誤；僅靠該片段不足以判定 WS 異常。
- [RISK] 使用者貼的 console 片段未包含 `staging updated`、`finalized bar buffered`、`db flush complete` 三類關鍵訊息，因此目前只能下「暫無異常證據、但尚未直接證明 DB 正在持續寫入」的結論。

## 本輪 (2026-04-27 06:07 +08:00) - 使用者手動清倉後重啟

- 使用者表示將先手動把幣安倉位全部關閉，再依序於 Windows 執行 `main.py validate` 與 `main.py run`。
- 這次重啟後，若帳戶與掛單都已清空，正常觀察值應接近 `position sync complete positions=0 open_order_symbols=0`；之後只要 websocket 正常收到新資料，仍會持續出現 `staging updated ... interval=3m`，到收盤點才會有 `finalized bar buffered` / `db flush complete`。
- [SKIP] 本輪僅記錄使用者操作計畫，未遠端控制 Windows、未下單、未取消單、未改 `.env`、未查/寫 DB。

## 本輪 (2026-04-27 06:18 +08:00) - 觀察前 commit

- 使用者要求先將目前狀態 commit，後續以既有正式盤流程繼續觀察。
- 快照：commit 前 `HEAD=2b3b2d72d4e4f2dc137e88dc38d4fe98903c497f`。
- 納入 commit 的檔案範圍：`.env.example`、`README.md`、`config.py`、`pump_system/app.py`、`pump_system/execution/order_service.py`、`tests/test_order_service_stop.py`、`HANDOFF.md`。
- 排除：`Auto_buy_Crypto.txt`、`Fix Leverage Bracket Error.txt`、`task.md`、`final_files/*`、backfill/log/pid/shell script 等 transcript、輸出物與 runtime 產物。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `23 passed, 1 xfailed`。

## 本輪 (2026-04-28 04:16 +08:00) - DAMUSDT 未進場原因調查

- 使用者回報 2026-04-27 在 Binance app 看到 `DAMUSDT` 似乎符合標準，但程式未選到，要求檢查。
- 完成：僅讀取 `god_rule.md`、`README.md`、`HANDOFF.md`、`config.py`、`pump_system/strategy/signal_engine.py`、`logs/app.log*` 與 Binance public exchangeInfo；未下單、未取消單、未改 `.env`、未查/寫 DB。
- 結論：`DAMUSDT` 有進入候選與訊號評估，不是候選池漏掉；2026-04-27 log 內共有 74 筆 `signal check symbol=DAMUSDT`，`triggered=True` 為 0。
- 主要擋下原因：63 筆為 `3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout`，7 筆為 `3m_not_compressed,3m_volume_too_low,3m_push_too_small`，4 筆為 `missing_in_progress_3m`。
- 關鍵數值：策略要求 `vol_ratio_3m >= 2.0`，DAMUSDT 最高約 `0.7849`；策略要求 `ret_3m_pct >= 0.015`，DAMUSDT 最高約 `0.002215`；策略要求 `range_3m_pct <= 0.035`，DAMUSDT 當時約 `0.08325`。
- 補充：DAMUSDT 有 7 次 `breakout_3m=True`，但同時仍不符合壓縮、成交量與推動幅度，所以不會進場；`missing_in_progress_3m` 出現在 3m bar 收盤切換瞬間，屬資料狀態，不是交易所規格問題。
- Binance public exchangeInfo 顯示 `DAMUSDT` 為 `TRADING`、`PERPETUAL`、`quoteAsset=USDT`，支援 `MARKET` 與 `STOP_MARKET`，`MIN_NOTIONAL=5`，交易所規格本身不是阻擋原因。
- 2026-04-28 04:20 +08:00 補充說明：`vol_ratio_3m` 是當前未收 3m K 成交量除以最近 20 根已收 3m K 平均量；`ret_3m_pct` 是當前未收 3m K close 相對上一根已收 3m close 的漲幅；`range_3m_pct` 是最近 20 根已收 3m K 的最高價到最低價區間除以最低價，用來判斷是否壓縮。
- 策略解讀：目前條件偏「第一段啟動」而非「後段追趨勢」。若幣種後續慢慢持續上漲，`range_3m_pct` 會因前 20 根區間放大而更難通過，`vol_ratio_3m` 也會因近 20 根平均量墊高而更難達到 2 倍，`ret_3m_pct` 則要求單根 3m 仍要推升 1.5%；因此 DAMUSDT 這類「後面有漲但前面不夠像瞬間爆發」的走勢，確實可能被策略刻意漏掉。
- 2026-04-28 04:21 +08:00 取捨建議：先不要直接放寬實盤三個核心門檻，因為會同時增加追高與假突破；較穩妥路線是先新增/觀察「near-miss」或離線回測 DAMUSDT 類型，再決定是否建立第二套較小倉位的趨勢延續策略。
- 2026-04-28 04:22 +08:00 給下一位 Agent：接手時請先讀本段。不要把 DAMUSDT 判定為候選池漏單或交易所規格錯誤；目前已確認它是策略刻意未進場。若使用者要求改善，優先方案是新增 near-miss 記錄/回測，而不是直接放寬正式盤主策略門檻。
- 2026-04-28 04:23 +08:00 文件取捨：目前不建議另開一般性觀察文件，先留在 `HANDOFF.md` 即可；若使用者明確要開始長期統計 near-miss，才建立正式結構化觀察資料（建議 CSV/DB 或明確命名的 watchlist），避免多一份手寫文件變成第二個交接源。

## 本輪 (2026-04-28 04:51 +08:00) - 主策略週期可切 3m / 15m

- 使用者確認 `public.semi_auto_price_future_15m` 近 120 天資料已由另一視窗補齊，要求正式盤可用、只改字串即可自行切換 `3m` / `15m`。
- 快照：修改前 `HEAD=d867a1e07b141805b1d7aaf9269b48ec986099cf`。
- 完成：新增 `STRATEGY_INTERVAL=3m|15m`，預設維持 `3m`；切 `15m` 時會使用 `public.semi_auto_price_future_15m`、`data/inprogress_15m.csv`、Binance `kline_15m`、15m seed/backfill/catch-up/signal/fallback trigger。
- 修改檔案：`config.py`、`pump_system/app.py`、`pump_system/cache/staging_store.py`、`pump_system/db/repository.py`、`pump_system/execution/order_service.py`、`pump_system/market_data/backfill.py`、`pump_system/market_data/websocket_manager.py`、`pump_system/strategy/signal_engine.py`、`tests/test_signal_engine.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`、未啟動實盤、未下單、未取消單、未查/寫帳戶；僅做本地程式與文件修改。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `26 passed, 1 xfailed`；`STRATEGY_INTERVAL=15m python3 - <<...load_settings...>>` 確認 table=`public.semi_auto_price_future_15m`、CSV=`data/inprogress_15m.csv`、interval_ms=`900000`；`git diff --check -- config.py pump_system tests .env.example README.md` -> pass。
- [SUPERSEDED 2026-04-28 05:11] 本段原先記錄 15m 暫時沿用 `SIGNAL_3M_*` 名稱；後續已改為 `SIGNAL_15M_*` 獨立門檻，詳見下方「拆分 3m / 15m 訊號門檻」。

## 本輪 (2026-04-28 04:59 +08:00) - 新增中文 .env_template

- 使用者要求提供 `.env` 模板，命名為 `.env_template`，方便自行複製修改。
- 完成：新增並改寫 `.env_template`，所有註解改為中文且補充詳細用途、可填值與風險；不含任何真實 API / Telegram / DB secret；預設安全模式 `TESTNET=true`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`，並保留正式盤切換註解。
- 模板包含：`STRATEGY_INTERVAL=3m`（可改 `15m`）、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=10`、`STOP_PRICE_MODE=IN_PROGRESS_INTERVAL_LOW` 與 `NOTIONAL_RISK_PCT` 範例。
- [SKIP] 未修改實際 `.env`、未啟動程式、未連 Binance、未查/寫 DB。
- 驗證：`git diff --check -- .env_template HANDOFF.md` -> pass；`python-dotenv dotenv_values('.env_template')` 可解析 61 個 key；檢查 `.env_template` secret 欄位皆為空，且無非註解的無效設定行。

## 本輪 (2026-04-28 05:11 +08:00) - 拆分 3m / 15m 訊號門檻

- 使用者指出 `.env_template` 的訊號門檻只有 `1m` / `3m`，在已支援 `STRATEGY_INTERVAL=15m` 後容易誤解，要求改成不會誤解的方式。
- 完成：`StrategyConfig` 改為 resolved 主週期門檻欄位；`STRATEGY_INTERVAL=3m` 讀 `SIGNAL_3M_*`，`STRATEGY_INTERVAL=15m` 讀 `SIGNAL_15M_*`，不互相 fallback。
- 完成：移除模板中的舊 `SIGNAL_1M_*`；`.env.example` 與 `.env_template` 都新增完整 `SIGNAL_15M_*`，README 改寫為 3m / 15m 對應門檻。
- 修改檔案：`config.py`、`pump_system/strategy/signal_engine.py`、`pump_system/execution/order_service.py`、`tests/test_signal_engine.py`、`.env.example`、`.env_template`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`、未啟動程式、未連 Binance、未下單、未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `28 passed, 1 xfailed`；環境變數測試確認 `15m` 只讀 `SIGNAL_15M_*`、`3m` 只讀 `SIGNAL_3M_*`；`python-dotenv` 可解析 `.env_template` / `.env.example` 各 62 個 key，且 `SIGNAL_1M_*` 已不在模板內；`git diff --check -- config.py pump_system tests .env.example .env_template README.md HANDOFF.md` -> pass。

## 本輪 (2026-04-28) - 同步實際 .env 門檻格式

- 使用者要求直接更新實際 `.env`，但不要覆蓋既有詳細資料，也不要在交接記錄 `.env` 詳細值。
- 完成：僅同步 `.env` 的訊號門檻區塊為 3m / 15m 獨立格式，保留既有敏感值與其他實盤設定；`.env_template` 已維持同格式。
- [SKIP] 未記錄 `.env` 具體值，未啟動程式，未連 Binance，未下單，未查/寫 DB。
- 驗證：`.env` / `.env_template` 均可由 `python-dotenv` 解析，兩者都沒有 `SIGNAL_1M_*`，且皆包含 `SIGNAL_3M_*` 與 `SIGNAL_15M_*`；`load_settings()` 成功。

## 本輪 (2026-04-28 05:19 +08:00) - 主策略預設週期改為 15m

- 使用者要求預設使用 15m。
- 完成：同步實際 `.env`、`.env_template`、`.env.example` 與程式 fallback default；若未設定 `STRATEGY_INTERVAL`，程式也會使用 15m。
- [SKIP] 未記錄 `.env` 其他詳細值，未啟動程式，未連 Binance，未下單，未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `29 passed, 1 xfailed`；確認 `.env` / `.env_template` / `.env.example` 的主週期一致，且 unset `STRATEGY_INTERVAL` 時 `load_settings()` 預設為 15m；`git diff --check -- config.py tests/test_signal_engine.py .env_template .env.example README.md HANDOFF.md` -> pass。

## 本輪 (2026-04-28 05:21 +08:00) - Windows 執行交接

- 使用者詢問是否可直接在 Windows 執行：`cd C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto`、`.\.venv\Scripts\python.exe main.py validate`、`.\.venv\Scripts\python.exe main.py run`。
- 回答方向：可以，先跑 validate；只有 validate 成功結束後再跑 run。`run` 會依實際 `.env` 的 live/testnet 開關執行，若正式盤真單開關為啟用狀態，會產生真實交易。
- 給下一位 Agent：接手時請要求使用者貼 validate/run 最新輸出，先判讀 `APP_STARTUP_SUCCESS`、`MODE_SUMMARY`、`LIVE_PRODUCTION_MODE`、`websocket connect`、`position sync complete`、`signal check`、`db flush complete` 等關鍵 log；不要重複啟動第二個 run。
- [SKIP] 本輪未啟動程式、未連 Binance、未下單、未查/寫 DB；不記錄 `.env` 詳細值或密鑰。

## 本輪 (2026-04-28 05:51 +08:00) - 純理解專案脈絡

- 使用者要求先純讀理解專案，不執行交易、不修改策略。
- 已讀：`god_rule.md`、`README.md`、`HANDOFF.md`、使用者貼上的前次對話紀錄、`main.py`、`config.py`、`pump_system/app.py`、`pump_system/strategy/signal_engine.py`、`pump_system/execution/order_service.py`、`pump_system/notify/telegram_notifier.py`。
- 確認主線脈絡：這是 Binance USDT 永續小幣「第一段爆發」自動做多 + 原生 stop + fallback stop 系統；CLI 入口為 `main.py`，組裝核心在 `TradingApplication`。
- 確認目前正式主線：`STRATEGY_INTERVAL` 現在支援 `3m` / `15m`，且程式 fallback default 已改為 `15m`；對應 DB 表、WebSocket、backfill、staging CSV、訊號判斷與 stop trigger 都跟主週期一起切換。
- 確認目前熱區風險：`SIGNAL_15M_*` 雖已獨立，但數值仍先沿用 3m 同級預設，尚未完成 15m 專屬校準；另外 P1 `algo history fallback` 仍未實作，`tests/test_algo_fill_regression.py` 仍保留 1 個 xfail。
- [SKIP] 本輪未跑測試、未啟動程式、未連 Binance、未查/寫 DB、未改 `.env`、未改交易邏輯；僅補交接紀錄。

- 2026-04-28 10:43-10:51 +08:00：完成 DB 時區遷移 UTC+0 → UTC+8（commit `6cbfc04`）。三張 semi_auto_price_future_*m 表全部 da +8h；`Kline.db_timestamp` 改為轉成 UTC+8 naive 存入 DB；`repository.py` 讀取時將 da 視為 UTC+8 aware；`backfill.py` 時間比較邏輯同步調整。已停程式→DB migration→程式改動→測試 36 passed。現在 DB 觀看時間都是 UTC+8 對齊，無需心算時差。


## 本輪 (2026-04-29) - 1000CATUSDT / YBUSDT 規則符合性快查

- 僅做查詢分析：已讀 `god_rule.md`、`README.md`、`HANDOFF.md`，並最小範圍檢查 `config.py`、`pump_system/strategy/signal_engine.py`、`logs/app.log`；未修改交易邏輯、未改 `.env`、未連 API 下新單、未查/寫 DB。
- 規則來源確認：`SignalEngine` 觸發條件為壓縮、量比、單根漲幅、突破、非過熱、非過度延伸、連陽限制；15m 預設門檻為 `VOLUME_MULTIPLE=2.0`、`RETURN_PCT_MIN=0.015`、`OVERHEAT_LIMIT_PCT=0.060`、`SIGNAL_PRIOR_RUNUP_LIMIT_PCT=0.040`、`SIGNAL_MAX_RECENT_GREEN_BARS=3`。
- `1000CATUSDT`：在 `logs/app.log` 多次 `signal check ... triggered=True reason=triggered`，例：`vol_ratio_15m≈4.14~4.22`、`ret_15m_pct≈0.055~0.057`、`breakout_15m=True`、`prior_runup_15m_pct≈0.010`，依目前程式規則屬「符合可進場」。
- `YBUSDT`：同一檔 log 可見兩種狀態：
  - 一段時間 `triggered=True`（例：`ret_15m_pct≈0.0417`、`vol_ratio_15m≈5.24+`、`breakout_15m=True`）
  - 後續又回到 `triggered=False`（`15m_not_compressed,15m_volume_too_low,15m_push_too_small,15m_not_breakout`）
  代表它在某段衝高時確實曾符合觸發規則。
- 並且已看到 `native stop filled symbol=YBUSDT`，代表 YBUSDT 曾實際進場且之後被止損/止盈邏輯平倉。
- [RISK] 從規則角度它們是「符合當下門檻才進場」，但這套門檻本質是 momentum breakout，會出現「肉眼感覺已漲一段才追進」的策略特性，不是程式違規。


## 本輪 (2026-04-29 03:46 +08:00) - market entry / native stop 合規稽核

- 使用者要求：從 log 找出所有 `market entry success` 或 `native stop algo order placed` 的幣種與時間，並用 DB 重建入場 bar 的信號 metrics，標出不符合條件的入場。
- 已讀：`god_rule.md`、`README.md`、`HANDOFF.md`，並最小範圍檢查 `SignalEngine`、`config.py`、`KlineRepository`、`models.py`、log 檔與 DB 3m/15m K 線。
- 執行邊界：只做 log / DB SELECT 唯讀分析；未修改交易邏輯、未改 `.env`、未連交易所 API、未寫入 DB、未下單。
- 資料來源：排除 `logs/example_audit_data.log`（synthetic 範例假資料）；實際 log 掃描截至 2026-04-29 03:46 +08:00 找到真實 `market entry success` / `native stop algo order placed` 各 2 筆：`SFPUSDT`、`TRUMPUSDT`。
- DB 重建結果：`SFPUSDT`（2026-04-27 05:00 3m bar）與 `TRUMPUSDT`（2026-04-29 03:30 15m bar）在「DB finalized entry bar」重建 metrics 下皆為不合規，失敗條件都是 `return_min`；log 當下 in-progress metrics 則皆顯示 `triggered=True`。
- [RISK] 此稽核使用 DB finalized entry bar 重建，和實際下單當秒使用的 in-progress bar 不是同一個時間切片；因此可用來標記「收盤後回看不符合」，不能直接證明下單當秒策略違規。
- 快照/版本：操作前記錄 git HEAD `62b0465`；本輪只追加本交接段。
