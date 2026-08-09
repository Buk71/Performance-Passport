
from __future__ import annotations
from dataclasses import dataclass
import datetime, json
from collections import Counter
from typing import Any
from core.database import get_athlete_sport_roles, get_connection

DAY_NAMES=("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")

@dataclass(frozen=True)
class ValidationScenario:
    key:str; athlete_id:int; label:str; target_date:datetime.date; weeks:int; outcome_type:str

@dataclass(frozen=True)
class ScenarioDecision:
    date:str; weekday:str; phase:str; planned_family:str; planned_session:str
    actual_title:str|None; actual_family:str|None; execution_score:float|None
    action:str; accepted:bool; status:str; explanation:tuple[str,...]

@dataclass(frozen=True)
class ScenarioResult:
    scenario:ValidationScenario; quality_days:tuple[str,...]; decisions:tuple[ScenarioDecision,...]
    decision_count:int; sensible_count:int; review_count:int; trusted_execution_count:int
    data_coverage:float; validation_rate:float; flags:tuple[str,...]; verdict:str

@dataclass(frozen=True)
class ValidationSuite:
    scenarios:tuple[ScenarioResult,...]; overall_verdict:str; release_ready:bool
    summary:str; blockers:tuple[str,...]; model_version:int=1

def _date(v):
    try: return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError,ValueError): return None

def _family(pj):
    try: phases=json.loads(pj or "[]")
    except (TypeError,json.JSONDecodeError): return None
    aliases={"short_interval":"short_intervals","short_reps":"short_intervals",
             "intervals":"long_intervals","mile_repetitions":"long_intervals",
             "continuous_threshold":"threshold","long_threshold":"threshold",
             "sustained_quality":"threshold"}
    types={aliases.get(str(p.get("phase_type") or "").lower(),
                       str(p.get("phase_type") or "").lower()) for p in phases if isinstance(p,dict)}
    if "threshold" in types: return "threshold"
    if {"short_intervals","vo2","long_intervals"} & types: return "vo2"
    if "strides" in types: return "speed"
    return None

def _infer_quality_days(athlete_id,start):
    lookback=start-datetime.timedelta(days=180)
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""SELECT activity_date,phase_json FROM workout_library
                   WHERE athlete_id=? AND activity_date>=? AND activity_date<?
                   AND phase_confidence>=0.70 AND recognition_confidence>=0.65""",
                (athlete_id,lookback.isoformat(),start.isoformat()))
    rows=cur.fetchall(); conn.close()
    counts=Counter()
    for dt,pj in rows:
        if _family(pj):
            d=_date(dt)
            if d: counts[d.weekday()]+=1
    chosen=[d for d,_ in counts.most_common(2)]
    if len(chosen)<2: return (2,5)
    chosen=sorted(chosen[:2])
    if min((chosen[1]-chosen[0])%7,(chosen[0]-chosen[1])%7)<2: return (2,5)
    return tuple(chosen)

def _standard_bucket(d):
    standards=(5.0,10.0,21.0975); c=min(standards,key=lambda x:abs(d-x))
    return c if abs(d-c)/c<=0.06 else None

def _prior_standard_paces(athlete_id,before,standard):
    roles=get_athlete_sport_roles(athlete_id); running={str(k) for k,v in roles.items() if v=="running"}
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""SELECT distance_m,moving_time_s,sport_id FROM activities
                   WHERE athlete_id=? AND activity_date<? AND distance_m IS NOT NULL AND moving_time_s IS NOT NULL""",
                (athlete_id,before.isoformat()))
    rows=cur.fetchall(); conn.close()
    out=[]
    for dm,t,sport in rows:
        if str(sport or "") not in running: continue
        try: d=float(dm); t=float(t)
        except (TypeError,ValueError): continue
        if d>250: d/=1000
        if d<=0 or t<=0 or abs(d-standard)/standard>0.06: continue
        p=t/d
        if 150<=p<=900: out.append(p)
    return sorted(out)

