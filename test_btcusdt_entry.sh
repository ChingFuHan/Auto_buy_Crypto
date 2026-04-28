#!/bin/bash
# BTCUSDT 實盤功能測試 - 第 1 步：前置檢查 + 下單 + 自動掛止損

set -e

PROJECT_DIR="/media/sf_agent_sanbox_vm/Auto_buy_Crypto"
cd "$PROJECT_DIR"

echo "════════════════════════════════════════════════════════════════"
echo "🔍 STEP 0: 前置檢查 - 帳戶是否清潔"
echo "════════════════════════════════════════════════════════════════"

PYTHONPATH="$PROJECT_DIR" python3 << 'PYTHON_EOF'
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def check():
    client = BinanceClient(load_settings())
    try:
        pos = await client.get_position_risk()
        orders = await client.get_open_orders()
        algos = await client.get_open_algo_orders(algo_type='CONDITIONAL')
        
        nonzero = [p for p in pos if abs(float(p.get('positionAmt','0') or 0)) > 0]
        
        print(f"📊 帳戶狀態:")
        print(f"   - 非零持倉: {len(nonzero)}")
        print(f"   - Open Orders: {len(orders)}")
        print(f"   - Algo Orders: {len(algos)}")
        
        if nonzero:
            print(f"\n⚠️  警告：存在非零持倉：")
            for p in nonzero:
                print(f"   {p['symbol']}: {p['positionAmt']} BTC")
            print("❌ 請先平倉所有持倉後再執行測試")
            return False
        
        if orders or algos:
            print(f"\n⚠️  警告：存在未平倉的單")
            return False
        
        print("\n✅ 帳戶清潔，可開始測試")
        return True
    finally:
        await client.close()

if not asyncio.run(check()):
    exit(1)
PYTHON_EOF

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🚀 STEP 1: 下單 + 自動掛止損"
echo "════════════════════════════════════════════════════════════════"
echo "執行：python3 main.py manual-test-entry"
echo ""
echo "系統將自動："
echo "  1. 市價買入 0.003 BTC"
echo "  2. 立即掛原生 STOP_MARKET algo order"
echo "  3. 發送 Telegram 通知"
echo ""
echo "預期時間：5-15 秒"
echo "────────────────────────────────────────────────────────────────"

python3 main.py manual-test-entry

echo ""
echo "✅ 下單完成"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📋 STEP 2: 驗證持倉與止損單"
echo "════════════════════════════════════════════════════════════════"

PYTHONPATH="$PROJECT_DIR" python3 << 'PYTHON_EOF'
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def verify():
    client = BinanceClient(load_settings())
    try:
        pos = await client.get_position_risk()
        algos = await client.get_open_algo_orders(symbol='BTCUSDT', algo_type='CONDITIONAL')
        
        btc_pos = [p for p in pos if p['symbol'] == 'BTCUSDT' and float(p.get('positionAmt',0)) > 0]
        
        if btc_pos:
            p = btc_pos[0]
            print(f"📍 BTCUSDT 持倉:")
            print(f"   - 數量: {p['positionAmt']}")
            print(f"   - 入場價: {p['entryPrice']}")
            print(f"   - 槓桿: {p['leverage']}x")
            print(f"   - 未實現盈虧: {p['unRealizedProfit']}")
        else:
            print("❌ 未找到 BTCUSDT 持倉")
            return
        
        if algos:
            a = algos[0]
            print(f"\n🛑 止損單 (Algo Order):")
            print(f"   - Algo ID: {a['algoId']}")
            print(f"   - Client ID: {a['clientAlgoId']}")
            print(f"   - 觸發價: {a['triggerPrice']}")
            print(f"   - Working Type: {a['workingType']}")
            print(f"   - 狀態: {a.get('algoStatus', 'ACTIVE')}")
        else:
            print("\n❌ 未找到止損單")
            return
        
        print("\n✅ 下單 + 止損單掛單成功")
    finally:
        await client.close()

asyncio.run(verify())
PYTHON_EOF

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "⏭️  後續步驟"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "選項 A - 等待止損自動觸發（同時監控）"
echo "  cd $PROJECT_DIR && python3 main.py run"
echo "  (Ctrl+C 停止監控)"
echo ""
echo "選項 B - 只監控日誌（不啟動 WebSocket）"
echo "  tail -f $PROJECT_DIR/logs/app.log | grep -E 'STOP|TRIGGER|BTCUSDT'"
echo ""
echo "選項 C - 查詢當前單狀態"
echo "  bash $PROJECT_DIR/check_btcusdt_status.sh"
echo ""
echo "選項 D - 平倉（在 Binance 網頁/App 手動平倉，或降低 BTC 價格觸發止損）"
echo ""
