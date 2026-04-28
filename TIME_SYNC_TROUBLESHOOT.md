# 時間同步問題排查指南

## 概述

本指南說明如何使用 `time_sync_diagnostic.py` 診斷和解決時間同步問題。

當您看到以下錯誤時，表示本地時間與幣安伺服器時間差距過大：

```
[ERROR] SERVER_TIME_OFFSET_BLOCKED
error: offset_exceeded_threshold
offset_ms: 101933
threshold_ms: 5000
```

---

## 快速診斷

### 步驟 1：執行診斷工具

```bash
# 單次檢測
python3 time_sync_diagnostic.py

# 重複檢測 5 次（推薦）
python3 time_sync_diagnostic.py --repeat 5
```

### 步驟 2：查看診斷結果

工具會顯示：

| 結果 | 含義 | 行動 |
|------|------|------|
| ✅ **NORMAL** | 時間差 ≤ 5 秒 | 無需處理，程式應該能正常執行 |
| ⚠️ **WARNING** | 時間差 5-20 秒 | 調查虛擬機設定，或臨時提升容差 |
| 🔴 **CRITICAL** | 時間差 > 20 秒 | 需立即修復 |

---

## 常見問題與解決方案

### 情景 A：結果為 NORMAL ✅

**問題已解決！** 程式應該能正常執行。

```bash
# 直接啟動交易程式
python3 main.py run
```

---

### 情景 B：結果為 WARNING ⚠️

時間差在 5-20 秒之間。有兩個選擇：

#### 選項 1：調查虛擬機時間設定（推薦長期解決）

如果您使用 VirtualBox 虛擬機：

```bash
# 檢查 NTP 同步狀態
timedatectl status

# 檢查 RTC 時鐘
hwclock

# 若 NTP 顯示未同步，重新啟動 NTP
sudo systemctl restart systemd-timesyncd

# 或更新時間
sudo timedatectl set-time "2026-04-28 11:30:00"
```

#### 選項 2：臨時提升容差（快速解決）

```bash
# 自動修復，容差改為 120 秒
python3 time_sync_diagnostic.py --fix

# 或手動修改 .env
# 將 MAX_SERVER_TIME_OFFSET_MS=5000 改為 MAX_SERVER_TIME_OFFSET_MS=120000

# 重新啟動程式
python3 main.py run
```

---

### 情景 C：結果為 CRITICAL 🔴

時間差超過 20 秒，**必須修復**才能交易。

#### 步驟 1：檢查系統時間

```bash
# 查看目前系統時間（應該是正確的）
date

# 查看 NTP 同步狀態
timedatectl status

# 查看 RTC 時鐘
hwclock
```

#### 步驟 2：強制重新同步

```bash
# 如果系統時間不正確，手動設定
sudo timedatectl set-ntp true

# 強制同步（可能需要 root）
sudo systemctl restart systemd-timesyncd

# 等待 5 秒
sleep 5

# 再次執行診斷
python3 time_sync_diagnostic.py --repeat 3
```

#### 步驟 3：若仍未解決

可能是虛擬機時間源問題：

```bash
# 如果使用 VirtualBox：
# 1. 停止虛擬機
# 2. 進入設定 → 系統 → 系統設定
# 3. 啟用「硬體時鐘設為 UTC」
# 4. 重新啟動虛擬機

# 如果使用其他虛擬化軟體（Hyper-V / KVM / VMware）：
# 在虛擬機設定中啟用時間同步
```

#### 步驟 4：臨時覆蓋容差

若系統時間確實正確，但就是無法縮小偏移，可使用臨時容差：

```bash
# 自動修復到 150 秒
python3 time_sync_diagnostic.py --fix --tolerance 150000

# 重新啟動程式
python3 main.py run
```

---

## 進階選項

### 重複多次檢測

```bash
# 執行 10 次診斷，找出時間偏移的平均值和變動範圍
python3 time_sync_diagnostic.py --repeat 10
```

### 指定自定義幣安 URL

```bash
# 若使用代理或自訂 URL
python3 time_sync_diagnostic.py --url https://your-proxy.com:8080/binance
```

### 完整自動修復流程

```bash
# 診斷 + 自動提升容差至 120 秒
python3 time_sync_diagnostic.py --fix

# 若要自訂容差值（例如 180 秒）
python3 time_sync_diagnostic.py --fix --tolerance 180000
```

---

## 理解診斷輸出

### 時間偏移 (Offset)

```
時間偏移: +40 ms
```