def _asof_hard_effort(athlete_id,date,title,distance_km,moving_s,elapsed_s):
    lower=(title or "").lower()
    if any(w in lower for w in ("race","parkrun","5k race","10k race","half marathon")): return True
    standard=_standard_bucket(distance_km)
    if standard is None or not moving_s or moving_s<=0: return False
    history=_prior_standard_paces(athlete_id,date,standard)
    if len(history)<6: return False
    pace=moving_s/distance_km; best=history[0]
    percentile=sum(x<=pace for x in history)/len(history)
    continuity=min(moving_s/elapsed_s,1.0) if elapsed_s and elapsed_s>0 else 1.0
    return pace<=best*1.10 and percentile<=0.20 and continuity>=0.985

def _actual(athlete_id,date):
    roles=get_athlete_sport_roles(athlete_id); running={str(k) for k,v in roles.items() if v=="running"}
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""SELECT id,title,distance_m,moving_time_s,elapsed_time_s,sport_id
                   FROM activities WHERE athlete_id=? AND activity_date=? ORDER BY distance_m DESC""",
                (athlete_id,date.isoformat()))
    acts=cur.fetchall()
    for row in acts:
        if str(row[5] or "") not in running: continue
        d=float(row[2] or 0); d=d/1000 if d>250 else d
        cur.execute("""SELECT phase_json,execution_score,recognition_confidence,phase_confidence
                       FROM workout_library WHERE activity_id=?""",(row[0],))
        w=cur.fetchone()
        fam=None; execution=None
        if w and float(w[2] or 0)>=0.65 and float(w[3] or 0)>=0.70:
            fam=_family(w[0]); execution=float(w[1]) if w[1] is not None else None
        hard=_asof_hard_effort(athlete_id,date,str(row[1] or ""),d,
                                float(row[3]) if row[3] is not None else None,
                                float(row[4]) if row[4] is not None else None)
        conn.close()
        return {"title":str(row[1] or "Run"),"family":"race" if hard else (fam or "easy"),
                "execution":execution}
    conn.close(); return None

def _prior_execution(athlete_id,family,date):
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""SELECT phase_json,execution_score FROM workout_library
                   WHERE athlete_id=? AND activity_date<? AND execution_score IS NOT NULL
                   AND recognition_confidence>=0.65 AND phase_confidence>=0.70
                   ORDER BY activity_date DESC,id DESC LIMIT 20""",(athlete_id,date.isoformat()))
    rows=cur.fetchall(); conn.close()
    vals=[]
    for pj,score in rows:
        f=_family(pj)
        if f==family or (family in {"vo2","speed","race_pace"} and f=="vo2"): vals.append(float(score))
        if len(vals)>=4: break
    return vals

def _phase(w):
    return "Taper" if w<=1 else ("Specific" if w<=4 else "Build")

def _planned(phase,slot,index):
    if phase=="Taper":
        return ("race_pace","3 × 1 km at race effort") if slot==1 else ("speed","6 × 200m relaxed")
    if phase=="Specific":
        a=("6 × 800m","5 × 1000m","4 × 1200m"); b=("3 × 10 min threshold","2 × 15 min threshold","2 × 10 min threshold + strides")
    else:
        a=("8 × 400m","10 × 400m","8 × 500m","8 × 600m","6 × 800m","7 × 800m")
        b=("4 × 8 min threshold","3 × 10 min threshold","4 × 10 min threshold","3 × 12 min threshold","2 × 15 min threshold")
    seq=a if slot==1 else b
    return ("vo2" if slot==1 else "threshold",seq[min(index-1,len(seq)-1)])

