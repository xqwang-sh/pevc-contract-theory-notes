"""Independently recompute teaching examples and inspect rendered local links."""
from collections import Counter, defaultdict
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse
import json
import math
import re

from schmidt_model import schmidt_checks

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    "student-notes.md", "student-notes.qmd", "w04-fund-contract.qmd",
    "w05-venture-contract.qmd", "w04-preparation.qmd",
    "w05-preparation.qmd", "exercises.qmd", "references-by-module.bib",
]
PAGES = [
    "index.html", "student-notes.html", "w04-fund-contract.html",
    "w05-venture-contract.html", "w04-preparation.html",
    "w05-preparation.html", "exercises.html",
]

def close(x, y):
    assert math.isclose(x, y, abs_tol=1e-8), (x, y)

def property_rights_checks():
    from fractions import Fraction as F

    value, cost = F(100), F(60)
    def continuation(effort, standalone, fixed_transfer=F(0)):
        total, da, db = value*effort, standalone*effort, F(0)
        gain = total-da-db
        assert gain >= 0
        # Symmetric Nash bargaining maximizes x * (gain-x) at x=gain/2.
        extra = gain/2
        assert extra*(gain-extra) >= F(0)
        assert gain-2*extra == 0
        a, b = da+extra, db+extra
        assert a+b == total and a >= da and b >= db
        return {'A_receipt':a-fixed_transfer,'B_receipt':b+fixed_transfer,
                'A_net':a-fixed_transfer-cost*effort,
                'welfare':total-cost*effort,'gain':gain}
    def choices(standalone, fixed_transfer=F(0)):
        rows={e:continuation(e,standalone,fixed_transfer) for e in (0,1)}
        best=max(row['A_net'] for row in rows.values())
        return rows,[e for e,row in rows.items() if row['A_net']==best]
    result={}
    for owner, standalone, best_effort in [('B',F(0),0),('A',F(40),1)]:
        rows,best=choices(standalone)
        assert best == [best_effort]
        result[owner]={'standalone_after_investment':standalone,
                       'conditional_on_investment':rows[1],
                       'chosen_effort':best[0],'equilibrium':rows[best[0]]}
    assert result['B']['conditional_on_investment']['A_receipt']==50
    assert result['B']['conditional_on_investment']['A_net']==-10
    assert result['A']['conditional_on_investment']['A_receipt']==70
    assert result['A']['conditional_on_investment']['B_receipt']==30
    assert result['A']['conditional_on_investment']['A_net']==10
    assert result['B']['equilibrium']['welfare']==0
    assert result['A']['equilibrium']['welfare']==40
    first_best=max((value-cost)*e for e in (0,1))
    assert first_best==40 and (value-cost)>0
    threshold=2*cost-value
    assert threshold==20
    for standalone in (F(0),F(19),F(20),F(21),F(40),F(100)):
        rows,best=choices(standalone)
        assert rows[1]['A_net']-rows[0]['A_net']==(standalone-threshold)/2
        expected=[0] if standalone<threshold else [0,1] if standalone==threshold else [1]
        assert best==expected
        for transfer in (F(-10),F(0),F(25)):
            shifted,_=choices(standalone,transfer)
            assert shifted[1]['A_net']-shifted[0]['A_net']==rows[1]['A_net']-rows[0]['A_net']
    return {'cooperation_value':value,'investment_cost':cost,'first_best':first_best,
            'ownership':result,'standalone_threshold':threshold,
            'threshold_best_responses':choices(threshold)[1],
            'fixed_transfer_does_not_change_investment_IC':True}


