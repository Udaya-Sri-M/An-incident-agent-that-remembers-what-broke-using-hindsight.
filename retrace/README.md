# RETRACE — Incident Memory Agent

RETRACE is a small hackathon-ready demo built around Hindsight's **Retain → Recall** memory loop and Groq for grounded response generation.

The project follows the supplied hackathon brief: Hindsight is mandatory; the brief says teams may use any LLM and specifically recommends Groq, including `openai/gpt-oss-120b` and `qwen/qwen3-32b`. It also encourages showing retain/recall live in the demo.

## What the demo does

1. **Load / refresh demo memory** — stores five realistic synthetic production incidents in a Hindsight memory bank.
2. **Run cold** — asks Groq for a generic troubleshooting checklist with no historical memory.
3. **Run with Hindsight** — recalls similar incidents from Hindsight and gives the retrieved evidence to Groq.
4. **Evidence panel** — shows the actual Hindsight memories used for the response.
5. **Incident cards** — click one to populate a new incident quickly during the demo.

## Stack

- Python
- FastAPI
- Hindsight Cloud (`hindsight-client`)
- Groq Python SDK
- Plain HTML/CSS/JavaScript

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure keys

Copy `.env.example` to `.env` and set:

```text
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
```

The hackathon brief provides Hindsight Cloud as the quickest route to an instance. Hindsight's current Python client is installed with `pip install hindsight-client` and supports `retain`, `recall`, and `reflect`.

### 3. Run

```powershell
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## 60–90 second demo

1. Click **Load / refresh demo memory**.
2. Paste/run this cold:

```text
Service: checkout-api
Symptoms: POST /checkout returns 502 after a traffic spike. Database connections are at the maximum and retries are increasing.
```

3. Click **Run cold**. Show the generic checklist.
4. Click **Run with Hindsight**.
5. Point to the evidence cards: the agent recalled the earlier checkout incidents and their fixes.
6. Point to the response: the recommendation is grounded in those memories.
7. Say: **“The model didn't learn a new fact from a prompt. Hindsight remembered what our team had already learned.”**

## Important honesty point

RETRACE should say that a historical match is evidence, not proof of causation. The LLM is instructed not to invent a root cause and to distinguish historical evidence from a fresh diagnosis.

## Optional local Hindsight

If you want to run Hindsight locally instead of Cloud, point `HINDSIGHT_API_URL` at your local Hindsight API. The official Hindsight quickstart documents Docker on port 8888 and the Python client connection.
