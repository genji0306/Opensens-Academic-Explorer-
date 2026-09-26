from copy import deepcopy
import pytest
from mve.record import Record,RecordError,transition
from mve.semantics import validate,content_hash
from mve.identity import execution_hash
from tests.mve.fixtures import populated,bare

AT='2026-09-27T01:00:00Z'


def supported():
    d=populated(); prop=d['observations'][0]['proposition']
    d['assumptions']=[{'id':'asm_1','adopted_by':'policy:fixture','proposition':deepcopy(prop),'depends_on':['obs_1']}]
    d['formal']={'status':'emitted','target':'mathlib','ir_sha256':'1'*64,'statement_sha256':'2'*64,
        'depends_on':['prop_1','prop_2'],'propositions':[
        {'id':'prop_1','role':'hypothesis','proposition':deepcopy(prop),'support':'assumption','depends_on':['asm_1']},
        {'id':'prop_2','role':'goal','proposition':deepcopy(prop),'support':'goal_source','depends_on':['goal_1']}]}
    d['versions'].update(lean_lock_sha='3'*64,lean_toolchain='lean4:v4.29.0')
    d['stage']='formalized'
    return d


def checked():
    d=supported(); d['formal'].update(status='typechecked',typecheck={
        'id':'tc_1','ok':True,'toolchain':'lean4:v4.29.0','log_sha256':'4'*64,
        'depends_on':['prop_1','prop_2']})
    return d


def proof():
    return {'id':'prf_1','prover':'fixture','ok':True,'sorry_free':True,
        'dependency_closure_checked':True,'statement_matches_accepted':True,
        'axioms':['propext','Classical.choice','Quot.sound'],'axiom_policy':'mathlib_standard_only',
        'budget_s':1,'log_sha256':'5'*64,'depends_on':['tc_1']}


def test_human_adoption_is_separate_from_confirmation():
    r=Record.from_dict(populated())
    judgment={'id':'jud_1','judge':'human:alice','question':'assumption_adopt','verdict':'adopt',
              'target':'obs_1','weight':1,'at':AT,'depends_on':['obs_1']}
    r=transition(r,'judge',actor='human:alice',expected_revision=1,at=AT,payload={'judgments':[judgment]})
    asm={'id':'asm_1','adopted_by':'human:alice','proposition':populated()['observations'][0]['proposition'],
         'depends_on':['jud_1']}
    r=transition(r,'adopt',actor='human:alice',expected_revision=2,at=AT,payload={'assumptions':[asm]})
    assert len(r.to_dict()['assumptions'])==1
    for verdict in ('confirm','reject','not_visible','unsure','decline'):
        d=r.to_dict(); d['judgments'][0]['verdict']=verdict
        with pytest.raises(RecordError): validate(d)


@pytest.mark.parametrize('defect',['class','equality','goal','unknown','trace','model','owner','axiom','closure','statement','tc_dependency','proof_dependency','stale_tc'])
def test_unauthorized_formal_evidence(defect):
    d=checked(); prop=d['formal']['propositions'][0]
    if defect=='class': prop['depends_on']=['obs_1']
    elif defect=='equality': prop['proposition']['pred']='RightAngle'
    elif defect=='goal': prop.update(support='goal_source',depends_on=['goal_1'])
    elif defect in ('unknown','trace'):
        d['derivations']=[{'id':'der_1','engine':'fixture','target':deepcopy(prop['proposition']),
            'outcome':'unknown' if defect=='unknown' else 'proved','depends_on':['prm_1'],'budget_s':1}]
        prop.update(support='derived',depends_on=['der_1'])
    elif defect in ('model','owner'):
        d['judgments']=[{'id':'jud_1','judge':'model:fake' if defect=='model' else 'human:bob',
            'question':'assumption_adopt','verdict':'adopt','target':'obs_1','weight':1,'at':AT,'depends_on':['obs_1']}]
        d['assumptions'][0].update(adopted_by='human:alice',depends_on=['jud_1'])
    elif defect=='tc_dependency': d['formal']['typecheck']['depends_on']=['prop_2']
    elif defect=='stale_tc': d['formal']['typecheck']['valid']=False
    else:
        d['formal'].update(status='proved',proof=proof()); d['stage']='proved'
        if defect=='axiom': d['formal']['proof']['axioms'].append('sorryAx')
        if defect=='closure': d['formal']['proof']['dependency_closure_checked']=False
        if defect=='statement': d['formal']['proof']['statement_matches_accepted']=False
        if defect=='proof_dependency': d['formal']['proof']['depends_on']=[]
    with pytest.raises(RecordError): validate(d)


