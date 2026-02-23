"""
compare_rag.py
==============
Angebotsabgleich – Kompatibilitätsprüfung
==========================================
Kernmodul: Prüft, ob die Komponentenliste (Angebot) alle Anforderungen des
Löschanlagenkonzepts (Pflichtenheft) vollständig erfüllt.

Läuft als CLI:  python compare_rag.py
Verwendet auch von:  app.py (Streamlit-UI)
"""

import os
import time
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ── API key & model (hardcoded) ───────────────────────────────────────────────
GOOGLE_API_KEY = "AIzaSyCRU2z7jggNYbi4AIHD9Skke1uyKdHM2t8"
MODEL          = "gemini-3-flash-preview"

# Keep alias so any external reference still works
MODEL_FLASH = MODEL

# ── File paths ─────────────────────────────────────────────────────────────────
KONZEPT_PDF      = "Loeschanlagenkonzept.pdf"
ANGEBOT_PDF      = "Komponentenliste.pdf"
RESULTS_FILE     = "abgleich_ergebnis.txt"
CHROMA_DIR_KONZEPT = ".chroma_konzept"
CHROMA_DIR_ANGEBOT = ".chroma_angebot"

# ── Structured compatibility checks ────────────────────────────────────────────
COMPATIBILITY_CHECKS = [
    {
        "id": "SPR-1",
        "category": "Sprinkleranlage – Compartment 1",
        "title": "Deckenschutz Compartment 1 (7,5 mm/min, RTI 50–80, 68 °C)",
        "konzept_query": "Sprinkler Deckenschutz Compartment 1 Wasserbeaufschlagung RTI Auslösetemperatur",
        "angebot_query": "Sprinkler Deckenschutz Compartment 1 Decke mm/min",
    },
    {
        "id": "SPR-2",
        "category": "Sprinkleranlage – Compartment 1",
        "title": "Regalschutz Compartment 1 (10,0 mm/min, RTI ≤ 50, 68 °C, 7 Ebenen)",
        "konzept_query": "Regalschutz Regalsprinkler Ebenen Wasserbeaufschlagung RTI Compartment 1",
        "angebot_query": "Regalschutz Regalsprinkler Compartment 1",
    },
    {
        "id": "SPR-3",
        "category": "Sprinkleranlage – Compartment 1",
        "title": "Vorzonenschutz Achse I-J'/27-33 (10,0 mm/min, Einzelstrang)",
        "konzept_query": "Vorzone Vorzonen Förderstrecke Deckenschutz HRL Einzelstrang",
        "angebot_query": "Vorzone Sprinkler Ein-Auslagerungsbahn Abschirmhaube",
    },
    {
        "id": "SPR-4",
        "category": "Sprinkleranlage – Nebenräume",
        "title": "Sprinklerschutz Büro-, Sozial- und Technikbereich",
        "konzept_query": "Bürobereich Sozialbereich Technikbereich Sprinkler",
        "angebot_query": "Büro Sozial Technik Sprinkler Zonecheck flexibel",
    },
    {
        "id": "SPR-5",
        "category": "Sprinkleranlage – Überwachung",
        "title": "Überwachungseinrichtungen (Schieberüberwachung, Druckschalter, Alarmgebung)",
        "konzept_query": "Alarmventile Druckschalter Schieberüberwachung Alarmglocken",
        "angebot_query": "Schieberüberwachung Alarmhahnüberwachung Temperaturüberwachung Blitzleuchte",
    },
    {
        "id": "CO2-1",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "CO2-Löschanlage LB 1 – Compartment 2 (3.070 kg, 3 Tiefdüsenebenen)",
        "konzept_query": "Löschbereich 1 Compartment 2 CO2 3070 kg Tiefdüsen",
        "angebot_query": "CO2 Löschanlage Bereichsventil DN150 DN80 Löschbereich",
    },
    {
        "id": "CO2-2",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "CO2-Löschanlage LB 2 – Compartment 3 (18.515 kg, 3 Tiefdüsenebenen)",
        "konzept_query": "Löschbereich 2 Compartment 3 CO2 18515 kg Tiefdüsen",
        "angebot_query": "CO2 Löschanlage Löschbereich 2",
    },
    {
        "id": "CO2-3",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "CO2-Löschanlage LB 3 – Kommissionierfläche (14.024 kg, 2 Tiefdüsenebenen)",
        "konzept_query": "Löschbereich 3 Kommissionierfläche CO2 14024 kg",
        "angebot_query": "CO2 Löschanlage Löschbereich 3 Kommissionierung",
    },
    {
        "id": "CO2-4",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "CO2-Vorratsbehälter (mind. 30.000 kg Nutzinhalt)",
        "konzept_query": "CO2 Vorratsmenge Vorratsbehälter 30000 kg Nutzinhalt",
        "angebot_query": "CO2 Vorratsbehälter Tank Speicher",
    },
    {
        "id": "CO2-5",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "CO2-Düsennetz (Gaslöschdüsen, Düsenleitungen DN 25–80)",
        "konzept_query": "CO2 Düsen Deckendüsen Tiefdüsenebenen Düsenleitungen",
        "angebot_query": "Gaslöschdüse Düsenleitung DN CO2",
    },
    {
        "id": "CO2-6",
        "category": "CO2-Niederdruck-Löschanlage",
        "title": "Druckentlastungsklappen (pneumatisch, Trox FK-DV o. ä., 200 Pa)",
        "konzept_query": "Druckentlastungsklappen pneumatisch Trox FK-DV 200 Pa Druckentlastung",
        "angebot_query": "Druckentlastung Druckentlastungsklappe pneumatisch",
    },
    {
        "id": "DET-1",
        "category": "Branderkennung & Alarmierung",
        "title": "Ansaugrauchmelder (VdS-konform, Ansaugnetze)",
        "konzept_query": "Ansaugrauchmelder Brandmelder BMA-Konzept Detektion VdS",
        "angebot_query": "Ansaugrauchmelder RAS Detektormodul Ansaugrohr ProSens",
    },
    {
        "id": "DET-2",
        "category": "Branderkennung & Alarmierung",
        "title": "UV-Flammenmelder",
        "konzept_query": "UV-Flammenmelder Flammerkennung Auslösung",
        "angebot_query": "UV Flammenmelder",
    },
    {
        "id": "DET-3",
        "category": "Branderkennung & Alarmierung",
        "title": "2-Melder-/2-Linien-Abhängigkeit und manuelle Handauslösung (DKM)",
        "konzept_query": "2-Melder 2-Linien Abhängigkeit Druckknopfmelder Handauslösung",
        "angebot_query": "Druckknopfmelder DKM Handauslösung",
    },
    {
        "id": "ALM-1",
        "category": "Alarmierungssysteme",
        "title": "Akustische und optische Alarmierung (Blitzleuchten, Hupen, Sirenen)",
        "konzept_query": "Voralarm Blitzleuchten elektrische Hupen Feueralarm pneumatische Hupen",
        "angebot_query": "Blitzleuchte Signalhupe Sirene Alarm Fanfare optisch akustisch",
    },
    {
        "id": "ALM-2",
        "category": "Alarmierungssysteme",
        "title": "Warntransparente / Leuchttableaus an Zugängen der Löschbereiche",
        "konzept_query": "Warntransparente Zugänge Löschbereich Warnung",
        "angebot_query": "Leuchttableau Warntableau Warntransparent",
    },
    {
        "id": "ALM-3",
        "category": "Alarmierungssysteme",
        "title": "Alarmweiterleitung zur BMZ und ständig besetzter Stelle",
        "konzept_query": "Brandmeldezentrale BMZ Alarmweiterleitung ständig besetzte Stelle",
        "angebot_query": "Brandmeldezentrale BMZ Meldemodul Löschsteuerzentrale Erweiterung",
    },
    {
        "id": "CTR-1",
        "category": "Löschsteuerzentrale & Energieversorgung",
        "title": "Löschsteuerzentrale inkl. 30-Stunden-Akku-Backup",
        "konzept_query": "Löschsteuerzentrale Akkumulatoren 30 Stunden Energieversorgung Netzausfall",
        "angebot_query": "Löschsteuerzentrale Steuereinheit Energieversorgung Akku Batterie",
    },
    {
        "id": "CTR-2",
        "category": "Betriebsmittelansteuerungen",
        "title": "Betriebsmittelabschaltungen (Lüftung, Brandschutzklappen, Tore/Türen)",
        "konzept_query": "Lüftungsanlage Brandschutzklappen Abschalten Betriebsmittel Tore Türen",
        "angebot_query": "Lüftung Brandschutzklappe Abschaltung Tor Tür Betriebsmittel",
    },
    {
        "id": "WTR-1",
        "category": "Wasserversorgung & Hydranten",
        "title": "Löschwasserversorgung Sprinkler (Pumpenzentrale / Bestandsanlage 600 m³)",
        "konzept_query": "Wasserversorgung Pumpen Vorratsbehälter Löschwasser Diesel 600 m³ Speck",
        "angebot_query": "Pumpe Wasserversorgung Vorratsbehälter Diesel Pumpenaggregat",
    },
    {
        "id": "WTR-2",
        "category": "Wasserversorgung & Hydranten",
        "title": "Hydrantenanlage (Innen- und Außenhydranten, 1.600 l/min, 60 min)",
        "konzept_query": "Hydranten Außenhydranten Innenhydranten 1600 l/min DIN 14462",
        "angebot_query": "Hydrant Innenhydrant Außenhydrant",
    },
    {
        "id": "QST-1",
        "category": "Qualität & Inbetriebnahme",
        "title": "VdS-Zulassung aller Anlagenteile, Errichteranerkennung, Prüfnachweise",
        "konzept_query": "VdS zugelassen Errichteranerkennung Qualitätsstandard Inbetriebnahme",
        "angebot_query": "VdS Zulassung Norm Zertifizierung Prüfnachweis",
    },
]

