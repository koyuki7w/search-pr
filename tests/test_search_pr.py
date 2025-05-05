import json
import subprocess
from collections.abc import Iterator
from os import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from _pytest.capture import CaptureFixture
from pytest_mock import MockerFixture
from requests import Response
from requests.structures import CaseInsensitiveDict

from search_pr.search_pr import Main


def mock_http_response(headers: dict[str, str], content: str) -> Response:
    r = Response()
    r.status_code = 200
    r.encoding = "UTF-8"
    r.headers = CaseInsensitiveDict()
    for k, v in headers.items():
        r.headers[k] = v
    r._content = content.encode(r.encoding)
    return r


@pytest.fixture
def repo_tmp() -> Iterator[None]:
    with TemporaryDirectory() as name:
        chdir(name)
        Path("cache").mkdir()
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/testOwner/testRepo.git"], check=True)
        yield


@pytest.mark.usefixtures("repo_tmp")
def test_main_1(mocker: MockerFixture, capsys: CaptureFixture[str]) -> None:
    def side_effect(arg: str, timeout: int) -> Response:
        assert timeout != 0
        mapping = {
            "https://api.github.com/repos/testOwner/testRepo/pulls"
            "?sort=updated&direction=desc&per_page=100&page=1": mock_http_response(
                {"Link": '<tests://NextLink>; rel="next", <tests://LastLink>; rel="last", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/1",
                            "diff_url": "test://path/to/diff/1",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/2",
                            "diff_url": "test://path/to/diff/2",
                            "updated_at": "1989-03-26T12:29:41Z",
                            "state": "open",
                        },
                    ],
                ),
            ),
            "tests://NextLink": mock_http_response(
                {"Link": '<tests://PrevLink>; rel="prev", <tests://FirstLink>; rel="first", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/3",
                            "diff_url": "test://path/to/diff/3",
                            "updated_at": "1988-12-31T09:33:11Z",
                            "state": "open",
                        },
                    ],
                ),
            ),
            "https://api.github.com/repos/testOwner/testRepo/pulls"
            "?sort=updated&direction=desc&state=all&per_page=100&page=1": mock_http_response(
                {"Link": '<tests://NextLinkUpdated>; rel="next", <tests://LastLink>; rel="last", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/1",
                            "diff_url": "test://path/to/diff/1",
                            "updated_at": "2005-01-29T18:23:00Z",
                            "state": "closed",
                        },
                        {
                            "url": "test://path/to/pr/4",
                            "diff_url": "test://path/to/diff/4",
                            "updated_at": "2002-11-22T01:12:59Z",
                            "state": "open",
                        },
                    ],
                ),
            ),
            "tests://NextLinkUpdated": mock_http_response(
                {"Link": '<tests://PrevLink>; rel="prev", <tests://FirstLink>; rel="first", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/3",
                            "diff_url": "test://path/to/diff/3",
                            "updated_at": "1988-12-31T22:41:46Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/5",
                            "diff_url": "test://path/to/diff/5",
                            "updated_at": "1980-05-01T06:32:19Z",
                            "state": "closed",
                        },
                    ],
                ),
            ),
            "test://path/to/diff/1": mock_http_response(
                {},
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..c65f630 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " 12345\n"
                "-34567\n"
                " 56789\n",
            ),
            "test://path/to/diff/2": mock_http_response(
                {},
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..4eb6cfb 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " 12345\n"
                " 34567\n"
                "-56789\n"
                "diff --git a/a.txt b/a.txt\n"
                "index aa410fc..eeaeebf 100644\n"
                "--- a/a.txt\n"
                "+++ b/a.txt\n"
                "@@ -1,3 +1,2 @@\n"
                "-abcde\n"
                " bcdef\n"
                " acegi\n",
            ),
            "test://path/to/diff/3": mock_http_response(
                {},
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..e2f2476 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1 @@\n"
                "-12345\n"
                "-34567\n"
                " 56789\n"
                "diff --git a/a.txt b/a.txt\n"
                "index aa410fc..70ecb1d 100644\n"
                "--- a/a.txt\n"
                "+++ b/a.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " abcde\n"
                " bcdef\n"
                "-acegi\n",
            ),
            "test://path/to/diff/4": mock_http_response(
                {},
                ""
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..f92c3c3 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                "-12345\n"
                " 34567\n"
                " 56789\n",
            ),
        }
        return mapping[arg]

    mocker.patch("requests.get", side_effect=side_effect)

    main = Main("origin", "cache")
    main.update()

    assert sorted(main.search("")) == [1, 2, 3]
    assert sorted(main.search("567")) == [1, 2, 3]
    assert sorted(main.search("123")) == [3]
    with Path.open(Path("cache/testOwner/testRepo/LASTUPDATED")) as f:
        assert json.loads(f.read()) == ["1989-07-13T02:36:43+00:00", [1]]

    main.update()

    assert sorted(main.search("")) == [2, 3, 4]
    assert sorted(main.search("ace")) == [3]
    assert sorted(main.search("123")) == [3, 4]
    with Path.open(Path("cache/testOwner/testRepo/LASTUPDATED")) as f:
        assert json.loads(f.read()) == ["2005-01-29T18:23:00+00:00", [1]]

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Listing open pull requests...... \r"
        "Listing open pull requests...... done.                   \n"
        "Fetching diffs of pull requests...... (0/3)\r"
        "Fetching diffs of pull requests...... (1/3)\r"
        "Fetching diffs of pull requests...... (2/3)\r"
        "Fetching diffs of pull requests...... (3/3)\r"
        "Fetching diffs of pull requests...... done.                   \n"
        "Listing updated pull requests...... \r"
        "Listing updated pull requests...... done.                   \n"
        "Fetching diffs of pull requests...... (0/1)\r"
        "Fetching diffs of pull requests...... (1/1)\r"
        "Fetching diffs of pull requests...... done.                   \n"
    )


