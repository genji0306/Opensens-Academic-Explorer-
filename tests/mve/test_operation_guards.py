from copy import deepcopy
import pytest
from mve.record import Record,RecordError,transition,create
from mve.semantics import validate
from tests.mve.fixtures import bare,populated
from tests.mve.test_authority import supported,checked,AT


def test_measure_and_derive():
    r=Record.from_dict(populated()); prop=r.to_dict()['observations'][0]['proposition']
    measurement={'id':'mea_1','proposition':prop,'method':'coordinate_consistency','kernel':'fixture',
        'outcome':'consistent','residual':0,'residual_unit':'px_normalized','tolerance':.01,
        'depends_on':['obs_1','geo_1','geo_2','geo_3']}
    r=transition(r,'measure',actor='A2',expected_revision=1,at=AT,
                 payload={'measurements':[measurement],'measurement_contract':'fixture-v1'})
    derivation={'id':'der_1','engine':'fixture','target':prop,'outcome':'proved',
                'trace_sha256':'a'*64,'budget_s':1,'depends_on':['prm_1']}
    r=transition(r,'derive',actor='A2c',expected_revision=2,at=AT,payload={'derivations':[derivation]})
    assert r.to_dict()['stage']=='derived'


@pytest.mark.parametrize('defect',['missing_geometry','mixed_image','negative_residual','wrong_outcome'])
def test_measurement_guards(defect):
    d=populated(); m={'id':'mea_1','proposition':d['observations'][0]['proposition'],
        'method':'coordinate_consistency','kernel':'fixture','outcome':'consistent','residual':0,
        'residual_unit':'px_normalized','tolerance':.01,'depends_on':['obs_1','geo_1','geo_2','geo_3']}
    d['measurements']=[m]
    if defect=='missing_geometry': m['depends_on']=['obs_1','geo_1']
    elif defect=='mixed_image': m['method']='image_measurement'
    elif defect=='negative_residual': m['residual']=-1
    else: m['residual']=1
    with pytest.raises(RecordError): validate(d)


def test_review_requires_eligible_reviewer():
    d=checked(); d['stage']='reviewed'
    d['judgments']=[{'id':'jud_1','judge':'model:random','target':'tc_1','question':'review',
        'verdict':'confirm','weight':.5,'at':AT,'depends_on':['tc_1']}]
    with pytest.raises(RecordError): validate(d)


def test_editing_assertion_invalidates_exact_geometry_owner_edge():
    d=populated()
    del d['entities'][0]['geometries'][0]['depends_on'][:]
    with pytest.raises(RecordError): validate(d)


def test_formalization_cannot_replace_proof_while_emitting():
    d=checked(); emitted=deepcopy(d['formal']); emitted['status']='emitted'
    r=Record.from_dict(d)
    with pytest.raises(RecordError):
        transition(r,'formalize',actor='A4',expected_revision=1,at=AT,payload={'formal':emitted})


def test_patch_cannot_rewrite_history_or_validity():
    r=Record.from_dict(populated())
    for path in ('/revision','/events/0/actor','/observations/0/valid','/sources/0/id'):
        with pytest.raises(RecordError):
            transition(r,'edit',actor='human:alice',expected_revision=1,at=AT,
                payload={'patch':[{'op':'add','path':path,'value':'bad'}]})


def test_create_and_duplicate_json():
    d=bare(); r=create(d,AT)
    assert Record.from_json(r.to_json())==r
    with pytest.raises(RecordError): Record.from_json('{"schema":"a","schema":"b"}')
    d['stage']='perceived'
    with pytest.raises(RecordError): create(d,AT)


def test_unknown_payload_fields_rejected():
    r=Record.from_dict(populated())
    with pytest.raises(RecordError):
        transition(r,'ingest',actor='A7',expected_revision=1,at=AT,payload={'secret_override':True})


def test_perception_can_add_entities_and_geometry():
    d=bare(); r=Record.from_dict(d)
    geo={'id':'geo_1','source':'perceiver_call_1','frame':'pixel_topleft_xy',
         'params':[10,10],'depends_on':['ent_1']}
    ent={'id':'ent_1','kind':'point','depends_on':[],'geometries':[geo]}
    obs={'id':'obs_1','kind':'free_text','free_text':'a point','confidence':.5,
         'call':1,'depends_on':['geo_1']}
    provenance=deepcopy(d['provenance'])
    provenance.update(perceiver_model='fixture',perceiver_calls=1,
                      prompt_sha256='a'*64,raw_response_sha256=['b'*64])
    r=transition(r,'perceive',actor='A1',expected_revision=1,at=AT,
        payload={'entities':[ent],'observations':[obs],'provenance':provenance})
    assert r.to_dict()['stage']=='perceived'
    assert len(r.to_dict()['entities'])==1


def test_invalidated_human_adoption_retains_historical_proposition():
    d=populated()
    d['judgments']=[{'id':'jud_1','judge':'human:alice','target':'obs_1',
        'question':'assumption_adopt','verdict':'adopt','weight':1,'at':AT,'depends_on':['obs_1']}]
    d['assumptions']=[{'id':'asm_1','adopted_by':'human:alice',
        'proposition':deepcopy(d['observations'][0]['proposition']),'depends_on':['jud_1']}]
    r=transition(Record.from_dict(d),'edit',actor='human:alice',expected_revision=1,at=AT,
        payload={'patch':[{'op':'replace','path':'/observations/0/proposition/pred','value':'RightAngle'}]})
    out=r.to_dict()
    assert not out['assumptions'][0]['valid']
    assert out['assumptions'][0]['proposition']['pred']=='Collinear'
    assert out['observations'][0]['proposition']['pred']=='RightAngle'