- **正值** (+): 本地時間比伺服器快
- **負值** (-): 本地時間比伺服器慢
- **0** : 完全同步
- **≤ 5000 ms** : 在允許範圍內 ✅
- **> 5000 ms** : 超出容差，會被拒絕 ❌

### RTT (往返延遲)

```
RTT (往返延遲): 154 ms
```

這是向幣安伺服器發送請求到收到回應的時間。

- **< 100 ms** : 網路狀況很好
- **100-200 ms** : 正常
- **> 200 ms** : 網路較慢或地理距離遠

---

## 故障排除決策樹

```
執行診斷
    ↓
結果是 NORMAL? ✅
    ├─ 是 → ✅ 無需處理，程式應正常執行
    └─ 否 ↓
    
結果是 WARNING? ⚠️
    ├─ 是 ↓
    │   有時間修復虛擬機設定?
    │   ├─ 是 → 修改虛擬機 NTP 設定，重新診斷
    │   └─ 否 → 執行: python3 time_sync_diagnostic.py --fix
    └─ 否 ↓
    
結果是 CRITICAL? 🔴
    ├─ 是 ↓
    │   檢查系統時間是否正確?
    │   ├─ 否 → 手動設定系統時間，重新診斷
    │   └─ 是 ↓
    │       嘗試修復虛擬機時間設定
    │       重新診斷
    │       ├─ 成功 → ✅ 完成
    │       └─ 失敗 → 執行: python3 time_sync_diagnostic.py --fix --tolerance 150000
    └─ 其他 → 聯絡支援
```

---

## 在 .env 中手動設定容差

若不想使用自動修復工具，可直接編輯 `.env`：

### 原始設定（5 秒容差）

```env
MAX_SERVER_TIME_OFFSET_MS=5000
```

### 臨時放寬容差

```env
# 120 秒容差
MAX_SERVER_TIME_OFFSET_MS=120000

# 或 150 秒
MAX_SERVER_TIME_OFFSET_MS=150000

# 或 300 秒（5 分鐘，應是最後手段）
MAX_SERVER_TIME_OFFSET_MS=300000
```

修改後重新啟動程式：

```bash
python3 main.py run
```

---

## 監控時間偏移

程式執行時，時間偏移會被記錄在日誌中：

```bash
# 查看最近的時間同步日誌
tail -f logs/*.log | grep "server time synced"
```

輸出範例：

```
INFO exchange.binance: server time synced offset_ms=+23 rtt_ms=120
```

若發現偏移值在不斷增加，可能表示：
- 系統時間有持續漂移
- 需要重新同步 NTP
- 應考慮重新啟動程式

---

## 關鍵配置參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `MAX_SERVER_TIME_OFFSET_MS` | 5000 | 允許的最大時間偏移（毫秒） |
| `SERVER_TIME_SYNC_ENABLED` | true | 是否啟用時間同步檢查 |
| `SERVER_TIME_RESYNC_INTERVAL_SECONDS` | 300 | 重新同步的間隔（秒） |

編輯 `.env` 可修改這些值。

---

## 常見問題 (FAQ)

**Q: 為什麼會有時間偏移?**

A: 本地時鐘和幣安伺服器時鐘之間可能存在差異，原因包括：
- NTP 同步延遲
- 虛擬機時間漂移
- 網路延遲
- 系統時鐘精度限制

**Q: 時間偏移會影響交易嗎?**

A: 是的。如果偏移超過 5 秒，幣安伺服器會拒絕您的訂單請求，導致無法交易。

**Q: 提升容差值會有問題嗎?**

A: 容差值只是允許範圍，不會改變實際的時間同步精度。提升容差可讓程式在偏移較大時繼續運行，但無法解決根本原因。建議在排查虛擬機設定後，將容差改回 5000。

**Q: 如何永久解決時間偏移?**

A: 確保虛擬機或系統的 NTP 正確配置，並定期同步時間。詳見「虛擬機時間設定」段落。

**Q: 診斷工具在哪個平台可用?**

A: Linux / macOS / Windows (WSL or native Python)

---

## 聯繫支援

若按照本指南仍無法解決，請提供：

1. 診斷輸出（執行 `python3 time_sync_diagnostic.py --repeat 5` 的完整輸出）
2. 系統信息（`uname -a` 或 Windows 版本）
3. 虛擬機類型（VirtualBox / Hyper-V / etc）
4. `.env` 中的 `MAX_SERVER_TIME_OFFSET_MS` 值

---

## 更新日誌

- **2026-04-28**: 初版發佈，新增 `time_sync_diagnostic.py` 工具
