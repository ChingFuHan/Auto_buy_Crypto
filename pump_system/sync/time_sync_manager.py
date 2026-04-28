"""
持續時間同步管理器 - 在程式運行期間持續監控和同步時間

此模組確保即使在長時間運行期間，本地時間與幣安伺服器的偏移
也始終保持在允許範圍內，無需停止主程式。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pump_system.exchange.binance_client import BinanceClient
    from pump_system.notify.telegram_notifier import TelegramNotifier


class TimeSyncManager:
    """持續監控和同步伺服器時間的管理器"""

    def __init__(
        self,
        exchange_client: "BinanceClient",
        notifier: "TelegramNotifier | None" = None,
        resync_interval_seconds: int = 60,
        warning_threshold_ms: int = 3000,
        critical_threshold_ms: int = 8000,
    ) -> None:
        """
        初始化時間同步管理器

        Args:
            exchange_client: 幣安交易所客戶端
            notifier: Telegram 通知器（可選）
            resync_interval_seconds: 重新同步間隔（秒）
            warning_threshold_ms: 警告閾值（毫秒）
            critical_threshold_ms: 嚴重閾值（毫秒）
        """
        self.exchange_client = exchange_client
        self.notifier = notifier
        self.resync_interval_seconds = resync_interval_seconds
        self.warning_threshold_ms = warning_threshold_ms
        self.critical_threshold_ms = critical_threshold_ms
        self.logger = logging.getLogger("sync.time")
        
        # 監控統計
        self.sync_count = 0
        self.last_offset_ms = 0
        self.max_offset_ms = 0
        self.warning_count = 0
        self.critical_count = 0
        self._last_warning_sent_at = 0.0
        self._last_critical_sent_at = 0.0

    async def run(self, stop_event: asyncio.Event) -> None:
        """
        執行持續時間同步監控循環

        這是主運行循環，會在背景持續監控時間偏移。
        若偏移超過閾值，會自動重新同步或發送警告。

        Args:
            stop_event: 用於停止循環的事件
        """
        self.logger.info(
            "time sync manager started resync_interval=%d warning_threshold=%d critical_threshold=%d",
            self.resync_interval_seconds,
            self.warning_threshold_ms,
            self.critical_threshold_ms,
        )

        while not stop_event.is_set():
            try:
                await asyncio.sleep(self.resync_interval_seconds)
                await self._perform_sync_check()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.error("time sync check failed error=%s", exc)

        self.logger.info(
            "time sync manager stopped total_syncs=%d warning_count=%d critical_count=%d max_offset=%d",
            self.sync_count,
            self.warning_count,
            self.critical_count,
            self.max_offset_ms,
        )

    async def _perform_sync_check(self) -> None:
        """執行一次完整的時間同步檢查"""
        try:
            # 執行時間同步
            offset_ms = await self.exchange_client.sync_server_time()
            self.sync_count += 1
            self.last_offset_ms = offset_ms
            abs_offset = abs(offset_ms)

            # 更新最大偏移記錄
            if abs_offset > self.max_offset_ms:
                self.max_offset_ms = abs_offset

            # 判定狀態
            status = self._get_status(abs_offset)

            # 記錄
            self.logger.info(
                "[%s] time sync check sync_count=%d offset=%+d max=%d rtt=%d",
                status,
                self.sync_count,
                offset_ms,
                self.max_offset_ms,
                self.exchange_client.last_sync_rtt_ms,
            )

            # 根據狀態採取行動
            await self._handle_status(status, abs_offset)

        except Exception as exc:
            self.logger.error("time sync check error error=%s", exc)
            if self.notifier:
                await self.notifier.send_error(
                    "TIME_SYNC_CHECK_FAILED",
                    error_message=str(exc),
                )

    def _get_status(self, abs_offset: int) -> str:
        """
        根據絕對偏移判定狀態

        Args:
            abs_offset: 絕對時間偏移（毫秒）

        Returns:
            狀態字符串: HEALTHY / WARNING / CRITICAL
        """
        if abs_offset <= self.warning_threshold_ms:
            return "HEALTHY"
        elif abs_offset <= self.critical_threshold_ms:
            return "WARNING"
        else:
            return "CRITICAL"

    async def _handle_status(self, status: str, abs_offset: int) -> None:
        """
        根據狀態採取相應行動

        Args:
            status: 狀態字符串
            abs_offset: 絕對時間偏移
        """
        import time

        if status == "HEALTHY":
            # 健康狀態，無需行動
            pass

        elif status == "WARNING":
            self.warning_count += 1
            # 每 5 次警告才發一次通知（避免過度通知）
            if self.warning_count % 5 == 0 and self.notifier:
                current_time = time.time()
                if current_time - self._last_warning_sent_at > 60:  # 至少 1 分鐘間隔
                    await self.notifier.send_warning(
                        "TIME_OFFSET_WARNING",
                        details={
                            "offset_ms": self.last_offset_ms,
                            "abs_offset_ms": abs_offset,
                            "warning_threshold_ms": self.warning_threshold_ms,
                            "warning_count": self.warning_count,
                        },
                    )
                    self._last_warning_sent_at = current_time

        elif status == "CRITICAL":
            self.critical_count += 1
            # 嚴重狀態，立即發送警告
            if self.notifier:
                current_time = time.time()
                if current_time - self._last_critical_sent_at > 30:  # 至少 30 秒間隔
                    await self.notifier.send_error(
                        "TIME_OFFSET_CRITICAL",
                        details={
                            "offset_ms": self.last_offset_ms,
                            "abs_offset_ms": abs_offset,
                            "critical_threshold_ms": self.critical_threshold_ms,
                            "critical_count": self.critical_count,
                        },
                    )
                    self._last_critical_sent_at = current_time

    def get_stats(self) -> dict:
        """
        獲取時間同步統計資訊

        Returns:
            統計字典：包含同步次數、最大偏移、警告數等
        """
        return {
            "sync_count": self.sync_count,
            "last_offset_ms": self.last_offset_ms,
            "max_offset_ms": self.max_offset_ms,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count,
            "current_status": self._get_status(abs(self.last_offset_ms)),
        }

    async def force_sync_now(self) -> int:
        """
        立即強制執行一次時間同步

        Returns:
            時間偏移（毫秒）
        """
        self.logger.info("forcing immediate time sync")
        offset_ms = await self.exchange_client.sync_server_time()
        self.last_offset_ms = offset_ms
        abs_offset = abs(offset_ms)
        if abs_offset > self.max_offset_ms:
            self.max_offset_ms = abs_offset
        return offset_ms