def week5_core_checks():
    from fractions import Fraction as F

    # Solve the binary search choice from the contract and renegotiation payoffs.
    R, p, phi, B, I, q = F(100), F(1,2), F(4,5), F(10), F(30), F(1,2)
    def search_contract(alpha, severance, control, cost=F(6)):
        keep_e, keep_v = alpha*p*R+B, (1-alpha)*p*R
        replace_e, replace_v = severance, phi*R-severance
        joint = replace_e+replace_v-keep_e-keep_v
        if control == 'founder' and severance < keep_e:
            replace_e, replace_v = keep_e+joint/2, keep_v+joint/2
        assert replace_v >= keep_v and replace_e >= 0 and replace_v >= 0
        search_gain = q*(replace_v-keep_v)-cost
        search = search_gain >= 0
        ev_e = q*replace_e+(1-q)*keep_e if search else keep_e
        ev_v = q*replace_v+(1-q)*keep_v-cost-I if search else keep_v-I
        surplus = (q*phi*R+(1-q)*p*R+(1-q)*B-cost-I
                   if search else p*R+B-I)
        assert ev_e+ev_v == surplus
        assert 0 <= alpha <= 1 and 0 <= severance/phi <= R
        return {'search':search,'search_gain':search_gain,'E':ev_e,'VC':ev_v,'surplus':surplus}
    founder=search_contract(F(2,5),F(20),'founder')
    fixed=search_contract(F(2,5),F(20),'vc')
    repriced=search_contract(F(19,25),F(20),'vc')
    full_comp=search_contract(F(12,25),F(34),'founder')
    assert founder['search'] is False and founder['search_gain']==-1
    assert (founder['E'],founder['VC'])==(30,0)
    assert (fixed['search_gain'],fixed['E'],fixed['VC'])==(9,25,9)
    assert repriced['search'] and (repriced['E'],repriced['VC'])==(34,0)
    assert full_comp['search'] and (full_comp['E'],full_comp['VC'])==(34,0)
    assert repriced['surplus']-founder['surplus']==4
    wasteful=search_contract(F(2,5),F(20),'vc',F(11))
    assert wasteful['search_gain']==4 and wasteful['surplus']-founder['surplus']==-1

    # Compute both agents' best responses and the passive financier's receipts.
    ce, cv, initial, cash = F(3,10), F(3,5), F(3), F(10)
    def effort_outcome(e,a,claims,advising=True):
        prob=F(3,10)+F(3,10)*e+F(1,5)*a
        eclaim,vclaim,fclaim=claims
        assert min(claims)>=0 and sum(claims)==cash
        return prob*eclaim-ce*e, prob*vclaim-(cv*a if advising else 0), prob*fclaim
    def check_efforts(claims, advising=True):
        a=int(advising)
        chosen=effort_outcome(1,a,claims,advising)
        assert chosen[0]>=effort_outcome(0,a,claims,advising)[0]
        if advising:
            assert chosen[1]>=effort_outcome(1,0,claims,advising)[1]
        return chosen
    no_advisor=check_efforts((F(5),F(0),F(5)),False)
    separate=check_efforts((F(13,4),F(3),F(15,4)))
    bundled=check_efforts((F(11,2),F(9,2),F(0)))
    assert no_advisor==(F(27,10),F(0),initial)
    assert separate==(F(23,10),F(9,5),initial)
    assert (bundled[0],bundled[1]-initial)==(F(41,10),F(0))
    assert sum(separate)-initial==sum(bundled)-initial==F(41,10)
    # Self funding produces the same no-advisor and consultant net payoffs.
    self_alone=check_efforts((cash,F(0),F(0)),False)[0]-initial
    self_advice=check_efforts((F(7),F(3),F(0)))[0]-initial
    assert self_alone==no_advisor[0] and self_advice==separate[0]
    lower=cv/F(1,5);upper=cash-ce/F(3,10)
    assert (lower,upper)==(3,9)
    low_capital=F(1,2);pc_only=(low_capital+cv)/F(4,5)
    assert pc_only==F(11,8) and F(1,5)*pc_only<cv
    assert F(4,5)*lower-cv-low_capital==F(13,10)
    assert F(4,5)*upper-cv==F(33,5)

    # Construct CY payoffs from one security and the primitive cash distributions.
    output=(F(0),F(100),F(200));face=F(100);conversion=F(19,20)
    pmf={'g':(F(1,10),F(4,5),F(1,10)),
         'b':(F(41,100),F(29,50),F(1,100))}
    receipts={}
    for kind,probs in pmf.items():
        assert sum(probs)==1
        receipts[kind]={}
        for instrument in ('debt','converted'):
            v=tuple(min(x,face) if instrument=='debt' else conversion*x for x in output)
            assert all(0<=claim<=x for claim,x in zip(v,output))
            vc=sum(prob*claim for prob,claim in zip(probs,v))
            total=sum(prob*x for prob,x in zip(probs,output))
            receipts[kind][instrument]=(vc,total-vc)
    assert receipts=={'g':{'debt':(90,10),'converted':(95,5)},
                      'b':{'debt':(59,1),'converted':(57,3)}}
    clean={'g':(F(0),F(1,10),F(2,5)),
           'b':(F(1,5),F(3,10),F(0))}
    dressed={'g':(F(0),F(2,25),F(21,50)),
             'b':(F(9,50),F(8,25),F(0))}
    first,second=F(10),F(65)
    for matrix in (clean,dressed):
        assert all(sum(row)==F(1,2) and min(row)>=0 for row in matrix.values())
    def choose_policy(matrix, convertible=True):
        policy=[];conditional=[]
        for signal in range(3):
            mass=sum(row[signal] for row in matrix.values())
            possible=('debt','converted') if convertible else ('debt',)
            menu={'stop':F(0)}
            for instrument in possible:
                menu[instrument]=sum(matrix[t][signal]*receipts[t][instrument][0]
                                     for t in matrix)/mass-second
            best=max(menu,key=menu.get)
            assert all(menu[best]>v for action,v in menu.items() if action!=best)
            policy.append(best);conditional.append(menu)
        return policy,conditional
    def exante(matrix, policy):
        vc,e,resources=-first,F(0),-first
        for signal,instrument in enumerate(policy):
            if instrument=='stop':continue
            for kind,row in matrix.items():
                vpay,epay=receipts[kind][instrument]
                vc+=row[signal]*(vpay-second);e+=row[signal]*epay
                resources+=row[signal]*(vpay+epay-second)
        assert vc+e==resources
        return vc,e,resources
    policy,menu=choose_policy(clean)
    assert policy==['stop','debt','converted']
    clean_v,clean_e,total=exante(clean,policy)
    deviation_e=exante(dressed,policy)[1]
    assert (clean_v,clean_e,total)==(F(27,10),F(33,10),6)
    assert deviation_e==F(161,50) and deviation_e-clean_e==F(-2,25)
    assert clean_v>=0 and clean_e>=0
    debt_policy,_=choose_policy(clean,False)
    actual_debt,_=choose_policy(dressed,False)
    assert debt_policy==actual_debt==['stop','debt','debt']
    assert exante(dressed,debt_policy)[1]-exante(clean,debt_policy)[1]==F(1,50)
    debt_v,debt_e,debt_total=exante(dressed,actual_debt)
    assert (debt_v,debt_e,debt_total)==(F(29,50),F(133,25),F(59,10))
    assert total-debt_total==F(1,50)*(second-F(60))
    bad_only={'g':clean['g'],'b':dressed['b']}
    assert exante(bad_only,policy)[1]-clean_e==F(1,50)

    # Derive the AB perfect-signal action plan, cash flow, and welfare separately.
    states=(((100,150),(200,0)),((0,49),(50,0)))
    first_best=[max(range(2),key=lambda a:sum(row[a])) for row in states]
    assert first_best==[0,1]
    assert [max(range(2),key=lambda a:row[a][1]) for row in states]==[0,0]
    assert [max(range(2),key=lambda a:row[a][0]) for row in states]==[1,1]
    vc_cash=sum(F(1,2)*states[s][a][0] for s,a in enumerate(first_best))
    en=sum(F(1,2)*states[s][a][1] for s,a in enumerate(first_best))
    assert vc_cash==en==75 and vc_cash-70==5 and vc_cash+en-70==80
    # Resolve control and actual renegotiation, imposing nonnegative E cash.
    def ab_contract(beta_good,beta_bad,capital=F(70)):
        branches=[]
        for state,beta in enumerate((beta_good,beta_bad)):
            for signal in (1,0):
                mass=F(1,2)*(beta if signal else 1-beta)
                initial=max(range(2),key=lambda a:states[state][a][1 if signal else 0])
                action=initial
                vc,eu=F(states[state][initial][0]),F(states[state][initial][1])
                cash_e=F(0)
                for candidate,(cash,private) in enumerate(states[state]):
                    available=F(cash)-vc
                    if available>=0 and available+private>eu:
                        action=candidate;cash_e=available;eu=available+private
                assert cash_e>=0 and cash_e+vc==states[state][action][0]
                assert eu==cash_e+states[state][action][1]
                branches.append({'state':state,'signal':signal,'probability':mass,
                                 'action':action,'renegotiated':action!=initial,
                                 'VC_cash':vc,'E_cash':cash_e,'E_utility':eu})
        vc=sum(row['probability']*row['VC_cash'] for row in branches)
        e=sum(row['probability']*row['E_utility'] for row in branches)
        resource=sum(row['probability']*sum(states[row['state']][row['action']])
                     for row in branches)-capital
        assert vc-capital+e==resource
        return {'branches':branches,'VC_cash':vc,'VC_net':vc-capital,'E':e,'surplus':resource}
    noisy=ab_contract(F(9,10),F(1,10))
    complete=ab_contract(F(1),F(0))
    assert (noisy['VC_cash'],noisy['VC_net'],noisy['E'],noisy['surplus'])==(F(155,2),F(15,2),70,F(155,2))
    assert [row['action'] for row in noisy['branches']]==[0,1,1,1]
    assert [row['renegotiated'] for row in noisy['branches']]==[False,False,True,False]
    assert complete['VC_cash']==complete['E']==75 and complete['surplus']==80
    assert complete['surplus']-noisy['surplus']==F(1,20)*(250-200)==F(5,2)
    assert noisy['VC_cash']>complete['VC_cash'] and noisy['surplus']<complete['surplus']
    # In the good state, I's original cash 200 exceeds all cash under a_g.
    assert states[0][0][0]<states[0][1][0]

    # Check the original continuous effort conditions through nearby deviations.
    alpha=F(4,5);B_private=F(1)/(4*alpha);B_social=F(1,4)
    success=lambda b:F(3,4)-2*b*b
    en_objective=lambda b:b+alpha*success(b)
    for step in (F(-1,100),F(1,100)):
        assert en_objective(B_private)>en_objective(B_private+step)
    assert B_private>B_social and 0<success(B_private)<1
    phi_c,M_c=F(19,20),F(2)
    joint=phi_c-success(B_private)-B_private
    full=B_private+alpha*success(B_private)
    vc_increment=lambda severance:phi_c-severance-(1-alpha)*success(B_private)
    m_fb=joint/M_c;m_low_severance=vc_increment(full-F(1,50))/M_c
    assert vc_increment(full)==joint>0
    assert m_low_severance-m_fb==F(1,50)/M_c
    for severance,mstar in ((full,m_fb),(full-F(1,50),m_low_severance)):
        value=lambda m:m*vc_increment(severance)-M_c*m*m/2
        for step in (F(-1,100),F(1,100)):
            assert value(mstar)>value(mstar+step)
    b_cost,g_cost,R_c,x_c=F(4),F(8),F(1),F(1,4)
    e_c,a_c=(R_c-x_c)/b_cost,x_c/g_cost
    u_e=lambda effort:(effort+a_c)*(R_c-x_c)-b_cost*effort*effort/2
    u_v=lambda effort:(e_c+effort)*x_c-g_cost*effort*effort/2
    for step in (F(-1,100),F(1,100)):
        assert u_e(e_c)>u_e(e_c+step) and u_v(a_c)>u_v(a_c+step)
    transfer=F(1,20)
    e_after=(R_c-x_c-transfer)/b_cost;a_after=(x_c+transfer)/g_cost
    assert e_after-e_c==-transfer/b_cost
    assert a_after-a_c==transfer/g_cost
    assert e_after+a_after<e_c+a_c<1

    for share in (F(1,2),F(3,4),F(1)):
        renegotiated=1-(1-share)*F(200,100)
        assert (1-renegotiated)*100==(1-share)*200
    return {'property_rights':property_rights_checks(),
            'schmidt':schmidt_checks(),
            'hellmann':{'founder_control':founder,'vc_fixed_cash_terms':fixed,
                       'vc_repriced':repriced,'full_compensation_founder_control':full_comp,
                       'cost_11':wasteful},
            'casamatta':{'E_no_advisor':no_advisor[0],'E_consultant':separate[0],
                         'E_bundled':bundled[0],'consultant_rent':separate[1],
                         'IC_interval':[lower,upper],'low_capital_rent':F(13,10)},
            'cornelli_yosha':{'payoffs':receipts,'policy':policy,'conditional_net_payoffs':menu,
                              'VC':clean_v,'E':clean_e,'surplus':total,'deviation_E':deviation_e,
                              'debt_VC':debt_v,'debt_E':debt_e,'debt_surplus':debt_total},
            'aghion_bolton_noisy_signal':noisy,
            'original_effort_conditions':{'hellmann_B_private':B_private,'hellmann_B_social':B_social,
                                          'hellmann_m_full_compensation':m_fb,'casamatta_e':e_c,'casamatta_a':a_c},
            'aghion_bolton_perfect_signal':{'VC_cash':vc_cash,'VC_net':vc_cash-70,'E':en,'surplus':80}}


