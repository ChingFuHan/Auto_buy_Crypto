# Always-Sync 時間同步功能 - 詳細指南

## 概述

新增了 **TimeSyncManager** 持續時間同步服務，在 `main.py run` 執行期間，**無需停止程式**即可自動持續監控和同步本地時間與幣安伺服器時間的偏移。

## 工作原理

### 背景架構

- **TimeSyncManager** 是一個獨立的背景任務，在程式啟動時自動開始運行
- 每隔 **60 秒**（可配置）執行一次時間同步檢查
- 若偏移在健康範圍內，靜默運行，不產生通知
- 若偏移超出閾值，自動發送 Telegram 警告或錯誤通知

### 三層監控機制

| 級別 | 範圍 | 行動 |
|------|------|------|
| 🟢 **HEALTHY** | ≤ 3,000 ms | 靜默運行，無通知 |
| 🟡 **WARNING** | 3,001 - 8,000 ms | 每 5 次警告發一次 Telegram 通知（避免過度提醒） |
| 🔴 **CRITICAL** | > 8,000 ms | 立即發送 Telegram 錯誤通知 |

## 使用方式

### 1. 啟動程式（和往常一樣）

```bash
python3 main.py run
```

程式啟動時會自動初始化 TimeSyncManager：

```
INFO app: time sync manager started resync_interval=60 warning_threshold=3000 critical_threshold=8000
```

### 2. 監控日誌

時間同步的狀態會每 60 秒記錄一次：

```bash
# 查看實時日誌
tail -f logs/app.log | grep "time sync"
```

日誌輸出範例：

```
INFO sync.time: [HEALTHY] time sync check sync_count=5 offset=+23 max=40 rtt=120
INFO sync.time: [HEALTHY] time sync check sync_count=6 offset=+15 max=40 rtt=105
INFO sync.time: [WARNING] time sync check sync_count=7 offset=+4500 max=4500 rtt=150
```

### 3. Telegram 通知

- **🟡 WARNING 通知**（每 5 次警告發送一次）
  ```
  ⚠️ TIME_OFFSET_WARNING
  offset_ms: +4500
  warning_threshold_ms: 3000
  warning_count: 5
  ```

- **🔴 CRITICAL 通知**（立即發送）
  ```
  ❌ TIME_OFFSET_CRITICAL
  offset_ms: +12000
  critical_threshold_ms: 8000
  critical_count: 1
  ```

### 4. 程式運行統計

在 Heartbeat 或日誌中，時間同步統計會包含：

```python
{
    "sync_count": 120,           # 總同步次數
    "last_offset_ms": 23,        # 最後一次偏移
    "max_offset_ms": 4500,       # 歷史最大偏移
    "warning_count": 2,          # 警告次數
    "critical_count": 0,         # 嚴重情況次數
    "current_status": "HEALTHY"  # 當前狀態
}
```

## 配置參數

在 `.env` 中可配置以下參數：

```env
# 時間同步重新檢查間隔（秒，預設 300=5 分鐘）
SERVER_TIME_RESYNC_INTERVAL_SECONDS=60

# 伺服器時間同步是否啟用（預設 true）
SERVER_TIME_SYNC_ENABLED=true

# 最大允許時間偏移（毫秒，預設 5000）
# 若偏移超過此值，程式會拒絕執行交易
MAX_SERVER_TIME_OFFSET_MS=5000
```

TimeSyncManager 的內部閾值（程式碼硬編碼）：

```python
warning_threshold_ms=3000      # 3 秒警告
critical_threshold_ms=8000     # 8 秒嚴重
```

## 工作流程圖

