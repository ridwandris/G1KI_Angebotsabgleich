# Angebotsabgleich – Löschanlagenkonzept

**LLM-basierte Kompatibilitätsprüfung**  
Automatically checks whether a component list (offer) fully satisfies all requirements
defined in a fire suppression system specification (Löschanlagenkonzept).

---

## Aufgabenstellung (Problemstellung)

> Sie sind ein Logistikunternehmen und planen den Neubau eines Gefahrstofflagers.
> Dafür haben Sie von einem Ingenieurbüro ein **Löschanlagenkonzept** erstellen
> lassen. Zur Umsetzung dieses Konzepts erhalten Sie von einem Dienstleister als
> Angebot eine **Komponentenliste**.  
> Erstellen Sie eine LLM-basierte Lösung, mit der automatisch die Kompatibilität
> der Komponentenliste mit dem Löschanlagenkonzept überprüft wird: Ist mit der
> Komponentenliste das Löschanlagenkonzept vollständig umsetzbar?

---

## Tech Stack

| Component         | Technology                                 |
|-------------------|--------------------------------------------|
| Language          | Python 3.11+                               |
| Package manager   | `uv`                                       |
| Orchestration     | LangChain (LCEL)                           |
| Vector database   | ChromaDB (persisted to disk)               |
| Embeddings        | Google – `models/gemini-embedding-001`     |
| LLM               | Google – `gemini-3-flash-preview`          |
| UI                | Streamlit                                  |

---

## Project Structure

```
G1KI_Angebotsabgleich/
├── app.py                     # Streamlit UI
├── compare_rag.py             # RAG core module (also CLI-capable)
├── Loeschanlagenkonzept.pdf   # Specification / requirements document
├── Komponentenliste.pdf       # Vendor component list (offer to be checked)
├── abgleich_ergebnis.txt      # Result report (generated on run)
├── .chroma_konzept/           # Persisted ChromaDB – specification index
├── .chroma_angebot/           # Persisted ChromaDB – component list index
├── pyproject.toml             # Project dependencies
├── uv.lock                    # Locked dependency versions
└── .venv/                     # Virtual environment (managed by uv)
```

---

## Step-by-Step Guide

### Step 1 – Check Prerequisites

Make sure **Python 3.11+** and **uv** are installed:

```bash
python3 --version      # must be 3.11 or higher
uv --version           # must be present
```

Install `uv` if not already available:

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

---

### Step 2 – Open or Create the Project Folder

```bash
# Open the existing folder:
cd /home/ridwan/Desktop/PROJECTS/LEUPHANA/G1KI_Angebotsabgleich

# Or create a new one:
mkdir G1KI_Angebotsabgleich
cd G1KI_Angebotsabgleich
uv init
```

---

### Step 3 – Set Up the Virtual Environment & Install Dependencies

```bash
uv venv                  # creates .venv/
uv sync                  # installs all packages from pyproject.toml
```

If `pyproject.toml` is missing, add dependencies manually:

```bash
uv add langchain \
       langchain-community \
       langchain-google-genai \
       langchain-chroma \
       langchain-text-splitters \
       pypdf \
       streamlit \
       pandas
```

---

### Step 4 – Place the PDF Documents

Both PDF files must be in the project root directory with **exactly these filenames**:

| Filename                     | Contents                                    |
|------------------------------|---------------------------------------------|
| `Loeschanlagenkonzept.pdf`   | Technical specification (requirements doc)  |
| `Komponentenliste.pdf`       | Vendor component list (offer)               |

```bash
# Verify both files are present:
ls -lh Loeschanlagenkonzept.pdf Komponentenliste.pdf
```

---

### Step 5 – Configure the VS Code Python Interpreter

To prevent Pylance/IntelliSense from showing false import errors, point VS Code
to the project-local `.venv`:

1. `Ctrl+Shift+P` → **Python: Select Interpreter**
2. Choose `.venv/bin/python` from the list  
   (path: `./G1KI_Angebotsabgleich/.venv/bin/python`)

---

### Step 6 – Start the Streamlit App

```bash
uv run streamlit run app.py
```

The app opens automatically in the browser at `http://localhost:8501`.

---