VERDICT_PROMPT = ChatPromptTemplate.from_template(
    "Du bist ein Brandschutzfachplaner und prüfst, ob ein Angebot die Anforderungen "
    "eines Löschanlagenkonzepts erfüllt.\n\n"
    "## Anforderung laut Löschanlagenkonzept\n"
    "Kategorie: {category}\n"
    "Prüfpunkt: {title}\n\n"
    "Relevante Passagen aus dem Löschanlagenkonzept:\n"
    "---\n{konzept_context}\n---\n\n"
    "## Angebot (Komponentenliste)\n"
    "Relevante Passagen aus der Komponentenliste:\n"
    "---\n{angebot_context}\n---\n\n"
    "## Aufgabe\n"
    "Bewerte, ob die Komponentenliste diese Anforderung erfüllt.\n"
    "Antworte NUR in diesem Format:\n\n"
    "VERDICT: <ERFÜLLT|TEILWEISE|FEHLT>\n"
    "BEGRÜNDUNG: <1–3 prägnante Sätze mit konkreten Positionsnummern oder Textbelegen>\n"
    "LÜCKEN: <Falls TEILWEISE oder FEHLT: Was fehlt konkret? Sonst: keine>\n"
)

SUMMARY_PROMPT = ChatPromptTemplate.from_template(
    "Du bist ein Brandschutzfachplaner und hast alle Einzelprüfungen abgeschlossen.\n\n"
    "Ergebnisse:\n---\n{all_results}\n---\n\n"
    "Erstelle eine Gesamtbewertung (max. 200 Wörter) auf Deutsch:\n"
    "1. Kann das Löschanlagenkonzept mit der Komponentenliste vollständig umgesetzt werden?\n"
    "2. Was sind die kritischen Lücken (falls vorhanden)?\n"
    "3. Empfohlene nächste Schritte?\n\n"
    "Beginne mit: VOLLSTÄNDIG UMSETZBAR / BEDINGT UMSETZBAR / NICHT VOLLSTÄNDIG UMSETZBAR\n"
)


