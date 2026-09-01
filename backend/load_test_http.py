"""Safe read-only HTTP load test for the CuadraApp backend."""
import argparse
import asyncio
import json
import statistics
import time
from collections import Counter
from urllib.parse import urljoin

import httpx


async def worker(client, base_url, token, duration, stats, worker_id):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = time.perf_counter() + duration
    endpoints = ["/products", "/dashboard", "/expenses", "/sales"]
    while time.perf_counter() < deadline:
        endpoint = endpoints[(worker_id + int(time.perf_counter() * 10)) % len(endpoints)]
        started = time.perf_counter()
        try:
            response = await client.get(urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/")), headers=headers)
            elapsed_ms = (time.perf_counter() - started) * 1000
            stats["latencies"].append(elapsed_ms)
            stats["codes"][response.status_code] += 1
            if response.status_code >= 400:
                stats["errors"] += 1
        except Exception as exc:
            stats["errors"] += 1
            stats["exceptions"].append(type(exc).__name__)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Public Railway backend URL")
    parser.add_argument("--token", default="", help="Valid JWT for a test user")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()

    stats = {"latencies": [], "codes": Counter(), "errors": 0, "exceptions": []}
    limits = httpx.Limits(max_connections=max(100, args.users * 2), max_keepalive_connections=max(50, args.users))
    timeout = httpx.Timeout(15.0, connect=10.0)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        started = time.perf_counter()
        await asyncio.gather(*(worker(client, args.url, args.token, args.duration, stats, i) for i in range(args.users)))
        elapsed = time.perf_counter() - started

    latencies = sorted(stats["latencies"])
    def percentile(q):
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, int(len(latencies) * q))]

    total = len(latencies)
    result = {
        "users": args.users,
        "duration_seconds": round(elapsed, 2),
        "requests": total,
        "requests_per_second": round(total / elapsed, 2) if elapsed else 0,
        "errors": stats["errors"],
        "error_rate": round(stats["errors"] / total, 4) if total else 0,
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 2) if latencies else None,
            "p50": round(percentile(0.50), 2) if latencies else None,
            "p95": round(percentile(0.95), 2) if latencies else None,
            "p99": round(percentile(0.99), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
        "status_codes": dict(stats["codes"]),
        "exceptions": dict(Counter(stats["exceptions"])),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
