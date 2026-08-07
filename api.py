import json
import logging
import threading
from pathlib import Path
from urllib.parse import unquote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import council
import db

logger = logging.getLogger("rcc.api")

app = FastAPI(
    title="Research Consensus Council API",
    description="FastAPI service for multi-agent academic paper consensus and deliberation.",
    version="1.0.0"
)

# Enable CORS for external dashboard client integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

# Global Human-in-the-Loop orchestration state
active_deliberation = {
    "status": "idle",              # idle | deliberating | waiting_for_approval | completed | aborted | failed
    "round_num": 0,
    "paper_path": "",
    "reviews": [],                 # Reviews accumulated in the current active round
    "error_message": "",
}
approval_event = threading.Event()
abort_flag = threading.Event()

def hitl_callback(round_num: int, reviews: list) -> bool:
    """
    Callback function injected into the deliberation engine.
    Updates the live state and blocks execution until human approval or abort is triggered from the API/UI.
    """
    global active_deliberation
    active_deliberation["status"] = "waiting_for_approval"
    active_deliberation["round_num"] = round_num
    active_deliberation["reviews"] = [
        {
            "agent_name": r.agent_name,
            "criterion": r.criterion,
            "score": r.score,
            "justification": r.justification or "",
            "challenge_target": r.challenge_target or "",
        } for r in reviews
    ]

    logger.info(f"Deliberation paused: Round {round_num} waiting for Human-in-the-Loop approval.")
    approval_event.clear()
    approval_event.wait()  # Block deliberation thread until approved or aborted

    if abort_flag.is_set():
        logger.warning(f"Deliberation aborted by user during Round {round_num} review.")
        return False

    logger.info(f"Round {round_num} approved by human. Resuming deliberation.")
    active_deliberation["status"] = "deliberating"
    active_deliberation["reviews"] = []
    return True

def background_deliberation_task(paper_path: str):
    """Orchestrates the deliberation execution inside a background worker thread."""
    global active_deliberation
    abort_flag.clear()
    approval_event.clear()

    active_deliberation["status"] = "deliberating"
    active_deliberation["paper_path"] = paper_path
    active_deliberation["round_num"] = 1
    active_deliberation["reviews"] = []
    active_deliberation["error_message"] = ""

    try:
        # Check if file exists before running
        if not Path(paper_path).exists():
            raise FileNotFoundError(f"Manuscript file not found: {paper_path}")

        # Run the full council engine, passing the callback hook
        council.run_council(paper_path, hitl_hook=hitl_callback)
        active_deliberation["status"] = "completed"
        logger.info(f"Deliberation successfully completed for {paper_path}.")
    except Exception as exc:
        if abort_flag.is_set():
            active_deliberation["status"] = "aborted"
            logger.info("Deliberation cleanup completed after abort trigger.")
        else:
            active_deliberation["status"] = "failed"
            active_deliberation["error_message"] = str(exc)
            logger.error(f"Deliberation failed: {exc}", exc_info=True)

