"""Single HTTPS exchange. Credentials exist only between preparation and return."""

import base64
from dataclasses import dataclass
import json
import subprocess
import urllib.error
import urllib.request

from mve.preflight.probe_contract import ProbeRefused

URL = "https://api.deepseek.com/chat/completions"
MAX_REPLY_BYTES = 1_048_576


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_opener():
    # Disable environment proxies, redirects (including same-host), and HTTP.
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        NoRedirect(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def read_key():
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "oae-deepseek-api-key",
                "-w",
            ],
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            raise ValueError
        key = result.stdout.decode("ascii").rstrip("\r\n")
        if not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError
        return key
    except Exception:
        pass
    # Raise outside the handler: even __context__ must not retain subprocess
    # stdout/stderr or a credential-bearing TimeoutExpired/CalledProcessError.
    raise ProbeRefused("Keychain key unavailable or invalid")


def payload(request):
    return json.dumps(
        {
            "model": request.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(request.image).decode("ascii")
                            },
                        },
                    ],
                }
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": request.max_output_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        },
        separators=(",", ":"),
    ).encode()


@dataclass(frozen=True)
class LiveReply:
    raw: bytes
    http_status: int | None
    error: str | None = None
    raw_redacted: bool = False


def prepare_call(request):
    """Called by prepare_dispatch before its final clock check; never sends here."""
    data = payload(request)
    key = read_key()

    def send():
        return exchange(data, request.timeout_s, key)

    return send


def exchange(data, timeout, key):
    """Internal transport; the live runner is its only production caller."""
    raw, status, error = b"", None, None
    try:
        request = urllib.request.Request(
            URL,
            data=data,
            method="POST",
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        try:
            response = make_opener().open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = response.status
            raw = response.read(MAX_REPLY_BYTES + 1)
            if len(raw) > MAX_REPLY_BYTES:
                error = "response_too_large"
    except Exception as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        error = "timeout" if isinstance(reason, TimeoutError) else "transport_error"
    # Sanitize even a vendor echo before raw persistence; parsing happens later.
    clean = raw.replace(key.encode("ascii"), b"[REDACTED]")
    return LiveReply(clean, status, error, clean != raw)
