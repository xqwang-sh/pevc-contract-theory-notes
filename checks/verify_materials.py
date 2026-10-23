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

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    "student-notes.md", "student-notes.qmd", "w04-fund-contract.qmd",
    "w05-venture-contract.qmd", "w04-preparation.qmd",
    "w05-preparation.qmd", "exercises.qmd",
]
PAGES = [
    "index.html", "student-notes.html", "w04-fund-contract.html",
    "w05-venture-contract.html", "w04-preparation.html",
    "w05-preparation.html", "exercises.html",
]

def close(x, y):
    assert math.isclose(x, y, abs_tol=1e-8), (x, y)

def week5_numerical_checks():
    from fractions import Fraction as F

    # Aghion–Bolton (1992), pp. 482–484 original numerical example.
    # y_i^j is monetary income; lambda_i^j is non-transferable private benefit.
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

    # Hellmann (1998) eq. (2) with alpha_0=0, teaching values; p and B held fixed.
    phi,p,B,M,th=F(4,5),F(1,2),F(1,10),F(1),F(1,2)
    G=phi-p-B; a=F(2,5)
    SFC=B+a*p; SR=SFC+th*G; mR=(phi-(1-a)*p-SR)/M
    assert (G,SFC,SR,mR)==(F(1,5),F(3,10),F(2,5),F(1,10))
    uvc=(1-a)*p+mR*(1-th)*G-M*mR**2/2; uen=B+a*p+mR*th*G
    assert (uvc,uen)==(F(61,200),F(31,100))
    a2=1-(uvc-G**2/(2*M))/p
    assert a2==F(43,100) and B+a2*p==F(63,200)>uen
    m_low=(phi-F(1,5)-(1-a)*p)/M
    assert m_low==F(3,10) and m_low*G-M*m_low**2/2==F(3,200)
    # Casamatta-style teaching model (not original numbers).
    R_,L0,cE,cV=F(10),F(2),F(3,5),F(2,5)
    E=F(4,5)*R_+F(1,5)*L0
    assert E==F(42,5) and cV/F(1,5)==2 and (R_-L0)-cE/F(3,10)==6
    assert F(3,4)*E-cV==F(59,10) and F(4,5)*8+F(1,5)*2-cV==F(32,5)
    assert F(1,4)*E-cV==F(17,10)
    sE=1-F(1,4)-3/E
    assert sE==F(11,28) and sE*E-cE==F(27,10) and E-3-cV-cE==F(22,5)
    xS=(F(31,5)+cV-F(1,5)*L0)/F(4,5)
    assert xS==F(31,4) and (R_-xS)*F(3,10)==F(27,40) and F(4,5)*(R_-xS)-cE==F(6,5)
    # H5-3 Hellmann exercise: phi=.9, p=.5, B=.2, M=1, theta=3/4, alpha=.4.
    phi3,p3,B3,th3,a3=F(9,10),F(1,2),F(1,5),F(3,4),F(2,5)
    G3=phi3-p3-B3; SR3=B3+a3*p3+th3*G3; m3=phi3-(1-a3)*p3-SR3
    uvc3=(1-a3)*p3+m3*(1-th3)*G3-m3**2/2; uen3=B3+a3*p3+m3*th3*G3
    assert (G3,SR3,m3,uvc3,uen3)==(F(1,5),F(11,20),F(1,20),F(241,800),F(163,400))
    a3b=1-(uvc3-G3**2/2)/p3
    assert a3b==F(7,16) and B3+a3b*p3==F(67,160)
    # H5-4 teaching numbers.
    E4=F(4,5)*12+F(1,5)*3
    assert E4==F(51,5) and F(2,9)*E4-F(2,5)==F(28,15) and E4-F(2,9)*E4-4-F(3,5)==F(10,3)
    assert (8+F(2,5))/E4==F(14,17) and (8+F(2,5)-F(3,5))/F(4,5)==F(39,4)
    assert F(1,2)*80+F(1,2)*10-10==35 and F(50,75)==F(2,3) and F(1,3)*75-3==22 and F(50,120)==F(5,12)
    # Staging and window dressing teaching model.
    assert F(1,2)*100+F(1,2)*20-40==20 and F(1,2)*70+F(1,2)*5-10==F(55,2)
    assert 1-F(4,15)==F(11,15) and 25/F(105,2)==F(10,21) and F(40,60)==F(2,3)
    assert F(1,3)*60-2==18 and (25-F(5,2))/F(1,2)==45 and F(1,2)*55==F(55,2)

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

    result={"aghion_bolton":{"pi1":pi1,"pi2":pi2,"pi3_beta_099_001":pi3,"pi4":pi4,
              "theta_b_direct_share":F(49,50)},
            "neher_example_4_1":{"P0":P0,"P1":P1,"P2":P2,"L2":L2,
              "U1_V":U1,"U2_V":U2,"S1":S1,"C1":C1,"E_NPV":F(33,50),
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
        "w05-venture-contract.qmd":["200 笔投资","118 家被投企业","56%","17.5%","Q<Q_1","0.305","0.315","0.43","17/42","6.4","27.5","11/15"],
        "w05-preparation.qmd":["49/50","3/2","50.005","62.5","0.015","[0.25,0.75]"],
        "exercises.qmd":["26.32","14.664","42.336","198.8406","49/50","62.5","1.1852","5/14","6.66","8.18","0.30125","0.41875","7/16","14/17","9.75","5/12"],
    }
    for name,claims in required.items():
        text=(ROOT/name).read_text().replace("−","-")
        for claim in claims:assert claim in text,(name,claim)
    text=(ROOT/"student-notes.md").read_text()
    for paper in ("Aghion","Admati","Bolton","Neher"):
        assert paper in text,("student-notes.md",paper)
    text=(ROOT/"w05-venture-contract.qmd").read_text()
    for paper in ("Aghion","Hellmann","Casamatta","Cornelli","Kaplan","Gompers"):
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
    assert "核对 P5-4" in prep and "Aghion" in prep and "**P5-2：Aghion–Bolton**" in prep
    assert "## 理论基础：Aghion–Bolton" not in (ROOT/"w05-venture-contract.qmd").read_text()
    for anchor in ("p4-0","p4-1","p4-2","p4-3","p4-4","p4-5"):
        assert "{#"+anchor+"}" in (ROOT/"w04-preparation.qmd").read_text()
    for anchor in ("h4-1","h4-2","h4-3","h4-4","h4-5","h4-asw-pooling","h4-asw-financing"):
        assert "{#"+anchor+"}" in (ROOT/"exercises.qmd").read_text()
    venture=book.split("## 第二篇：",1)[1].split("## 附录怎样读？",1)[0]
    for anchor in ("book-venture-motivation","book-venture-rights","book-venture-control","book-venture-hellmann","book-venture-double","book-venture-staging","book-venture-exit","book-venture-summary"):
        assert "{#"+anchor+"}" in venture,anchor
    assert venture.index("{#book-venture-control}")<venture.index("{#book-venture-hellmann}")<venture.index("{#book-venture-double}")<venture.index("{#book-venture-staging}")
    assert "{#book-venture-followon}" in book.split("## 附录 F：",1)[1].split("## 附录 G：",1)[0]
    for claim in ("49/50","62.5","0.305","0.315","17/42","27.5","11/15"):
        assert claim in venture,claim
    assert "本轮已重读" in book and "2024 年 6 月的工作论文版本" in book
    assert "暂不允许中期追加补偿或重谈" not in venture
    assert "book-venture-experiment" not in venture
    assert book.index("{#book-venture-experiment}") > book.index("{#book-app-h}")
    for name in ("student-notes.md","w05-venture-contract.qmd","w05-preparation.qmd"):
        assert "不是，而是" not in (ROOT/name).read_text(),name
    assert "开场问答：从预习答案进入模型" not in (ROOT/"w05-venture-contract.qmd").read_text()
    exercises=(ROOT/"exercises.qmd").read_text()
    assert exercises.index("{#h5-5}") > exercises.index("{#optional-homework}")
    assert "第 5 周完成 H5-1 至 H5-4" in exercises
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