def week5_numerical_checks():
    from fractions import Fraction as F

    # Aghion–Bolton (1992), pp. 482–484 original numerical example.
    # y_i^j is expected monetary income; lambda_i^j is non-transferable private benefit.
    pi1=F(1,2)*(F(1,50)*100)+F(1,2)*(F(1,50)*50)
    assert pi1==F(3,2)
    pi2=F(1,2)*100+F(1,2)*0
    assert pi2==50
    beta_g,beta_b=F(99,100),F(1,100)
    pi3=50*beta_g+(1-beta_g)+(1-beta_b)/2
    assert pi3==F(10001,200)
    pi4=(F(1,2)*200+F(1,2)*50)*F(100,200)
    assert pi4==F(125,2)
    # The entrepreneur's theta_b IC requires t_s*50 >= 49.
    assert F(49,50)*50==49

    beta,R,I1,I2=F(9,10),F(2),F(3,5),F(2,5)
    upfront_required=1/beta
    upfront_reneg=R/2
    P0=(I1+beta*I2)/beta**2
    L2=2*I1
    U2=max(L2,beta*R/2)
    P2=U2/beta
    S1=beta**2*R-beta*I2
    C1=beta**2*P2-beta*I2
    U1=max(F(0),min(C1,S1/2))
    P1=(U1+beta*I2)/beta**2
    assert upfront_required==F(10,9)>upfront_reneg==1
    assert (P0,P1,P2)==(F(32,27),F(11,9),F(4,3))
    assert P0<P1 and P0<P2
    assert beta**2*P0-I1-beta*I2==0
    assert beta**2*(R-P0)==F(33,50)
    assert S1-U1 < beta**2*(R-P0)
    assert beta*R-U2 < beta*(R-P0)
    assert (beta*R-1)-beta**2*(R-P0)==F(7,50)
    no_asset_P2=max(F(0),beta*R/2)/beta
    no_asset_C1=beta**2*no_asset_P2-beta*I2
    no_asset_U1=max(F(0),min(no_asset_C1,S1/2))
    no_asset_P1=(no_asset_U1+beta*I2)/beta**2
    assert no_asset_P1==no_asset_P2==1<P0
    multi=[]
    for T in range(1,7):
        path=[F(1)]
        for i in range(2,T+1):
            collateral=F(3,2)*sum(path)
            prior=sum(F(19,20)**(j+1-i)*v for j,v in enumerate(path))
            path.append(collateral-prior)
        scale=100/sum(path); path=[x*scale for x in path]
        surplus=F(19,20)**T*150-sum(F(19,20)**j*path[j] for j in range(1,T))
        feasible=path[0]<=surplus/2
        assert feasible==(T==6)
        multi.append({"T":T,"first_constraint_ratio":surplus/(2*path[0])})
    for got,want in zip(path,[19.6432,8.7877,11.6308,15.2017,19.6398,25.0968]):
        assert abs(float(got)-want)<.00006

    cutoff=F(2,5); conditional_success=(cutoff+1)/2
    Q=3/conditional_success
    # Eliminate N from the old-capital PC and cutoff indifference equation.
    M=(F(1)-F(3,5)*conditional_success*(10-Q-F(1)/cutoff))/(cutoff+F(3,5)*conditional_success/cutoff)
    N=10-Q-(1-M)/cutoff
    assert (M,N,Q)==(F(-7,29),F(530,203),F(30,7))
    assert cutoff*M+(1-cutoff)*conditional_success*N==1
    assert cutoff*(10-N-Q)==1-M and conditional_success*Q==3
    W=cutoff+(5-3)-(5*cutoff**2-3*cutoff)
    alpha=1/W
    assert W==F(14,5) and alpha==F(5,14)
    # Price the new securities, allocate old and new claims, then check every PC.
    old_v_success=alpha*(10-Q)
    new_v_success=alpha*Q
    outside_success=(1-alpha)*Q
    founder_success=(1-alpha)*(10-Q)
    assert old_v_success+new_v_success==alpha*10
    assert old_v_success+new_v_success+outside_success+founder_success==10
    vc_receipts=cutoff*alpha+(1-cutoff)*conditional_success*alpha*10
    vc_cost=1+(1-cutoff)*alpha*3
    outside_receipts=(1-cutoff)*conditional_success*outside_success
    outside_cost=(1-cutoff)*(1-alpha)*3
    founder_cash=cutoff*(1-alpha)+(1-cutoff)*conditional_success*founder_success
    assert vc_receipts==vc_cost and outside_receipts==outside_cost
    assert founder_cash==(1-alpha)*W==F(9,5)==W-1

    result={"core":week5_core_checks(),"aghion_bolton":{"pi1":pi1,"pi2":pi2,"pi3_beta_099_001":pi3,"pi4":pi4,
              "theta_b_direct_share":F(49,50)},
            "neher_example_4_1":{"P0":P0,"P1":P1,"P2":P2,"L2":L2,
              "U1_V":U1,"U2_V":U2,"S1":S1,"C1":C1,"E_NPV":F(33,50),
              "without_asset_accumulation":{"P1":no_asset_P1,"P2":no_asset_P2,
                                             "feasible":False},
              "upfront_required":upfront_required,"upfront_renegotiated":upfront_reneg},
            "neher_example_4_2":{"candidates":multi,"six_round_path":path},
            "admati_pfleiderer":{"M":M,"N":N,"Q":Q,"W":W,"alpha":alpha,
              "VC_receipts":vc_receipts,"VC_cost":vc_cost,
              "outside_receipts":outside_receipts,"outside_cost":outside_cost,
              "E_cash":founder_cash}}
    return json.loads(json.dumps(result,default=float))


