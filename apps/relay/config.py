"""Frozen v1 product rules. Epoch seconds are UTC, independent of host timezone."""
import time

MAX_FILE = 5_000_000_000
MAX_STORAGE = 500_000_000_000
FILE_TTL = 24 * 3600
RETRY_WINDOW = 10 * 60
PAIR_TTL = 10 * 60
UPLOAD_TTL = 24 * 3600
CHUNK_SIZE = 4 * 1024 * 1024
SCAN_INTERVAL = 60
LEASE_TTL = 90
LEASE_HEARTBEAT = 15
# 1 GB over ~35 KB/s; even a renewing transfer has a finite protection period.
MAX_DOWNLOAD_SECONDS = 8 * 3600
COOKIE_AGE = 10 * 365 * 24 * 3600
now = time.time
