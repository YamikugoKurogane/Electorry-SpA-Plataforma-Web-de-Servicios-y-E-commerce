import multiprocessing

bind = "0.0.0.0:8000"
workers = int(__import__("os").environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
timeout = 30
graceful_timeout = 30
max_requests = 1000          # reciclar workers evita fugas de memoria
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