def test_typecheck_prove_review_ingest_and_freeze():
    r=Record.from_dict(supported()); f=checked()['formal']
    r=transition(r,'formalize',actor='A4',expected_revision=1,at=AT,payload={'formal':f})
    r=transition(r,'prove',actor='A5',expected_revision=2,at=AT,payload={'proof':proof(),'status':'proved'})
    j={'id':'jud_1','judge':'audit:Opus','question':'review','verdict':'confirm','target':'prf_1',
       'weight':.5,'at':AT,'depends_on':['prf_1']}
    r=transition(r,'review',actor='Opus',expected_revision=3,at=AT,payload={'judgments':[j]})
    r=transition(r,'ingest',actor='A7',expected_revision=4,at=AT,payload={})
    assert r.to_dict()['stage']=='ingested_atlas'
    with pytest.raises(RecordError):
        transition(r,'edit',actor='human:alice',expected_revision=5,at=AT,
                   payload={'patch':[{'op':'replace','path':'/sources/0/sha256','value':'f'*64}]})


def test_full_artifact_invalidation():
    d=checked(); d['formal'].update(status='proved',proof=proof(),render_back={
        'id':'rnd_1','renderer':'fixture','realizations':'one','sha256':'6'*64,'depends_on':['tc_1']})
    d['stage']='proved'
    r=transition(Record.from_dict(d),'edit',actor='human:alice',expected_revision=1,at=AT,
                payload={'patch':[{'op':'replace','path':'/entities/0/geometries/0/params/0','value':11}]})
    result=r.to_dict()
    assert all(not result['formal'][key]['valid'] for key in ('typecheck','proof','render_back'))
    assert not result['formal']['propositions'][0]['valid']
    assert result['formal']['status']=='none'


def decision(confidence=.9):
    return {'id':'dec_1','question_id':'fixture','primitive':'choice','backend':'replay',
        'state_sha256':'7'*64,'input_tokens':30,'answer':'yes','abstained':False,
        'confidence':confidence,'threshold_high':.9,'threshold_low':.5,'route':'llm',
        'lock_sha256':'8'*64,'depends_on':['obs_1'],'probabilities':{'yes':confidence,'no':1-confidence}}


@pytest.mark.parametrize('confidence,route',[(.5,'human'),(.9,'llm'),(.91,'act')])
def test_decision_boundaries(confidence,route):
    d=populated(); dec=decision(confidence); dec['route']=route; d['decisions']=[dec]
    validate(d)
    dec['route']='act' if route!='act' else 'human'
    with pytest.raises(RecordError): validate(d)


def test_overflow_and_bad_probability():
    d=populated(); dec=decision(); d['decisions']=[dec]
    dec['input_tokens']=513
    with pytest.raises(RecordError): validate(d)
    dec.update(abstained=True,route='human'); validate(d)
    dec['probabilities']={'yes':.9,'no':.9}
    with pytest.raises(RecordError): validate(d)


def synthetic():
    d=bare(); d['image'].update(source='synthetic:fixture:seed0',ground_truth_ref='geo_100',truth={
        'source':'geo_100','split':'fit','family':'triangle','candidate_universe_sha256':'9'*64,
        'math_coordinates_sha256':'a'*64})
    d['sources']=[{'id':'geo_100','kind':'truth_artifact','sha256':'b'*64,'depends_on':[],
        'generator':{'id':'fixture','version':'1','config_sha256':'c'*64,'seed':0,
            'evaluator_version':'exact-1','ddar_version':'1','ddar_budget_s':30,'coordinates_exact':True}}]
    d['stage']='ground_truth'; d['content_hash']=content_hash(d); d['record_id']=execution_hash(d)
    return d


def test_truth_identity_vs_render_and_proof_evidence():
    d=synthetic(); validate(d); identity=d['content_hash']
    d['image']['sha256']='d'*64; d['sources'][0]['sha256']='e'*64
    d['sources'][0]['generator'].update(ddar_version='2',ddar_budget_s=99)
    assert content_hash(d)==identity
    d['sources'][0]['generator']['evaluator_version']='exact-2'
    assert content_hash(d)!=identity
    d=synthetic(); d['sources'][0]['generator']['coordinates_exact']=False
    with pytest.raises(RecordError): validate(d)


def test_truth_edit_creates_lineage_only_for_math_change():
    r=Record.from_dict(synthetic())
    payload={'patch':[{'op':'replace','path':'/sources/0/generator/evaluator_version','value':'exact-2'}]}
    with pytest.raises(RecordError): transition(r,'edit',actor='human:alice',expected_revision=1,at=AT,payload=payload)
    payload['request_nonce']='0000000000000001'
    out=transition(r,'edit',actor='human:alice',expected_revision=1,at=AT,payload=payload).to_dict()
    assert out['lineage']=={'parent_record_id':r.to_dict()['record_id'],'reason':'truth_identity_edit'}


def test_missing_decision_evidence_requires_human():
    d=populated(); dec=decision(); dec['depends_on']=[]; d['decisions']=[dec]
    with pytest.raises(RecordError): validate(d)
    dec.update(abstained=True,route='human'); validate(d)


def test_nondegeneracy_role_rejects_geometric_claim():
    d=supported(); d['formal']['propositions'][0]['role']='nondegeneracy'
    with pytest.raises(RecordError): validate(d)


def test_version_hash_fields_cannot_be_arbitrary_strings():
    d=checked(); d['versions']['lean_lock_sha']='not-a-hash'
    with pytest.raises(RecordError): validate(d)
