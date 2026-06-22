"""Offline scraper pipeline for the 2026 MLB Draft Hub.

Runs full Python (requests/selenium/bs4) OUTSIDE the browser, normalizes many big
boards into a single consensus, and writes small static JSON files into app/data/
that the shinylive (Pyodide) app reads. Nothing here runs in the browser.
"""
