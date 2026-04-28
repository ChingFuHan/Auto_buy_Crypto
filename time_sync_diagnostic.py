#!/usr/bin/env python3
"""
時間同步診斷工具 - 檢測和修復本地時間與幣安伺服器的偏移問題

用法:
  python3 time_sync_diagnostic.py                    # 診斷
  python3 time_sync_diagnostic.py --fix              # 自動修復（增加閾值）
  python3 time_sync_diagnostic.py --repeat 10        # 重複檢測 10 次
  python3 time_sync_diagnostic.py --tolerance 120000 # 設定容差為 120 秒
"""

import asyncio
import httpx
import time
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


class TimeSyncDiagnostic:
    """時間同步診斷引擎"""

    def __init__(self, rest_base_url: str = "https://fapi.binance.com"):
        self.rest_base_url = rest_base_url
        self.results = []

    async def fetch_server_time(self) -> Tuple[int, int, int]:
        """
        獲取幣安伺服器時間，使用中點估計法
        
        Returns:
            (server_time_ms, offset_ms, rtt_ms)
        """
        async with httpx.AsyncClient(timeout=20.0) as client:
            local_before = int(time.time() * 1000)
            try:
                response = await client.get(
                    f"{self.rest_base_url}/fapi/v1/time",
                    headers={"User-Agent": "TimeSyncDiagnostic/1.0"}
                )
                response.raise_for_status()
                local_after = int(time.time() * 1000)
                
                server_time = int(response.json()["serverTime"])
                midpoint = (local_before + local_after) // 2
                offset_ms = server_time - midpoint
                rtt_ms = local_after - local_before
                
                return server_time, offset_ms, rtt_ms
            except Exception as e:
                raise RuntimeError(f"無法連接幣安伺服器: {e}")

    async def diagnose(self, repeat_count: int = 1) -> dict:
        """
        執行診斷
        
        Args:
            repeat_count: 重複檢測次數
            
        Returns:
            診斷結果字典
        """
        print("\n" + "=" * 70)
        print("🔍 時間同步診斷工具 v1.0")
        print("=" * 70)
        
        # 顯示系統時間信息
        print("\n📌 系統時間信息:")
        local_time = time.time()
        local_ms = int(local_time * 1000)
        print(f"  本地時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"  時間戳(秒): {local_time:.3f}")
        print(f"  時間戳(毫秒): {local_ms}")
        
        # 執行多次檢測
        print(f"\n📊 執行 {repeat_count} 次時間同步檢測...\n")
        
        offsets = []
        rtts = []
        
        for attempt in range(1, repeat_count + 1):
            try:
                server_time, offset_ms, rtt_ms = await self.fetch_server_time()
                offsets.append(offset_ms)
                rtts.append(rtt_ms)
                
                # 顯示本次結果
                status = "✅" if abs(offset_ms) <= 5000 else "⚠️"
                print(f"  嘗試 #{attempt}:")
                print(f"    {status} 時間偏移: {offset_ms:+d} ms")
                print(f"    📡 RTT (往返延遲): {rtt_ms} ms")
                print(f"    🕐 幣安伺服器時間: {datetime.fromtimestamp(server_time / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                
                if attempt < repeat_count:
                    await asyncio.sleep(1)  # 檢測間隔
                    
            except Exception as e:
                print(f"  ❌ 嘗試 #{attempt}: 失敗 - {e}")
                if attempt < repeat_count:
                    await asyncio.sleep(1)
        
        # 統計分析
        if offsets:
            avg_offset = sum(offsets) / len(offsets)
            max_offset = max(offsets, key=abs)
            avg_rtt = sum(rtts) / len(rtts)
            
            print("\n" + "-" * 70)
            print("📈 統計結果:")
            print(f"  平均偏移: {avg_offset:+.0f} ms")
            print(f"  最大偏移: {max_offset:+d} ms")
            print(f"  最小偏移: {min(offsets):+d} ms")
            print(f"  平均 RTT: {avg_rtt:.1f} ms")
            
            # 診斷結論
            print("\n" + "-" * 70)
            print("🎯 診斷結論:")
            
            diagnosis = {
                "avg_offset_ms": avg_offset,
                "max_offset_ms": max(offsets, key=abs),
                "min_offset_ms": min(offsets),
                "avg_rtt_ms": avg_rtt,
                "measurements": len(offsets),
                "all_in_tolerance": all(abs(o) <= 5000 for o in offsets),
                "status": None,
                "recommendations": []
            }
            
            if all(abs(o) <= 5000 for o in offsets):
                diagnosis["status"] = "✅ NORMAL"
                print("  ✅ 時間偏移在允許範圍內 (≤ 5000 ms)")
                print("     → 可以正常交易")
            elif all(abs(o) <= 20000 for o in offsets):
                diagnosis["status"] = "⚠️ WARNING"
                print("  ⚠️ 時間偏移超過預設容差，但仍在警告範圍內 (5-20 秒)")
                print("     → 建議調查但不緊急")
                diagnosis["recommendations"].append("檢查虛擬機時間設定")
                diagnosis["recommendations"].append("考慮臨時提升容差至 20000 ms")
            else:
                diagnosis["status"] = "🔴 CRITICAL"
                print(f"  🔴 時間偏移嚴重超過容差 ({abs(avg_offset):+.0f} ms)")
                print("     → 必須修復才能交易")
                diagnosis["recommendations"].append("❌ 虛擬機時間可能有問題")
                diagnosis["recommendations"].append("❌ 檢查 NTP 同步狀態")
                diagnosis["recommendations"].append("❌ 考慮重新啟動 NTP 服務或系統")
            
            # 詳細建議
            if diagnosis["recommendations"]:
                print("\n💡 建議行動:")
                for i, rec in enumerate(diagnosis["recommendations"], 1):
                    print(f"  {i}. {rec}")
            
            return diagnosis
        else:
            print("❌ 無法獲得任何測量數據")
            return {"status": "🔴 FAILED", "error": "no measurements"}

    async def apply_fix(self, tolerance_ms: int = 120000) -> bool:
        """
        自動修復：提升 .env 中的容差
        
        Args:
            tolerance_ms: 新的容差值（毫秒）
            
        Returns:
            是否成功修復
        """
        print("\n" + "=" * 70)
        print(f"🔧 自動修復: 調整容差至 {tolerance_ms} ms ({tolerance_ms / 1000:.0f} 秒)")
        print("=" * 70)
        
        env_path = Path(".env")
        if not env_path.exists():
            print(f"❌ 找不到 .env 檔案在 {env_path.absolute()}")
            return False
        
        try:
            # 讀取現有 .env
            content = env_path.read_text()
            lines = content.split('\n')
            
            # 尋找或新增 MAX_SERVER_TIME_OFFSET_MS
            found = False
            new_lines = []
            
            for line in lines:
                if line.startswith('MAX_SERVER_TIME_OFFSET_MS='):
                    old_value = line.split('=')[1]
                    new_lines.append(f'MAX_SERVER_TIME_OFFSET_MS={tolerance_ms}')
                    print(f"✏️  更新: MAX_SERVER_TIME_OFFSET_MS")
                    print(f"   舊值: {old_value} ms")
                    print(f"   新值: {tolerance_ms} ms")
                    found = True
                else:
                    new_lines.append(line)
            
            # 如果沒找到，在檔案末尾新增
            if not found:
                new_lines.append(f'MAX_SERVER_TIME_OFFSET_MS={tolerance_ms}')
                print(f"➕ 新增: MAX_SERVER_TIME_OFFSET_MS={tolerance_ms}")
            
            # 寫入修改後的 .env
            env_path.write_text('\n'.join(new_lines))
            print(f"\n✅ 成功修改 .env")
            print(f"   路徑: {env_path.absolute()}")
            print(f"\n📌 後續步驟:")
            print(f"   1. 停止目前的交易程式 (Ctrl+C)")
            print(f"   2. 重新啟動: python3 main.py run")
            print(f"   3. 程式會使用新的容差值 {tolerance_ms} ms")
            
            return True
            
        except Exception as e:
            print(f"❌ 修復失敗: {e}")
            return False


async def main():
    parser = argparse.ArgumentParser(
        description="時間同步診斷與修復工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python3 time_sync_diagnostic.py                    # 單次診斷
  python3 time_sync_diagnostic.py --repeat 5         # 重複 5 次
  python3 time_sync_diagnostic.py --fix              # 修復（容差改 120 秒）
  python3 time_sync_diagnostic.py --fix --tolerance 150000  # 修復，容差改 150 秒
        """
    )
    
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="重複檢測次數 (預設: 1)"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="自動修復: 提升 .env 中的 MAX_SERVER_TIME_OFFSET_MS"
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=120000,
        help="修復時設定的容差 (毫秒，預設: 120000)"
    )
    parser.add_argument(
        "--url",
        default="https://fapi.binance.com",
        help="幣安 REST API URL (預設: https://fapi.binance.com)"
    )
    
    args = parser.parse_args()
    
    # 驗證參數
    if args.tolerance < 5000:
        print("⚠️  警告: 容差不應該小於 5000 ms (5 秒)")
        sys.exit(1)
    
    try:
        diagnostic = TimeSyncDiagnostic(rest_base_url=args.url)
        
        # 執行診斷
        result = await diagnostic.diagnose(repeat_count=args.repeat)
        
        # 若指定 --fix，則自動修復
        if args.fix:
            await asyncio.sleep(1)
            if result.get("status") and "CRITICAL" in result["status"]:
                confirm = input(f"\n⚠️  確認要將容差提升至 {args.tolerance} ms? (y/n): ").lower()
                if confirm == 'y':
                    await diagnostic.apply_fix(tolerance_ms=args.tolerance)
                else:
                    print("❌ 取消修復")
            else:
                print("\n✅ 時間同步正常，無需修復")
        
        print("\n" + "=" * 70)
        print("✅ 診斷完成")
        print("=" * 70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n❌ 使用者中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