def numerical_checks():
    # Reconstruct cash allocation by principal and profit, independently of the printed formula.
    def income(x, k=100, gp=.02, carry=.2):
        principal = min(x, k)
        profit = max(x-k, 0)
        return gp*principal + gp*profit + carry*(1-gp)*profit
    close(income(200), 23.6)
    close(income(80), 1.6)
    close(income(220), 27.92)
    close(income(220)-income(80), 26.32)
    for x in range(0, 301, 5):
        for share in (0, .02, .05, .5, 1):
            for carry in (0, .05, .2, .75, 1):
                g = income(x, gp=share, carry=carry)
                assert 0 <= g <= x+1e-10
                close(g+(x-g), x)
    def effort(carry, outside=1):
        success = income(200, carry=carry)
        high = .8*success-2-3
        low = .5*success-2+1
        choose_high = high >= low-1e-10
        actual_p = .8 if choose_high else .5
        return {"GP_success":success,"U_H":high,"U_L":low,
                "action":"H" if choose_high else "L",
                "GP_PC":max(high,low)>=outside-1e-10,
                "LP_net":actual_p*(200-success)-98}
    effort_main, effort_low = effort(.2), effort(.05)
    for got,want in ((effort_main["U_H"],13.88),(effort_main["U_L"],10.8),
                     (effort_main["LP_net"],43.12),(effort_low["U_H"],2.12),
                     (effort_low["U_L"],3.45),(effort_low["LP_net"],-2.45)):
        close(got,want)
    assert effort_main["action"] == "H" and effort_low["action"] == "L"
    assert effort_low["GP_PC"] and effort_low["LP_net"] < 0
    close(.8*(200-income(200,carry=.05))-98,54.88)
    lower, upper = 2/21, 3/4
    for carry in (lower, .2, upper):
        item = effort(carry)
        assert item["action"] == "H" and item["GP_PC"] and item["LP_net"] >= -1e-9
    assert effort(lower-1e-6)["action"] == "L"
    assert effort(upper+1e-6)["LP_net"] < 0
    assert not effort(.2,outside=14)["GP_PC"]
    changed = effort(.21,outside=14)
    close(changed["U_H"],14.664)
    close(changed["U_L"],11.29)
    close(changed["LP_net"],42.336)
    assert changed["GP_PC"]
    close(effort_main["U_H"]+effort_main["LP_net"],.8*200-100-3)
    close(effort_low["U_L"]+effort_low["LP_net"],.5*200-100+1)
    risk = {}
    for gp in (.02,.05,1/21):
        a = income(110,gp=gp)
        b = .5*income(130,gp=gp)+.5*income(50,gp=gp)
        keep = income(100,gp=gp)
        close(b-a,1-21*gp)
        risk[str(gp)]={"A_GP":a,"B_GP":b,"keep_GP":keep,
                       "A_LP_net":110-a-(1-gp)*100,
                       "B_LP_net":90-b-(1-gp)*100}
        close((a-gp*100)+risk[str(gp)]["A_LP_net"],10)
        close((b-gp*100)+risk[str(gp)]["B_LP_net"],-10)
    close(risk["0.02"]["A_GP"],4.16)
    close(risk["0.02"]["B_GP"],4.74)
    close(risk["0.02"]["B_LP_net"],-12.74)
    close(risk["0.05"]["A_GP"],7.4)
    close(risk["0.05"]["B_GP"],7.35)
    close(risk["0.05"]["A_LP_net"],7.6)
    assert risk["0.02"]["B_GP"] > risk["0.02"]["A_GP"]
    assert risk["0.05"]["A_GP"] > risk["0.05"]["B_GP"]
    close(.5*(income(130)+income(90)),5.14)
    close(income(.5*(130+90)),4.16)
    def preferred(w, l, alpha):
        return max(min(w, l), alpha*w)
    for w, want in ((400, 400), (1200, 600), (2800, 700)):
        close(preferred(w, 600, .25), want)
    close(600+.25*(2800-600), 1150)

    week5 = week5_numerical_checks()

    def portfolio_distribution(kind1, kind2, mixed=False):
        capital = 120 if mixed else 200
        used = 60 if mixed else 100
        out = defaultdict(float)
        def outcomes(kind):
            if kind is None:
                return [(0.,1.)]
            quality, debt = kind
            prob = 1. if quality == "G" else .2
            return [(150-debt,prob),(0.,1-prob)]
        for (cash1,p1),(cash2,p2) in product(outcomes(kind1),outcomes(kind2)):
            total = capital-used*sum(k is not None for k in (kind1,kind2))
            out[total+cash1+cash2] += p1*p2
        return dict(out)
    def gp_value(dist, capital):
        return sum(prob*.2*max(x-capital,0) for x,prob in dist.items())
    def second_value(first, mixed=False):
        cap = 120 if mixed else 200
        if mixed and first is None:
            debt = 40/.72
            return .6*(.65*gp_value(portfolio_distribution(None,("G",debt),True),cap)
                       +.35*gp_value(portfolio_distribution(None,("B",debt),True),cap))
        result = 0
        for quality,prob in (("G",.41),("B",.59)):
            debt = 40 if mixed else 0
            keep = gp_value(portfolio_distribution(first,None,mixed),cap)
            invest = gp_value(portfolio_distribution(first,(quality,debt),mixed),cap)
            result += prob*max(keep,invest)
        return result
    for mixed,wait_expected in ((False,5.28),(True,2.976)):
        debt = 40 if mixed else 0
        close(second_value(None,mixed),wait_expected)
        close(second_value(("G",debt),mixed),14.1)
        close(second_value(("B",debt),mixed),2.82)
    asw = {}
    for mixed in (False,True):
        capital = 120 if mixed else 200
        dist = defaultdict(float)
        def add(weight, distribution):
            for x,p in distribution.items():
                dist[x] += weight*p
        debt = 40 if mixed else 0
        add(.41*.41,portfolio_distribution(("G",debt),("G",debt),mixed))
        add(.41*.59,portfolio_distribution(("G",debt),None,mixed))
        if mixed:
            for quality,prob in (("G",.65),("B",.35)):
                add(.59*.6*prob,portfolio_distribution(None,(quality,40/.72),True))
            add(.59*.4,portfolio_distribution(None,None,True))
        else:
            for quality,prob in (("G",.41),("B",.59)):
                add(.59*prob,portfolio_distribution(None,(quality,0),False))
        close(sum(dist.values()),1)
        cash = sum(x*p for x,p in dist.items())
        gp = gp_value(dist,capital)
        lp = cash-gp
        assert gp >= 0 and lp >= capital
        asw["mixed" if mixed else "pure"] = {
            "cash":cash,"GP":gp,"LP":lp,
            "distribution":{str(round(x,8)):p for x,p in sorted(dist.items()) if p>1e-12},
        }
    close(asw["pure"]["cash"],216.633)
    close(asw["pure"]["GP"],8.8962)
    close(asw["pure"]["LP"],207.7368)
    close(asw["mixed"]["cash"],151.737)
    close(asw["mixed"]["GP"],7.53684)
    close(asw["mixed"]["LP"],144.20016)
    close(asw["pure"]["cash"]-2*asw["pure"]["GP"],198.8406)
    assert .24*150 < 40 <= .72*150

    experiment = {}
    for d,h_want,post_want,vc_want,e_want in (
        (.9,.42,6/7,12,2.84),(.45,.69,12/23,-1.5,3.38)):
        h=.4*.9+.6*(1-d)
        vc=.4*.9*100-h*50-3
        e=2+h*2
        close(h,h_want);close(.36/h,post_want);close(vc,vc_want);close(e,e_want)
        assert (.36/h)*100 > 50
        eta_max=1-50/((.36/h)*100)
        close(eta_max,5/12 if d==.9 else 1/24)
        experiment[str(d)]={"pass":h,"posterior":.36/h,"VC":vc,"E":e,
                            "discretionary_followon_eta_max":eta_max}
    for eta in (0,.05,.1,.3,.5):
        close(.36*(1-eta)*100-.69*50-3,-1.5-36*eta)
        assert -1.5-36*eta < 0
    def experiment_e(a,d,eta,t):
        h=.4*a+.6*(1-d)
        return 2+.4*a*eta*100+h*2+(1-h)*t
    for eta,t,want in ((0,0,(.9,.45)),(.1,3,(.9,.9))):
        choices=list(product((.7,.9),(.45,.9)))
        best=max(choices,key=lambda q:experiment_e(*q,eta,t))
        assert best==want, (eta,t,best)
    close(.36*90-.42*50-3-.58*3,6.66)
    close(experiment_e(.9,.9,.1,3),8.18)
    close(.4*(10+2-20),-3.2)

    double_effort = {}
    for share in (.2,.4):
        e_e,e_v=2*(1-share),share
        y=2*e_e+e_v
        vc=share*y-e_v**2/2
        e=(1-share)*y-e_e**2/2
        s=y-e_e**2/2-e_v**2/2
        close(vc+e,s)
        double_effort[str(share)]={"E_effort":e_e,"VC_effort":e_v,
                                 "surplus":s,"VC_before_capital":vc,"E":e}
    close(double_effort["0.2"]["VC_before_capital"],.66)
    close(double_effort["0.4"]["VC_before_capital"],1.04)
    return {"waterfall_GP_success":income(200),"waterfall_gap":income(220)-income(80),
            "effort_main":effort_main,"effort_low_carry":effort_low,
            "high_effort_carry_interval":[lower,upper],"risk_choice":risk,
            "week5":week5,
            "asw":asw,"experiment":experiment,"double_effort":double_effort}

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.links=[]
        self.details=0
        self.detail_depth=0
        self.text=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        if tag=="a" and "href" in a:self.links.append(a["href"])
        if tag=="details":
            self.details+=1
            self.detail_depth+=1
    def handle_endtag(self,tag):
        if tag=="details":self.detail_depth-=1
        assert self.detail_depth>=0
    def handle_data(self,data):
        self.text.append(data)

