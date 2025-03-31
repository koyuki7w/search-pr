import json
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

import click
import requests


def get_git_remote_url(remote: str) -> str:
    return subprocess.run(["git", "remote", "get-url", remote], check=True, stdout=subprocess.PIPE).stdout.decode().rstrip()


class Progress:
    def __init__(self, message: str, total: int | None = None) -> None:
        self._counter = 0
        self.total = total
        self.message = message
        self._print_progress()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            click.echo(f"{self.message}...... done.                   \n", nl=False, err=True)

    def increment(self) -> None:
        self._counter += 1
        self._print_progress()

    def _print_progress(self) -> None:
        if self.total is not None:
            click.echo(f"{self.message}...... ({self._counter}/{self.total})\r", nl=False, err=True)
        else:
            click.echo(f"{self.message}...... \r", nl=False, err=True)


class HttpResponse:
    def __init__(self, headers: dict[str, str], text: str) -> None:
        self.headers = headers
        self.text = text


def get_request(url: str) -> HttpResponse:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return HttpResponse(dict(response.headers), response.text)


class PullRequest:
    def __init__(self, pr_dict: dict[str, str]) -> None:
        self.is_open = pr_dict["state"] == "open"
        self.diff_url = pr_dict["diff_url"]
        self.timestamp = datetime.fromisoformat(pr_dict["updated_at"])
        self.num = int(pr_dict["url"].split("/")[-1])


class GithubHandler:
    def __init__(self, url: str) -> None:
        self.owner, self.repo = self._get_owner_and_repo(url)

    def _get_owner_and_repo(self, url: str) -> tuple[str, str]:
        if url.startswith("git@github.com:") and url.endswith(".git"):
            owner, repo = url[len("git@github.com:") : -len(".git")].split("/")
        elif url.startswith("https://github.com") and url.endswith(".git"):
            owner, repo = url[len("https://github.com/") : -len(".git")].split("/")
        else:
            message = f"Not a github repository: {url}"
            raise RuntimeError(message)
        return owner, repo

    def _get_next_page_url(self, links: str) -> str | None:
        for link in links.split(","):
            if link.rstrip() != "":
                url, rel = link.split(";")
                if rel.lstrip() == 'rel="next"':
                    return url.strip()[1:-1]
        return None

    def _iterate_pr_page(self, first_page_url: str) -> Iterator[Iterator[PullRequest]]:
        first_page_url += "&per_page=100&page=1"
        url: str | None = first_page_url
        while url:
            response = get_request(url)
            yield (PullRequest(pr_dict) for pr_dict in json.loads(response.text))
            url = self._get_next_page_url(response.headers["Link"])

    def _iterate_pr(self, url: str) -> Iterator[PullRequest]:
        for prs in self._iterate_pr_page(url):
            yield from prs

    def get_pr_diff(self, pr: PullRequest) -> str:
        return get_request(pr.diff_url).text

    def iterate_open_pr(self) -> Iterator[PullRequest]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?sort=updated&direction=desc"
        yield from self._iterate_pr(url)

    def iterate_all_pr(self) -> Iterator[PullRequest]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?sort=updated&direction=desc&state=all"
        yield from self._iterate_pr(url)


class CacheHandler:
    def __init__(self, base: Path) -> None:
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)
        self._last_updated = self._base / "LASTUPDATED"
        self._load_last_updated()

    def _load_last_updated(self) -> None:
        if not self._last_updated.is_file():
            self._timestamp = datetime.min.replace(tzinfo=UTC)
            self._updated: list[int] = []
            return
        with self._last_updated.open() as f:
            timestamp, updated = json.loads(f.read())
            self._timestamp = datetime.fromisoformat(timestamp)
            self._updated = updated

    def _save_last_updated(self) -> None:
        with self._last_updated.open("w") as f:
            f.write(json.dumps((self._timestamp.isoformat(), self._updated)))

    def _update_last_updated(self, num: int, timestamp: datetime) -> None:
        if self._timestamp != timestamp:
            self._timestamp = timestamp
            self._updated = []
        self._updated.append(num)
        self._save_last_updated()

    def exist_cache(self) -> bool:
        return self._timestamp != datetime.min.replace(tzinfo=UTC)

    def needs_update(self, num: int, timestamp: datetime) -> bool:
        return self._timestamp < timestamp or (self._timestamp == timestamp and num not in self._updated)

    def iterate_diff(self) -> Iterator[Path]:
        return (file for file in self._base.iterdir() if file.name.endswith(".diff"))

    def update_diff(self, num: int, diff: str, timestamp: datetime) -> None:
        path = self._base / f"{num}.diff"
        with path.open("w") as f:
            f.write(diff)
        self._update_last_updated(num, timestamp)

    def delete_diff(self, num: int, timestamp: datetime) -> None:
        path = self._base / f"{num}.diff"
        if path.is_file():
            path.unlink()
        self._update_last_updated(num, timestamp)


class Main:
    def __init__(self, remote: str, cache: str) -> None:
        self.github = GithubHandler(get_git_remote_url(remote))
        owner, repo = self.github.owner, self.github.repo
        self.cache = CacheHandler(Path(cache).expanduser() / f"{owner}/{repo}")

    def _list_open_pr(self) -> list[PullRequest]:
        with Progress("Listing open pull requests"):
            return list(self.github.iterate_open_pr())

    def _list_updated_pr(self) -> list[PullRequest]:
        prs = []
        with Progress("Listing updated pull requests"):
            for pr in self.github.iterate_all_pr():
                if not self.cache.needs_update(pr.num, pr.timestamp):
                    break
                prs.append(pr)
        return prs

    def _fetch_diff(self, prs: list[PullRequest]) -> None:
        total = len([pr for pr in prs if pr.is_open])
        with Progress("Fetching diffs of pull requests", total) as progress:
            for pr in reversed(prs):
                if pr.is_open:
                    diff = self.github.get_pr_diff(pr)
                    self.cache.update_diff(pr.num, diff, pr.timestamp)
                    progress.increment()
                else:
                    self.cache.delete_diff(pr.num, pr.timestamp)

    def update(self) -> None:
        prs = self._list_updated_pr() if self.cache.exist_cache() else self._list_open_pr()
        self._fetch_diff(prs)

    def search(self, query: str) -> Iterator[int]:
        for path in self.cache.iterate_diff():
            with path.open() as file:
                for line in file:
                    if line.startswith("-") and not line.startswith("---") and query in line.rstrip()[1:]:
                        break
                else:
                    continue
                yield int(path.stem)


@click.command()
@click.option("--cache", help="Cache directory.", default="~/.cache/search-pr", show_default=True)
@click.option("--remote", help="The git remote.", default="origin", show_default=True)
@click.argument("query")
def cli(cache: str, remote: str, query: str) -> None:
    """Search for open pull requests that modify lines containing QUERY."""
    main = Main(remote, cache)
    main.update()
    for num in sorted(main.search(query)):
        click.echo(num)
