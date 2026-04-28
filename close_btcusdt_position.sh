#!/bin/bash
# BTCUSDT 實盤功能測試 - 平倉 (cleanup)

PROJECT_DIR="/media/sf_agent_sanbox_vm/Auto_buy_Crypto"
cd "$PROJECT_DIR"

echo "════════════════════════════════════════════════════════════════"
echo "🔥 BTCUSDT 平倉"
echo "════════════════════════════════════════════════════════════════"

PYTHONPATH="$PROJECT_DIR" python3 << 'PYTHON_EOF'
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def close_position():
    client = BinanceClient(load_settings())
    try:
        # 獲取持倉
        pos = await client.get_position_risk()
        btc_pos = [p for p in pos if p['symbol'] == 'BTCUSDT' and float(p.get('positionAmt',0)) > 0]
        
        if not btc_pos:
            print("ℹ️  無 BTCUSDT 持倉，無需平倉")
            return
        
        p = btc_pos[0]
        qty = abs(float(p['positionAmt']))
        
        print(f"📍 當前持倉: {qty} BTC")
        print(f"   入場價: ${p['entryPrice']}")
        print(f"   當前標記價: ${p['markPrice']}")
        
        # 市價平倉
        print(f"\n🚀 執行市價平倉...\n")
        order = await client.create_order(
            symbol='BTCUSDT',
            side='SELL',
            order_type='MARKET',
            quantity=qty,
            reduce_only=True
        )
        
        print(f"✅ 平倉成功:")
        print(f"   Order ID: {order['orderId']}")
        print(f"   成交數量: {order['executedQty']}")
        print(f"   平均成交價: ${order['avgPrice']}")
        print(f"   手續費: {order.get('commission', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 平倉失敗: {e}")
    finally:
        await client.close()

asyncio.run(close_position())

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ 平倉完成 - 查詢最新狀態"
echo "════════════════════════════════════════════════════════════════"

# 調用 check_btcusdt_status.sh 進行驗證
bash "$PROJECT_DIR/check_btcusdt_status.sh"
PYTHON_EOF
