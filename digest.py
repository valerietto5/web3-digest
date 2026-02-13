
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import feedparser
from rich import print


@dataclass
class Job:
    source: str
    title: str
    company: str
    location: str
    url: str
    posted_at: Optional[str]
    snippet: str


CONFIG_PATH = "config.json"
SEEN_PATH = "seen.json"


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["keywords"] = [k.lower() for k in cfg.get("keywords", [])]
    cfg["include_locations"] = [l.lower() for l in cfg.get("include_locations", [])]
    cfg["exclude_phrases"] = [b.lower() for b in cfg.get("exclude_phrases", [])]
    cfg["max_results"] = int(cfg.get("max_results", 30))
    cfg["only_new"] = bool(cfg.get("only_new", True))
    return cfg


def load_seen(path: str = SEEN_PATH) -> Set[str]:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        return set()
    except Exception:
        return set()


def save_seen(seen: Set[str], path: str = SEEN_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def clean_text(s: str) -> str:
    s = s or ""
    s = re.sub(r"<[^>]+>", " ", s)          # strip HTML
    s = re.sub(r"\s+", " ", s).strip()
    return s


def matches(job: Job, cfg: dict) -> bool:
    text = " ".join([job.title, job.company, job.location, job.snippet]).lower()

    if cfg["keywords"] and not any(k in text for k in cfg["keywords"]):
        return False

    if cfg["include_locations"] and not any(loc in text for loc in cfg["include_locations"]):
        return False

    if cfg["exclude_phrases"] and any(bad in text for bad in cfg["exclude_phrases"]):
        return False

    return True


def parse_title(title: str) -> Tuple[str, str]:
    """
    Attempt to split common formats:
    - "Company - Role"
    - "Company — Role"
    Otherwise, company remains empty and title is used as role.
    """
    t = title.strip()
    if " - " in t:
        company, role = t.split(" - ", 1)
        return company.strip(), role.strip()
    if " — " in t:
        company, role = t.split(" — ", 1)
        return company.strip(), role.strip()
    return "", t


def fetch_rss(source_name: str, feed_url: str, limit: int = 200) -> List[Job]:
    feed = feedparser.parse(feed_url)
    jobs: List[Job] = []

    for e in feed.entries[:limit]:
        raw_title = clean_text(getattr(e, "title", ""))
        url = getattr(e, "link", "") or ""
        summary = clean_text(getattr(e, "summary", "") or getattr(e, "description", ""))

        company, role = parse_title(raw_title)

        posted = None
        if hasattr(e, "published"):
            posted = str(e.published)

        jobs.append(
            Job(
                source=source_name,
                title=role,
                company=company,
                location="",
                url=url,
                posted_at=posted,
                snippet=summary[:240],
            )
        )
    return jobs


def main() -> None:
    cfg = load_config()
    seen = load_seen()

    sources = [
        ("remoteok-blockchain", "https://remoteok.com/remote-blockchain-jobs.rss"),
        ("remoteok-crypto", "https://remoteok.com/remote-crypto-jobs.rss"),
    ]

    jobs: List[Job] = []
    for name, url in sources:
        jobs.extend(fetch_rss(name, url, limit=300))

    # de-dupe by URL first (RemoteOK sometimes repeats the same job)
    by_url: Dict[str, Job] = {}
    for j in jobs:
        if j.url:
            by_url[j.url] = j
    jobs = list(by_url.values())

    # apply your filters
    filtered = [j for j in jobs if matches(j, cfg)]

    # classify new vs already seen
    new_jobs = [j for j in filtered if j.url and j.url not in seen]
    old_jobs = [j for j in filtered if j.url and j.url in seen]

    # update seen set with whatever we matched today
    for j in filtered:
        if j.url:
            seen.add(j.url)
    save_seen(seen)

    # show output
    print("\n[bold]Daily Web3/Crypto Job Digest[/bold]")
    print(f"Total matches: {len(filtered)} | New since last run: {len(new_jobs)}\n")

    to_show = new_jobs if cfg.get("only_new", True) else (new_jobs + old_jobs)
    to_show = to_show[: cfg["max_results"]]

    if not to_show:
        print("[yellow]No new matches right now.[/yellow]\n")
        return

    for j in to_show:
        print(f"[bold]NEW[/bold] {j.title}" + (f" — {j.company}" if j.company else ""))
        if j.posted_at:
            print(f"  Posted: {j.posted_at}")
        print(f"  Link: {j.url}")
        if j.snippet:
            print(f"  Notes: {j.snippet}")
        print("")


if __name__ == "__main__":
    main()
