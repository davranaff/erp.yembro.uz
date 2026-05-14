import multiprocessing

# Workers: 2×CPU + 1 is the standard formula. On Railway starter (1 vCPU)
# that gives 3. Cap at 4 to stay within memory budget.
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)

# Gevent workers overlap I/O wait (DB, Redis, external HTTP) for free.
# Requires `pip install gevent`.
worker_class = "gevent"
worker_connections = 1000

# Recycle workers periodically to prevent memory leaks.
max_requests = 1000
max_requests_jitter = 100

# Railway sends a SIGTERM and expects the process to exit within 30 s.
timeout = 30
graceful_timeout = 20
keepalive = 5

# Logging — forward to stdout so Railway captures it.
accesslog = "-"
errorlog = "-"
loglevel = "warning"

# Bind is set via the CMD in Dockerfile / Procfile; leave it unset here
# so the explicit --bind flag wins.
