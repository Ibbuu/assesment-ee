import logging
import os
import re

from flask import Flask, jsonify

from .cache import TTLCache
from .config import Config
from .github import GistsClient, RateLimited, UpstreamUnavailable, UserNotFound

log = logging.getLogger(__name__)


USERNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")


def create_app(config=None, client=None):
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = config or Config
    app = Flask(__name__)
    app.config.from_object(config)

    client = client or GistsClient(config)
    cache = TTLCache(config.CACHE_TTL)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/<username>")
    def list_gists(username):
        if not USERNAME_RE.match(username):
            return error(400, "not a valid GitHub username")

        key = username.lower()
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)

        try:
            gists = client.list_public_gists(username)
        except UserNotFound:
            return error(404, "user not found")
        except RateLimited:
            return error(429, "GitHub rate limit exceeded, try again later")
        except UpstreamUnavailable as exc:
            log.warning("gist lookup failed for %s: %s", username, exc)
            return error(502, "GitHub is unavailable")

        log.info("returning %s gists for %s", len(gists), username)
        payload = [summarise(gist) for gist in gists]
        cache.set(key, payload)
        return jsonify(payload)

    @app.errorhandler(404)
    def not_found(_):
        return error(404, "not found, try /<username>")

    @app.errorhandler(405)
    def method_not_allowed(_):
        return error(405, "method not allowed")

    return app


def error(status, message):
    return jsonify(error=message), status


def summarise(gist):
    """Most of GitHub's gist payload is URLs we don't need, so pull out the
    bits a caller is likely to want."""
    files = gist.get("files") or {}
    return {
        "id": gist.get("id"),
        "description": gist.get("description"),
        "url": gist.get("html_url"),
        "created_at": gist.get("created_at"),
        "updated_at": gist.get("updated_at"),
        "comments": gist.get("comments"),
        "files": [
            {
                "filename": name,
                "language": meta.get("language"),
                "size": meta.get("size"),
                "raw_url": meta.get("raw_url"),
            }
            for name, meta in files.items()
        ],
    }
