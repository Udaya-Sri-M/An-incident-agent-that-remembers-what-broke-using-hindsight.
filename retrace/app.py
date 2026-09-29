import json
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from groq import Groq
from hindsight_client import Hindsight

load_dotenv()

BASE = Path(__file__).resolve().parent
INCIDENTS_PATH = BASE / "data" / "incidents.json"
with INCIDENTS_PATH.open("r", encoding="utf-8") as f:
    INCIDENTS = json.load(f)

APP_NAME = os.getenv("APP_NAME", "RETRACE")
HINDSIGHT_URL = os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_KEY = os.getenv("HINDSIGHT_API_KEY", "")
DEMO_BANK = os.getenv("HINDSIGHT_BANK_ID", "retrace-demo")
COLD_BANK = os.getenv("HINDSIGHT_COLD_BANK_ID", "retrace-cold")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

hindsight = Hindsight(base_url=HINDSIGHT_URL, api_key=HINDSIGHT_KEY or None)
groq = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None


def ensure_bank(bank_id: str):
    try:
        hindsight.create_bank(bank_id=bank_id, name=f"RETRACE {bank_id}")
    except Exception:
        # Existing banks are fine. Hindsight's API will report useful errors for real failures.
        pass


def incident_text(i: dict) -> str:
    return (
        f"Incident {i['id']} on {i['date']}. Service: {i['service']}. Severity: {i['severity']}. "
        f"Symptoms: {i['symptoms']} Root cause: {i['root_cause']} Fix: {i['fix']} "
        f"Resolution time: {i['resolution_minutes']} minutes. Lesson: {i['lesson']}"
    )


def memory_to_dict(m):
    return {
        "type": getattr(m, "type", "memory"),
        "text": getattr(m, "text", str(m)),
        "id": getattr(m, "id", None),
    }


def recall_incidents(query: str, bank_id: str):
    result = hindsight.recall(
        bank_id=bank_id,
        query=(
            "Find past production incidents that are relevant to this new incident. "
            "Prioritize same service, similar symptoms/error signatures, root causes, fixes, and lessons.\n\n"
            + query
        ),
        max_tokens=5000,
        budget="high",
        include_chunks=True,
    )
    return [memory_to_dict(x) for x in result.results]


def generic_answer(incident: str) -> str:
    if not groq:
        return "No GROQ_API_KEY configured. Add it to .env to enable the cold-run troubleshooting response."
    prompt = f"""You are a production incident assistant. The user has a new incident but there is NO historical memory available.
Give a short generic troubleshooting checklist. Do not invent a root cause. Make clear that this is a cold start.

New incident:
{incident}"""
    r = groq.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "Be concise, operational, and honest about uncertainty."},
            {"role": "user", "content": prompt},
        ],
    )
    return r.choices[0].message.content


def grounded_answer(incident: str, memories: list[dict]) -> str:
    if not groq:
        return "No GROQ_API_KEY configured. The Hindsight matches are shown below; add the key for the grounded recommendation."
    evidence = "\n\n".join(
        f"Memory {idx+1} ({m['type']}): {m['text']}" for idx, m in enumerate(memories[:8])
    )
    prompt = f"""You are RETRACE, an incident-memory agent.
A new incident has arrived. Hindsight retrieved historical memories below.
Use ONLY those memories for historical claims. Do not invent a root cause or claim causation that the memories do not support.
If the evidence is only correlated, say so.
Return a concise answer with these headings:
1. Historical match
2. What happened before
3. Previous fix
4. Recommended next checks
5. Confidence

New incident:
{incident}

Hindsight evidence:
{evidence}
"""
    r = groq.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a grounded SRE assistant. Never fabricate historical evidence."},
            {"role": "user", "content": prompt},
        ],
    )
    return r.choices[0].message.content


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "incidents": INCIDENTS,
        "demo_bank": DEMO_BANK,
    })


@app.post("/api/seed")
def seed():
    ensure_bank(DEMO_BANK)
    retained = []
    for i in INCIDENTS:
        hindsight.retain(
            bank_id=DEMO_BANK,
            content=incident_text(i),
            context="RETRACE resolved production incident",
            timestamp=datetime.fromisoformat(i["date"] + "T12:00:00"),
            document_id=i["id"],
            metadata={"incident_id": i["id"], "service": i["service"], "severity": i["severity"]},
        )
        retained.append(i["id"])
    return {"ok": True, "bank": DEMO_BANK, "retained": retained}


@app.post("/api/analyze")
def analyze(payload: dict):
    incident = (payload.get("incident") or "").strip()
    mode = payload.get("mode", "memory")
    if not incident:
        return JSONResponse({"error": "Please enter an incident description."}, status_code=400)

    bank = DEMO_BANK if mode == "memory" else COLD_BANK
    ensure_bank(bank)

    if mode == "cold":
        return {
            "mode": "cold",
            "answer": generic_answer(incident),
            "matches": [],
            "message": "Cold run: no incident history was used."
        }

    memories = recall_incidents(incident, bank)
    answer = grounded_answer(incident, memories)
    return {
        "mode": "memory",
        "answer": answer,
        "matches": memories[:5],
        "message": f"Hindsight recalled {len(memories)} relevant memories."
    }


@app.post("/api/retain")
def retain_new(payload: dict):
    incident = payload.get("incident", {})
    required = ["id", "date", "service", "severity", "symptoms", "root_cause", "fix", "resolution_minutes", "lesson"]
    missing = [x for x in required if not incident.get(x)]
    if missing:
        return JSONResponse({"error": f"Missing fields: {', '.join(missing)}"}, status_code=400)
    ensure_bank(DEMO_BANK)
    hindsight.retain(
        bank_id=DEMO_BANK,
        content=incident_text(incident),
        context="RETRACE newly resolved production incident",
        timestamp=datetime.fromisoformat(incident["date"] + "T12:00:00"),
        document_id=incident["id"],
        metadata={"incident_id": incident["id"], "service": incident["service"], "severity": incident["severity"]},
    )
    return {"ok": True, "retained": incident["id"]}
