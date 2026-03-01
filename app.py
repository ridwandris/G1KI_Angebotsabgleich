"""
app.py  –  Streamlit UI: Angebotsabgleich Löschanlagenkonzept
=============================================================
Startet mit:  streamlit run app.py
"""

import io
import time
from pathlib import Path

import streamlit as st

from compare_rag import (
    MODEL,
    KONZEPT_PDF,
    ANGEBOT_PDF,
    EMBEDDING_MODEL,
    MAX_WORKERS,
    run_abgleich,
    save_report,
    COMPATIBILITY_CHECKS,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Angebotsabgleich – Löschanlagenkonzept",
    page_icon="⚙️",
    layout="wide",
)

# ── Verdict helpers ───────────────────────────────────────────────────────────
VERDICT_ICON  = {"ERFÜLLT": "✅", "TEILWEISE": "⚠️", "FEHLT": "❌", "UNKLAR": "❓"}
VERDICT_COLOR = {
    "ERFÜLLT":  "#1a4d1a",  # dark green bg
    "TEILWEISE": "#4d3a00", # amber bg
    "FEHLT":    "#4d1a1a",  # dark red bg
    "UNKLAR":   "#2a2a2a",
}
VERDICT_BORDER = {
    "ERFÜLLT":  "#4caf50",
    "TEILWEISE": "#ffc107",
    "FEHLT":    "#f44336",
    "UNKLAR":   "#9e9e9e",
}


def verdict_badge(verdict: str) -> str:
    icon  = VERDICT_ICON.get(verdict, "❓")
    color = VERDICT_BORDER.get(verdict, "#9e9e9e")
    return (
        f"<span style='background:{VERDICT_COLOR.get(verdict,'#222')};color:{color};"
        f"border:1px solid {color};border-radius:4px;padding:2px 8px;"
        f"font-weight:bold;font-size:0.85em'>{icon} {verdict}</span>"
    )


def summary_color(text: str) -> str:
    t = text.upper()
    if "NICHT VOLLSTÄNDIG" in t:
        return "#f44336"
    if "BEDINGT" in t:
        return "#ffc107"
    return "#4caf50"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Fire_extinguisher.svg/64px-Fire_extinguisher.svg.png",
        width=48,
    )
    st.title("⚙️ Einstellungen")

    st.markdown(f"**LLM:** `{MODEL}`")
    st.markdown(f"**Embedding:** `{EMBEDDING_MODEL}`")
    st.markdown(f"**Parallel:** max {MAX_WORKERS} gleichzeitig")

    sleep_secs = st.slider(
        "Pause zwischen API-Aufrufen (s)",
        min_value=0,
        max_value=5,
        value=0,
        help="Pause nach jedem LLM-Aufruf. Bei 0 wird voll parallel gearbeitet.",
    )

    st.markdown("---")
    st.markdown("**Dokumente**")
    konzept_exists = Path(KONZEPT_PDF).exists()
    angebot_exists = Path(ANGEBOT_PDF).exists()
    st.markdown(f"{'✅' if konzept_exists else '❌'} `{KONZEPT_PDF}`")
    st.markdown(f"{'✅' if angebot_exists else '❌'} `{ANGEBOT_PDF}`")

    st.markdown("---")
    st.markdown(f"**Prüfpunkte:** {len(COMPATIBILITY_CHECKS)}")


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("Angebotsabgleich – Löschanlagenkonzept")
st.markdown(
    "Prüft automatisch, ob die **Komponentenliste** alle Anforderungen des "
    "**Löschanlagenkonzepts** vollständig erfüllt."
)

col_k, col_a = st.columns(2)
with col_k:
    st.info(f"📋 **Konzept (Pflichtenheft):**  `{KONZEPT_PDF}`")
with col_a:
    st.info(f"📦 **Angebot (Komponentenliste):**  `{ANGEBOT_PDF}`")

if not konzept_exists or not angebot_exists:
    st.error(
        "⚠️ Eine oder beide PDF-Dateien fehlen im Projektverzeichnis. "
        f"Benötigt: `{KONZEPT_PDF}` und `{ANGEBOT_PDF}`"
    )
    st.stop()


# ── Run button ─────────────────────────────────────────────────────────────────
run_btn = st.button("▶ Abgleich starten", type="primary")

if run_btn:
    st.session_state.pop("abgleich_data", None)

    progress_bar = st.progress(0.0, text="Initialisiere …")
    status_box   = st.empty()

    def on_progress(frac: float, msg: str):
        progress_bar.progress(min(frac, 1.0), text=msg)
        status_box.caption(msg)

    try:
        data = run_abgleich(
            sleep_between=sleep_secs,
            progress_callback=on_progress,
        )
        st.session_state["abgleich_data"] = data
        progress_bar.progress(1.0, text="Abgleich abgeschlossen ✅")
        status_box.empty()
        st.success(f"Abgleich abgeschlossen in {data['elapsed_total']} s")
    except Exception as exc:
        st.error(f"Fehler beim Abgleich: {exc}")
        st.stop()

