#!/usr/bin/env python3
"""
Diagnóstico de conexión y sensores de Home Assistant
"""
import asyncio
import aiohttp
import json
import ssl
import os
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_config(path="dashboard.yml"):
    with open(path, "r") as f:
        raw = os.path.expandvars(f.read())
    return yaml.safe_load(raw)

async def test_ha_connection():
    # Load configuration from dashboard.yml (same as main app)
    try:
        cfg = load_config("dashboard-temps.yml")
    except FileNotFoundError:
        try:
            cfg = load_config("dashboard.yml")
        except FileNotFoundError:
            print("❌ No se encontró dashboard.yml o dashboard-temps.yml")
            print("💡 Tip: Crea un archivo de configuración o usa variables de entorno:")
            print("   HA_TOKEN=tu_token python debug_ha.py")
            return

    ha_cfg = cfg["ha"]
    url = ha_cfg["url"].rstrip("/")
    token = ha_cfg["token"]
    verify_ssl = ha_cfg.get("verify_ssl", True)

    # Extract expected sensors from config
    expected_sensors = []
    for page in cfg.get("pages", []):
        for widget in page.get("widgets", []):
            if "entity" in widget:
                expected_sensors.append(widget["entity"])

    print("🔍 Diagnóstico de Home Assistant")
    print(f"URL: {url}")
    print(f"Token: {token[:20]}..." if len(token) > 20 else f"Token: {token}")
    print(f"SSL Verification: {verify_ssl}")
    print(f"Entities en configuración: {len(expected_sensors)}")
    print("-" * 50)

    try:
        # Create session
        async with aiohttp.ClientSession() as session:
            print("✅ Conectando a Home Assistant...")

            # Test API connection
            async with session.get(
                f"{url}/api/",
                headers={"Authorization": f"Bearer {token}"},
                ssl=False if not verify_ssl else None
            ) as r:
                if r.status == 200:
                    api_info = await r.json()
                    print(f"✅ API conectada - Versión: {api_info.get('version', 'Unknown')}")
                else:
                    print(f"❌ Error de API: {r.status}")
                    return

            # Get all states
            print("\n🔍 Obteniendo todos los sensores...")
            async with session.get(
                f"{url}/api/states",
                headers={"Authorization": f"Bearer {token}"},
                ssl=False if not verify_ssl else None
            ) as r:
                if r.status != 200:
                    print(f"❌ Error obteniendo estados: {r.status}")
                    return

                states = await r.json()
                print(f"✅ Obtenidos {len(states)} entidades")

                # Filter temperature sensors
                temp_sensors = [s for s in states if 'temperature' in s['entity_id'].lower()]
                print(f"🌡️  Encontrados {len(temp_sensors)} sensores de temperatura:")

                for sensor in temp_sensors:
                    entity_id = sensor['entity_id']
                    state = sensor['state']
                    friendly_name = sensor.get('attributes', {}).get('friendly_name', entity_id)
                    unit = sensor.get('attributes', {}).get('unit_of_measurement', '')

                    print(f"   • {entity_id}")
                    print(f"     Nombre: {friendly_name}")
                    print(f"     Estado: {state} {unit}")
                    print(f"     {'✅ CONFIGURADO' if entity_id in expected_sensors else '⚠️  NO CONFIGURADO'}")
                    print()

                # Check expected sensors
                print("🎯 Verificando sensores configurados:")
                missing_sensors = []
                for sensor_id in expected_sensors:
                    found = any(s['entity_id'] == sensor_id for s in states)
                    if found:
                        sensor_data = next(s for s in states if s['entity_id'] == sensor_id)
                        state = sensor_data['state']
                        print(f"   ✅ {sensor_id}: {state}")
                    else:
                        print(f"   ❌ {sensor_id}: NO ENCONTRADO")
                        missing_sensors.append(sensor_id)

                if missing_sensors:
                    print(f"\n⚠️  {len(missing_sensors)} sensores configurados no existen en HA")
                    print("💡 Sensores similares disponibles:")
                    for missing in missing_sensors:
                        base_name = missing.replace('sensor.', '').replace('_temperature', '')
                        similar = [s for s in temp_sensors if base_name.lower() in s['entity_id'].lower()]
                        for sim in similar:
                            print(f"   📍 {sim['entity_id']} -> {sim['state']} {sim.get('attributes', {}).get('unit_of_measurement', '')}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ha_connection())