from mve.perceiver.alignment import align


def point(name,x,y=0,kind='point'):
    return {'id':name,'label':name,'kind':kind,'params':[x,y]}


def test_geometry_not_names_and_hungarian_global_assignment():
    # Greedy first match loses the second valid match. Hungarian must keep both.
    left=[point('A',2),point('B',0)]
    right=[point('B',1),point('A',4)]
    result=align(left,right,100,100)
    assert [(m['left'],m['right']) for m in result['matches']]==[('A','A'),('B','B')]
    assert result['agreement_is_verification'] is False


def test_unmatched_and_kind_mismatch_and_threshold_inclusive():
    result=align([point('a',0),point('b',50)], [point('x',3),point('y',50,kind='crossing')],100,100)
    assert len(result['matches'])==1
    assert result['unmatched_left']==['b'] and result['unmatched_right']==['y']
    assert not align([],[],100,100)['matches']


def test_segment_endpoint_reversal():
    a={'id':'a','kind':'segment','params':[0,0,80,40]}
    b={'id':'b','kind':'segment','params':[80,40,0,0]}
    assert align([a],[b],100,100)['matches'][0]['distance']==0