# ── Results ────────────────────────────────────────────────────────────────────
if "abgleich_data" in st.session_state:
    data    = st.session_state["abgleich_data"]
    results = data["results"]

    # ---------- Summary card --------------------------------------------------
    st.markdown("---")
    st.subheader("📊 Gesamtbewertung")

    summary = data["summary"]
    first_line = summary.split("\n")[0]
    color = summary_color(first_line)

    st.markdown(
        f"<div style='background:#1a1a1a;border-left:6px solid {color};"
        f"padding:16px;border-radius:6px;font-size:1.0em'>{summary}</div>",
        unsafe_allow_html=True,
    )

    # ---------- KPI row -------------------------------------------------------
    counts: dict[str, int] = {}
    for r in results:
        k = r["verdict"].upper()
        counts[k] = counts.get(k, 0) + 1

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("✅ Erfüllt",   counts.get("ERFÜLLT", 0))
    k2.metric("⚠️ Teilweise", counts.get("TEILWEISE", 0))
    k3.metric("❌ Fehlt",     counts.get("FEHLT", 0))
    k4.metric("❓ Unklar",    counts.get("UNKLAR", 0))

    # ---------- Timing table --------------------------------------------------
    with st.expander("⏱️ Detailzeiten pro Prüfpunkt"):
        import pandas as pd
        df = pd.DataFrame([
            {
                "ID":          r["id"],
                "Kategorie":   r["category"],
                "Prüfpunkt":   r["title"],
                "Verdict":     r["verdict"],
                "Zeit (s)":    r["time_s"],
            }
            for r in results
        ])
        st.dataframe(df, width="stretch", hide_index=True)

    # ---------- Per-category sections -----------------------------------------
    st.markdown("---")
    st.subheader("🔍 Detailergebnisse nach Kategorie")

    categories = []
    seen: set = set()
    for r in results:
        if r["category"] not in seen:
            categories.append(r["category"])
            seen.add(r["category"])

    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_verdicts = [r["verdict"].upper() for r in cat_results]

        if "FEHLT" in cat_verdicts:
            cat_icon = "❌"
        elif "TEILWEISE" in cat_verdicts or "UNKLAR" in cat_verdicts:
            cat_icon = "⚠️"
        else:
            cat_icon = "✅"

        with st.expander(f"{cat_icon}  {cat}", expanded=("FEHLT" in cat_verdicts)):
            for r in cat_results:
                verdict = r["verdict"].upper()
                border  = VERDICT_BORDER.get(verdict, "#9e9e9e")
                bg      = VERDICT_COLOR.get(verdict, "#222")

                fehlt_color = VERDICT_BORDER["FEHLT"]
                gaps_html = (
                    f"<b style='color:{fehlt_color}'>⚠ Lücken:</b> {r['gaps']}"
                    if r["gaps"] and r["gaps"].lower() != "keine"
                    else ""
                )
                st.markdown(
                    f"<div style='background:{bg};border-left:4px solid {border};"
                    f"padding:10px 14px;border-radius:4px;margin-bottom:8px'>"
                    f"<b>[{r['id']}] {r['title']}</b><br>"
                    f"{verdict_badge(verdict)}<br><br>"
                    f"<b>Begründung:</b> {r['reasoning']}<br>"
                    + gaps_html
                    + "</div>",
                    unsafe_allow_html=True,
                )

    # ---------- Download / Save -----------------------------------------------
    st.markdown("---")
    col_dl, col_sv = st.columns(2)

    # In-memory txt for download
    buf = io.StringIO()
    buf.write("=" * 80 + "\n")
    buf.write("ANGEBOTSABGLEICH – KOMPATIBILITÄTSPRÜFUNG\n")
    buf.write(f"Konzept:   {KONZEPT_PDF}\n")
    buf.write(f"Angebot:   {ANGEBOT_PDF}\n")
    buf.write(f"Modell:    {data['model']}\n")
    buf.write(f"Erstellt:  {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    buf.write(f"Laufzeit:  {data['elapsed_total']} s\n")
    buf.write("=" * 80 + "\n\n")
    buf.write("ZUSAMMENFASSUNG\n" + "-" * 80 + "\n")
    buf.write(data["summary"] + "\n\n")
    buf.write(
        f"Statistik: ERFÜLLT={counts.get('ERFÜLLT',0)}  "
        f"TEILWEISE={counts.get('TEILWEISE',0)}  "
        f"FEHLT={counts.get('FEHLT',0)}\n"
    )
    buf.write("=" * 80 + "\n\nDETAILERGEBNISSE\n" + "=" * 80 + "\n\n")
    for r in results:
        buf.write(f"[{r['id']}]  {r['title']}\n")
        buf.write(f"Kategorie:  {r['category']}\n")
        buf.write(f"VERDICT:    {r['verdict']}  ({r['time_s']} s)\n")
        buf.write(f"Begründung: {r['reasoning']}\n")
        buf.write(f"Lücken:     {r['gaps']}\n")
        buf.write("-" * 80 + "\n\n")

    with col_dl:
        st.download_button(
            label="⬇️ Bericht herunterladen (.txt)",
            data=buf.getvalue(),
            file_name="abgleich_ergebnis.txt",
            mime="text/plain",
        )

    with col_sv:
        if st.button("💾 Bericht lokal speichern"):
            out = save_report(data, Path(__file__).parent / "abgleich_ergebnis.txt")
            st.success(f"Gespeichert: `{out}`")
