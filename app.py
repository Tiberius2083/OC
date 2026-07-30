import streamlit as st
import pandas as pd
import random
from rdkit import Chem
from rdkit.Chem import Draw
import os


# --- DATEN-HELFER ---
@st.cache_data
def load_excel():
    excel_path = "OC.xlsx"
    if not os.path.exists(excel_path):
        return None
    return pd.read_excel(excel_path)


@st.cache_resource
def get_plural_mapping():
    return {
        "Alkan": "Alkane", "Cycloalkan": "Cycloalkane", "Alken": "Alkene",
        "Alkin": "Alkine", "Aromat": "Aromaten", "Halogenierte Kohlenwasserstoffe": "Halogenierte Kohlenwasserstoffe",
        "Alkohol": "Alkohole", "Phenol": "Phenole", "Ether": "Ether",
        "Thiol": "Thiole", "Sulfid": "Sulfide", "Sulfoxid": "Sulfoxide",
        "Sulfon": "Sulfone", "Amin": "Amine", "Aldehyd": "Aldehyde",
        "Keton": "Ketone", "Chinon": "Chinone", "Monocarbonsäure": "Monocarbonsäuren",
        "Dicarbonsäure": "Dicarbonsäuren", "Hydroxycarbonsäure": "Hydroxycarbonsäuren",
        "Tricarbonsäure": "Tricarbonsäuren", "Fettsäure": "Fettsäuren",
        "ungesättigte Dicarbonsäure": "ungesättigte Dicarbonsäuren", "Carbonsäureester": "Carbonsäureester",
        "Lacton": "Lactone", "Carbonsäureamid": "Carbonsäureamide", "Lactam": "Lactame",
        "Imid": "Imide", "Nitril": "Nitrile", "Isocyanat": "Isocyanate",
        "Isothiocyanat": "Isothiocyanate", "Nitroverbindung": "Nitroverbindungen",
        "Lipid": "Lipide", "Kohlenhydrat": "Kohlenhydrate", "Aminosäure": "Aminosäuren",
        "Heterocyclus": "Heterocyclen"
    }


def pluralize(cls):
    return get_plural_mapping().get(cls, cls + "e")


# --- STREAMLIT BENUTZEROBERFLÄCHE ---
st.set_page_config(page_title="OC Lernapp", page_icon="🧪", layout="centered")

df = load_excel()
if df is None:
    st.error("Die Datei 'OC.xlsx' wurde nicht gefunden! Bitte lade sie mit ins GitHub-Repository hoch.")
    st.stop()

# Session State initialisieren
if "page" not in st.session_state:
    st.session_state.page = "menu"
if "quiz_mols" not in st.session_state:
    st.session_state.quiz_mols = []
if "curr_idx" not in st.session_state:
    st.session_state.curr_idx = 0
if "correct_count" not in st.session_state:
    st.session_state.correct_count = 0
if "wrong_count" not in st.session_state:
    st.session_state.wrong_count = 0

# --- HAUPTMENÜ ---
if st.session_state.page == "menu":
    st.title("🧪 Organische Chemie – Lernapp")
    st.subheader("Wähle deine Verbindungsklassen")

    raw_classes = df["Verbindungsklasse"].dropna().unique().tolist()
    available_classes = sorted(list(set([pluralize(c) for c in raw_classes])))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Alle auswählen"):
            st.session_state.select_all = True
    with col2:
        if st.button("Alle abwählen"):
            st.session_state.select_all = False

    default_val = st.session_state.get("select_all", True)

    class_checkboxes = {}
    for cls_name in available_classes:
        class_checkboxes[cls_name] = st.checkbox(cls_name, value=default_val)

    mode = st.selectbox("Lern-Modus:", [
        "Auswahl-Modus (Strukturformel -> Name)",
        "Tastatur-Modus (freies Tippen)"
    ])

    if st.button("Lernen starten", type="primary", use_container_width=True):
        selected_classes = [name for name, checked in class_checkboxes.items() if checked]
        if not selected_classes:
            st.warning("Bitte wähle mindestens eine Verbindungsklasse aus!")
        else:
            # Moleküle filtern
            mols = []
            for _, row in df.iterrows():
                rc = row.get("Verbindungsklasse")
                if pd.isna(rc): continue
                c_name = pluralize(rc)
                if c_name in selected_classes:
                    mols.append({
                        "id": str(row.get("ID")),
                        "name": str(row.get("Primärname")).strip(),
                        "class": c_name,
                        "smiles": str(row.get("SMILES")).strip()
                    })

            if not mols:
                st.warning("Keine Moleküle für diese Auswahl gefunden!")
            else:
                random.shuffle(mols)
                st.session_state.quiz_mols = mols
                st.session_state.curr_idx = 0
                st.session_state.correct_count = 0
                st.session_state.wrong_count = 0
                st.session_state.mode = mode
                st.session_state.page = "quiz"
                st.rerun()

# --- QUIZ-SEITE ---
elif st.session_state.page == "quiz":
    if st.button("← Zurück zum Hauptmenü"):
        st.session_state.page = "menu"
        st.rerun()

    mols = st.session_state.quiz_mols
    idx = st.session_state.curr_idx

    if idx >= len(mols):
        st.success("🎉 Du hast alle Moleküle dieser Runde durchgearbeitet!")
        st.write(
            f"**Statistik dieser Sitzung:** Richtig: {st.session_state.correct_count} | Falsch: {st.session_state.wrong_count}")
        if st.button("Nochmal von vorne starten"):
            random.shuffle(mols)
            st.session_state.curr_idx = 0
            st.session_state.correct_count = 0
            st.session_state.wrong_count = 0
            st.rerun()
    else:
        current_mol = mols[idx]
        st.write(f"**Frage {idx + 1} von {len(mols)}** | Klasse: `{current_mol['class']}`")

        # Molekül anzeigen
        mol = Chem.MolFromSmiles(current_mol['smiles'])
        if mol:
            img = Draw.MolToImage(mol, size=(400, 250))
            st.image(img, caption="Strukturformel")

        target_name = current_mol['name']

        # Antwort prüfen Logik
        if "freies Tippen" in st.session_state.mode:
            user_input = st.text_input("Gib den Namen des Moleküls ein:", key=f"input_{idx}")
            if st.button("Antwort prüfen", key=f"btn_{idx}"):
                if user_input.strip().lower() == target_name.lower():
                    st.success("Richtig! 🎉")
                    st.session_state.correct_count += 1
                else:
                    st.error(f"Falsch! Richtig wäre: **{target_name}**")
                    st.session_state.wrong_count += 1

                if st.button("Nächstes Molekül ➡️", key=f"next_{idx}"):
                    st.session_state.curr_idx += 1
                    st.rerun()
        else:
            # Multiple Choice
            all_names = df['Primärname'].dropna().unique().tolist()
            distractors = [n for n in all_names if n != target_name]
            choices = random.sample(distractors, min(3, len(distractors))) + [target_name]
            random.shuffle(choices)

            choice = st.radio("Welcher Name passt zum Molekül?", choices, key=f"radio_{idx}")
            if st.button("Antwort prüfen", key=f"btn_mc_{idx}"):
                if choice == target_name:
                    st.success("Richtig! 🎉")
                    st.session_state.correct_count += 1
                else:
                    st.error(f"Falsch! Richtig wäre: **{target_name}**")
                    st.session_state.wrong_count += 1

                if st.button("Nächstes Molekül ➡️", key=f"next_mc_{idx}"):
                    st.session_state.curr_idx += 1
                    st.rerun()