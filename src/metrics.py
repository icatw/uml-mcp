#!/usr/bin/env python3
"""
性能指标监控模块

提供 UML 渲染服务的性能监控和指标收集功能。
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from loguru import logger


@dataclass
class RenderMetric:
    """
    单次渲染指标
    """

    timestamp: float
    format: str
    duration: float
    size: int
    cache_hit: bool
    error: Optional[str] = None


class RenderMetrics:
    """
    渲染性能指标收集器

    收集和统计 UML 渲染服务的性能指标。
    """

    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._lock = asyncio.Lock()

        # 渲染历史记录
        self.render_history: deque = deque(maxlen=max_history)

        # 统计计数器
        self.counters: Dict[str, int] = defaultdict(int)

        # 格式统计
        self.format_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0.0,
                "total_size": 0,
                "avg_duration": 0.0,
                "avg_size": 0.0,
            }
        )

        # 错误统计
        self.error_stats: Dict[str, int] = defaultdict(int)

        # 缓存统计
        self.cache_stats = {"hits": 0, "misses": 0, "hit_rate": 0.0}

        # 性能统计
        self.performance_stats = {
            "min_duration": float("inf"),
            "max_duration": 0.0,
            "avg_duration": 0.0,
            "p50_duration": 0.0,
            "p95_duration": 0.0,
            "p99_duration": 0.0,
        }

        # 服务启动时间
        self.start_time = time.time()

    async def record_render(
        self, format: str, duration: float, size: int, cache_hit: bool = False
    ) -> None:
        """
        记录渲染指标

        Args:
            format (str): 输出格式
            duration (float): 渲染耗时（秒）
            size (int): 输出大小（字节）
            cache_hit (bool): 是否缓存命中
        """
        async with self._lock:
            # 创建指标记录
            metric = RenderMetric(
                timestamp=time.time(),
                format=format,
                duration=duration,
                size=size,
                cache_hit=cache_hit,
            )

            # 添加到历史记录
            self.render_history.append(metric)

            # 更新计数器
            self.counters["total_renders"] += 1
            self.counters[f"renders_{format}"] += 1

            # 更新格式统计
            stats = self.format_stats[format]
            stats["count"] += 1
            stats["total_duration"] += duration
            stats["total_size"] += size
            stats["avg_duration"] = stats["total_duration"] / stats["count"]
            stats["avg_size"] = stats["total_size"] / stats["count"]

            # 更新缓存统计
            if cache_hit:
                self.cache_stats["hits"] += 1
            else:
                self.cache_stats["misses"] += 1

            total_cache_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
            if total_cache_requests > 0:
                self.cache_stats["hit_rate"] = (
                    self.cache_stats["hits"] / total_cache_requests * 100
                )

            # 更新性能统计
            self._update_performance_stats()

            logger.debug(
                f"记录渲染指标: 格式={format}, 耗时={duration:.3f}s, "
                f"大小={size}字节, 缓存命中={cache_hit}"
            )

    async def record_error(self, error_type: str) -> None:
        """
        记录错误

        Args:
            error_type (str): 错误类型
        """
        async with self._lock:
            self.counters["total_errors"] += 1
            self.error_stats[error_type] += 1

            logger.debug(f"记录错误: {error_type}")

    async def record_cache_hit(self) -> None:
        """
        记录缓存命中
        """
        async with self._lock:
            self.cache_stats["hits"] += 1

            total_cache_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
            if total_cache_requests > 0:
                self.cache_stats["hit_rate"] = (
                    self.cache_stats["hits"] / total_cache_requests * 100
                )

    def _update_performance_stats(self) -> None:
        """
        更新性能统计
        """
        if not self.render_history:
            return

        # 获取非缓存命中的渲染记录
        durations = [m.duration for m in self.render_history if not m.cache_hit]

        if not durations:
            return

        durations.sort()

        self.performance_stats["min_duration"] = min(durations)
        self.performance_stats["max_duration"] = max(durations)
        self.performance_stats["avg_duration"] = sum(durations) / len(durations)

        # 计算百分位数
        n = len(durations)
        if n > 0:
            self.performance_stats["p50_duration"] = durations[int(n * 0.5)]
            self.performance_stats["p95_duration"] = durations[int(n * 0.95)]
            self.performance_stats["p99_duration"] = durations[int(n * 0.99)]

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        async with self._lock:
            uptime = time.time() - self.start_time

            # 计算请求速率
            total_renders = self.counters.get("total_renders", 0)
            requests_per_second = total_renders / uptime if uptime > 0 else 0

            # 计算错误率
            total_errors = self.counters.get("total_errors", 0)
            error_rate = (
                (total_errors / total_renders * 100) if total_renders > 0 else 0
            )

            return {
                "uptime_seconds": round(uptime, 2),
                "total_renders": total_renders,
                "total_errors": total_errors,
                "requests_per_second": round(requests_per_second, 2),
                "error_rate_percent": round(error_rate, 2),
                "performance": self.performance_stats.copy(),
                "cache": self.cache_stats.copy(),
                "formats": dict(self.format_stats),
                "errors": dict(self.error_stats),
            }

    async def get_recent_metrics(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的指标记录

        Args:
            minutes (int): 最近多少分钟

        Returns:
            List[Dict[str, Any]]: 指标记录列表
        """
        async with self._lock:
            cutoff_time = time.time() - (minutes * 60)

            recent_metrics = []
            for metric in self.render_history:
                if metric.timestamp >= cutoff_time:
                    recent_metrics.append(
                        {
                            "timestamp": metric.timestamp,
                            "format": metric.format,
                            "duration": metric.duration,
                            "size": metric.size,
                            "cache_hit": metric.cache_hit,
                            "error": metric.error,
                        }
                    )

            return recent_metrics

    async def get_hourly_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取按小时统计的数据

        Args:
            hours (int): 统计多少小时

        Returns:
            Dict[str, Any]: 按小时统计的数据
        """
        async with self._lock:
            cutoff_time = time.time() - (hours * 3600)

            hourly_data: Dict[int, Dict[str, Any]] = defaultdict(
                lambda: {
                    "renders": 0,
                    "errors": 0,
                    "total_duration": 0.0,
                    "avg_duration": 0.0,
                    "cache_hits": 0,
                }
            )

            for metric in self.render_history:
                if metric.timestamp >= cutoff_time:
                    # 计算小时键
                    hour_key = int(metric.timestamp // 3600) * 3600

                    data = hourly_data[hour_key]
                    data["renders"] += 1
                    data["total_duration"] += metric.duration

                    if metric.cache_hit:
                        data["cache_hits"] += 1

                    if metric.error:
                        data["errors"] += 1

            # 计算平均值
            for data in hourly_data.values():
                if data["renders"] > 0:
                    data["avg_duration"] = data["total_duration"] / data["renders"]

            return {str(k): v for k, v in hourly_data.items()}

    async def get_format_breakdown(self) -> Dict[str, Any]:
        """
        获取按格式分类的统计

        Returns:
            Dict[str, Any]: 格式统计
        """
        async with self._lock:
            total_renders = self.counters.get("total_renders", 0)

            breakdown = {}
            for format_name, stats in self.format_stats.items():
                percentage = (
                    (stats["count"] / total_renders * 100) if total_renders > 0 else 0
                )

                breakdown[format_name] = {**stats, "percentage": round(percentage, 2)}

            return breakdown

    async def get_performance_summary(self) -> Dict[str, Any]:
        """
        获取性能摘要

        Returns:
            Dict[str, Any]: 性能摘要
        """
        async with self._lock:
            total_renders = self.counters.get("total_renders", 0)
            total_errors = self.counters.get("total_errors", 0)

            # 计算成功率
            success_rate = (
                ((total_renders - total_errors) / total_renders * 100)
                if total_renders > 0
                else 0
            )

            # 获取最近的性能趋势
            recent_metrics = await self.get_recent_metrics(minutes=10)
            recent_avg_duration = 0.0

            if recent_metrics:
                recent_durations = [
                    m["duration"] for m in recent_metrics if not m["cache_hit"]
                ]
                if recent_durations:
                    recent_avg_duration = sum(recent_durations) / len(recent_durations)

            return {
                "total_requests": total_renders,
                "success_rate_percent": round(success_rate, 2),
                "cache_hit_rate_percent": round(self.cache_stats["hit_rate"], 2),
                "avg_response_time_seconds": round(
                    self.performance_stats["avg_duration"], 3
                ),
                "recent_avg_response_time_seconds": round(recent_avg_duration, 3),
                "p95_response_time_seconds": round(
                    self.performance_stats["p95_duration"], 3
                ),
                "uptime_hours": round((time.time() - self.start_time) / 3600, 2),
            }

    async def reset_stats(self) -> None:
        """
        重置所有统计信息
        """
        async with self._lock:
            self.render_history.clear()
            self.counters.clear()
            self.format_stats.clear()
            self.error_stats.clear()

            self.cache_stats = {"hits": 0, "misses": 0, "hit_rate": 0.0}

            self.performance_stats = {
                "min_duration": float("inf"),
                "max_duration": 0.0,
                "avg_duration": 0.0,
                "p50_duration": 0.0,
                "p95_duration": 0.0,
                "p99_duration": 0.0,
            }

            self.start_time = time.time()

            logger.info("性能指标已重置")

    async def export_metrics(self) -> Dict[str, Any]:
        """
        导出所有指标数据

        Returns:
            Dict[str, Any]: 完整的指标数据
        """
        async with self._lock:
            return {
                "summary": await self.get_performance_summary(),
                "detailed_stats": await self.get_stats(),
                "format_breakdown": await self.get_format_breakdown(),
                "recent_metrics": await self.get_recent_metrics(minutes=30),
                "hourly_stats": await self.get_hourly_stats(hours=24),
                "export_timestamp": time.time(),
            }