def ensure_api_key() -> str:
    os.environ.setdefault("GOOGLE_API_KEY", GOOGLE_API_KEY)
    return GOOGLE_API_KEY


def load_pdf(path: str | Path) -> list:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF nicht gefunden: '{path}'")
    return PyPDFLoader(str(path)).load()


def build_vectorstore(docs: list, api_key: str, persist_dir: str | None = None):
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key,
    )
    if persist_dir and Path(persist_dir).exists():
        print(f"  ♻️  Lade gespeicherte ChromaDB aus '{persist_dir}' …")
        return Chroma(persist_directory=persist_dir, embedding_function=embeddings), []
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    kwargs = {"persist_directory": persist_dir} if persist_dir else {}
    return Chroma.from_documents(chunks, embeddings, **kwargs), chunks


def get_context(vectorstore: Chroma, query: str, k: int = 5) -> str:
    docs = vectorstore.similarity_search(query, k=k)
    return "\n\n".join(d.page_content for d in docs)


def _invoke_with_retry(chain, inputs, max_retries=5):
    """Call chain.invoke with exponential backoff on 429 RESOURCE_EXHAUSTED."""
    delay = 15  # initial wait in seconds
    for attempt in range(max_retries):
        try:
            return chain.invoke(inputs)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = delay * (2 ** attempt)
                print(f"\n  ⏳ Rate limit hit – waiting {wait}s (attempt {attempt+1}/{max_retries}) …",
                      flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Max retries ({max_retries}) exceeded on rate-limit errors.")


def run_check(check, vs_konzept, vs_angebot, llm, sleep_between=2.0):
    konzept_ctx = get_context(vs_konzept, check["konzept_query"])
    angebot_ctx = get_context(vs_angebot, check["angebot_query"])
    chain = VERDICT_PROMPT | llm | StrOutputParser()
    t0 = time.perf_counter()
    raw = _invoke_with_retry(chain, {
        "category": check["category"],
        "title": check["title"],
        "konzept_context": konzept_ctx,
        "angebot_context": angebot_ctx,
    })
    elapsed = round(time.perf_counter() - t0, 2)
    time.sleep(sleep_between)

    verdict, reasoning, gaps = "UNKLAR", "", ""
    for line in raw.splitlines():
        ln = line.strip()
        if ln.startswith("VERDICT:"):
            verdict = ln.replace("VERDICT:", "").strip()
        elif ln.startswith("BEGRÜNDUNG:"):
            reasoning = ln.replace("BEGRÜNDUNG:", "").strip()
        elif ln.startswith("LÜCKEN:"):
            gaps = ln.replace("LÜCKEN:", "").strip()

    return {
        "id": check["id"],
        "category": check["category"],
        "title": check["title"],
        "verdict": verdict,
        "reasoning": reasoning,
        "gaps": gaps,
        "time_s": elapsed,
        "raw": raw,
    }


def run_abgleich(api_key=None, model_name=None, sleep_between=2.0, progress_callback=None):
    api_key    = api_key    or GOOGLE_API_KEY
    model_name = model_name or MODEL
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=api_key)

    if progress_callback:
        progress_callback(0.0, "Lade PDFs …")
    konzept_docs = load_pdf(KONZEPT_PDF)
    angebot_docs = load_pdf(ANGEBOT_PDF)

    if progress_callback:
        progress_callback(0.05, "Erstelle Vektordatenbanken …")
    vs_konzept, _ = build_vectorstore(konzept_docs, api_key, CHROMA_DIR_KONZEPT)
    vs_angebot, _ = build_vectorstore(angebot_docs, api_key, CHROMA_DIR_ANGEBOT)

    results = []
    total = len(COMPATIBILITY_CHECKS)
    t_start = time.perf_counter()

    for i, check in enumerate(COMPATIBILITY_CHECKS):
        if progress_callback:
            pct = 0.10 + (i / total) * 0.80
            progress_callback(pct, f"[{check['id']}] {check['title'][:65]} …")
        results.append(run_check(check, vs_konzept, vs_angebot, llm, sleep_between))

    if progress_callback:
        progress_callback(0.92, "Erstelle Gesamtbewertung …")

    summary_text = "\n\n".join(
        f"[{r['id']}] {r['title']}\nVERDICT: {r['verdict']}\n"
        f"BEGRÜNDUNG: {r['reasoning']}\nLÜCKEN: {r['gaps']}"
        for r in results
    )
    summary_chain = SUMMARY_PROMPT | llm | StrOutputParser()
    summary = _invoke_with_retry(summary_chain, {"all_results": summary_text})
    time.sleep(sleep_between)

    if progress_callback:
        progress_callback(1.0, "Abgeschlossen ✅")

    return {
        "results": results,
        "summary": summary,
        "model": model_name,
        "elapsed_total": round(time.perf_counter() - t_start, 1),
    }


