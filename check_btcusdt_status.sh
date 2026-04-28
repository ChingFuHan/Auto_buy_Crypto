#!/bin/bash
# BTCUSDT 實盤功能測試 - 查詢當前單狀態

PROJECT_DIR="/media/sf_agent_sanbox_vm/Auto_buy_Crypto"
cd "$PROJECT_DIR"

PYTHONPATH="$PROJECT_DIR" python3 << 'PYTHON_EOF'
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def check():
    client = BinanceClient(load_settings())
    try:
        pos = await client.get_position_risk()
        orders = await client.get_open_orders()
        algos = await client.get_open_algo_orders(symbol='BTCUSDT', algo_type='CONDITIONAL')
        
        print("════════════════════════════════════════════════════════════════")
        print("📊 BTCUSDT 實時狀態")
        print("════════════════════════════════════════════════════════════════")
        
        # 持倉
        btc_pos = [p for p in pos if p['symbol'] == 'BTCUSDT' and float(p.get('positionAmt',0)) > 0]
        if btc_pos:
            p = btc_pos[0]
            print(f"\n📍 持倉:")
            print(f"   數量: {p['positionAmt']} BTC")
            print(f"   入場價: ${p['entryPrice']}")
            print(f"   當前標記價: ${p['markPrice']}")
            print(f"   未實現盈虧: {p['unRealizedProfit']} USDT ({p['unRealizedProfitPercent']}%)")
            print(f"   槓桿: {p['leverage']}x")
        else:
            print("\n📍 持倉: ❌ 無")
        
        # Open Orders
        btc_orders = [o for o in orders if o['symbol'] == 'BTCUSDT']
        if btc_orders:
            print(f"\n📋 Open Orders ({len(btc_orders)}):")
            for o in btc_orders:
                print(f"   {o['side']} {o['type']} orderId={o['orderId']}")
                print(f"      原始: {o['origQty']}, 已成交: {o['executedQty']}")
        else:
            print(f"\n📋 Open Orders: ❌ 無")
        
        # Algo Orders (Stop Loss)
        if algos:
            print(f"\n🛑 止損單 ({len(algos)}):")
            for a in algos:
                print(f"   Algo ID: {a['algoId']}")
                print(f"      Client ID: {a['clientAlgoId']}")
                print(f"      觸發價: {a['triggerPrice']}")
                print(f"      Working Type: {a['workingType']}")
                print(f"      狀態: {a.get('algoStatus', 'ACTIVE')}")
        else:
            print(f"\n🛑 止損單: ❌ 無 (已觸發或取消)")
        
        print("\n════════════════════════════════════════════════════════════════")
        
        # 狀態判斷
        if not btc_pos and not algos and not btc_orders:
            print("✅ 已全部平倉")
        elif btc_pos and algos:
            print("✅ 持倉 + 止損單 正常")
        elif btc_pos and not algos:
            print("⚠️  持倉存在但無止損單（需要設置）")
        
    finally:
        await client.close()

asyncio.run(check())
PYTHON_EOF
