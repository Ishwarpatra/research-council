import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import council
import db
from config import settings

logger = logging.getLogger("rcc.api")

# Dynamic global human-in-the-loop tracking
active_deliberation = {
    "status": "idle",              # idle | deliberating | waiting_for_approval | completed | aborted | failed
    "round_num": 0,
    "paper_path": "",
    "reviews": [],
    "error_message": "",
}
approval_event = asyncio.Event()
abort_flag = asyncio.Event()

# Main ASGI loop — set in lifespan; HITL runs on a worker thread and must bridge here
_main_loop: asyncio.AbstractEventLoop | None = None

# Active WebSocket connections list
connected_clients = set()
global_seq_id = 0

async def broadcast_ws(payload: dict, app_db):
    """Log to database and broadcast to all connected WebSocket clients."""
    global global_seq_id
    global_seq_id += 1
    payload["seq_id"] = global_seq_id
    payload_str = json.dumps(payload)

    # 1. Non-blocking persistent database logging
    try:
        # Check if active paper path matches a paper in database
        if active_deliberation["paper_path"]:
            pid = db.get_paper_id_by_path(active_deliberation["paper_path"])
            if pid:
                await db.log_frame(app_db, pid, global_seq_id, payload_str)
    except Exception as e:
        logger.error(f"Failed to log frame: {e}")

    # 2. Broadcast to clients
    for ws in list(connected_clients):
        try:
            await ws.send_text(payload_str)
        except Exception:
            connected_clients.discard(ws)

def hitl_callback(round_num: int, reviews: list) -> bool:
    """Block the deliberation worker thread until the ASGI loop completes HITL approval."""
    if _main_loop is None or not _main_loop.is_running():
        raise RuntimeError(
            "HITL callback requires a running API event loop. "
            "Start the server with `python council.py --api`."
        )
    future = asyncio.run_coroutine_threadsafe(
        async_hitl_callback(round_num, reviews),
        _main_loop,
    )
    try:
        return future.result()
    except Exception:
        future.cancel()
        raise

async def async_hitl_callback(round_num: int, reviews: list) -> bool:
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

    logger.info(f"Pause: Round {round_num} waiting for Human-in-the-Loop approval.")

    # Broadcast state change to websockets
    app_db = app.state.db if hasattr(app, "state") and hasattr(app.state, "db") else None
    await broadcast_ws({
        "type": "approval_required",
        "round_num": round_num,
        "reviews": active_deliberation["reviews"]
    }, app_db)

    approval_event.clear()
    await approval_event.wait()

    if abort_flag.is_set():
        logger.warning(f"Deliberation aborted during Round {round_num}.")
        return False

    logger.info(f"Round {round_num} approved. Resuming...")
    active_deliberation["status"] = "deliberating"
    active_deliberation["reviews"] = []

    await broadcast_ws({
        "type": "round_approved",
        "round_num": round_num
    }, app_db)

    return True

async def background_deliberation_task(paper_path: str, app_db):
    global active_deliberation
    abort_flag.clear()
    approval_event.clear()

    active_deliberation["status"] = "deliberating"
    active_deliberation["paper_path"] = paper_path
    active_deliberation["round_num"] = 1
    active_deliberation["reviews"] = []
    active_deliberation["error_message"] = ""

    await broadcast_ws({
        "type": "deliberation_started",
        "paper_path": paper_path
    }, app_db)

    try:
        if not Path(paper_path).exists():
            raise FileNotFoundError(f"Manuscript file not found: {paper_path}")

        loop = asyncio.get_running_loop()
        # Run synchronous engine deliberation inside a separate thread pool executor
        report = await loop.run_in_executor(
            None,
            lambda: council.run_council(paper_path, hitl_hook=hitl_callback)
        )
        active_deliberation["status"] = "completed"
        logger.info(f"Deliberation completed for {paper_path}.")
        if app_db:
            try:
                pid = db.get_paper_id_by_path(paper_path)
                if pid:
                    await db.cleanup_websocket_frames(app_db, pid)
            except Exception as clean_err:
                logger.warning(f"Frame cleanup issue: {clean_err}")
        await broadcast_ws({
            "type": "deliberation_completed",
            "report": report
        }, app_db)
    except Exception as exc:
        if app_db and active_deliberation.get("paper_path"):
            try:
                pid = db.get_paper_id_by_path(active_deliberation["paper_path"])
                if pid:
                    await db.cleanup_websocket_frames(app_db, pid)
            except Exception:
                pass
        if abort_flag.is_set():
            active_deliberation["status"] = "aborted"
            logger.info("Deliberation cleanup completed after abort.")
            await broadcast_ws({
                "type": "deliberation_aborted"
            }, app_db)
        else:
            active_deliberation["status"] = "failed"
            active_deliberation["error_message"] = f"{type(exc).__name__}: {exc}"
            logger.error(f"Deliberation failed: {exc}", exc_info=True)
            await broadcast_ws({
                "type": "deliberation_failed",
                "error": str(exc)
            }, app_db)


