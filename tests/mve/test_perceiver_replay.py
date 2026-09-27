import gzip
import hashlib
import json
import pytest
from mve.record import Record
from mve.errors import RecordError
from mve.identity import execution_hash
from mve.predicates import canonical_proposition
from tests.mve.perceiver_helpers import ROOT, OFF, book, reply, run
from mve.perceiver import perceive, Replay
from mve.perceiver.contract import ImageInput


@pytest.mark.parametrize('seed',range(5))
def test_frozen_wp2_development_replays_are_evidence_only(tmp_path,seed):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    row=manifest['items'][seed]
    assert row['split']=='development'
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    ledger=book(tmp_path)
    result=perceive(ledger,ImageInput((ROOT/f'public/development_{seed}.png').read_bytes()),
        replay=Replay((reply(1,seed),reply(2,seed))),output=tmp_path/'run',nonce=f'{seed:016x}',clock=lambda:OFF)
    data=result.record.to_dict()
    assert Record.from_json(result.record.to_json())==result.record
    assert data['stage']=='perceived' and data['provenance']['perceiver_calls']==2
    assert data['sources']==[] and data['problem']['premises']==[]
    assert data['formal']['propositions']==[] and data['assumptions']==[] and data['derivations']==[]
    assert data['provenance']['cost_usd']==0 # actual hosted spend; simulated totals in receipt
    assert result.report()['simulated_cost_usd']=='0.003600'
    assert result.report()['hosted_calls']==0
    assert len(ledger.snapshot()['attempts'])==2
    assert len(result.report()['alignment']['matches'])==len(data['entities'])
    assert all(len(e['geometries'])==2 for e in data['entities'])
    labels={e['id']:e['label'] for e in data['entities']}
    props=[canonical_proposition(o['proposition'],labels) for o in data['observations'] if o['kind']=='proposition']
    assert props[0]==props[1]
    # Only the test scorer reads these frozen development answers, after inference.
    truth_bytes=gzip.decompress((ROOT/f'truth/development_{seed}.json.gz').read_bytes())
    assert hashlib.sha256(truth_bytes).hexdigest()==row['truth_sha256']
    truth=json.loads(truth_bytes)
    candidate=next(c for c in truth['candidates'] if c['proposition']==props[0])
    assert candidate['class'] in {'premise','incidental_unproved','false','unknown'}
    assert data['image']['sha256']==row['image_sha256']
    assert (tmp_path/'run/record.json').read_text().strip()==result.record.to_json()


def test_observations_cannot_authorise_and_returned_record_is_immutable(tmp_path):
    result=run(tmp_path)
    data=result.record.to_dict()
    obs=next(o for o in data['observations'] if o['kind']=='proposition')
    data['formal']['propositions']=[{'id':'prop_1','role':'hypothesis','proposition':obs['proposition'],
        'support':'assumption','depends_on':[obs['id']]}]
    with pytest.raises(RecordError):
        Record.from_dict(data)
    assert result.record.to_dict()['formal']['propositions']==[]


def test_two_identical_requests_no_first_reply_or_truth_in_second_prompt(tmp_path):
    result=run(tmp_path)
    requests=[json.loads(p.read_text()) for p in sorted((tmp_path/'run').glob('call*/request.json'))]
    assert requests[0]==requests[1]
    assert requests[0]['thinking'] is False and requests[0]['temperature']==0
    assert requests[0]['model']=='deepseek-flash'
    assert 'truth' not in requests[0]['prompt']
    assert result.report()['alignment']['agreement_is_verification'] is False
