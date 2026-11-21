from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from pathlib import Path
import csv, io, sqlite3


from fastapi.responses import HTMLResponse

DASHBOARD = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comissão Pro</title><style>
*{box-sizing:border-box}body{margin:0;padding:16px;background:#f1f5f7;color:#172b36;font-family:Arial,sans-serif}
main{max-width:900px;margin:auto}header{background:#142b3b;color:white;padding:22px;border-radius:18px}
h1{margin:0 0 5px}.muted{color:#6a7a83;font-size:13px}.stats,.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
.card{background:white;border:1px solid #dfe7eb;border-radius:14px;padding:16px}.value{font-size:25px;font-weight:bold;margin-top:8px}
.cols{grid-template-columns:1fr 1fr}.tag{display:inline-block;background:#eaf2f4;padding:6px 10px;border-radius:20px;font-size:12px}
label{display:block;font-size:13px;margin:10px 0 5px;color:#566a75}input,select,button{width:100%;padding:12px;border-radius:9px;border:1px solid #cbd7dd;background:white;font-size:15px}
button{background:#087e65;color:white;border:0;font-weight:bold;margin-top:12px;cursor:pointer}
button.alt{background:#e8eff2;color:#233b48}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}td,th{text-align:left;padding:9px 5px;border-bottom:1px solid #e6ecef}
.notice{background:#fff8e8;border:1px solid #efdfb7;border-radius:12px;padding:12px;font-size:13px;line-height:1.4;margin-top:14px}
@media(max-width:620px){.stats{grid-template-columns:1fr}.cols{grid-template-columns:1fr}.row{grid-template-columns:1fr}}
</style></head><body><main>
<header><h1>COMISSÃO PRO</h1><div>Central de comissões • Mercado Livre + Shopee</div></header>
<section class="stats">
<div class="card"><div class="muted">Confirmadas</div><div class="value" id="confirmed">R$ 0,00</div></div>
<div class="card"><div class="muted">Pendentes</div><div class="value" id="pending">R$ 0,00</div></div>
<div class="card"><div class="muted">Registros</div><div class="value" id="records">0</div></div></section>
<section class="cols">
<div class="card"><h3>Mercado Livre</h3><span class="tag">Importação de relatório</span><p class="muted">Exporte o relatório de métricas/comissões no Portal do Afiliado e envie o CSV aqui.</p>
<form id="ml"><input type="file" id="mlfile" accept=".csv" required><button>Importar relatório ML</button></form></div>
<div class="card"><h3>Shopee</h3><span class="tag">Importação de relatório</span><p class="muted">Envie o CSV de conversões/comissões exportado do painel de afiliados. A conexão API fica para a etapa de credenciais oficiais.</p>
<form id="sh"><input type="file" id="shfile" accept=".csv" required><button>Importar relatório Shopee</button></form></div>
</section>
<section class="card"><h3>Registrar comissão</h3><form id="manual"><div class="row">
<div><label>Plataforma</label><select id="platform"><option>Mercado Livre</option><option>Shopee</option></select></div>
<div><label>Valor em R$</label><input id="amount" type="number" min=".01" step=".01" required></div></div>
<div class="row"><div><label>Referência do pedido</label><input id="reference"></div><div><label>Situação</label><select id="status"><option>Pendente</option><option>Confirmada</option><option>Cancelada</option></select></div></div>
<button>Salvar registro</button></form></section>
<section class="card" style="margin-top:14px"><h3>Histórico</h3><div style="overflow:auto"><table><thead><tr><th>Plataforma</th><th>Referência</th><th>Status</th><th>Valor</th></tr></thead><tbody id="history"></tbody></table></div></section>
<div class="notice"><b>Automação real:</b> o backend pode ficar em execução num servidor e processar relatórios enviados. A sincronização direta das contas ainda depende de credenciais e permissões oficiais; esta tela não simula vendas nem cria comissões.</div>
<p class="muted" id="message"></p>
</main><script>
const fmt=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(n);
async function refresh(){let s=await fetch('/summary').then(r=>r.json());document.getElementById('confirmed').textContent=fmt(s.confirmed);document.getElementById('pending').textContent=fmt(s.pending);document.getElementById('records').textContent=s.records;
let a=await fetch('/commissions').then(r=>r.json());let tb=document.getElementById('history');tb.innerHTML='';if(!a.length){tb.innerHTML='<tr><td colspan="4">Nenhum registro ainda.</td></tr>';return}a.forEach(x=>{let tr=document.createElement('tr');[x.platform,x.reference||'—',x.status,fmt(x.amount)].forEach(v=>{let td=document.createElement('td');td.textContent=v;tr.appendChild(td)});tb.appendChild(tr)})}
async function upload(formId,fileId,platform){document.getElementById('message').textContent='Importando...';let f=document.getElementById(fileId).files[0];let fd=new FormData();fd.append('file',f);let r=await fetch('/import/'+platform,{method:'POST',body:fd});let j=await r.json();document.getElementById('message').textContent=r.ok?`Importação concluída: ${j.new_records} novos registros.`:(j.detail||'Falha na importação');await refresh()}
document.getElementById('ml').onsubmit=e=>{e.preventDefault();upload('ml','mlfile','mercado-livre')};
document.getElementById('sh').onsubmit=e=>{e.preventDefault();upload('sh','shfile','shopee')};
document.getElementById('manual').onsubmit=async e=>{e.preventDefault();let item={platform:document.getElementById('platform').value,amount:Number(document.getElementById('amount').value),reference:document.getElementById('reference').value,status:document.getElementById('status').value};let r=await fetch('/commissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});document.getElementById('message').textContent=r.ok?'Registro salvo.':'Não foi possível salvar.';e.target.reset();refresh()};
refresh();
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD

DB = Path("data/comissao_pro.db")
app = FastAPI(title="Comissão Pro API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            reference TEXT,
            amount_cents INTEGER NOT NULL,
            status TEXT NOT NULL,
            event_date TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            UNIQUE(platform, reference, amount_cents, status, event_date)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            ran_at TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT
        )""")

@app.on_event("startup")
def startup():
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(record_scheduler_heartbeat, "interval", hours=6, id="heartbeat", replace_existing=True)
    scheduler.start()
    app.state.scheduler = scheduler

@app.on_event("shutdown")
def shutdown():
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler:
        scheduler.shutdown(wait=False)

def record_scheduler_heartbeat():
    # Confirma que o agendador está vivo; não consulta lojas sem integração oficial autorizada.
    with db() as con:
        now = datetime.now(timezone.utc).isoformat()
        for platform in ("Mercado Livre", "Shopee"):
            con.execute("INSERT INTO sync_runs(platform, ran_at, result, details) VALUES(?,?,?,?)",
                        (platform, now, "aguardando_conector", "Nenhuma API oficial foi configurada."))

class CommissionIn(BaseModel):
    platform: str
    reference: str = ""
    amount: float = Field(gt=0)
    status: str = "Pendente"
    event_date: str = ""

@app.get("/health")
def health():
    return {"status": "online", "service": "Comissão Pro API"}

@app.get("/summary")
def summary():
    with db() as con:
        rows = con.execute("SELECT status, SUM(amount_cents) total FROM commissions GROUP BY status").fetchall()
        counts = con.execute("SELECT COUNT(*) n FROM commissions").fetchone()["n"]
    totals = {r["status"]: (r["total"] or 0)/100 for r in rows}
    return {"confirmed": totals.get("Confirmada", 0), "pending": totals.get("Pendente", 0),
            "cancelled": totals.get("Cancelada", 0), "records": counts}

@app.get("/commissions")
def commissions():
    with db() as con:
        rows = con.execute("SELECT * FROM commissions ORDER BY id DESC").fetchall()
    return [dict(r, amount=r["amount_cents"]/100) for r in rows]

@app.post("/commissions")
def add_commission(item: CommissionIn):
    if item.platform not in ("Mercado Livre", "Shopee"):
        raise HTTPException(400, "Plataforma inválida")
    if item.status not in ("Pendente", "Confirmada", "Cancelada"):
        raise HTTPException(400, "Situação inválida")
    date = item.event_date or datetime.now(timezone.utc).date().isoformat()
    with db() as con:
        cur = con.execute("""INSERT OR IGNORE INTO commissions
            (platform, reference, amount_cents, status, event_date, imported_at)
            VALUES(?,?,?,?,?,?)""",
            (item.platform, item.reference, round(item.amount*100), item.status, date,
             datetime.now(timezone.utc).isoformat()))
        return {"saved": cur.rowcount == 1, "duplicate_ignored": cur.rowcount == 0}

@app.post("/import/{platform}")
async def import_csv(platform: str, file: UploadFile = File(...)):
    names = {"mercado-livre": "Mercado Livre", "shopee": "Shopee"}
    if platform not in names:
        raise HTTPException(400, "Use mercado-livre ou shopee")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\\t")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    except Exception:
        raise HTTPException(400, "CSV inválido. Salve como CSV UTF-8.")
    # Cabeçalhos esperados: referencia, valor, status, data
    headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
    required = ("valor", "status")
    if any(k not in headers for k in required):
        raise HTTPException(400, "O CSV precisa ter colunas valor e status; referencia e data são opcionais.")
    saved = 0
    for row in reader:
        try:
            amount = float(row[headers["valor"]].strip().replace("R$", "").replace(".", "").replace(",", "."))
            status = row[headers["status"]].strip().capitalize()
            if status not in ("Pendente", "Confirmada", "Cancelada") or amount <= 0:
                continue
            ref = row.get(headers.get("referencia", ""), "") if "referencia" in headers else ""
            date = row.get(headers.get("data", ""), "") if "data" in headers else ""
            date = date.strip() or datetime.now(timezone.utc).date().isoformat()
            with db() as con:
                cur = con.execute("""INSERT OR IGNORE INTO commissions
                    (platform, reference, amount_cents, status, event_date, imported_at)
                    VALUES(?,?,?,?,?,?)""",
                    (names[platform], ref.strip(), round(amount*100), status, date,
                     datetime.now(timezone.utc).isoformat()))
                saved += max(cur.rowcount, 0)
        except Exception:
            continue
    with db() as con:
        con.execute("INSERT INTO sync_runs(platform,ran_at,result,details) VALUES(?,?,?,?)",
                    (names[platform], datetime.now(timezone.utc).isoformat(), "importacao_csv",
                     f"{saved} registros novos"))
    return {"platform": names[platform], "new_records": saved}

@app.get("/sync-status")
def sync_status():
    with db() as con:
        rows = con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 20").fetchall()
    return [dict(r) for r in rows]
