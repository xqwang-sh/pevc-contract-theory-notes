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

    returns = {"G": {"E": (100,30), "V": (120,0)},
               "B": {"E": (50,18), "V": (80,0)}}
    control = {}
    for label, policy in {
        "entrepreneur": {"G":"E","B":"E"},
        "vc": {"G":"V","B":"V"},
        "contingent": {"G":"E","B":"V"},
    }.items():
        e_util = vc_cash = total = 0
        for state, action in policy.items():
            cash, benefit = returns[state][action]
            e_util += .5*(.3*cash+benefit)
            vc_cash += .5*.7*cash
            total += .5*(cash+benefit)
        close(e_util + vc_cash - 60, total-60)
        control[label] = {"E_utility":e_util, "VC_cash":vc_cash,
                          "net_surplus":total-60}
    for label, e, vc, total in (
        ("entrepreneur",46.5,52.5,39),("vc",30,70,40),
        ("contingent",42,63,45)):
        close(control[label]["E_utility"],e)
        close(control[label]["VC_cash"],vc)
        close(control[label]["net_surplus"],total)
    assert 18/30 > 1-60/90
    close(.5*.1*10+.5*.2*12, 1.7)
    close(.7*(102+74)/2, 61.6)

    neher_deviations = [(1.8-j-l)/2 for j,l in ((.4,0),(.4,.5),(0,.5))]
    for x,y in zip(neher_deviations,(.7,.45,.65)):
        close(x,y)
        assert x < .8
    assert 1-.4 > .5
    assert 1.8/2 < 1
    assert (1.8-0)/2 > .8

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

    for z in (80,90,100,120,130):
        assert ((.3*z-.3*100)>=-1e-10) == (z>=100)
    close(.4*90-.1*100,26)
    close(.4*130-.6*100,-8)

    experiment = {}
    for d,h_want,post_want,vc_want,e_want in (
        (.9,.42,6/7,12,2.84),(.45,.69,12/23,-1.5,3.38)):
        h=.4*.9+.6*(1-d)
        vc=.4*.9*100-h*50-3
        e=2+h*2
        close(h,h_want);close(.36/h,post_want);close(vc,vc_want);close(e,e_want)
        assert (.36/h)*100 > 50
        experiment[str(d)]={"pass":h,"posterior":.36/h,"VC":vc,"E":e}
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
            "control":control,"neher_deviations":neher_deviations,
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
        "w05-venture-contract.qmd":["52.5","0.65","2.84","3.38","-1.5"],
        "w05-preparation.qmd":["0.8571","0.5217"],
        "exercises.qmd":["26.32","14.664","42.336","198.8406","41.7","6.66","8.18"],
    }
    for name,claims in required.items():
        text=(ROOT/name).read_text().replace("−","-")
        for claim in claims:assert claim in text,(name,claim)
    for name in ("student-notes.md","w05-venture-contract.qmd"):
        text=(ROOT/name).read_text()
        for paper in ("Aghion","Admati","Bolton","Neher"):
            assert paper in text,(name,paper)
    book=(ROOT/"student-notes.md").read_text()
    fund=book.split("## 第一篇：",1)[1].split("## 第二篇：",1)[0]
    assert "GP 无初始财富" not in fund
    assert "### 4. 有业绩报酬" in fund
    assert "### 6. 为什么新老管理机构" in fund
    assert "## ASW附录D：" in book
    for anchor in ("p4-0","p4-1","p4-2","p4-3","p4-4","p4-5"):
        assert "{#"+anchor+"}" in (ROOT/"w04-preparation.qmd").read_text()
    for anchor in ("h4-1","h4-2","h4-3","h4-4","h4-5","h4-asw-pooling","h4-asw-financing"):
        assert "{#"+anchor+"}" in (ROOT/"exercises.qmd").read_text()
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