# ──────────────────────────────────────────────
# Lifespan Context Manager
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    # --- STARTUP PHASE ---
    _main_loop = asyncio.get_running_loop()
    logger.info("Initializing persistent aiosqlite database connection...")
    try:
        # Initialize schema and get persistent database handle
        app.state.db = await db.init_db_async(settings.db_path)
        logger.info("Database connection successfully mounted to app.state.db.")

        # Register circuit breaker listener to broadcast to WebSocket clients
        async def on_circuit_state_change(new_state: str, message: str):
            logger.info(f"Broadcasting circuit breaker state change to WS: {new_state}")
            await broadcast_ws({
                "type": "system_alert",
                "alert_type": "circuit_breaker",
                "state": new_state,
                "message": message
            }, app.state.db if hasattr(app, "state") and hasattr(app.state, "db") else None)

        council.primary_breaker.register_callback(on_circuit_state_change)
        logger.info("Registered circuit breaker listener.")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        _main_loop = None
        raise

    try:
        yield  # Application runs while suspended here
    finally:
        # --- SHUTDOWN PHASE ---
        logger.info("Closing persistent database connection...")
        _main_loop = None
        if hasattr(app.state, "db") and app.state.db is not None:
            try:
                await app.state.db.close()
                logger.info("Database connection safely closed.")
            except Exception as close_err:
                logger.error(f"Error closing database connection: {close_err}")

app = FastAPI(
    title="Research Consensus Council API",
    description="FastAPI service for multi-agent academic paper consensus and deliberation.",
    version="1.0.0",
    lifespan=lifespan
)

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# ──────────────────────────────────────────────
# Web Dashboard HTML
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
    <div id="hitl-panel-area"></div>
    <div class="form-panel">
      <div class="form-row">
        <input class="form-input" id="delib-path" type="text" placeholder="Enter path to paper (e.g. tests/fixtures/test_paper.txt)">
        <button class="btn btn-primary" onclick="startDeliberation()">Start Deliberation</button>
      </div>
    </div>
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
# REST Endpoints
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
    def _clip(value, n=600):
        return (value or "")[:n]
    return {
        "file_path": p["file_path"],
        "abstract":  _clip(p.get("abstract")),
        "methods":   _clip(p.get("methods")),
        "results":   _clip(p.get("results")),
        "claims":    _clip(p.get("claims")),
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
        except json.JSONDecodeError:
            logger.warning("Corrupt report_json for paper_id=%s; returning raw string", pid)
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

    cfg_path = Path("council_config.json")
    try:
        persisted = {}
        if cfg_path.exists():
            persisted = json.loads(cfg_path.read_text(encoding="utf-8"))
        persisted["weights"] = parsed_weights
        cfg_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

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
    """Legacy monthly drift plus full audit skill tree."""
    from skills import run_skill_tree
    return {
        "monthly": council.run_monthly_audit(),
        "skill_tree": run_skill_tree("audit", context={"reviews": []}),
    }

@app.get("/api/active_deliberation")
async def get_active_deliberation():
    return active_deliberation

_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
_UPLOAD_SUFFIXES = {".pdf", ".txt", ".md"}


@app.post("/api/upload")
async def upload_manuscript(file: UploadFile = File(...)):
    """Persist an uploaded manuscript under uploads/ and return a path for /api/deliberate."""
    name = Path(file.filename or "").name
    if not name:
        raise HTTPException(status_code=400, detail="Filename is required.")
    suffix = Path(name).suffix.lower()
    if suffix not in _UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix or '(none)'}'. Allowed: .pdf, .txt, .md",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > _UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 25 MB limit.")

    uploads = Path(__file__).resolve().parent / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    # Avoid collisions: keep basename, prefix with unix timestamp
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    dest = uploads / f"{int(time.time())}_{safe}"
    dest.write_bytes(raw)
    return {"paper_path": str(dest), "filename": name, "bytes": len(raw)}


