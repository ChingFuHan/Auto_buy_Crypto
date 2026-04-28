# P1 下一步詳解：algo history fallback

> 給第一次看到這個專案的人。
> 看完這份就能知道：為什麼要做這四步、每一步做什麼、改哪些檔案、要小心什麼。

---

## 0. 先看懂一個情境：止損明明觸發了，程式卻不確定

這個專案會在 Binance 期貨上自動開倉，並掛上一張「**原生止損單**」（native stop / algo stop）。
你可以把它想成：「我買進後，跟 Binance 說『價格跌到 X 元時自動幫我市價賣出平倉』。」

當價格真的跌到 X 元，Binance 會在背後做兩件事：

1. 自動產生一張**子單**（child order）去市價平倉。
2. 把原本那張止損單標記成「已完成」。

我們的程式有一個監控迴圈叫 `reconcile_native_stops()`（位於 `pump_system/execution/order_service.py:106`），
它的工作是定期檢查：

- 倉位是不是已經被平掉了？
- 如果倉位平掉了，是被我們掛的止損平掉的嗎？
- 如果是，發 Telegram 通知 `STOP_ORDER_TRIGGERED`，告訴你「止損已觸發」。

判斷「是不是我們的止損平掉的」用的方法是：
**比對子單的 `clientOrderId` 是否等於我們當初掛單時給的 `clientAlgoId`。**

這個比對函式在 `_find_order_by_client_id()`（`order_service.py:613`），它會從最近 20 筆訂單中找。

### 缺口在哪裡

實測發現，Binance 有時候不會把子單的 `clientOrderId` 設成我們給的 `clientAlgoId`，
而是塞一個它自己產生的 ID（例如 `binance_generated_id_xyz`）。

這時 `_find_order_by_client_id()` 找不到匹配 → 回傳 `None`
→ 程式只好降級為發 `STOP_ORDER_POSITION_CLOSED` 警告（白話：「倉位是平了，但我不能確認是被止損平的」）。

實際後果：

- 倉位已正確平倉（資金安全沒問題）。
- 但 Telegram 通知不準確：你會收到「倉位平倉，原因不明」，而不是「止損觸發」。
- 任何依賴「止損是否真的觸發」的後續邏輯（例如績效統計、再進場判斷）都會誤判。

這個缺口在 `tests/test_algo_fill_regression.py:370` 被刻意保留成一個**特性化測試**
（characterisation test，意思是「先把目前怪行為記錄下來，等修好再改」）。

### 修補方向：問 Binance 的「歷史 algo 單」

Binance 有另一個 API 可以查**歷史 algo 單**（不是 open algo orders）。
歷史記錄裡會帶這三個欄位：

- `actualOrderId`：真正觸發的那張子單的 ID
- `actualQty`：真實成交量
- `actualPrice`：真實成交均價

而且歷史 algo 單可以用 **`algoId`** 比對（不是用 `clientOrderId`），
這個 `algoId` 是我們**掛單時就拿到並自己保存**的，絕對不會被 Binance 換掉。

所以修補邏輯是：

> 「`clientOrderId` 找不到時，**退而求其次**用 `algoId` 去查歷史 algo 單，
> 找到後讀 `actualOrderId / actualQty / actualPrice`，正確發出 `STOP_ORDER_TRIGGERED`。」

這個「退而求其次」就是專業術語裡的 **fallback**。
所以這個 P1 任務叫做 **algo history fallback**。

---

## 1. Step 1：跑 `tests/test_algo_fill_regression.py` 確認基線

### 用途

在動任何程式碼之前，先確認**「目前已經對的，全部還是對的」**。
這套測試一共 6 個 case，覆蓋了原生止損監控所有關鍵欄位名稱和分支邏輯：

