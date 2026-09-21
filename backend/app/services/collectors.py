import asyncio
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


def _parse_date(value: str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _annualize(value: int | float | None, period: str | None) -> int | None:
    if value is None:
        return None
    multipliers = {
        "hourly": 2080,
        "weekly": 52,
        "fortnightly": 26,
        "monthly": 12,
        "yearly": 1,
        "annual": 1,
    }
    return int(value * multipliers.get((period or "annual").lower(), 1))


async def collect_remoteok(limit: int = 50) -> list[CollectedJob]:
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


async def collect_wwr(limit: int = 50) -> list[CollectedJob]:
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


async def collect_himalayas(limit: int = 40) -> list[CollectedJob]:
    jobs: list[CollectedJob] = []
    cursor: str | None = None

    async with httpx.AsyncClient(timeout=25) as client:
        while len(jobs) < limit:
            params: dict[str, Any] = {"limit": min(20, limit - len(jobs))}
            if cursor:
                params["cursor"] = cursor
            response = await client.get("https://himalayas.app/jobs/api", params=params)
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("jobs", []):
                regions = item.get("locationRestrictions") or []
                timezone = item.get("timezoneRestrictions") or []
                remote_region = ", ".join(regions) or "Worldwide"
                if timezone:
                    remote_region += " · TZ " + ", ".join(map(str, timezone))
                period = item.get("salaryPeriod")
                jobs.append(
                    CollectedJob(
                        source="Himalayas",
                        external_id=str(item.get("guid") or item.get("applicationLink")),
                        title=item.get("title", ""),
                        company=item.get("companyName", ""),
                        location="Remote",
                        remote_region=remote_region,
                        description=_clean_html(item.get("description") or item.get("excerpt", "")),
                        tags=list(item.get("categories") or item.get("parentCategories") or []),
                        salary_min=_annualize(item.get("minSalary"), period),
                        salary_max=_annualize(item.get("maxSalary"), period),
                        currency=item.get("currency") or "USD",
                        url=item.get("applicationLink") or "https://himalayas.app/jobs",
                        published_at=_parse_date(item.get("pubDate")),
                    )
                )
            cursor = payload.get("nextCursor")
            if not cursor:
                break
    return jobs[:limit]


async def collect_jobicy(limit: int = 50) -> list[CollectedJob]:
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": min(100, limit), "industry": "engineering"},
        )
        response.raise_for_status()
        payload = response.json()

    jobs: list[CollectedJob] = []
    for item in payload.get("jobs", []):
        period = item.get("salaryPeriod")
        tags = list(item.get("jobIndustry") or []) + list(item.get("jobType") or [])
        jobs.append(
            CollectedJob(
                source="Jobicy",
                external_id=str(item.get("id") or item.get("url")),
                title=item.get("jobTitle", ""),
                company=item.get("companyName", ""),
                location="Remote",
                remote_region=item.get("jobGeo") or "Remote / unspecified",
                description=_clean_html(item.get("jobDescription") or item.get("jobExcerpt", "")),
                tags=tags,
                salary_min=_annualize(item.get("salaryMin"), period),
                salary_max=_annualize(item.get("salaryMax"), period),
                currency=item.get("salaryCurrency") or "USD",
                url=item.get("url") or "https://jobicy.com/jobs",
                published_at=_parse_date(item.get("pubDate")),
            )
        )
    return jobs[:limit]


async def collect_arbeitnow(limit: int = 50) -> list[CollectedJob]:
    """Collect fresh Europe/Germany jobs from Arbeitnow's public job-board API."""
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        response = await client.get("https://www.arbeitnow.com/api/job-board-api")
        response.raise_for_status()
        payload = response.json()

    jobs: list[CollectedJob] = []
    for item in payload.get("data", [])[:limit]:
        slug = str(item.get("slug") or "")
        url = item.get("url") or (
            f"https://www.arbeitnow.com/jobs/{slug}" if slug else "https://www.arbeitnow.com"
        )
        created_at = item.get("created_at")
        published_at = _parse_date(created_at)
        tags = list(item.get("tags") or []) + list(item.get("job_types") or [])
        jobs.append(
            CollectedJob(
                source="Arbeitnow",
                external_id=slug or url,
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                location=item.get("location", "") or ("Remote" if item.get("remote") else ""),
                remote_region="Remote" if item.get("remote") else item.get("location", ""),
                description=_clean_html(item.get("description", "")),
                tags=tags,
                salary_min=None,
                salary_max=None,
                currency="EUR",
                url=url,
                published_at=published_at,
            )
        )
    return jobs


async def collect_public_jobs(limit: int = 160) -> list[CollectedJob]:
    per_source = max(20, min(50, limit // 5))
    results = await asyncio.gather(
        collect_remoteok(per_source),
        collect_wwr(per_source),
        collect_himalayas(per_source),
        collect_jobicy(per_source),
        collect_arbeitnow(per_source),
        return_exceptions=True,
    )
    combined: list[CollectedJob] = []
    for result in results:
        if isinstance(result, list):
            combined.extend(result)
    return combined[:limit]
