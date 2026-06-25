"""App-level configuration.

GITHUB_TOKEN is intentionally a placeholder here — it is injected from the
DRAFT_PAT GitHub Actions secret at build time (see deploy.yml).
For local development, set DRAFT_PAT in your environment and it will be read below.
"""
import os

GITHUB_REPO = "maxquirk/draft"
GITHUB_BRANCH = "main"
GITHUB_DRAFTS_PATH = "app/data/saved_drafts.csv"
# Reads from env var at runtime so local dev works without hardcoding the token.
# In production the deploy workflow replaces DRAFT_PAT_PLACEHOLDER via sed.
GITHUB_TOKEN = os.environ.get("DRAFT_PAT", "DRAFT_PAT_PLACEHOLDER")