| 測試名稱 | 目前狀態 | 在保護什麼 |
|---|---|---|
| `test_restore_watchlist_extracts_all_algo_response_fields` | pass | Binance API 回應欄位名稱（`clientAlgoId`、`algoId`、`triggerPrice` 等）沒被改名 |
| `test_restore_watchlist_skips_orders_with_wrong_type_side_or_prefix` | pass | 不會把別的訂單（手機 App 掛的、做空的、止盈的）誤認成我們的止損 |
| `test_reconcile_fill_extracts_order_id_executedqty_avgprice` | pass | 正常 fill 路徑能讀到正確 orderId / executedQty / avgPrice |
| `test_reconcile_fill_falls_back_to_tracker_qty_when_executedqty_absent` | pass | 即使 `executedQty` 缺失也能用我們本地保存的數量補上 |
| `test_reconcile_continues_when_position_open_and_algo_present` | pass | 在「位置還沒關 + 止損還在」時不要亂發通知（避免 race condition） |
| `test_reconcile_stop_missing_emits_error_and_deduplicates` | pass | 「位置還在但止損不見了」要發 `STOP_ORDER_MISSING` 警報，且只發一次 |
| `test_reconcile_position_closed_when_clientorderid_mismatch__known_gap` | pass | **記錄**目前缺口的怪行為（將來修好後這個測試會「故意」改寫） |
| `test_reconcile_triggered_via_algo_history_fallback` | **xfail** | 描述「修好後應該怎樣」的目標；現在跑會故意失敗 |

> **xfail** = expected to fail（預期失敗）。
> 它跑起來會失敗，但 pytest 不會把它當成「壞掉」，因為我們已經知道功能還沒做。
> 等實作完成、應該會通過時，就要把這個標記拿掉，它就變成普通的 pass 測試。

### 怎麼做

```bash
python3 -m pytest -q tests/test_algo_fill_regression.py
```

### 你會看到什麼

正常結果應該長這樣（順序可能不同）：

```
.......x
7 passed, 1 xfailed in 0.XXs
```

- `7 passed`：7 個測試正常通過。
- `1 xfailed`：1 個 xfail 測試「成功地失敗了」，所以也是綠燈。

**任何一個從 pass 變成 fail，就要先停下來查清楚，不能急著做後面的步驟。**
這是基線保護，避免你以為自己只是新增功能，結果不小心改壞了既有的關鍵分支。

---

## 2. Step 2：實作 `BinanceClient.get_historical_algo_orders()`

### 用途

新增一個方法，讓我們的程式可以呼叫 Binance「**歷史 algo 單**」這個 API endpoint。
目前 `BinanceClient`（位於 `pump_system/exchange/binance_client.py`）只有：

- `create_algo_order` — 建立 algo 單（例如掛止損）
- `get_open_algo_orders` — 查目前還掛著的 algo 單

但**沒有**查「已經完成 / 已觸發 / 已取消」的歷史 algo 單。
我們要新增一個 async 方法，讓 reconcile 流程可以呼叫它。

### 怎麼做

在 `binance_client.py` 大約 `get_open_algo_orders` 附近新增：

```python
async def get_historical_algo_orders(
    self,
    symbol: str | None = None,
    algo_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if symbol:
        params["symbol"] = symbol
    if algo_type:
        params["algoType"] = algo_type
    data = await self._request("GET", "<endpoint_path>", signed=True, params=params)
    return list(data)
```

### ⚠️ 關鍵注意：endpoint 名稱要先確認

這是 **HANDOFF.md 已經標記的風險**。

`tests/test_algo_fill_regression.py:419` 裡的 xfail reason 寫了 `GET /fapi/v1/algoOrders`，
但 Binance 官方文件目前列的可能是：

- `GET /fapi/v1/algoOrder`（單筆查詢）
- `GET /fapi/v1/allAlgoOrders`（全部）
- `GET /sapi/v1/algo/futures/historicalOrders`（屬於另一條 Algo Trading 產品線文件）

**做法**：

