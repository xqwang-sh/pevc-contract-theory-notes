"""Recompute the Schmidt teaching contract from cash flows and unilateral choices.

The affine cash table and quadratic effort cost are teaching primitives, not
numerical estimates or a transcription of Schmidt's general Proposition 3.
"""
from fractions import Fraction as F
from itertools import combinations

COST = {'maintain': F(0), 'support': F(3, 4), 'control': F(1, 4)}
PROB = {'L': F(1, 4), 'M': F(1, 2), 'H': F(1, 4)}
# Cash is slope * effort + intercept, before either party's costs.
CASH = {
    'L': {'maintain': (F(0), F(1, 8)), 'support': (F(0), F(1, 4)), 'control': (F(0), F(1, 2))},
    'M': {'maintain': (F(1), F(1)), 'support': (F(1), F(3, 2)), 'control': (F(0), F(3, 4))},
    'H': {'maintain': (F(1), F(9, 8)), 'support': (F(2), F(2)), 'control': (F(0), F(1))},
}
INITIAL, FACE, SHARE, BARGAIN = F(1), F(5, 4), F(1, 3), F(1, 2)


def choices(state, effort, face=FACE, share=SHARE, support_cost=None):
    rows = []
    for action, (slope, intercept) in CASH[state].items():
        cash = slope * effort + intercept
        cost = support_cost if action == 'support' and support_cost is not None else COST[action]
        for converted in (False, True):
            receipt = share * cash if converted else min(face, cash)
            rows.append({'action': action, 'converted': converted, 'cash': cash,
                         'cost': cost, 'receipt': receipt, 'VC': receipt - cost,
                         'E': cash - receipt - effort * effort / 2})
    return rows


def continuation(state, effort, renegotiate=True, face=FACE, share=SHARE, support_cost=None):
    rows = choices(state, effort, face, share, support_cost)
    # At an exact private tie choose the efficient action, as declared in the text.
    row = max(rows, key=lambda r: (r['VC'], r['cash'] - r['cost'], not r['converted'])).copy()
    efficient = max(rows, key=lambda r: r['cash'] - r['cost'])
    gain = efficient['cash'] - efficient['cost'] - (row['cash'] - row['cost'])
    assert gain >= 0
    if renegotiate:
        row['E'] += BARGAIN * gain
        row['VC'] += (1 - BARGAIN) * gain
    row['gain'] = gain
    row['surplus'] = row['E'] + row['VC']
    return row


def global_effort(state, renegotiate=True):
    """Bound every piece of the upper envelope exactly, without a grid search."""
    end = F(10)
    curves, breaks = [], {F(0), end}
    for action, (slope, intercept) in CASH[state].items():
        cost = COST[action]
        curves.extend([(slope, intercept-cost), (F(0), FACE-cost),
                       (SHARE*slope, SHARE*intercept-cost)])
        if slope:
            root = (FACE-intercept)/slope
            if 0 < root < end:
                breaks.add(root)
    for (s1,t1),(s2,t2) in combinations(curves, 2):
        if s1 != s2:
            root=(t2-t1)/(s1-s2)
            if 0 < root < end:
                breaks.add(root)
    cuts=sorted(breaks)
    actual=[(continuation(state,e,renegotiate)['E'],e) for e in cuts]
    bounds=[]
    efficient_action=max(CASH[state],key=lambda a: CASH[state][a][0]*F(1,2)+CASH[state][a][1]-COST[a])
    fs,ft=CASH[state][efficient_action]
    # Each efficient action dominates the alternatives for every effort >= 0.
    assert all(fs-s >= 0 and ft-COST[efficient_action]-(t-COST[a]) >= 0
               for a,(s,t) in CASH[state].items())
    for left,right in zip(cuts,cuts[1:]):
        midpoint=(left+right)/2
        chosen=continuation(state,midpoint,False)
        action=chosen['action'];slope,intercept=CASH[state][action]
        if chosen['converted']:
            rs,rt=SHARE*slope,SHARE*intercept
        elif chosen['cash'] < FACE:
            rs,rt=slope,intercept
        else:
            rs,rt=F(0),FACE
        es,et=slope-rs,intercept-rt
        if renegotiate:
            es += BARGAIN*(fs-slope)
            et += BARGAIN*(ft-COST[efficient_action]-intercept+COST[action])
        candidates=[left,right]
        if left < es < right:
            candidates.append(es)
            actual.append((continuation(state,es,renegotiate)['E'],es))
        bounds.extend(es*e+et-e*e/2 for e in candidates)
    optimum=max(actual)
    assert optimum[0] == max(bounds), (state,optimum,max(bounds))
    # Beyond 10, even all gross cash minus E's cost is negative and decreasing.
    assert all(s <= 2 and t <= 2 for row in CASH.values() for s,t in row.values())
    assert 2+2*end-end*end/2 < 0 and end > 2
    return {'effort':optimum[1], 'E':optimum[0], 'pieces_checked':len(cuts)-1}