def save_report(data, output_path=RESULTS_FILE):
    output_path = Path(output_path)
    results = data["results"]
    counts = {}
    for r in results:
        k = r["verdict"].upper()
        counts[k] = counts.get(k, 0) + 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("ANGEBOTSABGLEICH – KOMPATIBILITÄTSPRÜFUNG\n")
        f.write(f"Konzept:   {KONZEPT_PDF}\n")
        f.write(f"Angebot:   {ANGEBOT_PDF}\n")
        f.write(f"Modell:    {data['model']}\n")
        f.write(f"Erstellt:  {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Laufzeit:  {data['elapsed_total']} s\n")
        f.write("=" * 80 + "\n\n")
        f.write("ZUSAMMENFASSUNG\n")
        f.write("-" * 80 + "\n")
        f.write(data["summary"] + "\n\n")
        f.write(
            f"Statistik: ERFÜLLT={counts.get('ERFÜLLT',0)}  "
            f"TEILWEISE={counts.get('TEILWEISE',0)}  "
            f"FEHLT={counts.get('FEHLT',0)}  "
            f"UNKLAR={counts.get('UNKLAR',0)}\n"
        )
        f.write("=" * 80 + "\n\n")
        f.write("DETAILERGEBNISSE\n")
        f.write("=" * 80 + "\n\n")
        for r in results:
            f.write(f"[{r['id']}]  {r['title']}\n")
            f.write(f"Kategorie:   {r['category']}\n")
            f.write(f"VERDICT:     {r['verdict']}  ({r['time_s']} s)\n")
            f.write(f"Begründung:  {r['reasoning']}\n")
            f.write(f"Lücken:      {r['gaps']}\n")
            f.write("-" * 80 + "\n\n")
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    api_key = ensure_api_key()
    ICONS = {"ERFÜLLT": "✅", "TEILWEISE": "⚠️ ", "FEHLT": "❌", "UNKLAR": "❓"}

    def cli_progress(frac, msg):
        bar = "#" * int(frac * 30)
        print(f"\r  [{bar:<30}] {msg:<70}", end="", flush=True)

    print(f"\n🔍  Angebotsabgleich – {KONZEPT_PDF} vs. {ANGEBOT_PDF}\n")

    for model in [MODEL]:
        print(f"\n{'='*60}\nModell: {model}\n{'='*60}")
        data = run_abgleich(api_key, model_name=model, progress_callback=cli_progress)
        print()
        out = save_report(data, f"abgleich_{model.replace('-','_').replace('.','_')}.txt")
        print(f"\n📄  Bericht: {out}\n")
        counts: dict = {}
        for r in data["results"]:
            icon = ICONS.get(r["verdict"], "❓")
            print(f"  {icon}  [{r['id']:<7}] {r['title'][:60]}")
            k = r["verdict"].upper()
            counts[k] = counts.get(k, 0) + 1
        print(f"\n  ✅ {counts.get('ERFÜLLT',0)}  ⚠️  {counts.get('TEILWEISE',0)}  ❌ {counts.get('FEHLT',0)}")
        print(f"\n  GESAMTBEWERTUNG:\n  {data['summary'][:500]}")
