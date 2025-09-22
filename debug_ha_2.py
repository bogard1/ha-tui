#!/usr/bin/env python3
import os, asyncio, json, ssl
import aiohttp, websockets, yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_config(path="dashboard.yml"):
    with open(path, "r") as f:
        raw = os.path.expandvars(f.read())
    return yaml.safe_load(raw)

async def debug_ha_connection():
    cfg = load_config()
    ha_cfg = cfg["ha"]

    base_url = ha_cfg["url"].rstrip("/")
    token = ha_cfg["token"]
    verify_ssl = ha_cfg.get("verify_ssl", True)

    print(f"🔧 HA Debug - Conectando a {base_url}")
    print(f"🔑 Token: {token[:20]}...")
    print(f"🔒 SSL Verify: {verify_ssl}")
    print()

    # SSL context
    ssl_ctx = None
    if base_url.startswith("https") and not verify_ssl:
        ssl_ctx = ssl.SSLContext()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        print("⚠️  SSL verification disabled")

    session = None
    ws = None

    try:
        # Test REST API
        print("📡 Testing REST API...")
        session = aiohttp.ClientSession()

        async with session.get(
            f"{base_url}/api/",
            headers={"Authorization": f"Bearer {token}"},
            ssl=False if not verify_ssl else None
        ) as r:
            print(f"   Status: {r.status}")
            if r.status == 200:
                data = await r.json()
                print(f"   Message: {data.get('message', 'OK')}")
            else:
                print(f"   Error: {await r.text()}")

        # Test states endpoint
        print("\n📊 Getting states...")
        async with session.get(
            f"{base_url}/api/states",
            headers={"Authorization": f"Bearer {token}"},
            ssl=False if not verify_ssl else None
        ) as r:
            if r.status == 200:
                states = await r.json()
                print(f"   Found {len(states)} entities")

                # Show some example entities
                print("\n   Sample entities:")
                for i, state in enumerate(states[:5]):
                    print(f"     {state['entity_id']}: {state['state']}")
                if len(states) > 5:
                    print(f"     ... and {len(states) - 5} more")
            else:
                print(f"   Error: {r.status} - {await r.text()}")

        # Test WebSocket
        print("\n🔄 Testing WebSocket...")
        ws_url = base_url.replace("http", "ws") + "/api/websocket"
        print(f"   Connecting to: {ws_url}")

        ws = await websockets.connect(ws_url, ssl=ssl_ctx)
        print("   Connected!")

        # Auth flow
        msg = json.loads(await ws.recv())
        print(f"   Received: {msg['type']}")

        if msg["type"] == "auth_required":
            await ws.send(json.dumps({"type":"auth","access_token": token}))
            msg = json.loads(await ws.recv())
            print(f"   Auth result: {msg['type']}")

            if msg["type"] == "auth_ok":
                print("   ✅ WebSocket authenticated!")

                # Subscribe to events for 3 seconds
                await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
                print("   Listening for events (3 seconds)...")

                event_count = 0
                try:
                    for _ in range(3):
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg)
                        if data.get("type") == "event":
                            event_count += 1
                            event_data = data["event"]["data"]
                            if "new_state" in event_data:
                                entity = event_data["new_state"]["entity_id"]
                                state = event_data["new_state"]["state"]
                                print(f"     Event: {entity} = {state}")
                except asyncio.TimeoutError:
                    pass

                print(f"   Received {event_count} events")
            else:
                print(f"   ❌ Auth failed: {msg}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if ws:
            await ws.close()
        if session:
            await session.close()
        print("\n🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(debug_ha_connection())