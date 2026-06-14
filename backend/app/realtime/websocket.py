"""
WebSocket 即時數據推送模組

提供服務器/客戶端雙向通信，支援價格/決策/告警的即時推送。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ─── 消息類型 ─────────────────────────────────────────────────────────────────

class MessageType(str, Enum):
    PRICE = "price"
    DECISION = "decision"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ACK = "ack"
    ERROR = "error"


@dataclass
class WSMessage:
    """WebSocket 消息"""
    type: MessageType
    channel: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    subscription_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "channel": self.channel,
            "data": self.data,
            "timestamp": self.timestamp,
            "subscription_id": self.subscription_id,
        })

    @classmethod
    def from_json(cls, raw: str) -> "WSMessage":
        obj = json.loads(raw)
        return cls(
            type=MessageType(obj["type"]),
            channel=obj["channel"],
            data=obj["data"],
            timestamp=obj.get("timestamp", time.time()),
            subscription_id=obj.get("subscription_id"),
        )


# ─── ConnectionManager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """
    連接管理器

    管理所有 WebSocket 連接的註冊、取消、訂閱。
    """

    def __init__(self):
        self._connections: Dict[str, Any] = {}   # conn_id -> websocket
        self._subscriptions: Dict[str, Set[str]] = {}  # conn_id -> set of channels
        self._counter = 0
        self._lock = asyncio.Lock()

    async def register(self, websocket: Any) -> str:
        """註冊一個新連接"""
        async with self._lock:
            self._counter += 1
            conn_id = f"conn_{self._counter}"
            self._connections[conn_id] = websocket
            self._subscriptions[conn_id] = set()
            logger.info(f"連接已註冊：{conn_id}，總連接數：{len(self._connections)}")
            return conn_id

    async def unregister(self, conn_id: str) -> None:
        """取消連接"""
        async with self._lock:
            if conn_id in self._connections:
                del self._connections[conn_id]
            if conn_id in self._subscriptions:
                del self._subscriptions[conn_id]
            logger.info(f"連接已註銷：{conn_id}，剩餘：{len(self._connections)}")

    async def subscribe(self, conn_id: str, channel: str) -> bool:
        """訂閱頻道"""
        async with self._lock:
            if conn_id not in self._subscriptions:
                return False
            self._subscriptions[conn_id].add(channel)
            logger.debug(f"訂閱：{conn_id} -> {channel}")
            return True

    async def unsubscribe(self, conn_id: str, channel: str) -> bool:
        """取消訂閱"""
        async with self._lock:
            if conn_id not in self._subscriptions:
                return False
            self._subscriptions[conn_id].discard(channel)
            return True

    async def broadcast(self, channel: str, message: WSMessage) -> int:
        """廣播消息到指定頻道的所有連接"""
        sent = 0
        async with self._lock:
            targets = [
                (conn_id, ws)
                for conn_id, channels in self._subscriptions.items()
                if channel in channels and conn_id in self._connections
            ]
        for conn_id, ws in targets:
            try:
                await ws.send(message.to_json())
                sent += 1
            except Exception as e:
                logger.warning(f"廣播失敗 {conn_id}: {e}")
        return sent

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# ─── WebSocketServer ────────────────────────────────────────────────────────────

class WebSocketServer:
    """
    WebSocket 服務器

    處理連接、消息路由、廣播、心跳。
    """

    def __init__(self, manager: Optional[ConnectionManager] = None):
        self.manager = manager or ConnectionManager()
        self._running = False
        self._server = None

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """啟動 WebSocket 服務器"""
        try:
            from websockets.server import serve
        except ImportError:
            logger.error("請安裝 websockets：pip install websockets")
            return

        self._running = True
        logger.info(f"WebSocket 服務器啟動：{host}:{port}")
        self._server = await serve(
            self._handle_client,
            host,
            port,
            ping_interval=30,
            ping_timeout=10,
        )
        await asyncio.Future()  # run forever

    async def stop(self) -> None:
        """停止服務器"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket 服務器已停止")

    async def _handle_client(self, websocket: Any, path: str) -> None:
        """處理客戶端連接"""
        conn_id = await self.manager.register(websocket)
        logger.info(f"客戶端連入：{conn_id} from {websocket.remote_address}")

        try:
            # 發送歡迎 ACK
            await websocket.send(WSMessage(
                type=MessageType.ACK,
                channel="system",
                data={"status": "connected", "conn_id": conn_id},
            ).to_json())

            async for raw in websocket:
                try:
                    msg = WSMessage.from_json(raw)
                except Exception:
                    await websocket.send(WSMessage(
                        type=MessageType.ERROR,
                        channel="system",
                        data={"error": "Invalid message format"},
                    ).to_json())
                    continue

                if msg.type == MessageType.SUBSCRIBE:
                    await self.manager.subscribe(conn_id, msg.channel)
                    await websocket.send(WSMessage(
                        type=MessageType.ACK,
                        channel=msg.channel,
                        data={"subscribed": True},
                    ).to_json())

                elif msg.type == MessageType.UNSUBSCRIBE:
                    await self.manager.unsubscribe(conn_id, msg.channel)

                elif msg.type == MessageType.HEARTBEAT:
                    await websocket.send(WSMessage(
                        type=MessageType.HEARTBEAT,
                        channel="system",
                        data={"pong": True, "server_time": time.time()},
                    ).to_json())

        except Exception as e:
            logger.error(f"客戶端錯誤 {conn_id}: {e}")
        finally:
            await self.manager.unregister(conn_id)


