#!/usr/bin/env python3
"""
缓存管理模块

提供 UML 渲染结果的缓存功能，支持内存缓存和文件缓存。
"""

import asyncio
import pickle
import time
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

from .config import Config


class CacheItem:
    """
    缓存项

    存储缓存的数据和元数据。
    """

    def __init__(self, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.data = data
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.accessed_at = time.time()
        self.access_count = 0

    def access(self) -> bytes:
        """
        访问缓存项

        Returns:
            bytes: 缓存的数据
        """
        self.accessed_at = time.time()
        self.access_count += 1
        return self.data

    def is_expired(self, ttl: int) -> bool:
        """
        检查是否过期

        Args:
            ttl (int): 生存时间（秒）

        Returns:
            bool: 是否过期
        """
        return time.time() - self.created_at > ttl

    def size(self) -> int:
        """
        获取缓存项大小

        Returns:
            int: 大小（字节）
        """
        return len(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            Dict[str, Any]: 缓存项信息
        """
        return {
            "size": self.size(),
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }


class RenderCache:
    """
    渲染缓存管理器

    支持内存缓存和持久化缓存，提供 LRU 淘汰策略。
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cache: Dict[str, CacheItem] = {}
        self.access_order: list = []  # LRU 访问顺序
        self._lock = asyncio.Lock()
        self._initialized = False
        self._load_task = None

        # 缓存目录
        self.cache_dir = Path(config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 统计信息
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "size": 0, "errors": 0}

    async def initialize(self) -> None:
        """异步初始化缓存"""
        if not self._initialized:
            await self._load_persistent_cache()
            self._initialized = True

    async def get(self, key: str) -> Optional[bytes]:
        """
        获取缓存项

        Args:
            key (str): 缓存键

        Returns:
            Optional[bytes]: 缓存的数据，如果不存在则返回 None
        """
        async with self._lock:
            try:
                # 检查内存缓存
                if key in self.cache:
                    item = self.cache[key]

                    # 检查是否过期
                    if item.is_expired(self.config.cache_ttl):
                        await self._remove_item(key)
                        self.stats["misses"] += 1
                        return None

                    # 更新访问顺序
                    self._update_access_order(key)

                    self.stats["hits"] += 1
                    return item.access()

                # 尝试从持久化缓存加载
                data = await self._load_from_disk(key)
                if data:
                    # 添加到内存缓存
                    await self._add_to_memory_cache(key, data)
                    self.stats["hits"] += 1
                    return data

                self.stats["misses"] += 1
                return None

            except Exception as e:
                logger.error(f"缓存获取失败: {str(e)}")
                self.stats["errors"] += 1
                return None

    async def set(
        self, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        设置缓存项

        Args:
            key (str): 缓存键
            data (bytes): 要缓存的数据
            metadata (Dict[str, Any], optional): 元数据

        Returns:
            bool: 是否设置成功
        """
        async with self._lock:
            try:
                # 检查缓存大小限制
                if len(self.cache) >= self.config.max_cache_size:
                    await self._evict_lru()

                # 创建缓存项
                item = CacheItem(data, metadata)

                # 添加到内存缓存
                self.cache[key] = item
                self._update_access_order(key)

                # 异步保存到磁盘
                asyncio.create_task(self._save_to_disk(key, item))

                self.stats["sets"] += 1

                logger.debug(f"缓存设置成功: {key[:16]}..., 大小: {len(data)} 字节")
                return True

            except Exception as e:
                logger.error(f"缓存设置失败: {str(e)}")
                self.stats["errors"] += 1
                return False

    async def delete(self, key: str) -> bool:
        """
        删除缓存项

        Args:
            key (str): 缓存键

        Returns:
            bool: 是否删除成功
        """
        async with self._lock:
            try:
                await self._remove_item(key)
                return True
            except Exception as e:
                logger.error(f"缓存删除失败: {str(e)}")
                self.stats["errors"] += 1
                return False

    async def clear(self) -> bool:
        """
        清空所有缓存

        Returns:
            bool: 是否清空成功
        """
        async with self._lock:
            try:
                # 清空内存缓存
                self.cache.clear()
                self.access_order.clear()

                # 清空磁盘缓存
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink()

                logger.info("缓存已清空")
                return True

            except Exception as e:
                logger.error(f"缓存清空失败: {str(e)}")
                self.stats["errors"] += 1
                return False

    async def _add_to_memory_cache(
        self, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加到内存缓存

        Args:
            key (str): 缓存键
            data (bytes): 数据
            metadata (Optional[Dict[str, Any]]): 元数据
        """
        if len(self.cache) >= self.config.max_cache_size:
            await self._evict_lru()

        item = CacheItem(data, metadata or {})
        self.cache[key] = item
        self._update_access_order(key)

    def _update_access_order(self, key: str) -> None:
        """
        更新访问顺序（LRU）

        Args:
            key (str): 缓存键
        """
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    async def _evict_lru(self) -> None:
        """
        淘汰最近最少使用的缓存项
        """
        if not self.access_order:
            return

        lru_key = self.access_order[0]
        await self._remove_item(lru_key)
        self.stats["evictions"] += 1

        logger.debug(f"LRU 淘汰缓存项: {lru_key[:16]}...")

    async def _remove_item(self, key: str) -> None:
        """
        移除缓存项

        Args:
            key (str): 缓存键
        """
        # 从内存缓存移除
        if key in self.cache:
            del self.cache[key]

        # 从访问顺序移除
        if key in self.access_order:
            self.access_order.remove(key)

        # 从磁盘移除
        cache_file = self.cache_dir / f"{key}.cache"
        if cache_file.exists():
            cache_file.unlink()

    async def _save_to_disk(self, key: str, item: CacheItem) -> None:
        """
        保存到磁盘

        Args:
            key (str): 缓存键
            item (CacheItem): 缓存项
        """
        try:
            cache_file = self.cache_dir / f"{key}.cache"

            cache_data = {
                "data": item.data,
                "metadata": item.metadata,
                "created_at": item.created_at,
            }

            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f)

            logger.debug(f"缓存已保存到磁盘: {cache_file}")

        except Exception as e:
            logger.warning(f"保存缓存到磁盘失败: {str(e)}")

    async def _load_from_disk(self, key: str) -> Optional[bytes]:
        """
        从磁盘加载

        Args:
            key (str): 缓存键

        Returns:
            Optional[bytes]: 缓存数据
        """
        try:
            cache_file = self.cache_dir / f"{key}.cache"

            if not cache_file.exists():
                return None

            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)

            # 检查是否过期
            created_at = cache_data.get("created_at", 0)
            if time.time() - created_at > self.config.cache_ttl:
                cache_file.unlink()  # 删除过期文件
                return None

            logger.debug(f"从磁盘加载缓存: {cache_file}")
            data = cache_data["data"]
            if isinstance(data, bytes):
                return data
            return None

        except Exception as e:
            logger.warning(f"从磁盘加载缓存失败: {str(e)}")
            return None

    async def _load_persistent_cache(self) -> None:
        """
        启动时加载持久化缓存
        """
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            loaded_count = 0

            for cache_file in cache_files:
                try:
                    key = cache_file.stem

                    with open(cache_file, "rb") as f:
                        cache_data = pickle.load(f)

                    # 检查是否过期
                    created_at = cache_data.get("created_at", 0)
                    if time.time() - created_at > self.config.cache_ttl:
                        cache_file.unlink()  # 删除过期文件
                        continue

                    # 只加载到内存缓存（如果有空间）
                    if len(self.cache) < self.config.max_cache_size:
                        item = CacheItem(
                            data=cache_data["data"],
                            metadata=cache_data.get("metadata", {}),
                        )
                        item.created_at = created_at

                        self.cache[key] = item
                        self.access_order.append(key)
                        loaded_count += 1

                except Exception as e:
                    logger.warning(f"加载缓存文件失败 {cache_file}: {str(e)}")
                    # 删除损坏的缓存文件
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass

            if loaded_count > 0:
                logger.info(f"从磁盘加载了 {loaded_count} 个缓存项")

        except Exception as e:
            logger.error(f"加载持久化缓存失败: {str(e)}")

    async def cleanup(self) -> None:
        """
        清理缓存资源
        """
        logger.info("清理缓存资源...")

        # 清理过期的磁盘缓存
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        cache_data = pickle.load(f)

                    created_at = cache_data.get("created_at", 0)
                    if time.time() - created_at > self.config.cache_ttl:
                        cache_file.unlink()

                except Exception:
                    # 删除损坏的缓存文件
                    cache_file.unlink()

            logger.info("缓存清理完成")

        except Exception as e:
            logger.warning(f"缓存清理失败: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        # 计算内存使用
        memory_usage = sum(item.size() for item in self.cache.values())

        return {
            "memory_items": len(self.cache),
            "max_items": self.config.max_cache_size,
            "memory_usage_bytes": memory_usage,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            **self.stats,
        }

    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取详细的缓存信息

        Returns:
            Dict[str, Any]: 缓存信息
        """
        items_info = {}

        for key, item in self.cache.items():
            items_info[key[:16] + "..."] = item.to_dict()

        return {
            "config": {
                "enabled": self.config.enable_cache,
                "ttl_seconds": self.config.cache_ttl,
                "max_size": self.config.max_cache_size,
                "cache_dir": str(self.cache_dir),
            },
            "stats": self.get_stats(),
            "items": items_info,
        }