```
main.py run 啟動
     ↓
TradingApplication 初始化
     ↓
TimeSyncManager 創建並啟動
     ↓
[背景循環] 每 60 秒
     ├─ 執行 sync_server_time()
     ├─ 計算偏移 offset_ms
     ├─ 比較與 3000ms/8000ms 閾值
     ├─ 判定狀態 (HEALTHY/WARNING/CRITICAL)
     └─ 根據狀態採取行動
        ├─ HEALTHY → 靜默
        ├─ WARNING → 統計計數，每 5 次發一次通知
        └─ CRITICAL → 立即發送錯誤通知
     ↓
[重複直到程式停止]
     ↓
程式關閉，記錄最終統計
```

## 與舊 `_server_time_loop` 的區別

### 舊方式（已移除）

```python
# 老的 _server_time_loop
async def _server_time_loop(self):
    while not self.stop_event.is_set():
        await asyncio.sleep(300)  # 5 分鐘
        try:
            healthy = await self.exchange_client.ensure_time_sync(force=True)
            if not healthy:  # 若失敗，才發送通知
                await self.notifier.send_error(...)
        except:
            await self.notifier.send_error(...)
```

**缺點**：
- ❌ 只在同步失敗時才知道有問題
- ❌ 缺乏統計與監控
- ❌ 無法區分警告與嚴重
- ❌ 無法持續監控偏移趨勢

### 新方式（TimeSyncManager）

```python
# 新的 TimeSyncManager
async def run(self, stop_event):
    while not stop_event.is_set():
        await asyncio.sleep(60)  # 1 分鐘
        await self._perform_sync_check()
        # 自動同步、判定狀態、統計、分層通知
```

**優點**：
- ✅ 持續監控，不只在失敗時
- ✅ 完整的統計（總次數、最大偏移、警告計數）
- ✅ 三層狀態（HEALTHY/WARNING/CRITICAL）
- ✅ 智能通知（避免過度提醒）
- ✅ 可獲取實時統計 `get_stats()`
- ✅ 支援立即強制同步 `force_sync_now()`

## 故障排除

### 情景 1：頻繁出現 CRITICAL 通知

```
❌ TIME_OFFSET_CRITICAL
offset_ms: +15000
```

**原因**：時間偏移超過 8 秒

**解決**：
1. 執行診斷工具
   ```bash
   python3 time_sync_diagnostic.py --repeat 5
   ```
2. 查看結果是否 NORMAL / WARNING / CRITICAL
3. 若為 CRITICAL，執行自動修復
   ```bash
   python3 time_sync_diagnostic.py --fix --tolerance 150000
   ```
4. 重新啟動程式
   ```bash
   python3 main.py run
   ```

### 情景 2：警告計數不斷增加

```
INFO sync.time: [WARNING] time sync check sync_count=10 offset=+4200
INFO sync.time: [WARNING] time sync check sync_count=11 offset=+4100
```

**原因**：時間偏移長期在 3-8 秒範圍（警告區間）

**行動**：
1. 這是正常的，會每 5 次警告發一次 Telegram 通知（避免過度提醒）
2. 建議調查虛擬機 NTP 設定
3. 不會影響交易，因為交易仍在 5000ms 容差內

### 情景 3：想調整警告閾值

如果 3000ms / 8000ms 對你不適合，可修改代碼：

**文件**：`pump_system/app.py` 第 86-91 行

```python
self.time_sync_manager = TimeSyncManager(
    exchange_client=self.exchange_client,
    notifier=self.notifier,
    resync_interval_seconds=settings.server_time_resync_interval_seconds,
    warning_threshold_ms=3000,         # ← 修改此值（例如改成 2000）
    critical_threshold_ms=8000,        # ← 或修改此值（例如改成 10000）
)
```

修改後重新啟動程式即可生效。

## 進階功能

### 1. 手動獲取統計資訊

在程式運行時，可透過 Telegram 命令或內部 API 獲取統計：

```python
# 在 app.py 或其他地方
stats = app.time_sync_manager.get_stats()
print(stats)
# 輸出:
# {
#     'sync_count': 120,
#     'last_offset_ms': 23,
#     'max_offset_ms': 4500,
#     'warning_count': 2,
#     'critical_count': 0,
#     'current_status': 'HEALTHY'
# }
```

