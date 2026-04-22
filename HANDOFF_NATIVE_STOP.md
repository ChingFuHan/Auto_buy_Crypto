# 原生止損單 (Native Stop Loss) 交接文件

## 當前狀態

### ✅ 已完成
1. **止損價格修正** - 改用上一根已完成 K 線的 low（order_service.py 第 91-114 行）
2. **倉位檢查** - 有倉位時 skip 而非 crash（order_service.py 第 70-84 行）
3. **持續監控** - manual-test-entry 後台持續運行（app.py 第 104-115 行）
4. **Fallback Stop 平仓单** - 已加 positionSide: "LONG"（manager.py 第 168 行）

### ❌ 待解決
**Binance STOP_LOSS_LIMIT 類型在 `/fapi/v1/order` 端點報 -1116 Invalid orderType**

## 問題分析

```
嘗試過的類型：
1. type=STOP_LOSS → -1116 Invalid orderType
2. type=STOP + workingType=CONTRACT_PRICE → -1116 Invalid orderType  
3. type=STOP_LOSS_LIMIT + stopPrice + price → -1116 Invalid orderType
4. type=STOP_LOSS_LIMIT + reduceOnly=true → -1106 Parameter 'reduceonly' sent when not required
```

## 解決方案（由下一位接手）

### 方案 A：查詢 Binance 官方文檔
- [ ] 確認 Futures 雙向持倉模式下的正確止損單語法
- [ ] 檢查是否需要用其他 API 端點（例如 `/fapi/v1/openOrders` vs `/fapi/v1/conditionalOrder`）
- [ ] 確認是否需要特殊的訂單類型組合

### 方案 B：嘗試其他類型
```python
# 在 order_service.py 的 _place_exchange_stop() 方法中嘗試：

# 可能性 1: 使用 type=STOP 但不同的參數組合
{
    "type": "STOP",
    "stopPrice": stop_price,
    # 不加 price、workingType 等參數
}

# 可能性 2: 檢查是否需要 priceProtect
{
    "type": "STOP_LOSS_LIMIT",
    "stopPrice": stop_price,
    "price": limit_price,
    "priceProtect": True/False,
}

# 可能性 3: 用 Algo Orders API（如果存在）
# 改用 /fapi/v1/algo/orders 端點而非 /fapi/v1/order
```

### 方案 C：驗證交易所限制
- [ ] 確認雙向持倉模式是否有止損單限制
- [ ] 如果不支援原生止損，則 fallback_stop 是最終方案

## 關鍵文件位置

| 文件 | 行數 | 說明 |
|------|------|------|
| `pump_system/execution/order_service.py` | 339-368 | `_place_exchange_stop()` 方法 - 核心止損邏輯 |
| `pump_system/app.py` | 104-115 | `manual_test_entry()` - 入口點 |
| `pump_system/fallback_stop/manager.py` | 163-174 | 備用止損平倉單 |
| `pump_system/models.py` | SignalDecision class | 交易決策數據結構 |

## 測試命令

```powershell
# 清倉後執行測試
.\.venv\Scripts\python main.py manual-test-entry
```

### 預期輸出
```
✅ 入場單：market entry success
✅ 止損單：native stop order placed  <-- 這行會成功
✅ App 持續運行：keeping app running for stop monitoring
```

### 當前輸出
```
✅ 入場單：market entry success
❌ 止損單：native stop order failed symbol=BTCUSDT ... error=status=400 code=-1116 msg=Invalid orderType
⚠️  Fallback：fallback stop activated (備用方案啟動)
```

## 下一步檢查清單

- [ ] 查詢 Binance Futures API 文檔關於雙向持倉的止損單用法
- [ ] 在 Postman/測試環境試驗正確的止損單參數
- [ ] 更新 `_place_exchange_stop()` 方法中的訂單參數
- [ ] 執行 `manual-test-entry` 測試驗證
- [ ] 如果仍失敗，評估 fallback_stop 是否為可接受的最終方案

## 參考資訊

- **Binance Futures API**: https://binance-docs.github.io/apidocs/futures/cn/#
- **雙向持倉模式**: 所有訂單都需要 `positionSide: "LONG"` 或 `"SHORT"`
- **當前賬戶**: BTCUSDT 已設為 150x 槓桿、雙向持倉模式
