import json
import pytest
from mve.preflight.probe_contract import ProbeReply
from tests.mve.perceiver_helpers import run, reply, mutate_reply, content, book


@pytest.mark.parametrize('response,status',[
    (ProbeReply(b'not json','0.0018'),'malformed'),
    (mutate_reply(refusal='cannot comply'),'refused'),
    (mutate_reply(finish='length'),'truncated'),
    (mutate_reply(model='deepseek-v4-pro'),'model_mismatch'),
    (mutate_reply(content={'entities':[],'observations':[]}),'missing_entities'),
    (mutate_reply(content='[]'),'malformed'),
    (mutate_reply(usage=False),'usage_missing'),
    (mutate_reply(bill='NaN'),'invalid_billing'),
])
def test_outcomes_are_distinct_raw_retained_and_billing_counted(tmp_path,response,status):
    ledger=book(tmp_path)
    result=run(tmp_path,[response,reply(2)],ledger=ledger,retries=0)
    assert result.report()['calls'][0]['status']==status
    assert (tmp_path/'run/call1-attempt1/response.raw').read_bytes()==response.raw
    assert result.record is None
    assert ledger.snapshot()['attempts'][0]['state']==('dispatched' if status=='invalid_billing' else 'settled')


def test_retries_are_bounded_and_distinct_charged_attempts(tmp_path):
    bad=ProbeReply(b'broken','0.0018')
    ledger=book(tmp_path)
    result=run(tmp_path,[bad,bad,reply(),reply(2)],ledger=ledger)
    assert result.record is not None
    assert len(result.report()['attempts'])==4
    assert result.report()['simulated_cost_usd']=='0.007200'
    rows=ledger.snapshot()['attempts']
    assert len({r['id'] for r in rows})==4 and all(r['state']=='settled' for r in rows)
    result=run(tmp_path/'exhausted',[bad]*6)
    assert len(result.report()['attempts'])==6 and result.record is None


def test_timeout_keeps_reservation_and_missing_total_is_not_zero(tmp_path):
    ledger=book(tmp_path)
    result=run(tmp_path,['timeout',reply(),reply(2)],ledger=ledger)
    assert result.report()['attempts'][0]['status']=='timeout'
    assert result.report()['simulated_cost_usd'] is None
    assert result.report()['known_simulated_cost_usd']=='0.003600'
    assert ledger.snapshot()['attempts'][0]['state']=='dispatched'
    assert result.record is not None


@pytest.mark.parametrize('change,status',[
    (lambda c:c['entities'][0].update(params=[-1,20]),'out_of_image'),
    (lambda c:c['entities'][0].update(params=[True,20]),'malformed'),
    (lambda c:c['entities'][0].update(params=[1]),'malformed'),
    (lambda c:c['entities'][0].update(params=[float('inf'),20]),'malformed'),
    (lambda c:c['entities'][1].update(id=c['entities'][0]['id']),'malformed'),
    (lambda c:c['observations'][0]['proposition'].update(args=['Z']*4),'missing_entities'),
    (lambda c:c.update(assumptions=[]),'malformed'),
    (lambda c:c['observations'][0].update(confidence=2),'malformed'),
])
def test_content_guards_fail_closed(tmp_path,change,status):
    c=content();change(c)
    result=run(tmp_path,[mutate_reply(content=c),reply(2)],retries=0)
    assert result.report()['calls'][0]['status']==status and result.record is None
