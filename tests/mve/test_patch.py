import pytest
from mve.patch import apply_patch
from mve.errors import RecordError


def test_rfc_operations_and_escaped_pointer():
    original={'list':[1,2],'a/b':{'~x':3}}
    got=apply_patch(original,[{'op':'test','path':'/list/0','value':1},
        {'op':'add','path':'/list/-','value':4},{'op':'copy','from':'/a~1b/~0x','path':'/copied'},
        {'op':'move','from':'/list/0','path':'/list/2'},{'op':'replace','path':'/copied','value':5},
        {'op':'remove','path':'/a~1b/~0x'}])
    assert got=={'list':[2,4,1],'a/b':{},'copied':5}
    assert original['list']==[1,2]


@pytest.mark.parametrize('patch',[[{'op':'test','path':'/a','value':2}],
    [{'op':'replace','path':'/missing','value':1}],[{'op':'remove','path':'/items/02'}],
    [{'op':'add','path':'bad','value':1}],[{'op':'add','path':'/bad~2','value':1}],
    [{'op':'move','from':'/items','path':'/items/0'}],[{'op':'wat','path':'/a'}]])
def test_bad_patches(patch):
    with pytest.raises(RecordError): apply_patch({'a':1,'items':[1,2,3]},patch)
