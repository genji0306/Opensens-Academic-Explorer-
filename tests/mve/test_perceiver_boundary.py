import json
import pytest
from mve.budget import BudgetLedger, BudgetError
from mve.preflight.probe_fixtures import FakeTransport
from mve.perceiver import perceive, Replay
from mve.perceiver.contract import ImageInput
from tests.mve.perceiver_helpers import ROOT, OFF, PEAK, prices, book, reply, run


def invoke(ledger,path,**kwargs):
    options=dict(replay=Replay((reply(),reply(2))), output=path/'run',nonce='0123456789abcdef',clock=lambda:OFF)
    options.update(kwargs)
    return perceive(ledger,ImageInput((ROOT/'public/development_0.png').read_bytes()),**options)


@pytest.mark.parametrize('table',[{},prices(False)])
def test_prices_refused_before_reservation(tmp_path,table):
    ledger=BudgetLedger(tmp_path/'ledger.sqlite',price_table=table)
    with pytest.raises(BudgetError,match='price'):
        invoke(ledger,tmp_path)
    assert ledger.snapshot()['attempts']==[]


@pytest.mark.parametrize('times,states',[([PEAK],[]),([OFF,PEAK],['cancelled'])])
def test_window_checked_twice(tmp_path,times,states):
    ledger=book(tmp_path);clock=iter(times)
    with pytest.raises(BudgetError,match='peak'):
        invoke(ledger,tmp_path,clock=lambda:next(clock))
    assert [r['state'] for r in ledger.snapshot()['attempts']]==states
    assert not list((tmp_path/'run').glob('*/response.raw'))


@pytest.mark.parametrize('options',[{'model':'deepseek-v4-pro'},{'model':'other'},{'phase':'P2'},
    {'retries':3},{'retries':True},{'replay':lambda:None},{'nonce':'../escape'}])
def test_request_guards(tmp_path,options):
    ledger=book(tmp_path)
    with pytest.raises((ValueError,BudgetError)):
        invoke(ledger,tmp_path,**options)
    assert ledger.snapshot()['attempts']==[]


@pytest.mark.parametrize('phase',['P0','P1'])
def test_durable_intent_before_send_and_raw_before_inspection(tmp_path,monkeypatch,phase):
    from mve.preflight import probe
    ledger=book(tmp_path)
    send=FakeTransport.send;inspect=probe.inspect_reply
    def before_send(self,request):
        assert ledger.snapshot()['attempts'][-1]['state']=='dispatched'
        return send(self,request)
    def before_parse(response,request):
        assert any(p.read_bytes()==response.raw for p in (tmp_path/'run').glob('*/response.raw'))
        return inspect(response,request)
    monkeypatch.setattr(FakeTransport,'send',before_send)
    monkeypatch.setattr(probe,'inspect_reply',before_parse)
    invoke(ledger,tmp_path,phase=phase)
    assert all(r['phase']==phase for r in ledger.snapshot()['attempts'])


def test_same_nonce_cannot_dispatch_again_even_in_new_output_directory(tmp_path):
    ledger=book(tmp_path)
    invoke(ledger,tmp_path)
    with pytest.raises(BudgetError,match='already exists'):
        invoke(ledger,tmp_path/'restart')
    assert len(ledger.snapshot()['attempts'])==2


def test_post_dispatch_persistence_failure_retains_exposure(tmp_path,monkeypatch):
    from mve.preflight import probe
    from pathlib import Path
    ledger=book(tmp_path);original=Path.open
    def broken(self,*args,**kwargs):
        if self.name=='response.raw': raise OSError('disk full')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',broken)
    with pytest.raises(OSError,match='disk full'):
        invoke(ledger,tmp_path)
    assert ledger.snapshot()['attempts'][0]['state']=='dispatched'
    assert ledger.snapshot()['exposure_micro_usd']>0


def test_inflight_caps_and_frozen_ledger_block(tmp_path):
    for index,kw in enumerate([{'aggregate':'.001'}, {'p1':'.001'}, {}]):
        path=tmp_path/str(index);path.mkdir();ledger=book(path,**kw)
        if not kw: ledger.stop('operator_stop')
        with pytest.raises(BudgetError): invoke(ledger,path)
        assert not ledger.snapshot()['attempts']