### Step 7 – Run the Compatibility Check (UI)

1. Browser opens at `http://localhost:8501`
2. Sidebar shows the active model and the number of check points
3. Increase the delay slider if needed (recommended: **5–8 s** for free-tier)
4. Click **▶ Abgleich starten**
5. A progress bar tracks all 22 check points in real time
6. Results are displayed as colour-coded cards:
   - ✅ **ERFÜLLT** – Requirement is covered by the component list
   - ⚠️ **TEILWEISE** – Partially covered; gaps exist
   - ❌ **FEHLT** – Requirement is missing entirely from the offer
7. Download the report or save it locally

---

### Step 8 – CLI Mode (optional, without UI)

```bash
uv run python compare_rag.py
```

Output is printed to the terminal; the result report is saved to
`abgleich_ergebnis.txt`.

---

## Configuration (`compare_rag.py`)

All configurable constants are at the top of `compare_rag.py`:

```python
GOOGLE_API_KEY     = "AIzaSy..."               # API key (Google AI Studio)
MODEL              = "gemini-3-flash-preview"  # Active LLM model
KONZEPT_PDF        = "Loeschanlagenkonzept.pdf"
ANGEBOT_PDF        = "Komponentenliste.pdf"
RESULTS_FILE       = "abgleich_ergebnis.txt"
CHROMA_DIR_KONZEPT = ".chroma_konzept"         # Persisted vector DB – specification
CHROMA_DIR_ANGEBOT = ".chroma_angebot"         # Persisted vector DB – component list
```

### Switching the Model

If you encounter quota errors (429), list available models:

```bash
uv run python -c "
import requests
key = 'YOUR_API_KEY'
r = requests.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={key}')
for m in r.json().get('models', []):
    if 'generateContent' in m.get('supportedGenerationMethods', []):
        print(m['name'])
"
```

Test a model live:

```bash
uv run python -c "
from langchain_google_genai import ChatGoogleGenerativeAI
r = ChatGoogleGenerativeAI(model='gemini-3-flash-preview', temperature=0,
    google_api_key='YOUR_API_KEY').invoke('Say OK')
print(r.content)
"
```

---

## ChromaDB – Persisted Vector Store

### Why the Change?

The original implementation used **in-memory ChromaDB**: both PDFs were
re-embedded from scratch on every single run. Each run called the Google
embedding API twice (once per PDF), consuming free-tier quota and adding
20–60 seconds of setup time before any compatibility check even started.

The updated implementation **persists the vector stores to disk**:

| | Before (in-memory) | After (persisted) |
|---|---|---|
| Embedding API calls per run | 2 (every time) | 0 (after first run) |
| Setup time (subsequent runs) | ~30–60 s | < 1 s |
| Disk usage | none | ~5–15 MB total |
| Quota consumed per run | 2 extra calls | 0 extra calls |

### How It Works

On the **first run**, `build_vectorstore()` splits each PDF into chunks,
calls the embedding API, and writes the resulting index to disk:

```
.chroma_konzept/   ← index for Loeschanlagenkonzept.pdf
.chroma_angebot/   ← index for Komponentenliste.pdf
```

On every **subsequent run**, if those folders already exist, the function
loads directly from disk — no PDF parsing, no embedding API calls.

### Forcing a Rebuild

If you replace either PDF with a new version, delete the corresponding
cache folder so it gets rebuilt:

```bash
# Rebuild both:
rm -rf .chroma_konzept .chroma_angebot

# Rebuild only the specification index:
rm -rf .chroma_konzept
```

---

## Compatibility Check Points (22 total)