def _action(family,actual,prior):
    if actual is None: return "hold",False,"No run recorded."
    af=actual["family"]
    if af=="race": return "recover",True,"Hard race-quality effort replaces planned quality."
    accepted=af==family or (family in {"vo2","speed","race_pace"} and af=="vo2")
    if not accepted: return "hold",False,f"Different stimulus ({af}); no progression."
    score=actual["execution"]
    if score is None: return "hold",True,"Matching stimulus but execution evidence unavailable."
    avg=sum(prior)/len(prior) if prior else None
    if avg is not None and score<=avg-10: return ("repeat" if score>=72 else "reduce"),True,"Execution dropped versus baseline."
    if score>=90 and (avg is None or avg>=82): return "progress",True,"Strong execution."
    if score>=82: return "small_progress",True,"Good execution; modest overload only."
    if score>=72: return "repeat",True,"Repeat before overload."
    return "reduce",True,"Reduce next load."

def simulate_scenario(scenario):
    start=scenario.target_date-datetime.timedelta(weeks=scenario.weeks)
    qdays=_infer_quality_days(scenario.athlete_id,start); mapping={qdays[0]:1,qdays[1]:2}
    counts=Counter(); decisions=[]; flags=[]; sensible=review=trusted=0; last=None
    current=start
    while current<scenario.target_date:
        if current.weekday() in mapping:
            weeks_to=(scenario.target_date-current).days/7; phase=_phase(weeks_to); slot=mapping[current.weekday()]
            counts[(phase,slot)]+=1; family,prescription=_planned(phase,slot,counts[(phase,slot)])
            actual=_actual(scenario.athlete_id,current); prior=_prior_execution(scenario.athlete_id,family,current)
            action,accepted,reason=_action(family,actual,prior)
            if actual and actual["execution"] is not None: trusted+=1
            status="sensible"
            if last is not None and (current-last).days<2:
                status="review"; flags.append(f"{current}: quality spacing <48h")
            if phase=="Taper" and action in {"progress","small_progress"}:
                status="review"; flags.append(f"{current}: progression attempted in taper")
            sensible += status=="sensible"; review += status=="review"; last=current
            decisions.append(ScenarioDecision(current.isoformat(),current.strftime("%A"),phase,family,prescription,
                                               actual["title"] if actual else None,actual["family"] if actual else None,
                                               actual["execution"] if actual else None,action,accepted,status,(reason,)))
        current+=datetime.timedelta(days=1)
    count=len(decisions); coverage=trusted/count if count else 0; rate=sensible/count if count else 0
    if coverage<0.20: flags.append("Execution-data coverage below 20%; progression proof is limited.")
    verdict="Needs refinement" if rate<0.90 else ("Pass with review" if review else "Pass")
    return ScenarioResult(scenario,tuple(DAY_NAMES[d] for d in qdays),tuple(decisions),count,sensible,review,
                          trusted,round(coverage,4),round(rate,4),tuple(flags),verdict)

def build_validation_suite():
    scenarios=(
        ValidationScenario("richard_pb",1,"Richard · 10 weeks before 19:07 5K PB",datetime.date(2026,5,5),10,"successful"),
        ValidationScenario("jo_strong",3,"Jo · 8 weeks before 22:51 5K",datetime.date(2026,7,7),8,"successful"),
        ValidationScenario("richard_ordinary",1,"Richard · ordinary 8-week period ending 7 Mar",datetime.date(2026,3,7),8,"ordinary"),
    )
    results=tuple(simulate_scenario(s) for s in scenarios)
    blockers=[]
    for r in results:
        if r.verdict=="Needs refinement": blockers.append(f"{r.scenario.label}: needs refinement.")
        if r.review_count: blockers.append(f"{r.scenario.label}: {r.review_count} decisions need review.")
    ready=not blockers
    return ValidationSuite(results,"Pass" if ready else "Hold",ready,
        "Adaptive Coach is now tested across a successful Richard build, a strong Jo build and an ordinary Richard period, with pre-start schedule inference and no future performance lookahead in hard-effort detection.",
        tuple(blockers))