# ──────────────────────────────────────────────
# Dashboard UI
# ──────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Research Consensus Council - Dashboard</title>
<meta name="description" content="Multi-agent paper review dashboard: verdict badge, score breakdown by criterion, and full review-chain timeline.">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d0f1a;--surface:#151826;--s2:#1e2235;--card:#242840;
  --accent:#7c6ff7;--text:#e4e8f1;--muted:#7a86a1;--border:#2b3050;
  --acc:#22c55e;--acc-bg:rgba(34,197,94,.13);
  --min:#f59e0b;--min-bg:rgba(245,158,11,.13);
  --maj:#f97316;--maj-bg:rgba(249,115,22,.13);
  --rej:#ef4444;--rej-bg:rgba(239,68,68,.13);
  --font:'Segoe UI',system-ui,-apple-system,sans-serif;
  --r:10px;--rl:16px;--sh:0 8px 32px rgba(0,0,0,.35)
}
body{font-family:var(--font);background:var(--bg);color:var(--text);display:flex;flex-direction:column;min-height:100vh}
header{background:linear-gradient(135deg,#1a1d35,#0d0f1a);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:14px}
header h1{font-size:1.05rem;font-weight:600;letter-spacing:-.01em}
.hbadge{background:var(--accent);color:#fff;border-radius:20px;padding:2px 9px;font-size:.68rem;font-weight:700;letter-spacing:.07em}
.hsub{color:var(--muted);font-size:.76rem;margin-left:auto}
.layout{display:flex;flex:1;overflow:hidden;height:calc(100vh - 53px)}
.sidebar{width:265px;min-width:210px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.sbhdr{padding:13px;border-bottom:1px solid var(--border)}
.sbhdr h2{font-size:.69rem;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);margin-bottom:8px}
.srch{background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:7px 10px;color:var(--text);font-size:.81rem;width:100%;outline:none;transition:border-color .2s}
.srch:focus{border-color:var(--accent)}
.plist{flex:1;overflow-y:auto;padding:6px}
.pitem{padding:9px 11px;border-radius:var(--r);cursor:pointer;transition:background .14s;margin-bottom:3px;border:1px solid transparent}
.pitem:hover{background:var(--s2)}
.pitem.active{background:var(--s2);border-color:var(--accent)}
.pname{font-size:.81rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pdate{font-size:.69rem;color:var(--muted);margin-top:2px}
.main{flex:1;overflow-y:auto;padding:22px 26px;background:var(--bg)}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:35vh;color:var(--muted);gap:10px;text-align:center}
.empty .ico{font-size:2.8rem;opacity:.22}
.empty code{background:var(--s2);padding:2px 7px;border-radius:5px;font-size:.74rem;color:#aab}

/* Glassmorphism Human-in-the-loop Active panel */
.hitl-panel{background:rgba(21,24,38,0.7);backdrop-filter:blur(10px);border:1px solid var(--border);border-radius:var(--rl);padding:20px;margin-bottom:20px;box-shadow:var(--sh)}
.hitl-header{display:flex;align-items:center;justify-content:between;margin-bottom:12px;border-bottom:1px solid var(--border);padding-bottom:10px}
.hitl-title{font-size:0.9rem;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:0.05em}
.hitl-status{font-size:0.75rem;padding:3px 9px;border-radius:12px;font-weight:600}
.hitl-controls{display:flex;gap:10px;margin-top:14px}
.btn{padding:8px 16px;border-radius:var(--r);font-size:0.75rem;font-weight:700;cursor:pointer;outline:none;border:none;transition:opacity 0.2s}
.btn-primary{background:var(--acc);color:#fff}
.btn-danger{background:var(--rej);color:#fff}
.btn-primary:hover, .btn-danger:hover{opacity:0.85}
.hitl-review-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px, 1fr));gap:10px;margin-top:12px}
.hitl-card{background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:10px}
.hitl-card-header{display:flex;justify-content:space-between;align-items:center;font-size:0.72rem;font-weight:700;color:var(--text);margin-bottom:6px}
.hitl-card-body{font-size:0.68rem;color:var(--muted);line-height:1.4}

/* Deliberation form */
.form-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px;margin-bottom:20px}
.form-row{display:flex;gap:10px;align-items:center}
.form-input{flex:1;background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:8px 12px;color:var(--text);font-size:0.8rem;outline:none}
.form-input:focus{border-color:var(--accent)}

.vc{background:linear-gradient(135deg,var(--surface),var(--s2));border:1px solid var(--border);border-radius:var(--rl);padding:20px 22px;display:flex;align-items:center;gap:20px;margin-bottom:16px;box-shadow:var(--sh)}
.sring{width:78px;height:78px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;border:4px solid var(--border);flex-shrink:0}
.sval{font-size:1.35rem;font-weight:700;line-height:1}
.smax{font-size:.65rem;color:var(--muted)}
.vinfo h2{font-size:1.28rem;font-weight:700;margin-bottom:4px}
.vbadge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.73rem;font-weight:600;letter-spacing:.04em}
.va{background:var(--acc-bg);color:var(--acc)}.vm{background:var(--min-bg);color:var(--min)}.vmj{background:var(--maj-bg);color:var(--maj)}.vr{background:var(--rej-bg);color:var(--rej)}
.stitle{font-size:.69rem;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);margin-bottom:9px;padding-bottom:7px;border-bottom:1px solid var(--border)}
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:9px;margin-bottom:20px}
.scard{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:12px 14px;transition:transform .14s,box-shadow .14s;cursor:default}
.scard:hover{transform:translateY(-2px);box-shadow:var(--sh)}
.scn{font-size:.72rem;color:var(--muted);margin-bottom:5px}
.scv{font-size:1.12rem;font-weight:700;margin-bottom:6px}
.sbbg{background:var(--s2);border-radius:4px;height:5px;overflow:hidden}
.sbf{height:100%;border-radius:4px;transition:width .65s ease}
.scag{font-size:.66rem;color:var(--muted);margin-top:5px}
.rnd{margin-bottom:17px}
.rlbl{font-size:.71rem;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;display:flex;align-items:center;gap:7px}
.rlbl::after{content:'';flex:1;height:1px;background:var(--border)}
.rcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:8px}
.rc{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px 12px}
.rct{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px}
.rag{font-size:.76rem;font-weight:600}
.rcrn{font-size:.66rem;color:var(--muted);margin-bottom:3px}
.rpill{font-size:.72rem;font-weight:700;padding:2px 7px;border-radius:11px;background:var(--s2);flex-shrink:0}
.rjust{font-size:.7rem;color:var(--muted);line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.sp{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>
<header>
  <span style="font-size:1.25rem">⚖️</span>
  <h1>Research Consensus Council</h1>
  <span class="hbadge">LIVE</span>
  <span class="hsub" id="ref">Loading...</span>
</header>
<div class="layout">
  <aside class="sidebar">
    <div class="sbhdr">
      <h2>Processed Papers</h2>
      <input class="srch" id="srch" type="text" placeholder="Search..." oninput="filter()">
    </div>
    <div class="plist" id="plist">
      <div style="text-align:center;padding:18px"><span class="sp"></span></div>
    </div>
  </aside>
  <main class="main" id="main-area">
    <!-- Live Deliberation Panel -->
    <div id="hitl-panel-area"></div>

    <!-- Deliberation Trigger Form -->
    <div class="form-panel">
      <div class="form-row">
        <input class="form-input" id="delib-path" type="text" placeholder="Enter path to paper (e.g. tests/fixtures/test_paper.txt)">
        <button class="btn btn-primary" onclick="startDeliberation()">Start Deliberation</button>
      </div>
    </div>

    <!-- Selected Paper Content Detail Area -->
    <div id="main">
      <div class="empty">
        <div class="ico">📋</div>
        <p>Select a paper to view its deliberation results.</p>
        <p style="font-size:.74rem">Process a paper or trigger one from the box above.</p>
      </div>
    </div>
  </main>
</div>
<script>
var papers=[],sel=null;
function scoreColor(s){return s>=4?'#22c55e':s>=3?'#f59e0b':s>=2?'#f97316':'#ef4444';}
function verdictCls(v){if(!v)return'';var l=v.toLowerCase();if(l==='accept')return'va';if(l.includes('minor'))return'vm';if(l.includes('major'))return'vmj';return'vr';}
function fmtDate(ts){if(!ts)return'';return new Date(ts*1000).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function basename(p){return(p||'').split(/[\\/]/).pop();}

async function loadPapers(){
  try{
    var r=await fetch('/api/papers');papers=await r.json();
    renderList(papers);
    document.getElementById('ref').textContent='Refreshed '+new Date().toLocaleTimeString();
  }catch(e){
    document.getElementById('plist').innerHTML='<p style="color:#ef4444;padding:14px;font-size:.76rem">Failed to load papers</p>';
  }
}

function renderList(list){
  var el=document.getElementById('plist');
  if(!list.length){el.innerHTML='<p style="color:#7a86a1;padding:14px;font-size:.76rem;text-align:center">No papers yet.</p>';return;}
  el.innerHTML=list.map(function(p){
    var n=basename(p.file_path);
    var ac=p.file_path===sel?' active':'';
    return '<div class="pitem'+ac+'" onclick="pick('+JSON.stringify(p.file_path)+')" title="'+esc(p.file_path)+'">'
      +'<div class="pname">'+esc(n)+'</div>'
      +'<div class="pdate">'+fmtDate(p.created_at)+'</div></div>';
  }).join('');
}

function filter(){var q=document.getElementById('srch').value.toLowerCase();renderList(papers.filter(function(p){return p.file_path.toLowerCase().includes(q);}));}

async function pick(path){
  sel=path;renderList(papers);
  var m=document.getElementById('main');
  m.innerHTML='<div style="text-align:center;padding:40px"><span class="sp" style="width:30px;height:30px;border-width:3px"></span></div>';
  try{
    var ep=encodeURIComponent(path);
    var res=await Promise.all([fetch('/api/deliberation?path='+ep),fetch('/api/reviews?path='+ep)]);
    var d=await res[0].json(),rv=await res[1].json();
    renderDetail(path,d,rv);
  }catch(e){m.innerHTML='<p style="color:#ef4444;padding:22px">Failed to load data.</p>';}
}

function renderDetail(path,d,rv){
  var m=document.getElementById('main');
  var report=d.report_json?d.report_json:{};
  var verdict=d.verdict||'Unknown',score=parseFloat(d.aggregate_score)||0;
  var fname=esc(basename(path));
  var col=scoreColor(score);
  var ir=report.individual_reviews||[];
  var scards=ir.map(function(r){
    var pct=Math.max(0,Math.min(100,((r.score-1)/4*100))).toFixed(0);
    var c=scoreColor(r.score);
    return '<div class="scard"><div class="scn">'+esc(r.criterion)+'</div>'
      +'<div class="scv" style="color:'+c+'">'+r.score.toFixed(1)
      +'<span style="font-size:.66rem;color:#7a86a1;font-weight:400">/5.0</span></div>'
      +'<div class="sbbg"><div class="sbf" style="width:'+pct+'%;background:'+c+'"></div></div>'
      +'<div class="scag">'+esc(r.agent)+'</div></div>';
  }).join('');
  var br=rv.rounds||{};
  var rl={'1':'Round 1 - Initial Assessment','2':'Round 2 - Peer Debate','3':'Round 3 - Final Positions'};
  var timeline=Object.keys(br).sort(function(a,b){return a-b;}).map(function(rn){
    var cards=br[rn].map(function(r){
      var rs=parseFloat(r.score);
      return '<div class="rc"><div class="rct"><div><div class="rag">'+esc(r.agent_name)+'</div>'
        +'<div class="rcrn">'+esc(r.criterion)+'</div></div>'
        +'<span class="rpill" style="color:'+scoreColor(rs)+'">'+rs.toFixed(1)+'</span></div>'
        +'<div class="rjust">'+(esc(r.justification)||'&mdash;')+'</div></div>';
    }).join('');
    return '<div class="rnd"><div class="rlbl">'+(rl[rn]||'Round '+rn)+'</div>'
      +'<div class="rcards">'+cards+'</div></div>';
  }).join('');
  m.innerHTML=
    '<div class="vc">'
      +'<div class="sring" style="border-color:'+col+'">'
        +'<span class="sval" style="color:'+col+'">'+score.toFixed(2)+'</span>'
        +'<span class="smax">/5.0</span>'
      +'</div>'
      +'<div class="vinfo">'
        +'<div style="font-size:.72rem;color:#7a86a1;margin-bottom:3px">'+fname+'</div>'
        +'<h2>'+esc(verdict)+'</h2>'
        +'<span class="vbadge '+verdictCls(verdict)+'">'+esc(verdict)+'</span>'
      +'</div>'
      +'</div>'
    +'<div class="stitle">Score Breakdown by Criterion</div>'
    +'<div class="sgrid">'+(scards||'<p style="color:#7a86a1;font-size:.8rem">No scores available.</p>')+'</div>'
    +'<div class="stitle">Review Chain</div>'
    +'<div>'+(timeline||'<p style="color:#7a86a1;font-size:.8rem">No reviews found.</p>')+'</div>';
}

async function startDeliberation() {
  var path = document.getElementById('delib-path').value.trim();
  if(!path) return alert('Please enter a paper path.');
  try {
    var r = await fetch('/api/deliberate?path=' + encodeURIComponent(path), {method: 'POST'});
    var res = await r.json();
    if(res.error) alert('Error: ' + res.error);
    else pollHITL();
  } catch(e) { alert('Failed to start deliberation.'); }
}

async function approveRound() {
  await fetch('/api/approve_round', {method: 'POST'});
  pollHITL();
}

async function abortRound() {
  await fetch('/api/abort_round', {method: 'POST'});
  pollHITL();
}

async function pollHITL() {
  try {
    var r = await fetch('/api/active_deliberation');
    var d = await r.json();
    var area = document.getElementById('hitl-panel-area');

    if (d.status === "idle" || d.status === "completed" || d.status === "aborted" || d.status === "failed") {
      if(d.status === "completed") {
        area.innerHTML = '<div class="hitl-panel" style="border-color:var(--acc)">'
          +'<div class="hitl-header"><span class="hitl-title">Active Deliberation</span>'
          +'<span class="hitl-status" style="background:var(--acc-bg);color:var(--acc)">Deliberation Completed</span></div>'
          +'<p style="font-size:0.8rem">Consensus reached. Refreshing manuscript listings.</p></div>';
        loadPapers();
        setTimeout(function(){ area.innerHTML = ""; }, 4000);
      } else if(d.status === "failed") {
        area.innerHTML = '<div class="hitl-panel" style="border-color:var(--rej)">'
          +'<div class="hitl-header"><span class="hitl-title">Active Deliberation</span>'
          +'<span class="hitl-status" style="background:var(--rej-bg);color:var(--rej)">Failed</span></div>'
          +'<p style="font-size:0.8rem;color:var(--rej)">Error: '+esc(d.error_message)+'</p></div>';
      } else {
        area.innerHTML = "";
      }
      return;
    }

    // Status is either "deliberating" or "waiting_for_approval"
    var statusText = d.status === "deliberating" ? "Engine Deliberating..." : "Human-in-the-Loop Review Required";
    var statusColor = d.status === "deliberating" ? "var(--min)" : "var(--accent)";
    var statusBg = d.status === "deliberating" ? "var(--min-bg)" : "rgba(124,111,247,0.15)";

    var reviewsHtml = "";
    if (d.reviews && d.reviews.length) {
      reviewsHtml = '<div class="hitl-review-cards">' + d.reviews.map(function(rev){
        return '<div class="hitl-card">'
          +'<div class="hitl-card-header"><span>'+esc(rev.agent_name)+'</span>'
          +'<span style="color:'+scoreColor(rev.score)+'">'+rev.score.toFixed(1)+'</span></div>'
          +'<div class="hitl-card-body">'+esc(rev.justification)+'</div></div>';
      }).join('') + '</div>';
    }

    var controls = "";
    if (d.status === "waiting_for_approval") {
      controls = '<div class="hitl-controls">'
        +'<button class="btn btn-primary" onclick="approveRound()">Approve Round '+d.round_num+' and Continue</button>'
        +'<button class="btn btn-danger" onclick="abortRound()">Abort Deliberation</button></div>';
    } else {
      controls = '<div style="margin-top:14px;font-size:0.75rem;color:var(--muted)"><span class="sp" style="width:12px;height:12px;border-width:2px;vertical-align:middle;margin-right:6px"></span>Agent deliberation in progress...</div>';
    }

    area.innerHTML = '<div class="hitl-panel" style="border-color:'+statusColor+'">'
      +'<div class="hitl-header"><span class="hitl-title">Active Deliberation: Round '+d.round_num+'</span>'
      +'<span class="hitl-status" style="background:'+statusBg+';color:'+statusColor+'">'+statusText+'</span></div>'
      +'<p style="font-size:0.78rem;color:var(--muted)">Manuscript: '+esc(d.paper_path)+'</p>'
      +reviewsHtml
      +controls
      +'</div>';

    // Continue polling while active
    setTimeout(pollHITL, 1000);
  } catch(e) {}
}

loadPapers();
setInterval(loadPapers, 30000);
pollHITL();
</script>
</body>
</html>"""

# ──────────────────────────────────────────────
# API Handlers
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    return DASHBOARD_HTML

@app.get("/api/papers")
async def list_papers():
    return db.list_all_papers()

@app.get("/api/paper")
async def get_paper_detail(path: str):
    p = db.load_paper(unquote(path))
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {
        "file_path": p["file_path"],
        "abstract":  p["abstract"][:600],
        "methods":   p["methods"][:600],
        "results":   p["results"][:600],
        "claims":    p["claims"][:600],
    }

@app.get("/api/reviews")
async def get_reviews(path: str):
    pid = db.get_paper_id_by_path(unquote(path))
    if not pid:
        raise HTTPException(status_code=404, detail="Paper not found")
    rows = db.get_paper_reviews(pid)

    by_round = {}
    for r in rows:
        review_dict = dict(r)
        if isinstance(review_dict.get("evidence"), str):
            try:
                review_dict["evidence"] = json.loads(review_dict["evidence"])
            except Exception:
                review_dict["evidence"] = []
        by_round.setdefault(r["round_num"], []).append(review_dict)
    return {"rounds": by_round}

@app.get("/api/deliberation")
async def get_deliberation(path: str):
    pid = db.get_paper_id_by_path(unquote(path))
    if not pid:
        raise HTTPException(status_code=404, detail="Paper not found")
    row = db.get_latest_deliberation(pid)
    if not row:
        raise HTTPException(status_code=404, detail="No deliberation found")

    delib_dict = dict(row)
    if isinstance(delib_dict.get("report_json"), str):
        try:
            delib_dict["report_json"] = json.loads(delib_dict["report_json"])
        except Exception:
            pass
    return delib_dict

@app.get("/api/settings")
async def get_settings():
    c = dict(council.CFG)
    if "openai_key" in c:
        c["openai_key"] = "[REDACTED]" if c["openai_key"] else ""
    return c

@app.post("/api/settings")
async def post_settings(request: Request):
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Malformed JSON: {exc}")

    new_weights = data.get("weights")
    if not new_weights:
        raise HTTPException(status_code=400, detail="Missing 'weights' key in request payload.")

    req_keys = set(council.WEIGHTS.keys())
    got_keys = set(new_weights.keys())
    if req_keys != got_keys:
        raise HTTPException(status_code=400, detail=f"Invalid weights criteria keys. Expected: {list(req_keys)}")

    try:
        parsed_weights = {k: float(v) for k, v in new_weights.items()}
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="All weight values must be numbers.")

    w_sum = sum(parsed_weights.values())
    if not (0.999 <= w_sum <= 1.001):
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0 (got {w_sum:.4f})")

    # Persist config file
    cfg_path = Path("council_config.json")
    try:
        persisted = {}
        if cfg_path.exists():
            persisted = json.loads(cfg_path.read_text(encoding="utf-8"))
        persisted["weights"] = parsed_weights
        cfg_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

        # Reload configuration
        council.CFG["weights"] = parsed_weights
        council.WEIGHTS = parsed_weights
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not write configuration file: {exc}")

    c = dict(council.CFG)
    if "openai_key" in c:
        c["openai_key"] = "[REDACTED]" if c["openai_key"] else ""
    return c

@app.get("/api/audit")
async def get_audit():
    return council.run_monthly_audit()

@app.get("/api/active_deliberation")
async def get_active_deliberation():
    return active_deliberation

@app.post("/api/deliberate")
async def trigger_deliberation(path: str, background_tasks: BackgroundTasks):
    global active_deliberation
    decoded_path = unquote(path)
    if active_deliberation["status"] in ("deliberating", "waiting_for_approval"):
        raise HTTPException(status_code=400, detail="Another deliberation is already in progress.")

    if not Path(decoded_path).exists():
        raise HTTPException(status_code=404, detail=f"Manuscript file not found: {decoded_path}")

    # Start task in background worker thread
    background_tasks.add_task(background_deliberation_task, decoded_path)
    return {"status": "started", "paper_path": decoded_path}

@app.post("/api/approve_round")
async def approve_round():
    global active_deliberation
    if active_deliberation["status"] != "waiting_for_approval":
        raise HTTPException(status_code=400, detail="No deliberation round is waiting for approval.")
    approval_event.set()
    return {"status": "approved"}

@app.post("/api/abort_round")
async def abort_round():
    global active_deliberation
    if active_deliberation["status"] not in ("deliberating", "waiting_for_approval"):
        raise HTTPException(status_code=400, detail="No active deliberation to abort.")
    abort_flag.set()
    approval_event.set()  # Unblock thread to let it abort
    return {"status": "aborting"}

# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

def start_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    logger.info(f"Starting async FastAPI Microservice on http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
