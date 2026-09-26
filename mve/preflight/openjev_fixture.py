"""One local inference fixture; a routing answer carries no truth authority."""
from dataclasses import asdict
import json
import importlib.metadata
import sys
import time

sys.path.insert(0, sys.argv[1])
from rhjev.openjev import OpenJevBackend
from rhjev.questions import Choice, make_request

backend = OpenJevBackend()
request = make_request('Three points and three straight segments form a triangle.',
                       {'domain': Choice('Which workflow?', ('plane_geometry', 'topology'))})
start = time.monotonic()
answer = backend.ask(request)
if answer is None:
    raise RuntimeError('openJev inference unavailable')
print(json.dumps({'duration_s': time.monotonic() - start, 'answers': asdict(answer),
                  'complete_input_tokens': backend.token_counts(request),
                  'runtime_versions': {name: importlib.metadata.version(name)
                      for name in ('onnxruntime', 'tokenizers', 'numpy')}}, indent=2))