def schmidt_checks():
    results={state:global_effort(state) for state in PROB}
    assert {s:r['effort'] for s,r in results.items()} == {'L':F(0),'M':F(1),'H':F(2)}
    assert {s:r['E'] for s,r in results.items()} == {'L':F(0),'M':F(1,4),'H':F(2)}
    expected_actions={'L':('control',False),'M':('maintain',False),'H':('support',True)}
    branches={}
    for state,result in results.items():
        e=result['effort'];row=continuation(state,e)
        assert (row['action'],row['converted']) == expected_actions[state]
        assert row['gain']==0
        branches[state]={'effort':e,**row}
    high=choices('H',F(2))
    payoff={(r['action'],r['converted']):r['VC'] for r in high}
    assert payoff[('support',True)]==payoff[('maintain',False)]==FACE
    assert payoff[('maintain',True)]==F(25,24)<FACE
    incremental_return=SHARE*(F(6)-F(25,8))
    assert incremental_return==F(23,24)>=COST['support']
    assert FACE*(F(6)-F(25,8))/F(25,8)==F(23,20)>=COST['support']
    small=continuation('H',F(3,2))['E']
    large=continuation('H',F(1,8))['E']
    assert small==F(17,16)<2 and large==F(15,128)<2
    assert global_effort('H',False)['E']==2
    expected_v=sum(PROB[s]*r['VC'] for s,r in branches.items())-INITIAL
    expected_e=sum(PROB[s]*r['E'] for s,r in branches.items())
    welfare=sum(PROB[s]*r['surplus'] for s,r in branches.items())-INITIAL
    assert expected_v==0 and expected_e==welfare==F(5,8)
    liquidation=branches['L']['cash']-COST['control']
    assert liquidation==F(1,4)
    assert (INITIAL-liquidation)/(PROB['M']+PROB['H'])+liquidation==FACE
    assert (FACE+COST['support'])/branches['H']['cash']==SHARE
    # H5-3: calibrating only support-and-convert versus debt misses free riding.
    changed_share=(FACE+F(3,2))/F(6)
    changed=continuation('H',F(2),False,share=changed_share,support_cost=F(3,2))
    assert changed_share==F(11,24)
    assert (changed['action'],changed['converted'])==('maintain',True)
    assert changed['VC']==F(275,192)>FACE
    # Additional displays in the founder-IC and fixed-security explanations.
    slope, intercept = CASH['H']['maintain']
    repay_cutoff = (FACE-intercept)/slope
    assert repay_cutoff == F(1,8) < slope < 2
    no_reneg = continuation('H',slope,False)
    assert no_reneg['E'] == F(3,8)
    assert (no_reneg['action'],no_reneg['converted']) == ('maintain',False)
    assert continuation('H',F(4,3),False)['action']=='maintain'
    high_cash = CASH['H']['support'][0]*2+CASH['H']['support'][1]
    maintain_cash = slope*2+intercept
    assert high_cash-maintain_cash == F(23,8)
    assert high_cash-maintain_cash-COST['support'] == F(17,8)
    for effort in (F(0),F(1,8),F(1),F(3,2),F(2)):
        support_cash = CASH['H']['support'][0]*effort+CASH['H']['support'][1]
        old_cash = slope*effort+intercept
        assert support_cash-COST['support']-old_cash == effort+F(1,8)
    debt_best = slope+BARGAIN*(CASH['H']['support'][0]-slope)
    assert debt_best == F(3,2)
    debt_low = continuation('H',debt_best,True,share=F(0))
    debt_target = continuation('H',F(2),True,share=F(0))
    assert debt_low['E']==F(17,16)>debt_target['E']==F(15,16)
    assert min(FACE,intercept)>max(FACE-COST['support'],F(1)-COST['control'])
    assert debt_best>=repay_cutoff and debt_low['E']>large
    pure_share = F(1,3)
    equity_effort = (1-pure_share)*CASH['M']['maintain'][0]
    equity_best = (1-pure_share)*(1+equity_effort)-equity_effort**2/2
    equity_target = (1-pure_share)*2-F(1,2)
    assert equity_effort==F(2,3) and equity_best==F(8,9)>equity_target==F(5,6)
    assert pure_share*F(1,2)-COST['support']<0
    assert CASH['M']['support'][0]==CASH['M']['maintain'][0]
    assert pure_share*(CASH['M']['control'][1]-CASH['M']['maintain'][1])-COST['control']<0
    # Middle-state first best forces s=0, then D<=3/2; debt fails near e_H=2.
    for face in (F(0),F(1),F(3,2)):
        at_target=continuation('H',F(2),True,face=face,share=F(0))['E']
        below=continuation('H',F(19,10),True,face=face,share=F(0))['E']
        assert below-at_target==F(9,200)>0
    off_path=continuation('M',F(3),False)
    assert off_path['cash']-off_path['receipt']>=0 and off_path['E']<0
    fixed_comparison={'underinvestment_without_renegotiation':no_reneg['E'],
                      'pure_debt_H_effort':debt_best,'pure_debt_H_E':debt_low['E'],
                      'pure_debt_H_E_at_2':debt_target['E'],
                      'pure_equity_M_effort':equity_effort,'pure_equity_M_E':equity_best,
                      'H_cash_increment_at_2':high_cash-maintain_cash,
                      'H_net_support_increment_at_2':high_cash-maintain_cash-COST['support']}
    return {'primitives':{'I':INITIAL,'C':FACE,'alpha':SHARE,'lambda':BARGAIN,
                          'probabilities':PROB,'action_costs':COST,'cash_table':CASH},
            'global_effort':results,'equilibrium':branches,'VC_net':expected_v,
            'E':expected_e,'welfare':welfare,'VC_support_IC':incremental_return,
            'renegotiation_underinvestment_max':small,'default_region_supremum':large,
            'fixed_security_comparison':fixed_comparison,
            'higher_support_cost':{'alpha':changed_share,'action':changed['action'],
                                    'converted':changed['converted'],'VC':changed['VC']}}


if __name__ == '__main__':
    import json
    print(json.dumps(schmidt_checks(),default=str,ensure_ascii=False,indent=2))
