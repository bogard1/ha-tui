import json, ssl, asyncio
import aiohttp, websockets


class HAClient:
    def __init__(self, url, token, verify_ssl=True):
        self.base_url = url.rstrip("/")
        if self.base_url.startswith("https://"):
            self.ws_url = "wss://" + self.base_url[8:] + "/api/websocket"
        else:
            self.ws_url = "ws://" + self.base_url[7:] + "/api/websocket"
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = None
        self.state_cache = {}
        self.history = {}
        self._ws = None

    def _ssl_ctx(self):
        if not self.verify_ssl:
            ctx = ssl.SSLContext()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        return None

    async def connect_ws(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        ssl_ctx = self._ssl_ctx() if self.base_url.startswith("https") else None
        self._ws = await websockets.connect(self.ws_url, ssl=ssl_ctx)
        msg = json.loads(await self._ws.recv())
        if msg["type"] != "auth_required":
            raise RuntimeError(f"Expected auth_required, got: {msg['type']}")
        await self._ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        msg = json.loads(await self._ws.recv())
        if msg["type"] != "auth_ok":
            raise RuntimeError(f"Autenticación fallida: {msg.get('message', msg['type'])}")
        await self._ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))

    async def initial_states(self):
        async with self.session.get(
            f"{self.base_url}/api/states",
            headers={"Authorization": f"Bearer {self.token}"},
            ssl=self._ssl_ctx()
        ) as r:
            r.raise_for_status()
            for st in await r.json():
                self.state_cache[st["entity_id"]] = st
                try:
                    v = float(st.get("state"))
                    self.history.setdefault(st["entity_id"], []).append(v)
                except (ValueError, TypeError):
                    pass

    async def pump(self):
        backoff = 1
        while True:
            try:
                async for raw in self._ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "event" and msg["event"].get("event_type") == "state_changed":
                        new_state = msg["event"]["data"].get("new_state")
                        if new_state:
                            ent = new_state["entity_id"]
                            self.state_cache[ent] = new_state
                            try:
                                v = float(new_state.get("state"))
                                hist = self.history.setdefault(ent, [])
                                hist.append(v)
                                if len(hist) > 600:
                                    self.history[ent] = hist[-600:]
                            except (ValueError, TypeError):
                                pass
                backoff = 1
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            try:
                await self.connect_ws()
            except Exception:
                pass

    async def call_service(self, service: str, payload: dict):
        domain, srv = service.split("/")
        async with self.session.post(
            f"{self.base_url}/api/services/{domain}/{srv}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json=payload,
            ssl=self._ssl_ctx()
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self.session:
            await self.session.close()