def source_checks():
    hashes={}
    for name in SOURCES:
        path=ROOT/name
        text=path.read_text()
        hashes[name]=sha256(path.read_bytes()).hexdigest()
        anchors=re.findall(r"\{#([^}]+)\}",text)
        assert len(anchors)==len(set(anchors)),name
        assert not re.search(r"\d+\s*分钟|预计.{0,20}(分钟|小时)",text),name
    required={
        "student-notes.md":["13.88","10.8","43.12","-2.45","4.74","2/21","207.7368","144.20016","2.84","6.66"],
        "w04-fund-contract.qmd":["13.88","10.8","43.12","-2.45","4.74","54.88"],
        "w04-preparation.qmd":["13.88","10.8","43.12","-2.45","23.6","19.6"],
        "w05-venture-contract.qmd":["213 笔投资","119 家企业","信息对称","不完全合同","双边道德风险","有限责任","不可核实","Schmidt","17/16",r"\frac{25}{24}","5/8","77.5","Example 4.1","1.1852","1.2222","1.3333","0.66","794","人力资本"],
        "w05-preparation.qmd":["60","100","40","50-60=-10","70-60=10","Schmidt","5/4","25/24","7/12"],
        "exercises.qmd":["26.32","14.664","42.336","198.8406","49/50","1.1852","5/14","6.66","8.18","2.3","4.1","1.375","-0.08"],
    }
    for name,claims in required.items():
        text=(ROOT/name).read_text().replace("−","-")
        for claim in claims:assert claim in text,(name,claim)
    text=(ROOT/"student-notes.md").read_text()
    for paper in ("Aghion","Admati","Bolton","Neher"):
        assert paper in text,("student-notes.md",paper)
    text=(ROOT/"w05-venture-contract.qmd").read_text()
    for paper in ("Aghion","Hellmann","Casamatta","Neher","Cornelli","Kaplan","Gompers","Bergemann","Repullo","Schmidt"):
        assert paper in text,("w05-venture-contract.qmd",paper)
    book=(ROOT/"student-notes.md").read_text()
    fund=book.split("## 第一篇：",1)[1].split("## 第二篇：",1)[0]
    assert "GP 无初始财富" not in fund
    assert "### 4. 有业绩报酬" in fund
    assert "### 6. 为什么新老管理机构" in fund
    assert "## 附录 C：多项目投资与基金融资结构" in book
    headings=re.findall(r"^## 附录 ([A-H])：.*\{#book-app-([a-h])\}",book,re.M)
    assert headings==[(x,x.lower()) for x in "ABCDEFGH"], headings
    for letter in "ABCDEFGH":
        section=book.split("## 附录 "+letter+"：",1)[1].split("\n## ",1)[0]
        numbers=re.findall(r"^### ([A-H])\.(\d+)",section,re.M)
        assert [x for x,_ in numbers]==[letter]*len(numbers),(letter,numbers)
        assert [int(n) for _,n in numbers]==list(range(1,len(numbers)+1)),(letter,numbers)
    for name in SOURCES:
        value=(ROOT/name).read_text()
        assert "ASW附录D" not in value,name
        for label,target in re.findall(r"\[附录 ([A-H])\]\([^)]*#book-app-([a-h])\)",value):
            assert label.lower()==target,(name,label,target)
    prep=(ROOT/"w05-preparation.qmd").read_text()
    assert re.findall(r"^## P5-(\d)：",prep,re.M)==["1","2","3","4"]
    assert "#p5-3a" not in prep and "#p5-3b" not in prep
    assert "检验通过率与后验概率" not in prep
    assert "核对 P5-4" in prep and "P5-2：事后能合作，事前为什么仍不投入？" in prep
    assert "## 第一部分：不完全合同，为什么事前需要安排事后决定权？" in (ROOT/"w05-venture-contract.qmd").read_text()
    for anchor in ("p4-0","p4-1","p4-2","p4-3","p4-4","p4-5"):
        assert "{#"+anchor+"}" in (ROOT/"w04-preparation.qmd").read_text()
    for anchor in ("h4-1","h4-2","h4-3","h4-4","h4-5","h4-asw-pooling","h4-asw-financing"):
        assert "{#"+anchor+"}" in (ROOT/"exercises.qmd").read_text()
    venture=book.split("## 第二篇：",1)[1].split("## 附录怎样读？",1)[0]
    for anchor in ("book-venture-motivation","book-venture-rights","book-venture-control","book-venture-incomplete","book-venture-holdup","book-venture-ab-financing","book-venture-ab-signal","book-venture-double","book-venture-schmidt","book-venture-staging","book-venture-exit","book-venture-summary"):
        assert "{#"+anchor+"}" in venture,anchor
    assert venture.index("{#book-venture-control}")<venture.index("{#book-venture-incomplete}")<venture.index("{#book-venture-holdup}")<venture.index("{#book-venture-ab-financing}")<venture.index("{#book-venture-ab-signal}")<venture.index("{#book-venture-rights}")<venture.index("{#book-venture-double}")<venture.index("{#book-venture-schmidt}")<venture.index("{#book-venture-staging}")
    assert "{#book-venture-followon}" in book.split("## 附录 F：",1)[1].split("## 附录 G：",1)[0]
    for claim in ("77.5","70","17/16",r"\frac{25}{24}","5/8","六个选择","Example 4.1","1.2222","0.66"):
        assert claim in venture,claim
    classroom=(ROOT/"w05-venture-contract.qmd").read_text()
    third=classroom.split("## 第三部分：",1)[1].split("## 分阶段融资之后",1)[0]
    assert "Neher" in third and "L_2=0" in third and "Gompers" in third
    assert "粉饰怎样移动信号" not in third
    assert "尚不知道项目好坏" in book.split("### G.3 ",1)[1].split("### G.4 ",1)[0]
    hellmann=book.split("### G.1 ",1)[1].split("### G.2 ",1)[0]
    casamatta=book.split("### G.2 ",1)[1].split("### G.3 ",1)[0]
    assert all(x in hellmann for x in ("0.76","34","1+\\alpha p_B","vesting"))
    assert all(x in casamatta for x in ("2.3","4.1","1.8","自己出资"))
    assert "### Hellmann（1998）：" not in classroom and "### Casamatta：" not in classroom
    expected=classroom[classroom.index("## 一份 VC 合同需要回答哪些问题？"):]
    expected=re.sub(r"^(#{2,5}) ",lambda m:"#"+m[1]+" ",expected,flags=re.M)
    names={"w05-motivation":"book-venture-motivation","w05-payments":"book-venture-rights",
           "w05-control":"book-venture-control","w05-schmidt":"book-venture-schmidt",
           "w05-incomplete":"book-venture-incomplete","w05-holdup":"book-venture-holdup",
           "w05-ab-financing":"book-venture-ab-financing","w05-ab-signal":"book-venture-ab-signal",
           "w05-double":"book-venture-double","w05-staging":"book-venture-staging",
           "w05-reading-map":"book-venture-reading-map","w05-exit":"book-venture-exit",
           "w05-check":"book-venture-summary"}
    for old,new in names.items():expected=expected.replace("{#"+old+"}","{#"+new+"}")
    expected=expected.replace("student-notes.html#book-","#book-")
    assert venture.split("\n\n",1)[1].strip()==expected.strip(),"Classroom/book body drift"
    intro=classroom.split("### 不完全合同、专用性投资与重新谈判",1)[1].split("### 金融合同应用",1)[0]
    for claim in ("Grossman", "Hart–Moore", "关系专用性投资", "谈判破裂收益", "一次性转移", "可写合同集合", "50-60=-10", "70-60=10", "事前投资不足", "人力资本"):
        assert claim in intro,claim
    assert "完全准确信号" not in prep.split("## P5-2：",1)[1].split("## P5-3：",1)[0]
    h2=(ROOT/"exercises.qmd").read_text().split("### H5-2：",1)[1].split("### H5-3：",1)[0]
    assert all(claim in h2 for claim in ("x\\ge20", "弱激励", "77.5", "事前没有投资"))
    bib=(ROOT/"references-by-module.bib").read_text()
    keys=re.findall(r"@\w+\{([^,]+),",bib)
    assert len(keys)==len(set(keys)),"Duplicate bibliography key"
    for key,doi in (("grossman1986ownership","10.1086/261404"),("hart1990property","10.1086/261729")):
        assert key in keys and doi in bib,(key,doi)

    assert "2024 年 6 月的工作论文版本" in book
    assert "暂不允许中期追加补偿或重谈" not in venture
    assert "book-venture-experiment" not in venture
    assert "+-\\underbrace" not in venture
    assert "仍由 VC 提供全部启动资本" in book
    assert book.index("{#book-venture-experiment}") > book.index("{#book-app-h}")
    for name in ("student-notes.md","w05-venture-contract.qmd","w05-preparation.qmd"):
        assert "不是，而是" not in (ROOT/name).read_text(),name
    assert "开场问答：从预习答案进入模型" not in (ROOT/"w05-venture-contract.qmd").read_text()
    exercises=(ROOT/"exercises.qmd").read_text()
    assert exercises.index("{#h5-5}") < exercises.index("{#optional-homework}")
    assert exercises.index("{#h5-6}") > exercises.index("{#optional-homework}")
    assert "第 5 周完成 H5-1 至 H5-5" in exercises
    assert re.findall(r"^### H5-(\d+)：",exercises,re.M)==[str(i) for i in range(1,14)]
    for exercise in re.finditer(r"^### H5-\d+：.*?(?=^### |^## |\Z)",exercises,re.M|re.S):
        numbers=re.findall(r"^(\d+)\. ",exercise[0].split("<details",1)[0],re.M)
        assert [int(n) for n in numbers]==list(range(1,len(numbers)+1)),exercise[0].splitlines()[0]
    for name in SOURCES:
        text=(ROOT/name).read_text()
        assert not [c for c in text if ord(c)<32 and c not in "\n\t"], name
    return hashes

