"""Request log for Locust: the platform's standard "http-requests" format.

Loaded by Locust next to the application's own locustfile
(`locust -f locustfile.py,request_log.py`), so that the locustfile itself stays
untouched. Writes one row per request into <dir>/000001.csv, 000002.csv... (a new
file every --requests-per-file rows, each with its header). Columns:

  timestamp           request start, Unix seconds (with decimals)
  method, endpoint    e.g. GET, /product/OLJCESPC7Z
  status_code         HTTP status, when a response was received
  no_response_reason  only when no response was received, one of:
                        timeout             no answer in time (e.g. overloaded service)
                        connection_refused  nothing listening (e.g. pod stopped)
                        connection_reset    connection cut mid-request (e.g. pod evicted)
                        other               any other transport failure
                      empty otherwise
"""

import csv
import time
from pathlib import Path

from locust import events

FIELDS = [
    "timestamp",
    "method",
    "endpoint",
    "status_code",
    "response_time_ms",
    "no_response_reason",
]


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--requests-dir",
        default="",
        help="Directory of the per-request CSV files (http-requests format). Disabled if empty.",
    )
    parser.add_argument(
        "--requests-per-file",
        type=int,
        default=100000,
        help="Rows per CSV file before starting a new one (default: 100000)",
    )


def no_response_reason(exception) -> str:
    """Maps a client-side exception to a fixed, library-independent value."""
    text = " ".join(
        f"{type(e).__name__} {e}".lower() for e in _exception_chain(exception)
    )
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "refused" in text:
        return "connection_refused"
    if any(word in text for word in ("reset", "disconnected", "aborted", "broken pipe")):
        return "connection_reset"
    return "other"


def _exception_chain(exception):
    seen = set()
    while exception is not None and id(exception) not in seen:
        seen.add(id(exception))
        yield exception
        exception = exception.__cause__ or exception.__context__ or (
            exception.args[0] if exception.args and isinstance(exception.args[0], BaseException)
            else None
        )


class RequestLog:
    def __init__(self, directory: str, per_file: int):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.per_file = per_file
        self.index = 0
        self.rows = 0
        self.stream = None
        self.writer = None

    def _next_file(self):
        if self.stream is not None:
            self.stream.close()
        self.index += 1
        self.rows = 0
        self.stream = (self.directory / f"{self.index:06d}.csv").open("w", newline="")
        self.writer = csv.writer(self.stream)
        self.writer.writerow(FIELDS)

    def write(self, method, endpoint, response_time, response, exception, start_time):
        if self.writer is None or self.rows >= self.per_file:
            self._next_file()
        status = getattr(response, "status_code", None) if response is not None else None
        # A received response has a status code (an HTTP error included); only
        # when there is none do we record why.
        reason = "" if status else no_response_reason(exception)
        self.writer.writerow(
            [
                f"{start_time:.3f}",
                method,
                endpoint,
                status or "",
                f"{response_time:.1f}" if response_time is not None else "",
                reason,
            ]
        )
        self.rows += 1
        self.stream.flush()

    def close(self):
        if self.stream is not None:
            self.stream.close()


_log = None


@events.init.add_listener
def _(environment, **kwargs):
    global _log
    options = environment.parsed_options
    if options is not None and options.requests_dir:
        _log = RequestLog(options.requests_dir, options.requests_per_file)


@events.request.add_listener
def _(request_type, name, response_time, response_length, response=None, exception=None,
      start_time=None, **kwargs):
    if _log is None:
        return
    if start_time is None:
        start_time = time.time() - (response_time or 0) / 1000
    _log.write(request_type, name, response_time, response, exception, start_time)


@events.quitting.add_listener
def _(environment, **kwargs):
    if _log is not None:
        _log.close()
