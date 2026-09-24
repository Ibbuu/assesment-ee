import os


class Config:
    GITHUB_API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or None
    REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "10"))
    # 100 is the maximum GitHub allows.
    PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "100"))
    # Stops a single request walking an unbounded number of pages.
    MAX_PAGES = int(os.environ.get("MAX_PAGES", "10"))
    # Set to 0 to turn the response cache off.
    CACHE_TTL = float(os.environ.get("CACHE_TTL", "60"))
