from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
import re
from typing import Any

import feedparser
import httpx


@dataclass
class CollectedJob:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    remote_region: str
    description: str
    tags: list[str]
    salary_min: int | None
    salary_max: int | None
    currency: str
    url: str
    published_at: datetime | None


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


async def collect_remoteok(limit: int = 100) -> list[CollectedJob]:
    headers = {"User-Agent": "JobScoutAI/0.1 (+https://github.com/Twinkkkie/jobscout-ai)"}
    async with httpx.AsyncClient(timeout=25, headers=headers) as client:
        response = await client.get("https://remoteok.com/api")
        response.raise_for_status()
        payload: list[dict[str, Any]] = response.json()

    jobs: list[CollectedJob] = []
    for item in payload:
        if not item.get("id") or not item.get("position"):
            continue
        jobs.append(
            CollectedJob(
                source="Remote OK",
                external_id=str(item["id"]),
                title=item.get("position", ""),
                company=item.get("company", ""),
                location=item.get("location", "") or "Remote",
                remote_region=item.get("location", "") or "Global / unspecified",
                description=_clean_html(item.get("description", "")),
                tags=[str(tag) for tag in item.get("tags", [])],
                salary_min=item.get("salary_min") or None,
                salary_max=item.get("salary_max") or None,
                currency="USD",
                url=item.get("url") or item.get("apply_url") or "https://remoteok.com",
                published_at=_parse_date(item.get("date")),
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


async def collect_wwr(limit: int = 100) -> list[CollectedJob]:
    url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(url)
        response.raise_for_status()

    feed = feedparser.parse(response.content)
    jobs: list[CollectedJob] = []
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        company = entry.get("author", "") or entry.get("dc_creator", "") or "Unknown"
        link = entry.get("link", "")
        summary = _clean_html(entry.get("summary", ""))
        published = None
        struct_time = entry.get("published_parsed")
        if struct_time:
            published = datetime(*struct_time[:6], tzinfo=UTC)

        jobs.append(
            CollectedJob(
                source="We Work Remotely",
                external_id=entry.get("id") or link,
                title=title,
                company=company,
                location="Remote",
                remote_region="See source for region restrictions",
                description=summary,
                tags=["remote", "programming"],
                salary_min=None,
                salary_max=None,
                currency="USD",
                url=link,
                published_at=published,
            )
        )
    return jobs


async def collect_public_jobs(limit: int = 100) -> list[CollectedJob]:
    per_source = max(10, limit // 2)
    remoteok, wwr = await __import__("asyncio").gather(
        collect_remoteok(per_source),
        collect_wwr(per_source),
        return_exceptions=True,
    )
    combined: list[CollectedJob] = []
    for result in (remoteok, wwr):
        if isinstance(result, list):
            combined.extend(result)
    return combined[:limit]
