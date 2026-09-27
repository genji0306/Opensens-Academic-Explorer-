"""One local inference fixture; a routing answer carries no truth authority."""

from dataclasses import asdict
import json
import sys
import time


def exercise(backend, request):
    """Exercise an injected backend; tests supply a fake, CLI supplies local openJev."""
    start = time.monotonic()
    answer = backend.ask(request)
    if answer is None:
        raise RuntimeError("openJev inference unavailable")
    return {
        "duration_s": time.monotonic() - start,
        "answers": asdict(answer),
        "complete_input_tokens": backend.token_counts(request),
    }


def main():
    sys.path.insert(0, sys.argv[1])
    from rhjev.openjev import OpenJevBackend
    from rhjev.questions import Choice, make_request

    request = make_request(
        "Three points and three straight segments form a triangle.",
        {"domain": Choice("Which workflow?", ("plane_geometry", "topology"))},
    )
    print(json.dumps(exercise(OpenJevBackend(), request), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