| ID      | Kategorie                            | Prüfpunkt (Zusammenfassung)                                        |
|---------|--------------------------------------|--------------------------------------------------------------------|
| SPR-1   | Sprinkleranlage – Lagerbereich 1     | Deckenschutz (7,5 mm/min, RTI 50–80, 68 °C)                       |
| SPR-2   | Sprinkleranlage – Lagerbereich 1     | Regalschutz (10,0 mm/min, RTI ≤ 50, 7 Ebenen)                     |
| SPR-3   | Sprinkleranlage – Lagerbereich 1     | Vorzonenschutz Achse I-J'/27-33                                    |
| SPR-4   | Sprinkleranlage – Nebenräume         | Büro-, Sozial- und Technikbereiche                                 |
| SPR-5   | Sprinkleranlage – Überwachung        | Absperrüberwachung, Druckschalter, Alarmierung                     |
| CO2-1   | CO2-Löschanlage                      | Zone 1 – Lagerbereich 2 (3.070 kg, 3 Düsenebenen)                 |
| CO2-2   | CO2-Löschanlage                      | Zone 2 – Lagerbereich 3 (18.515 kg, 3 Düsenebenen)                |
| CO2-3   | CO2-Löschanlage                      | Zone 3 – Kommissionierbereich (14.024 kg, 2 Ebenen)               |
| CO2-4   | CO2-Löschanlage                      | Vorratsbehälter (mind. 30.000 kg CO2)                              |
| CO2-5   | CO2-Löschanlage                      | Düsennetz DN 25–80 in allen Zonen                                  |
| CO2-6   | CO2-Löschanlage                      | Pneumatische Druckentlastungsklappen (200 Pa)                      |
| DET-1   | Branderkennung                       | Ansaugrauchmelder (VdS-zugelassen)                                 |
| DET-2   | Branderkennung                       | UV-Flammenmelder                                                   |
| DET-3   | Branderkennung                       | 2-Melder-/2-Linien-Abhängigkeit + Druckknopfmelder (DKM)          |
| ALM-1   | Alarmierung                          | Blitzleuchten, Hupen, Sirenen                                      |
| ALM-2   | Alarmierung                          | Warntableaus / Leuchtanzeigen                                      |
| ALM-3   | Alarmierung                          | Alarmweiterleitung an Brandmeldezentrale (BMZ)                     |
| CTR-1   | Löschsteuerzentrale                  | Steuereinheit + 30-Stunden-Akkupufferung                           |
| CTR-2   | Betriebsmittelabschaltung            | Lüftung, Brandschutzklappen, Tore/Türen                            |
| WTR-1   | Wasserversorgung                     | Pumpenzentrale / Bestandsanlage 600 m³                             |
| WTR-2   | Hydranten                            | Innen-/Außenhydranten 1.600 l/min, 60 min                          |
| QST-1   | Qualität & Inbetriebnahme            | VdS-Zulassung, anerkannter Errichter                               |

---

## Troubleshooting

### 429 RESOURCE_EXHAUSTED (Quota exceeded)

The code includes automatic **retry with exponential backoff** (up to 5 attempts,
starting at 15 s). If the error persists:

1. **Increase the delay** – set the UI slider to 8–10 s
2. **Switch the model** – change `MODEL` in `compare_rag.py`
   (e.g. `gemini-2.5-flash`, `gemini-2.0-flash`)
3. **Try again tomorrow** – free-tier daily quota resets at midnight

Free-tier limits (as of Feb 2026):

| Model                   | Requests/day | Requests/minute |
|-------------------------|--------------|-----------------|
| gemini-2.0-flash        | unlimited    | 15 RPM          |
| gemini-2.5-flash-lite   | 20/day       | 5 RPM           |
| gemini-3-flash-preview  | higher       | variable        |

### Import errors in VS Code (Pylance)

Cause: VS Code is using the global Python instead of the project `.venv`.

```
Ctrl+Shift+P → Python: Select Interpreter → .venv/bin/python
```

### PDF not found

```bash
ls Loeschanlagenkonzept.pdf Komponentenliste.pdf
# Both files must be in the project root directory
```

### ChromaDB index is stale (PDF was replaced)

```bash
rm -rf .chroma_konzept .chroma_angebot
uv run streamlit run app.py   # rebuilds indexes on next run
```

---

## Get an API Key

1. Sign in at [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Paste the key into `compare_rag.py` under `GOOGLE_API_KEY`

---

## Quick Start

```bash
# 1. Enter the project folder
cd /home/ridwan/Desktop/PROJECTS/LEUPHANA/G1KI_Angebotsabgleich

# 2. Install dependencies (only needed once)
uv sync

# 3. Verify PDFs are present
ls Loeschanlagenkonzept.pdf Komponentenliste.pdf

# 4. Start the app
uv run streamlit run app.py
```