# ─── WebSocketClient ────────────────────────────────────────────────────────────

class WebSocketClient:
    """
    WebSocket 客戶端

    自動重連、指數退避、訂閱追蹤、回調機制。
    """

    def __init__(
        self,
        uri: str,
        reconnect_delay: float = 1.0,
        max_delay: float = 60.0,
        on_message: Optional[Callable[[WSMessage], None]] = None,
    ):
        self.uri = uri
        self.reconnect_delay = reconnect_delay
        self.max_delay = max_delay
        self.on_message = on_message
        self._ws: Optional[Any] = None
        self._running = False
        self._subscriptions: Set[str] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> bool:
        """連接服務器（帶重試）"""
        try:
            import websockets
        except ImportError:
            logger.error("請安裝 websockets：pip install websockets")
            return False

        delay = self.reconnect_delay
        while self._running:
            try:
                self._ws = await websockets.connect(self.uri, ping_interval=30)
                logger.info(f"WebSocket 連接成功：{self.uri}")
                # 重訂閱
                for ch in list(self._subscriptions):
                    await self.subscribe(ch)
                return True
            except Exception as e:
                logger.warning(f"WebSocket 連接失敗: {e}，{delay:.0f}s 後重試...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.max_delay)
        return False

    async def disconnect(self) -> None:
        """主動斷開連接"""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe(self, channel: str) -> None:
        """訂閱頻道"""
        self._subscriptions.add(channel)
        if self._ws:
            await self._ws.send(WSMessage(
                type=MessageType.SUBSCRIBE,
                channel=channel,
                data={},
            ).to_json())

    async def send(self, msg: WSMessage) -> None:
        """發送消息"""
        if self._ws:
            await self._ws.send(msg.to_json())

    async def listen(self) -> None:
        """監聽消息（調用 on_message 回調）"""
        self._running = True
        self._loop = asyncio.get_event_loop()
        await self.connect()

        while self._running:
            try:
                raw = await self._ws.recv()
                msg = WSMessage.from_json(raw)
                if self.on_message:
                    asyncio.create_task(self._safe_callback(msg))
            except Exception as e:
                if self._running:
                    logger.error(f"監聽錯誤: {e}")
                    await self.connect()


# ─── RealtimePushService ────────────────────────────────────────────────────────

class RealtimePushService:
    """
    即時數據推送服務（高層封裝）

    提供 price / decision / alert 三種頻道的高層推送接口，
    內建 ConnectionManager 管理連接，應用層直接使用此类即可。
    """

    def __init__(self, manager: Optional[ConnectionManager] = None):
        self.manager = manager or ConnectionManager()
        self._handlers: Dict[str, List[Callable[[WSMessage], None]]] = {
            MessageType.PRICE.value: [],
            MessageType.DECISION.value: [],
            MessageType.ALERT.value: [],
        }

    # ── 高層推送介面 ────────────────────────────────────────────────────

    async def push_price(self, symbol: str, price: float, metadata: Optional[Dict] = None) -> int:
        """推送價格更新"""
        msg = WSMessage(
            type=MessageType.PRICE,
            channel=f"price:{symbol}",
            data={"symbol": symbol, "price": price, "metadata": metadata or {}},
        )
        return await self.manager.broadcast(f"price:{symbol}", msg)

    async def push_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        reason: str,
    ) -> int:
        """推送交易決策"""
        msg = WSMessage(
            type=MessageType.DECISION,
            channel=f"decision:{symbol}",
            data={
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "reason": reason,
            },
        )
        return await self.manager.broadcast(f"decision:{symbol}", msg)

    async def push_alert(
        self,
        level: str,
        title: str,
        body: str,
        symbol: Optional[str] = None,
    ) -> int:
        """推送告警"""
        msg = WSMessage(
            type=MessageType.ALERT,
            channel="alert",
            data={"level": level, "title": title, "body": body, "symbol": symbol},
        )
        return await self.manager.broadcast("alert", msg)

    # ── 回調註冊 ─────────────────────────────────────────────────────────

    def on_price(self, handler: Callable[[WSMessage], None]) -> None:
        self._handlers[MessageType.PRICE.value].append(handler)

    def on_decision(self, handler: Callable[[WSMessage], None]) -> None:
        self._handlers[MessageType.DECISION.value].append(handler)

    def on_alert(self, handler: Callable[[WSMessage], None]) -> None:
        self._handlers[MessageType.ALERT.value].append(handler)

    @property
    def connection_count(self) -> int:
        return self.manager.connection_count