@pytest.mark.usefixtures("repo_tmp")
def test_main_2(mocker: MockerFixture, capsys: CaptureFixture[str]) -> None:
    def side_effect(arg: str, timeout: int) -> Response:
        assert timeout > 0
        mapping = {
            "https://api.github.com/repos/testOwner/testRepo/pulls"
            "?sort=updated&direction=desc&per_page=100&page=1": mock_http_response(
                {},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/1",
                            "diff_url": "test://path/to/diff/1",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/2",
                            "diff_url": "test://path/to/diff/2",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/3",
                            "diff_url": "test://path/to/diff/3",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "open",
                        },
                    ],
                ),
            ),
            "https://api.github.com/repos/testOwner/testRepo/pulls"
            "?sort=updated&direction=desc&state=all&per_page=100&page=1": mock_http_response(
                {"Link": '<tests://NextLinkUpdated>; rel="next", <tests://LastLink>; rel="last", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/1",
                            "diff_url": "test://path/to/diff/1",
                            "updated_at": "1989-07-13T02:36:44Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/2",
                            "diff_url": "test://path/to/diff/2",
                            "updated_at": "1989-07-13T02:36:44Z",
                            "state": "closed",
                        },
                    ],
                ),
            ),
            "tests://NextLinkUpdated": mock_http_response(
                {"Link": '<tests://PrevLink>; rel="prev", <tests://FirstLink>; rel="first", '},
                json.dumps(
                    [
                        {
                            "url": "test://path/to/pr/3",
                            "diff_url": "test://path/to/diff/3",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "open",
                        },
                        {
                            "url": "test://path/to/pr/4",
                            "diff_url": "test://path/to/diff/4",
                            "updated_at": "1989-07-13T02:36:43Z",
                            "state": "closed",
                        },
                    ],
                ),
            ),
            "test://path/to/diff/1": mock_http_response(
                {},
                ""
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..c65f630 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " 12345\n"
                "-34567\n"
                " 56789\n",
            ),
            "test://path/to/diff/2": mock_http_response(
                {},
                ""
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..4eb6cfb 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " 12345\n"
                " 34567\n"
                "-56789\n"
                "diff --git a/a.txt b/a.txt\n"
                "index aa410fc..eeaeebf 100644\n"
                "--- a/a.txt\n"
                "+++ b/a.txt\n"
                "@@ -1,3 +1,2 @@\n"
                "-abcde\n"
                " bcdef\n"
                " acegi\n",
            ),
            "test://path/to/diff/3": mock_http_response(
                {},
                ""
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..e2f2476 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1 @@\n"
                "-12345\n"
                "-34567\n"
                " 56789\n"
                "diff --git a/a.txt b/a.txt\n"
                "index aa410fc..70ecb1d 100644\n"
                "--- a/a.txt\n"
                "+++ b/a.txt\n"
                "@@ -1,3 +1,2 @@\n"
                " abcde\n"
                " bcdef\n"
                "-acegi\n",
            ),
            "test://path/to/diff/4": mock_http_response(
                {},
                "diff --git a/1.txt b/1.txt\n"
                "index 8a5cb96..f92c3c3 100644\n"
                "--- a/1.txt\n"
                "+++ b/1.txt\n"
                "@@ -1,3 +1,2 @@\n"
                "-12345\n"
                " 34567\n"
                " 56789\n",
            ),
        }
        return mapping[arg]

    mocker.patch("requests.get", side_effect=side_effect)

    main = Main("origin", "cache")

    main.update()
    with Path.open(Path("cache/testOwner/testRepo/LASTUPDATED")) as f:
        s = f.read()
        assert json.loads(s)[0] == "1989-07-13T02:36:43+00:00"
        assert sorted(json.loads(s)[1]) == [1, 2, 3]

    main.update()
    with Path.open(Path("cache/testOwner/testRepo/LASTUPDATED")) as f:
        s = f.read()
        assert json.loads(s)[0] == "1989-07-13T02:36:44+00:00"
        assert sorted(json.loads(s)[1]) == [1, 2]

    main = Main("origin", "cache")
    main.update()
    with Path.open(Path("cache/testOwner/testRepo/LASTUPDATED")) as f:
        s = f.read()
        assert json.loads(s)[0] == "1989-07-13T02:36:44+00:00"
        assert sorted(json.loads(s)[1]) == [1, 2]

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Listing open pull requests...... \r"
        "Listing open pull requests...... done.                   \n"
        "Fetching diffs of pull requests...... (0/3)\r"
        "Fetching diffs of pull requests...... (1/3)\r"
        "Fetching diffs of pull requests...... (2/3)\r"
        "Fetching diffs of pull requests...... (3/3)\r"
        "Fetching diffs of pull requests...... done.                   \n"
        "Listing updated pull requests...... \r"
        "Listing updated pull requests...... done.                   \n"
        "Fetching diffs of pull requests...... (0/1)\r"
        "Fetching diffs of pull requests...... (1/1)\r"
        "Fetching diffs of pull requests...... done.                   \n"
        "Listing updated pull requests...... \r"
        "Listing updated pull requests...... done.                   \n"
        "Fetching diffs of pull requests...... (0/0)\r"
        "Fetching diffs of pull requests...... done.                   \n"
    )
