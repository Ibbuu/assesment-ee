"""Client for the GitHub gists endpoint."""

import logging

import requests

log = logging.getLogger(__name__)


class GitHubError(Exception):
    pass


class UserNotFound(GitHubError):
    pass


class RateLimited(GitHubError):
    pass


class UpstreamUnavailable(GitHubError):
    pass


class GistsClient:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()

    def list_public_gists(self, username):
        """Return every public gist for a user, following GitHub's paging."""
        url = "{}/users/{}/gists".format(self.config.GITHUB_API_URL, username)
        params = {"per_page": self.config.PAGE_SIZE}

        gists = []
        pages = 0
        while url and pages < self.config.MAX_PAGES:
            response = self._get(url, params)
            gists.extend(self._body(response))
            pages += 1

            # The next link already has the paging params in it.
            next_link = response.links.get("next")
            url = next_link["url"] if next_link else None
            params = None

        if url:
            log.warning("stopped at %s pages of gists for %s", pages, username)

        return gists

    def _get(self, url, params):
        headers = {
            "Accept": "application/vnd.github+json",
            # Pinned so a future default doesn't change the payload under us.
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.GITHUB_TOKEN:
            headers["Authorization"] = "Bearer " + self.config.GITHUB_TOKEN

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise UpstreamUnavailable("could not reach GitHub: {}".format(exc))

        if response.status_code == 404:
            raise UserNotFound(url)

        # GitHub uses 403 for rate limiting as well as for refusing a request,
        # so the remaining-requests header is what tells them apart.
        if response.status_code in (403, 429):
            out_of_quota = response.headers.get("X-RateLimit-Remaining") == "0"
            if response.status_code == 429 or out_of_quota:
                raise RateLimited("rate limit exhausted")
            raise UpstreamUnavailable("GitHub refused the request")

        if response.status_code != 200:
            raise UpstreamUnavailable("unexpected status {}".format(response.status_code))

        return response

    @staticmethod
    def _body(response):
        try:
            return response.json()
        except ValueError:
            raise UpstreamUnavailable("GitHub returned a non-JSON body")
