from copy import deepcopy
from dataclasses import FrozenInstanceError
import pytest

from mve.exact import canonical_exact
from mve.record import Record, RecordError, transition
from mve.semantics import canonical_proposition, content_hash, validate
from tests.mve.fixtures import bare, populated


@pytest.mark.parametrize('seed',range(100))
def test_independent_v5_records(seed):
    data = bare(seed)
    assert Record.from_dict(data).to_dict() == data


@pytest.mark.parametrize('value,expected',[('2/4','1/2'),('sqrt(8)','2*sqrt(2)'),
    ('(1+sqrt(2))^2','2*sqrt(2)+3'),('-2','-2'),('90','90')])
def test_exact_normalization(value, expected):
    assert canonical_exact(value) == expected
    assert canonical_exact(expected) == expected


@pytest.mark.parametrize('value',['pi','1.5','__import__("os")','sqrt(-1)', '1/0',
    '2^10000000','sqrt(2+2)','a', 'sin(0)', '('*121+'1'+')'*121])
def test_exact_parser_fails_closed(value):
    with pytest.raises(ValueError): canonical_exact(value)


def test_canonical_symmetries_and_binding():
    p={'pred':'EqualAngle','args':['F','E','D','C','B','A']}
    assert canonical_proposition(p)['args'] == ['A','B','C','D','E','F']
    assert canonical_proposition({'pred':'SBetween','args':['M','Z','A']})['args'] == ['M','A','Z']
    data=populated()
    assert content_hash(data)==data['content_hash']
    validate(data)


@pytest.mark.parametrize('defect', ['id','ref','arity','kind','source','geometry','nan',
    'identity','old_schema','missing_edge','cycle','false_valid','fake_call','unknown_field'])
def test_negative_records(defect):
    d=populated()
    if defect=='id': d['observations'][0]['id']='ent_1'
    elif defect=='ref': d['observations'][0]['depends_on']=['geo_999']
    elif defect=='arity': d['observations'][0]['proposition']['args']=['ent_1']
    elif defect=='kind': d['entities'][0]['kind']='circle'
    elif defect=='source': d['problem']['premises'][0]['depends_on']=['obs_1']
    elif defect=='geometry': d['entities'][0]['geometries'][0]['params']=[10]
    elif defect=='nan': d['entities'][0]['geometries'][0]['params'][0]=float('nan')
    elif defect=='identity': d['record_id']='f'*64
    elif defect=='old_schema': d['schema']='oae-mve-observation-v2'
    elif defect=='missing_edge': d['entities'][0]['depends_on']=[]
    elif defect=='cycle': d['sources'][0]['depends_on']=['obs_1']
    elif defect=='false_valid': d['entities'][0]['valid']=False
    elif defect=='fake_call': d['provenance']['perceiver_calls']=0
    elif defect=='unknown_field': d['image']['extra']=True
    with pytest.raises(RecordError): validate(d)


def test_immutable_roundtrip():
    d=populated(); r=Record.from_dict(d); d['entities'].clear()
    assert len(r.to_dict()['entities'])==3
    with pytest.raises(FrozenInstanceError): r._json='{}'


def test_edit_transitively_invalidates_preserving_evidence():
    r=Record.from_dict(populated())
    result=transition(r,'edit',actor='human:alice',expected_revision=1,
        at='2026-09-27T01:00:00Z',payload={'patch':[
        {'op':'replace','path':'/sources/0/sha256','value':'e'*64}]})
    d=result.to_dict()
    assert d['revision']==2 and d['content_hash']==r.to_dict()['content_hash']
    assert not d['entities'][0]['valid']
    assert not d['entities'][0]['geometries'][0]['valid']
    assert not d['observations'][0]['valid']
    assert set(d['events'][-1]['invalidates']) >= {'prm_1','goal_1','ent_1','geo_1','obs_1'}
    assert r.to_dict()['observations'][0].get('valid',True)


@pytest.mark.parametrize('actor,revision',[('model:x',1),('human:alice',0)])
def test_edits_reject_bad_actor_and_stale_revision(actor,revision):
    with pytest.raises(RecordError):
        transition(Record.from_dict(populated()),'edit',actor=actor,expected_revision=revision,
                   at='2026-09-27T01:00:00Z',payload={'patch':[]})
