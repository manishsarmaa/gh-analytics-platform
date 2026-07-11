"""Event Hubs producer: GitHub Events API → Event Hubs.

Polls the public events feed (~300 events, refreshed ~every 60s), de-duplicates
by event id, and publishes new events to the ``gh-events`` hub. Runs *outside*
Databricks (locally, an Azure Container Instance, or a scheduled Function).

Auth: the entity-scoped connection string from Key Vault
(``eventhub-connection-string``). A GitHub PAT raises the API rate limit.

Usage:
    export EVENTHUB_CONN="$(az keyvault secret show --vault-name ghan-dev-kv-a5k8k \
        --name eventhub-connection-string --query value -o tsv)"
    python -m streaming.eventhub_producer --iterations 5 --interval 30
"""

from __future__ import annotations

import argparse
import json
import os
import time

import requests
from azure.eventhub import EventData, EventHubProducerClient

GITHUB_EVENTS_URL = "https://api.github.com/events"


def fetch_events(session: requests.Session) -> list[dict]:
    resp = session.get(GITHUB_EVENTS_URL, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code in (403, 429):
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        time.sleep(max(0, reset - time.time()) + 1)
        return []
    resp.raise_for_status()
    return []


def send_events(producer: EventHubProducerClient, events: list[dict]) -> int:
    batch = producer.create_batch()
    sent = 0
    for e in events:
        data = EventData(json.dumps(e))
        try:
            batch.add(data)
        except ValueError:  # batch full → flush and start a new one
            producer.send_batch(batch)
            batch = producer.create_batch()
            batch.add(data)
        sent += 1
    if len(batch) > 0:
        producer.send_batch(batch)
    return sent


def run(
    conn_str: str, hub: str, github_pat: str | None, interval: int, iterations: int | None
) -> None:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    if github_pat:
        session.headers["Authorization"] = f"Bearer {github_pat}"

    producer = EventHubProducerClient.from_connection_string(conn_str, eventhub_name=hub)
    seen: set[str] = set()
    n = 0
    try:
        while iterations is None or n < iterations:
            events = fetch_events(session)
            new = [e for e in events if e.get("id") and e["id"] not in seen]
            for e in new:
                seen.add(e["id"])
            sent = send_events(producer, new) if new else 0
            print(json.dumps({"iteration": n, "fetched": len(events), "new_sent": sent}))
            # keep the seen-set bounded
            if len(seen) > 5000:
                seen = set(list(seen)[-2000:])
            n += 1
            if iterations is None or n < iterations:
                time.sleep(interval)
    finally:
        producer.close()


def main() -> None:
    p = argparse.ArgumentParser(description="GitHub Events → Event Hubs producer")
    p.add_argument("--hub", default="gh-events")
    p.add_argument("--interval", type=int, default=30, help="seconds between polls")
    p.add_argument(
        "--iterations", type=int, default=None, help="stop after N polls (default: run forever)"
    )
    args = p.parse_args()

    conn = os.environ.get("EVENTHUB_CONN")
    if not conn:
        raise SystemExit("Set EVENTHUB_CONN (the eventhub-connection-string secret).")
    run(conn, args.hub, os.environ.get("GITHUB_PAT"), args.interval, args.iterations)


if __name__ == "__main__":
    main()