@app.post("/api/deliberate")
async def trigger_deliberation(path: str, background_tasks: BackgroundTasks):
    global active_deliberation
    decoded_path = unquote(path)
    p = Path(decoded_path)
    if active_deliberation["status"] in ("deliberating", "waiting_for_approval"):
        raise HTTPException(status_code=400, detail="Another deliberation is already in progress.")

    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Manuscript file not found: {decoded_path}")

    if p.is_dir():
        kids = [c.name for c in p.iterdir() if c.is_file() and c.suffix.lower() in {".pdf", ".txt", ".md"}][:8]
        hint = f" Found manuscripts: {', '.join(kids)}." if kids else ""
        raise HTTPException(
            status_code=400,
            detail=(
                f"Path is a folder, not a manuscript file: {decoded_path}."
                f" Point Research at a single .pdf or .txt file.{hint}"
            ),
        )

    if not p.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a readable manuscript file: {decoded_path}")

    app_db = app.state.db if hasattr(app, "state") and hasattr(app.state, "db") else None
    background_tasks.add_task(background_deliberation_task, decoded_path, app_db)
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
    approval_event.set()
    return {"status": "aborting"}


@app.post("/api/appeal")
async def submit_appeal(path: str, rebuttal: str):
    decoded_path = unquote(path)
    if not rebuttal or not str(rebuttal).strip():
        raise HTTPException(status_code=400, detail="Rebuttal text is required.")
    paper_id = db.get_paper_id_by_path(decoded_path)
    if not paper_id:
        raise HTTPException(status_code=404, detail=f"Paper not found: {decoded_path}")

    loop = asyncio.get_running_loop()
    try:
        report = await loop.run_in_executor(
            None,
            lambda: council.submit_appeal(decoded_path, rebuttal.strip())
        )
    except Exception as exc:
        logger.exception("Appeal processing failed for %s", decoded_path)
        raise HTTPException(status_code=500, detail=f"Appeal processing failed: {exc}")

    if isinstance(report, dict) and report.get("error"):
        err = report["error"]
        if "Rebuttal" in err:
            status = 400
        elif "failed" in err.lower():
            status = 500
        else:
            status = 404
        raise HTTPException(status_code=status, detail=err)
    return report

@app.get("/api/appeals")
async def get_appeals(path: str):
    decoded_path = unquote(path)
    paper_id = db.get_paper_id_by_path(decoded_path)
    if not paper_id:
        raise HTTPException(status_code=404, detail=f"Paper not found: {decoded_path}")
    return db.get_appeals_by_paper(paper_id)

@app.get("/api/prior_art")
async def get_prior_art(query: str):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query text is required.")
    try:
        from skills.prior_art_validator import PriorArtValidator
        validator = PriorArtValidator()
        return validator.query_prior_art(query.strip())
    except Exception as exc:
        logger.exception("Prior art query failed")
        raise HTTPException(status_code=500, detail=f"Prior art query failed: {exc}")


@app.post("/api/skills/review")
async def skills_review(path: str):
    """Run the pre-council review skill tree on a manuscript path."""
    decoded_path = unquote(path)
    if not Path(decoded_path).exists():
        raise HTTPException(status_code=404, detail=f"Manuscript file not found: {decoded_path}")
    loop = asyncio.get_running_loop()
    try:
        def _run():
            paper = council.extract_content(decoded_path)
            from skills import run_skill_tree
            return run_skill_tree("review", paper=paper)

        return await loop.run_in_executor(None, _run)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Review skill tree failed")
        raise HTTPException(status_code=500, detail=f"Review skill tree failed: {exc}")


@app.post("/api/skills/claim_grounding")
async def skills_claim_grounding(path: str, claim_text: str | None = None):
    """Jenni-style claim grounding for a manuscript (agent-kit tool)."""
    decoded_path = unquote(path)
    if not Path(decoded_path).exists():
        raise HTTPException(status_code=404, detail=f"Manuscript file not found: {decoded_path}")
    loop = asyncio.get_running_loop()
    try:
        def _run():
            paper = council.extract_content(decoded_path)
            from skills.agent_tools import dispatch_tool
            args = {}
            if claim_text and claim_text.strip():
                args["claim_text"] = claim_text.strip()
            return dispatch_tool("query_claim_grounding", args, paper=paper)

        return await loop.run_in_executor(None, _run)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Claim grounding failed")
        raise HTTPException(status_code=500, detail=f"Claim grounding failed: {exc}")