1. 上 Binance 官方 USDⓈ-M Futures API 文件，找出**正確的 historical algo orders endpoint 名稱**。
2. 同時確認回應欄位是否真的叫 `actualOrderId / actualQty / actualPrice`，還是有其他名稱。
3. 用 testnet 或唯讀 API key 實際呼叫一次，看真實回應。
4. 文件名稱、測試 xfail reason、實際程式碼，**三邊要對上**才實作。

**不可以**只看測試裡的字串就照抄，因為那個字串本來就是「待確認」狀態。

### 怎麼驗證

不要直接接到正式流程。先寫一個小腳本獨立呼叫，確認回傳格式：

```python
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def main():
    settings = load_settings()
    client = BinanceClient(settings)
    rows = await client.get_historical_algo_orders(symbol="BTCUSDT", limit=5)
    for row in rows:
        print(row)

asyncio.run(main())
```

確認你能看到 `algoId`、`actualOrderId`、`actualQty`、`actualPrice` 這幾個欄位，再進下一步。

---

## 3. Step 3：在 `reconcile_native_stops()` 接入 history fallback

### 用途

讓監控迴圈在「`clientOrderId` 找不到匹配」時，**自動退而求其次**用 `algoId` 查歷史 algo 單，
正確發出 `STOP_ORDER_TRIGGERED` 通知。

### 目前邏輯（`order_service.py:141-184`）

```
if 找不到 clientOrderId 對應的 fill order:
    → 拋掉 tracker（從監控清單移除）
    → 發 STOP_ORDER_POSITION_CLOSED 警告（白話：「倉位平了，原因不明」）
```

### 改完後的邏輯

```
if 找不到 clientOrderId 對應的 fill order:
    # ↓↓↓ 新增這段 fallback ↓↓↓
    歷史 = await get_historical_algo_orders(symbol=symbol)
    歷史命中 = 在 歷史 裡找 algoId == tracker.algo_id 的那一筆
    if 歷史命中 and 狀態是已完成:
        → 拋掉 tracker
        → 發 STOP_ORDER_TRIGGERED,
            order_id=歷史命中.actualOrderId,
            quantity=歷史命中.actualQty,
            fill_price=歷史命中.actualPrice
        return
    # ↑↑↑ 新增這段 ↑↑↑

    # 才走原本的降級路徑
    → 拋掉 tracker
    → 發 STOP_ORDER_POSITION_CLOSED 警告
```

要修改的具體位置：`pump_system/execution/order_service.py:141` 那一塊
（從 `closed_order = await self._find_order_by_client_id(...)` 開始）。

### 設計小細節

1. **歷史 API 不要每次都查**。先用 `_find_order_by_client_id`，找不到才查歷史。
   原因：歷史 API 比較吃 rate limit，正常情況下 clientOrderId 是匹配的。
2. **比對用 `algoId` 不是 `clientAlgoId`**。
   `algoId` 是 Binance 給我們的數字 ID，掛單時就拿到並寫進 `tracker.algo_id`，最可靠。
3. **歷史命中要檢查狀態**。
   只有「已完成 / 已觸發」的歷史記錄才該發 TRIGGERED。
   被取消、被人手動刪掉的不該發。
4. **找不到歷史命中**仍然走原本降級路徑，發 `STOP_ORDER_POSITION_CLOSED`。
   這保留了「不確定就保守通知」的安全網。

### 怎麼驗證

實作完先執行：

```bash
python3 -m pytest -q tests/test_algo_fill_regression.py
```

預期：

- 原本 7 個 pass 還是 pass。
- `test_reconcile_position_closed_when_clientorderid_mismatch__known_gap` 這個測試**可能會壞掉**
  ——因為它預期「子單 clientOrderId 不匹配 → 走 POSITION_CLOSED」，
  但你現在加了 fallback，會改成走 TRIGGERED。
- 那個 known-gap 測試需要改寫：要嘛在 fixture 裡讓 `historical_algo_orders` 也是空（這樣才會走原本降級路徑），
  要嘛把它整個刪掉並承認缺口已修復。

---

## 4. Step 4：把 xfail 測試推進為 pass

