"""
Network client that bridges asyncio WebSocket with Tkinter's main thread.

Uses a background thread for the asyncio event loop and a queue.Queue
for thread-safe message passing to the Tkinter main thread.
"""

import asyncio
import json
import queue
import threading


class NetworkClient:
    def __init__(self, server_url, on_message):
        """
        Args:
            server_url: WebSocket URL, e.g. "ws://localhost:8765"
            on_message: Callback(dict) called on Tkinter main thread for each message
        """
        self.server_url = server_url
        self.on_message = on_message
        self._msg_queue = queue.Queue()
        self._ws = None
        self._loop = None
        self._thread = None
        self._connected = False
        self._poll_id = None

    def connect(self, on_connected=None, on_error=None):
        """Start background thread and connect to the server.

        Args:
            on_connected: Callback() on success (called on Tk thread via queue)
            on_error: Callback(error_msg) on failure (called on Tk thread via queue)
        """
        self._on_connected = on_connected
        self._on_error = on_error
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_listen())

    async def _connect_and_listen(self):
        try:
            import websockets
        except ImportError:
            self._msg_queue.put({"type": "_connection_error",
                                 "message": "Missing 'websockets' package. Install with: pip install websockets"})
            return

        try:
            async with websockets.connect(self.server_url, ping_interval=20, ping_timeout=10) as ws:
                self._ws = ws
                self._connected = True
                self._msg_queue.put({"type": "_connected"})
                async for raw_msg in ws:
                    try:
                        data = json.loads(raw_msg)
                        self._msg_queue.put(data)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            self._msg_queue.put({"type": "_connection_error", "message": str(e)})
        finally:
            self._connected = False
            self._ws = None

    def send(self, msg_dict):
        """Thread-safe send. Schedules the send on the asyncio loop."""
        if self._loop and self._ws and self._connected:
            asyncio.run_coroutine_threadsafe(self._async_send(msg_dict), self._loop)

    async def _async_send(self, msg_dict):
        if self._ws:
            try:
                await self._ws.send(json.dumps(msg_dict))
            except Exception:
                pass

    def start_polling(self, root):
        """Start polling the message queue from Tkinter's main thread."""
        self._root = root
        self._poll(root)

    def _poll(self, root):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                if msg.get("type") == "_connected":
                    if self._on_connected:
                        self._on_connected()
                elif msg.get("type") == "_connection_error":
                    if self._on_error:
                        self._on_error(msg.get("message", "Connection failed"))
                else:
                    self.on_message(msg)
        except queue.Empty:
            pass
        self._poll_id = root.after(100, self._poll, root)

    def stop_polling(self):
        """Stop the Tkinter polling loop."""
        if self._poll_id and hasattr(self, "_root"):
            try:
                self._root.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None

    def disconnect(self):
        """Clean shutdown."""
        self.stop_polling()
        if self._loop and self._ws and self._connected:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop)

    async def _async_close(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