@app.get("/api/skills/tools")
async def list_agent_tools():
    """List registered agent-kit tool schemas (OpenAI function format)."""
    from skills.agent_tools import TOOL_SCHEMAS, list_tool_names
    return {"tools": list_tool_names(), "schemas": TOOL_SCHEMAS}


@app.get("/api/skills/audit")
async def skills_audit(path: str | None = None):
    """Run audit skill tree; optional path loads that paper's reviews for consistency checks."""
    reviews = []
    paper = None
    query_text = ""
    if path:
        decoded = unquote(path)
        pid = db.get_paper_id_by_path(decoded)
        if not pid:
            raise HTTPException(status_code=404, detail=f"Paper not found: {decoded}")
        reviews = db.get_paper_reviews(pid)
        loaded = db.load_paper(decoded)
        if loaded:
            query_text = loaded.get("claims") or loaded.get("abstract") or ""
            paper = council.PaperContent(
                file_path=loaded.get("file_path", decoded),
                content_hash=loaded.get("content_hash", ""),
                abstract=loaded.get("abstract") or "",
                methods=loaded.get("methods") or "",
                results=loaded.get("results") or "",
                claims=loaded.get("claims") or "",
                full_text=loaded.get("full_text") or "",
            )
    try:
        from skills import run_skill_tree
        tree = run_skill_tree(
            "audit",
            paper=paper,
            context={"reviews": reviews, "query_text": query_text},
        )
        return {"monthly": council.run_monthly_audit(), "skill_tree": tree}
    except Exception as exc:
        logger.exception("Audit skill tree failed")
        raise HTTPException(status_code=500, detail=f"Audit skill tree failed: {exc}")


# ──────────────────────────────────────────────
# Active WebSockets & Delta Replay Routes
# ──────────────────────────────────────────────

@app.websocket("/api/ws/{paper_id:path}")
async def websocket_stream(websocket: WebSocket, paper_id: str):
    await websocket.accept()
    connected_clients.add(websocket)
    decoded_pid = unquote(paper_id)
    logger.info(f"WebSocket connected for paper_id/path: {decoded_pid}")
    try:
        while True:
            # Maintain active connection listening for optional client ping messages
            await websocket.receive_text()
            # Ignore client pings, only check connection validity
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket disconnected for paper_id/path: {decoded_pid}")
    except Exception as e:
        connected_clients.discard(websocket)
        logger.error(f"WebSocket error: {e}")

@app.get("/api/deliberation/{paper_id:path}/replay")
async def replay_websocket_frames(paper_id: str, since_seq: int = 0):
    """Replay sequence tracked frames for client-side offline hydration."""
    decoded_id = unquote(paper_id)
    numeric_id = None
    if decoded_id.isdigit():
        numeric_id = int(decoded_id)
    else:
        numeric_id = db.get_paper_id_by_path(decoded_id)

    if not numeric_id:
        return []

    try:
        frames = await db.get_websocket_frames(settings.db_path, numeric_id, since_seq)
        return frames
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay database retrieval failed: {e}")

@app.get("/api/health/circuit")
async def get_circuit_health():
    """Retrieve active LLM provider circuit status."""
    state = await council.primary_breaker.get_state()
    return {
        "status": state,
        "primary_failures": council.primary_breaker.failure_count,
        "llm_provider": settings.llm_provider,
        "fallback_provider": settings.fallback_provider
    }


# Mount static files to serve the compiled frontend if it exists
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

def start_server(host: str = "127.0.0.1", port: int = 8080):
    import socket
    import urllib.request
    import uvicorn

    # If a healthy RCC already owns the port, skip re-bind (avoids WinError 10048 / exit 3).
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        in_use = s.connect_ex((host, port)) == 0
        s.close()
        if in_use:
            with urllib.request.urlopen(f"http://{host}:{port}/api/skills/tools", timeout=2) as r:
                body = r.read(180).decode("utf-8", errors="replace")
            if "query_claim_grounding" in body:
                msg = f"RCC API already running on http://{host}:{port}/ — skipping bind."
                logger.info(msg)
                print(msg)
                return
            raise OSError(10048, f"Port {port} is in use by a non-RCC process on {host}")
    except OSError:
        raise
    except Exception:
        pass

    logger.info(f"Starting async FastAPI Microservice on http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