### 2. 立即強制同步

若懷疑時間偏移，可在程式運行時強制立即同步：

```python
# 在任何異步上下文中
offset_ms = await app.time_sync_manager.force_sync_now()
print(f"Current offset: {offset_ms} ms")
```

## 與 Telegram Heartbeat 的整合

Heartbeat 每 900 秒（預設）發送一次心跳信號，其中會包含時間同步統計：

```
💚 HEARTBEAT
Uptime: 12:34:56
Active Positions: 3
Time Sync Status: HEALTHY
  - Total Syncs: 750
  - Last Offset: +45 ms
  - Max Offset: 2500 ms
Strategy: 3m (300) | Live: true | Testnet: false | Data Symbols: 535
```

## 日誌示例

### 正常運行

```
INFO sync.time: time sync manager started resync_interval=60 warning_threshold=3000 critical_threshold=8000
INFO sync.time: [HEALTHY] time sync check sync_count=1 offset=+20 max=20 rtt=115
INFO sync.time: [HEALTHY] time sync check sync_count=2 offset=+15 max=20 rtt=108
INFO sync.time: [HEALTHY] time sync check sync_count=3 offset=+25 max=25 rtt=120
```

### 警告狀態

```
INFO sync.time: [WARNING] time sync check sync_count=4 offset=+3500 max=3500 rtt=140
INFO sync.time: [WARNING] time sync check sync_count=5 offset=+3400 max=3500 rtt=125
INFO sync.time: [WARNING] time sync check sync_count=6 offset=+3300 max=3500 rtt=118
WARN notify: sending warning TIME_OFFSET_WARNING details={'offset_ms': 3300, ...}
```

### 嚴重狀態

```
INFO sync.time: [CRITICAL] time sync check sync_count=7 offset=+10000 max=10000 rtt=150
ERROR notify: sending error TIME_OFFSET_CRITICAL details={'offset_ms': 10000, ...}
```

## 架構圖

```
TradingApplication
    ├── exchange_client (BinanceClient)
    │   ├── sync_server_time()
    │   └── time_offset_ms (當前偏移)
    │
    ├── time_sync_manager (TimeSyncManager) ← NEW
    │   ├── run()                          ← 背景循環
    │   ├── _perform_sync_check()          ← 每 60 秒執行
    │   ├── _handle_status()               ← 判定與處理
    │   ├── get_stats()                    ← 獲取統計
    │   └── force_sync_now()               ← 立即同步
    │
    ├── background_tasks
    │   ├── staging_store.periodic_flush()
    │   ├── fallback_manager.run()
    │   ├── order_service.run_native_stop_monitor()
    │   ├── time_sync_manager.run()        ← NEW
    │   ├── _position_refresh_loop()
    │   ├── _symbol_refresh_loop()
    │   ├── _db_flush_loop()
    │   └── _heartbeat_loop()
    │
    └── notifier (TelegramNotifier)
        ├── send_warning()  ← WARNING 通知
        └── send_error()    ← CRITICAL 通知
```

## 總結

✅ **無需停止程式** - `main.py run` 持續運行，TimeSyncManager 自動在背景同步

✅ **智能監控** - 三層狀態，避免過度通知

✅ **完整統計** - 同步次數、最大偏移、警告計數、當前狀態

✅ **向後相容** - 舊的 `_server_time_loop` 保留為空殼

✅ **與診斷工具配合** - 若需要手動干預，可用 `time_sync_diagnostic.py` 診斷

---

**使用時間**：2026-04-28

**相關檔案**：
- `pump_system/sync/time_sync_manager.py` - 實現
- `pump_system/app.py` - 整合
- `TIME_SYNC_TROUBLESHOOT.md` - 排查指南
- `time_sync_diagnostic.py` - 診斷工具
