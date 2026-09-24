"""GitHub is stubbed out with `responses`, so these run offline and don't eat
into the API rate limit."""

import pytest
import requests
import responses

from gistservice import create_app
from gistservice.config import Config

# .test can never resolve, so if a stub is ever missed the call fails loudly
# instead of quietly going to the real GitHub.
API = "https://api.github.test"
GISTS_URL = API + "/users/octocat/gists"

# Trimmed down from a real response for octocat.
OCTOCAT_GISTS = [
    {
        "id": "aa5a315d61ae9438b18d",
        "description": "Hello world!",
        "public": True,
        "html_url": "https://gist.github.com/octocat/aa5a315d61ae9438b18d",
        "created_at": "2014-05-15T22:38:42Z",
        "updated_at": "2019-01-25T22:03:18Z",
        "comments": 0,
        "files": {
            "hello_world.rb": {
                "filename": "hello_world.rb",
                "type": "application/x-ruby",
                "language": "Ruby",
                "raw_url": "https://gist.githubusercontent.com/octocat/raw/hello_world.rb",
                "size": 167,
            }
        },
    },
    {
        "id": "6cad326836d38bd3a7ae",
        "description": "Hello world Python",
        "public": True,
        "html_url": "https://gist.github.com/octocat/6cad326836d38bd3a7ae",
        "created_at": "2014-05-15T22:38:20Z",
        "updated_at": "2019-01-25T22:03:18Z",
        "comments": 0,
        "files": {
            "hello_world.py": {
                "filename": "hello_world.py",
                "type": "application/x-python",
                "language": "Python",
                "raw_url": "https://gist.githubusercontent.com/octocat/raw/hello_world.py",
                "size": 199,
            }
        },
    },
]


class StubConfig(Config):
    GITHUB_API_URL = API
    GITHUB_TOKEN = None
    REQUEST_TIMEOUT = 2
    MAX_PAGES = 5
    CACHE_TTL = 0  # off by default, the cache test turns it back on
    TESTING = True


@pytest.fixture
def client():
    return create_app(StubConfig).test_client()


@responses.activate
def test_lists_a_users_gists(client):
    responses.get(GISTS_URL, json=OCTOCAT_GISTS)

    response = client.get("/octocat")

    assert response.status_code == 200
    body = response.get_json()
    assert [gist["id"] for gist in body] == [g["id"] for g in OCTOCAT_GISTS]
    assert body[0]["url"] == OCTOCAT_GISTS[0]["html_url"]
    assert body[0]["description"] == "Hello world!"
    assert body[0]["files"] == [
        {
            "filename": "hello_world.rb",
            "language": "Ruby",
            "size": 167,
            "raw_url": "https://gist.githubusercontent.com/octocat/raw/hello_world.rb",
        }
    ]


@responses.activate
def test_asks_for_the_largest_page_github_allows(client):
    responses.get(GISTS_URL, json=[])

    client.get("/octocat")

    assert responses.calls[0].request.params["per_page"] == "100"


@responses.activate
def test_user_with_no_gists_gets_an_empty_list(client):
    responses.get(API + "/users/nobody/gists", json=[])

    response = client.get("/nobody")

    assert response.status_code == 200
    assert response.get_json() == []


@responses.activate
def test_follows_paging(client):
    page_two = GISTS_URL + "?per_page=100&page=2"
    responses.get(
        GISTS_URL,
        json=[{"id": "page-one"}],
        headers={"Link": '<{}>; rel="next"'.format(page_two)},
        match=[responses.matchers.query_param_matcher({"per_page": "100"})],
    )
    responses.get(
        GISTS_URL,
        json=[{"id": "page-two"}],
        match=[responses.matchers.query_param_matcher({"per_page": "100", "page": "2"})],
    )

    response = client.get("/octocat")

    assert [gist["id"] for gist in response.get_json()] == ["page-one", "page-two"]


@responses.activate
def test_stops_at_the_page_limit():
    # A stub that always claims there is another page.
    link = '<{}?per_page=100&page=99>; rel="next"'.format(GISTS_URL)
    responses.get(GISTS_URL, json=[{"id": "x"}], headers={"Link": link})

    class ThreePages(StubConfig):
        MAX_PAGES = 3

    response = create_app(ThreePages).test_client().get("/octocat")

    assert len(response.get_json()) == 3


@responses.activate
def test_unknown_user_is_a_404(client):
    responses.get(API + "/users/nosuchuser/gists", json={"message": "Not Found"}, status=404)

    response = client.get("/nosuchuser")

    assert response.status_code == 404
    assert response.get_json() == {"error": "user not found"}


@responses.activate
def test_rate_limiting_comes_back_as_429(client):
    responses.get(
        GISTS_URL,
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={"X-RateLimit-Remaining": "0"},
    )

    response = client.get("/octocat")

    assert response.status_code == 429


@responses.activate
def test_github_error_is_a_502(client):
    responses.get(GISTS_URL, body="boom", status=500)

    response = client.get("/octocat")

    assert response.status_code == 502


@responses.activate
def test_timeout_is_a_502(client):
    responses.get(GISTS_URL, body=requests.ConnectTimeout("too slow"))

    response = client.get("/octocat")

    assert response.status_code == 502


@responses.activate
def test_token_is_sent_when_configured():
    responses.get(GISTS_URL, json=[])

    class WithToken(StubConfig):
        GITHUB_TOKEN = "s3cret"

    create_app(WithToken).test_client().get("/octocat")

    assert responses.calls[0].request.headers["Authorization"] == "Bearer s3cret"


@pytest.mark.parametrize("username", ["a" * 40, "under_score", "has.dot"])
def test_bad_usernames_are_rejected_without_calling_github(client, username):
    # No stubs registered here, so an outbound call would fail the test.
    assert client.get("/" + username).status_code == 400


@responses.activate
def test_repeat_lookups_come_from_the_cache():
    responses.get(GISTS_URL, json=OCTOCAT_GISTS)

    class Cached(StubConfig):
        CACHE_TTL = 60

    cached_client = create_app(Cached).test_client()
    first = cached_client.get("/octocat")
    second = cached_client.get("/OCTOCAT")

    assert first.get_json() == second.get_json()
    assert len(responses.calls) == 1


def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