def html_checks():
    pages={}
    for name in PAGES:
        path=ROOT/"docs"/name
        assert path.exists(),path
        parsed=Page();parsed.feed(path.read_text())
        assert not [k for k,v in Counter(parsed.ids).items() if v>1],name
        assert parsed.detail_depth==0,name
        assert not re.search(r"\d+\s*分钟|预计.{0,20}(分钟|小时)"," ".join(parsed.text)),name
        pages[name]=parsed
    count=0
    for name,parsed in pages.items():
        for href in parsed.links:
            u=urlsplit(href)
            if u.scheme or u.netloc:continue
            path=unquote(u.path) or name
            if path not in pages:
                assert (ROOT/"docs"/path).exists(),(name,href)
            elif u.fragment:
                assert unquote(u.fragment) in pages[path].ids,(name,href)
            count+=1
    return {"pages":len(pages),"local_links_checked":count,
            "details":sum(p.details for p in pages.values()),
            "sha256":{n:sha256((ROOT/"docs"/n).read_bytes()).hexdigest() for n in PAGES}}

def mirror_checks():
    base=ROOT.parent
    matched=0
    for name in SOURCES+["pevc-handout.css"]:
        assert (ROOT/name).read_bytes()==(base/"html-src"/name).read_bytes(),name
        matched+=1
    assert (ROOT/"student-notes.md").read_bytes()==(base/"W04-W05-PEVC合同理论-学生讲义.md").read_bytes()
    matched+=1
    for name in PAGES:
        raw=(ROOT/"docs"/name).read_bytes()
        for folder in (base/"docs",base/"docs/html-src"):
            assert raw==(folder/name).read_bytes(),str(folder/name)
            matched+=1
    assert (ROOT/"docs/w05-venture-contract.html").read_bytes()==(ROOT/"w05-venture-contract.html").read_bytes()
    existing_md=base/"docs/html-src/student-notes.md"
    if existing_md.is_file():
        assert (ROOT/"student-notes.md").read_bytes()==existing_md.read_bytes()
        matched+=1
    return matched+1

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--sources-only",action="store_true")
    args=parser.parse_args()
    result={"numerical":numerical_checks(),"source_sha256":source_checks()}
    if not args.sources_only:
        result["html"]=html_checks()
        result["mirrored_files_checked"]=mirror_checks()
    destination=ROOT/"checks"/("numeric-report.json" if args.sources_only else "verification-report.json")
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"result":"passed","report":str(destination),
                      "html":result.get("html",{}).get("pages"),
                      "mirrors":result.get("mirrored_files_checked")},ensure_ascii=False))
