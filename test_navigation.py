#!/usr/bin/env python3
import asyncio
import subprocess
import time

async def test_navigation():
    print("Starting HA TUI test...")

    # Start the app in background
    proc = subprocess.Popen(
        ["python", "ha-tui.py", "dashboard-temps.yml"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait a bit for app to start
    await asyncio.sleep(2)

    # Send Tab to navigate to next page
    print("Sending Tab to navigate to values page...")
    proc.stdin.write('\t')
    proc.stdin.flush()

    # Wait a bit more
    await asyncio.sleep(2)

    # Send 'q' to quit
    print("Sending 'q' to quit...")
    proc.stdin.write('q')
    proc.stdin.flush()

    # Wait for process to finish
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait()

    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_navigation())