"""Independent v5 input fixtures, not generated from production constructors."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bare(seed=0):
    image = hashlib.sha256(str(seed).encode()).hexdigest()
    problem = {'binders': [], 'premises': [], 'nondegeneracy': [], 'goal': None}
    content = digest({'image_sha256': image, 'predicate_registry': 'v1', 'problem': problem})
    nonce = f'{seed:016x}'
    return {'schema': 'oae-mve-observation-v5', 'content_hash': content,
        'record_id': digest([content, None, None, nonce]), 'revision': 1, 'stage': 'ingested',
        'lineage': {'parent_record_id': None, 'reason': None},
        'versions': {'code_sha': 'a'*40, 'predicate_registry': 'v1',
            'measurement_contract': None, 'classifier_weights': None,
            'label_set': None, 'calibration_lock': None},
        'image': {'sha256': image, 'width': 200, 'height': 200, 'source': 'user:12345678',
            'track': 'annotated_problem', 'eval_task': 'none'},
        'domain': 'euclidean_plane', 'problem': problem, 'sources': [], 'entities': [],
        'observations': [], 'measurements': [], 'derivations': [], 'assumptions': [],
        'judgments': [], 'decisions': [], 'formal': {'status': 'none', 'propositions': [], 'depends_on': []},
        'events': [{'id': 'evt_1', 'at': '2026-09-27T00:00:00Z', 'actor': 'ingest',
            'kind': 'created', 'from_revision': 0, 'to_revision': 1, 'touches': []}],
        'provenance': {'perceiver_model': None, 'perceiver_calls': 0, 'prompt_sha256': None,
            'request_nonce': nonce, 'raw_response_sha256': [],
            'created_at': '2026-09-27T00:00:00Z', 'cost_usd': 0}}


def populated():
    data = bare()
    prop = {'pred': 'Collinear', 'args': ['A', 'B', 'C']}
    data['sources'] = [{'id': 'txt_1', 'kind': 'text', 'sha256': 'b'*64,
                         'span': [0, 30], 'depends_on': []}]
    data['problem'] = {'binders': [{'name': x, 'type': 'Point', 'entity': f'ent_{i}'}
                                  for i,x in enumerate('ABC',1)],
        'premises': [{'id': 'prm_1', 'proposition': prop, 'depends_on': ['txt_1']}],
        'nondegeneracy': [], 'goal': {'id': 'goal_1', 'kind': 'prove',
                                      'proposition': prop, 'depends_on': ['txt_1']}}
    data['entities'] = [{'id': f'ent_{i}', 'label': x, 'kind': 'point',
        'depends_on': ['prm_1', 'goal_1'], 'geometries': [{'id': f'geo_{i}',
        'source': 'perceiver_call_1', 'frame': 'pixel_topleft_xy',
        'params': [10*i, 20], 'depends_on': [f'ent_{i}']}]} for i,x in enumerate('ABC',1)]
    canonical_problem = {'binders': [{'name': x, 'type': 'Point'} for x in 'ABC'],
                          'premises': [prop], 'nondegeneracy': [],
                          'goal': {'kind': 'prove', 'proposition': prop}}
    content = digest({'image_sha256': data['image']['sha256'], 'predicate_registry': 'v1',
                      'problem': canonical_problem})
    data['content_hash'] = content
    data['provenance'].update(perceiver_model='fixture', perceiver_calls=1,
                             prompt_sha256='c'*64, raw_response_sha256=['d'*64])
    data['record_id'] = digest([content,'fixture','c'*64,'0000000000000000'])
    data['stage'] = 'perceived'
    data['observations'] = [{'id': 'obs_1', 'call': 1, 'kind': 'proposition',
        'confidence': .5, 'proposition': {'pred': 'Collinear','args':['ent_1','ent_2','ent_3']},
        'depends_on': ['geo_1','geo_2','geo_3']}]
    return data
