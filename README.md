## :warning: Please read these instructions carefully and entirely first
* Clone this repository to your local machine.
* Use your IDE of choice to complete the assignment.
* When you have completed the assignment, you need to  push your code to this repository and [mark the assignment as completed by clicking here](https://app.snapcode.review/submission_links/610a3f86-55ab-49c3-98fe-a674fd01a6d0).
* Once you mark it as completed, your access to this repository will be revoked. Please make sure that you have completed the assignment and pushed all code from your local machine to this repository before you click the link.

## Operability Take-Home Exercise

Welcome to the start of our recruitment process for Operability Engineers. It was great to speak to you regarding an opportunity to join the Equal Experts network!

Please write code to deliver a solution to the problems outlined below.

We appreciate that your time is valuable and do not expect this exercise to **take more than 90 minutes**. If you think this exercise will take longer than that, I **strongly** encourage you to please get in touch to ask any clarifying questions.

### Submission guidelines
**Do**
- Provide a README file in text or markdown format that documents a concise way to set up and run the provided solution.
- Take the time to read any applicable API or service docs, it may save you significant effort.
- Make your solution simple and clear. We aren't looking for overly complex ways to solve the problem since in our experience, simple and clear solutions to problems are generally the most maintainable and extensible solutions.

**Don't**

Expect the reviewer to dedicate a machine to review the test by:

- Installing software globally that may conflict with system software
- Requiring changes to system-wide configurations
- Providing overly complex solutions that need to spin up a ton of unneeded supporting dependencies. We aspire to keep our dev experiences as simple as possible (but no simpler)!
- Include identifying information in your submission. We are endeavouring to make our review process anonymous to reduce bias.

### Exercise
If you have any questions on the below exercise, please do get in touch and we’ll answer as soon as possible.

#### Build an API, test it, and package it into a container
- Build a simple HTTP web server API in any general-purpose programming language[^1] that interacts with the GitHub API and responds to requests on `/<USER>` with a list of the user’s publicly available Gists[^2].
- Create an automated test to validate that your web server API works. An example user to use as test data is `octocat`.
- Package the web server API into a docker container that listens for requests on port `8080`. You do not need to publish the resulting container image in any container registry, but we are expecting the Dockerfile in the submission.
- The solution may optionally provide other functionality (e.g. pagination, caching) but the above **must** be implemented.

Best of luck,  
Equal Experts
__________________________________________
[^1]: For example Go, Python or Ruby but not Bash or Powershell.  
[^2]: https://docs.github.com/en/rest/gists/gists?apiVersion=2022-11-28

---

# My solution

A small Flask service that returns a GitHub user's public gists, so `GET /octocat` gives you
octocat's gists. There's also `GET /healthz` for probes.

## Docker

```
docker build -t gists-api .
docker run --rm -p 8080:8080 gists-api
curl localhost:8080/octocat
```

## Locally

Python 3.9 or newer, everything into a virtualenv.

```
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python wsgi.py
```

That's Flask's dev server on port 8080. The container runs gunicorn instead.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

GitHub is stubbed out with `responses` so the tests run offline and don't chew through the 60
requests an hour you get without a token. They cover octocat's gists, paging, users with no
gists, unknown users, rate limiting, GitHub being down or slow, username validation and the
cache.

## Response

```
$ curl -s localhost:8080/octocat | jq '.[0]'
{
  "id": "6cad326836d38bd3a7ae",
  "description": "Hello world!",
  "url": "https://gist.github.com/octocat/6cad326836d38bd3a7ae",
  "created_at": "2014-10-01T16:19:34Z",
  "updated_at": "2026-09-20T08:28:06Z",
  "comments": 297,
  "files": [
    {
      "filename": "hello_world.rb",
      "language": "Ruby",
      "size": 175,
      "raw_url": "https://gist.githubusercontent.com/octocat/..."
    }
  ]
}
```

GitHub's gist payload is mostly URLs you'll never use, so I trim it to the fields a caller is
likely to want.

Status codes:

* 200, with an empty list if the user has no gists
* 400 if it couldn't be a GitHub username in the first place
* 404 if GitHub doesn't know the user
* 429 if we've run out of GitHub API quota
* 502 if GitHub is down, slow, or sends back something odd

Errors all look like `{"error": "..."}`.

## Config

Defaults are fine for a quick look. All environment variables:

* `GITHUB_TOKEN` - optional access token. 60 requests an hour without one, 5000 with, so
  worth setting if you're poking at it a lot.
* `GITHUB_API_URL` - defaults to https://api.github.com.
* `REQUEST_TIMEOUT` - seconds to wait on GitHub, default 10.
* `PAGE_SIZE` - gists per page, default 100, which is GitHub's max.
* `MAX_PAGES` - how many pages to follow, default 10.
* `CACHE_TTL` - seconds, default 60. Set to 0 to turn the cache off.
* `LOG_LEVEL` - default INFO.

```
docker run --rm -p 8080:8080 -e GITHUB_TOKEN=... gists-api
```

## A few notes

A user can have more than 100 gists, so the client follows GitHub's `Link: rel="next"`
headers rather than returning a truncated first page. `MAX_PAGES` stops one request to us
turning into an unbounded number of requests to GitHub.

Responses are cached in memory for a minute, which keeps repeat lookups off the rate limit.
It's per worker process. With more workers than this I'd use something shared like Redis.

GitHub answers 403 both when you're out of quota and when it just won't serve you, so the
client looks at `X-RateLimit-Remaining` to tell them apart and returns 429 for the first.
That's more use to a caller than a blanket 502.

The container runs gunicorn rather than Flask's dev server, as a non-root user that doesn't
own the code it runs. Its `--timeout` is set above the worst case of `MAX_PAGES` pages each
waiting `REQUEST_TIMEOUT` on GitHub, so a slow upstream doesn't get a busy worker killed.

Things I left out: no auth on our own endpoints, no metrics, no persistence. All sensible
next steps, none of them needed here.

## Layout

```
wsgi.py                  entry point
gistservice/
  __init__.py            app factory, routes, error handling
  github.py              GitHub client, paging and errors
  cache.py               small TTL cache
  config.py              settings from the environment
tests/test_gists.py
Dockerfile
```