### 用途

`test_reconcile_triggered_via_algo_history_fallback`（`tests/test_algo_fill_regression.py:415-465`）
這個測試一開始就被設計成「描述修好後該怎麼運作」的目標。

修好之後，它應該可以**自然通過**。
這時要把 `@pytest.mark.xfail(strict=True, ...)` 那個裝飾器整個拿掉，讓它變成普通測試。

### 為什麼要拿掉

`strict=True` 的意思是：「這個測試**必須**失敗，否則 pytest 也會報錯。」
所以實作完成後，如果 fallback 真的成功了：

- 不拿掉 → pytest 會說「咦，本來該失敗的測試居然通過了」→ 整個 suite 變紅燈。
- 拿掉 → 它變成普通綠燈測試，從此守住 fallback 行為，避免將來改壞。

### 怎麼做

把 `tests/test_algo_fill_regression.py:415-424` 這整段 decorator 刪掉：

```python
# 刪掉這整段
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Algo-history fallback not yet implemented. ..."
    ),
)
```

只保留下面的 `def test_reconcile_triggered_via_algo_history_fallback() -> None:` 函式本體。

### 怎麼驗證

```bash
python3 -m pytest -q tests/test_algo_fill_regression.py
```

預期：

```
........
8 passed
```

完全沒有 xfailed，全部綠。

---

## 5. 為什麼要按 1 → 2 → 3 → 4 這個順序

| 順序 | 為什麼是現在做 |
|---|---|
| Step 1 先跑回歸測試 | 確定起點是乾淨的，後面才有比較基準 |
| Step 2 先寫底層 API | 沒有 `get_historical_algo_orders()` 就接不上 reconcile |
| Step 3 再接 reconcile | 要先有 API 才有東西可以接 |
| Step 4 最後改測試 | 功能可運作後，把測試從「目標」轉成「守門員」 |

如果順序顛倒，例如先把 xfail 拿掉，會變成測試紅燈一直擋著你開發；
或者先改 reconcile 沒寫底層 API，會直接 AttributeError 進不了主邏輯。

---

## 6. 整個 P1 的「成功」長什麼樣

實作完之後，下面這幾件事**全部**要為真：

- [ ] `python3 -m pytest -q tests/test_algo_fill_regression.py` 顯示 `8 passed`，沒有 xfailed。
- [ ] `python3 -m pytest -q` 整個 suite 不少於原本的綠燈數（不能因為這個 P1 退掉其他測試）。
- [ ] 有一筆 testnet 或正式盤的真實止損觸發，Telegram 收到 `STOP_ORDER_TRIGGERED`，
      而**不是** `STOP_ORDER_POSITION_CLOSED`。
- [ ] HANDOFF.md 把 [RISK] 標記「algo history fallback 未實作」這條移除或標記為 RESOLVED。

---

## 7. 名詞速查表

| 名詞 | 白話解釋 |
|---|---|
| native stop / algo stop | 我們在 Binance 那邊掛的「自動止損單」，由 Binance 直接觸發 |
| `clientAlgoId` | 我們**自己取**的 algo 單名字（例：`stop_btcusdt_111`）。掛單時送給 Binance |
| `algoId` | Binance 收到我們掛單後**回傳給我們**的數字 ID。穩定、唯一、不會被換掉 |
| `clientOrderId` | 子單（觸發後產生的市價平倉單）的客戶端 ID。**有時候不等於 `clientAlgoId`，這就是缺口的根本原因** |
| `actualOrderId` | 歷史 algo 單裡記錄的「真正子單 ID」 |
| reconcile | 對帳。比對「我以為的狀態」和「Binance 實際狀態」差異的動作 |
| fallback | 主路徑失敗時的「退而求其次」路徑 |
| xfail | pytest 標記「這個測試預期失敗」，失敗算對、通過反而算錯 |
| characterisation test | 把目前怪行為先記錄下來的測試。修好之後要被改寫，不是被刪掉 |
