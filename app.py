import streamlit as st
import pandas as pd
import sqlite3
import random
import os
from io import BytesIO
from rdkit import Chem
from rdkit.Chem import Draw

# --- DATENBANK & LOGIK MANAGER ---
DB_PATH = "data/learning_progress.db"
EXCEL_PATH = "OC.xlsx" if os.path.exists("OC.xlsx") else "data/OC.xlsx"


def init_database():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            molecule_id TEXT PRIMARY KEY,
            leitner_box INTEGER DEFAULT 1,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('leitner_mode', 'Normal')")
    cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('current_streak', '0')")
    cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('longest_streak', '0')")
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM progress")
    count = cursor.fetchone()[0]

    if count == 0 and os.path.exists(EXCEL_PATH):
        df = pd.read_excel(EXCEL_PATH)
        for _, row in df.iterrows():
            mol_id = str(row.get("ID"))
            cursor.execute("INSERT OR IGNORE INTO progress (molecule_id, leitner_box) VALUES (?, 1)", (mol_id,))
        conn.commit()
    conn.close()


def get_setting(key, default=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE app_settings SET value = ? WHERE key = ?", (str(value), key))
    conn.commit()
    conn.close()


def reset_progress():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE progress SET leitner_box = 1, correct_count = 0, wrong_count = 0")
    cursor.execute("UPDATE app_settings SET value = '0' WHERE key IN ('current_streak', 'longest_streak')")
    conn.commit()
    conn.close()


def record_answer(mol_id, is_correct):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT leitner_box, correct_count, wrong_count FROM progress WHERE molecule_id = ?", (mol_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    box, correct, wrong = row
    current_streak = int(get_setting("current_streak", "0"))
    longest_streak = int(get_setting("longest_streak", "0"))

    if is_correct:
        new_box = min(5, box + 1)
        correct += 1
        current_streak += 1
        if current_streak > longest_streak:
            longest_streak = current_streak
    else:
        new_box = 1
        wrong += 1
        current_streak = 0

    cursor.execute("UPDATE progress SET leitner_box = ?, correct_count = ?, wrong_count = ? WHERE molecule_id = ?",
                   (new_box, correct, wrong, mol_id))
    conn.commit()
    conn.close()

    set_setting("current_streak", current_streak)
    set_setting("longest_streak", longest_streak)


def pluralize_class(class_name):
    mapping = {
        "Alkan": "Alkane", "Cycloalkan": "Cycloalkane", "Alken": "Alkene",
        "Alkin": "Alkine", "Aromat": "Aromaten",
        "Halogenierte Kohlenwasserstoffe": "Halogenierte Kohlenwasserstoffe",
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
    return mapping.get(class_name, class_name + "e")


def get_molecules_by_classes(selected_plural_classes):
    if not os.path.exists(EXCEL_PATH):
        return []
    df = pd.read_excel(EXCEL_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    molecules = []
    for _, row in df.iterrows():
        raw_cls = row.get("Verbindungsklasse")
        if pd.isna(raw_cls): continue
        converted_cls = pluralize_class(raw_cls)

        if converted_cls in selected_plural_classes:
            m_id = str(row.get("ID"))
            cursor.execute("SELECT leitner_box, (correct_count + wrong_count) FROM progress WHERE molecule_id = ?",
                           (m_id,))
            res = cursor.fetchone()
            box = res[0] if res else 1
            total_answered_mol = res[1] if res else 0

            molecules.append({
                "id": m_id,
                "name": str(row.get("Primärname")).strip(),
                "class": converted_cls,
                "smiles": str(row.get("SMILES")).strip(),
                "box": box,
                "total_answered": total_answered_mol
            })
    conn.close()

    unseen_mols = [m for m in molecules if m['total_answered'] == 0]
    seen_mols = [m for m in molecules if m['total_answered'] > 0]
    random.shuffle(unseen_mols)

    mode = get_setting("leitner_mode", "Normal")
    probs = {
        "Entspannt": {1: 1.0, 2: 0.50, 3: 0.25, 4: 0.10, 5: 0.05},
        "Normal": {1: 1.0, 2: 0.75, 3: 0.50, 4: 0.25, 5: 0.10},
        "Intensiv": {1: 1.0, 2: 1.0, 3: 0.75, 4: 0.50, 5: 0.25},
        "Extrem": {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.75, 5: 0.50}
    }
    mode_probs = probs.get(mode, probs["Normal"])

    filtered_seen = [mol for mol in seen_mols if random.random() <= mode_probs.get(mol['box'], 1.0)]
    filtered_seen.sort(key=lambda x: (x['box'], random.random()))
    final_pool = unseen_mols + filtered_seen

    if not final_pool and molecules:
        final_pool = list(molecules)
        random.shuffle(final_pool)

    return final_pool


def mol_to_bytes(smiles, size=(400, 250)):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        img = Draw.MolToImage(mol, size=size)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    return None


# --- STREAMLIT SETUP ---
st.set_page_config(page_title="Organische Chemie - Lernapp", layout="centered")
init_database()

if "page" not in st.session_state:
    st.session_state.page = "menu"
if "quiz_mols" not in st.session_state:
    st.session_state.quiz_mols = []
if "curr_idx" not in st.session_state:
    st.session_state.curr_idx = 0
if "checked" not in st.session_state:
    st.session_state.checked = False

# --- SEITEN-ROUTING ---
if st.session_state.page == "menu":
    st.title("Organische Chemie - Lernapp")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Statistiken anzeigen", use_container_width=True):
            st.session_state.page = "stats"
            st.rerun()
    with col_s2:
        if st.button("Einstellungen anzeigen", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

    st.write("---")
    st.subheader("Wähle deine Verbindungsklassen & Modus")

    df = pd.read_excel(EXCEL_PATH) if os.path.exists(EXCEL_PATH) else pd.DataFrame()
    raw_classes = df["Verbindungsklasse"].dropna().unique().tolist() if "Verbindungsklasse" in df.columns else []
    available_classes = sorted(list(set([pluralize_class(c) for c in raw_classes])))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Alle auswählen"):
            st.session_state.select_all_state = True
    with col2:
        if st.button("Alle abwählen"):
            st.session_state.select_all_state = False

    default_val = st.session_state.get("select_all_state", True)

    class_checkboxes = {}
    for cls_name in available_classes:
        class_checkboxes[cls_name] = st.checkbox(cls_name, value=default_val)

    mode = st.selectbox("Lern-Modus:", [
        "Auswahl-Modus (Name -> Strukturformel)",
        "Auswahl-Modus (Strukturformel -> Name)",
        "Schwerer Kachel-Modus (ganzes Wort)",
        "Tastatur-Modus (freies Tippen)"
    ])

    if st.button("Lernen starten", type="primary", use_container_width=True):
        selected_classes = [name for name, checked in class_checkboxes.items() if checked]
        if not selected_classes:
            st.warning("Bitte wähle mindestens eine Verbindungsklasse aus!")
        else:
            mols = get_molecules_by_classes(selected_classes)
            if not mols:
                st.warning("Keine Moleküle für diese Auswahl gefunden!")
            else:
                st.session_state.quiz_mols = mols
                st.session_state.curr_idx = 0
                st.session_state.mode = mode
                st.session_state.checked = False
                st.session_state.page = "quiz"
                st.rerun()

elif st.session_state.page == "stats":
    st.title("Deine Statistiken")
    if st.button("Zurück zum Hauptmenü"):
        st.session_state.page = "menu"
        st.rerun()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(correct_count), SUM(wrong_count) FROM progress")
    row = cursor.fetchone()
    total_correct = row[0] or 0
    total_wrong = row[1] or 0
    total_answered = total_correct + total_wrong
    rate = round((total_correct / total_answered * 100) if total_answered > 0 else 0, 1)

    st.write(f"**Beantwortete Fragen:** {total_answered}")
    st.write(f"**Richtige Antworten:** {total_correct}")
    st.write(f"**Falsche Antworten:** {total_wrong}")
    st.write(f"**Erfolgsquote:** {rate}%")
    st.write(f"**Aktuelle Serie:** {get_setting('current_streak', '0')}")
    st.write(f"**Längste Serie:** {get_setting('longest_streak', '0')}")

    st.subheader("Problematischste Verbindungen")
    cursor.execute("""
        SELECT molecule_id, correct_count, wrong_count, leitner_box
        FROM progress WHERE (correct_count + wrong_count) > 2 AND leitner_box <= 2
        ORDER BY (CAST(wrong_count AS FLOAT) / (correct_count + wrong_count)) DESC LIMIT 5
    """)
    prob_rows = cursor.fetchall()
    df_excel = pd.read_excel(EXCEL_PATH) if os.path.exists(EXCEL_PATH) else pd.DataFrame()
    if prob_rows:
        for pr in prob_rows:
            m_data = df_excel[df_excel['ID'].astype(str) == str(pr[0])]
            if not m_data.empty:
                name = m_data.iloc[0]['Primärname']
                err_rate = round((pr[2] / (pr[1] + pr[2])) * 100, 1)
                st.write(f"- {name} (Fehlerrate: {err_rate}%, Box {pr[3]})")
    else:
        st.write("Noch keine Problem-Fälle erfasst.")
    conn.close()

elif st.session_state.page == "settings":
    st.title("Einstellungen")
    if st.button("Zurück zum Hauptmenü"):
        st.session_state.page = "menu"
        st.rerun()

    current_mode = get_setting("leitner_mode", "Normal")
    new_mode = st.selectbox("Leitner-Wiederholungsmodus:", ["Entspannt", "Normal", "Intensiv", "Extrem"],
                            index=["Entspannt", "Normal", "Intensiv", "Extrem"].index(current_mode))
    if new_mode != current_mode:
        set_setting("leitner_mode", new_mode)
        st.success("Modus aktualisiert!")

    st.write("---")
    if st.button("Lernfortschritt komplett zurücksetzen", type="primary"):
        reset_progress()
        st.success("Dein Lernfortschritt wurde auf Null gesetzt.")

elif st.session_state.page == "quiz":
    if st.button("Zurück zum Hauptmenü"):
        st.session_state.page = "menu"
        st.session_state.checked = False
        st.rerun()

    mols = st.session_state.quiz_mols
    idx = st.session_state.curr_idx

    if idx >= len(mols):
        st.success("Du hast alle Moleküle dieser Runde durchgearbeitet!")
        if st.button("Nochmal von vorne starten"):
            random.shuffle(mols)
            st.session_state.curr_idx = 0
            st.session_state.checked = False
            st.rerun()
    else:
        current_mol = mols[idx]
        mode = st.session_state.mode
        st.write(f"**Frage {idx + 1} von {len(mols)}** | Klasse: {current_mol['class']}")

        # Stabile Daten pro Frage cachen
        if "quiz_question_idx" not in st.session_state or st.session_state.quiz_question_idx != idx:
            st.session_state.quiz_question_idx = idx
            st.session_state.checked = False
            st.session_state.user_tile_guess = []

            # Distraktoren generieren
            df_all = pd.read_excel(EXCEL_PATH) if os.path.exists(EXCEL_PATH) else pd.DataFrame()
            all_pool = []
            for _, r in df_all.iterrows():
                if not pd.isna(r.get("Primärname")) and not pd.isna(r.get("SMILES")):
                    all_pool.append({
                        "id": str(r.get("ID")),
                        "name": str(r.get("Primärname")).strip(),
                        "class": pluralize_class(r.get("Verbindungsklasse")) if not pd.isna(
                            r.get("Verbindungsklasse")) else "",
                        "smiles": str(r.get("SMILES")).strip()
                    })

            same_cls = [m for m in all_pool if m['class'] == current_mol['class'] and m['id'] != current_mol['id']]
            other_cls = [m for m in all_pool if m['class'] != current_mol['class'] and m['id'] != current_mol['id']]
            distractors = (same_cls + other_cls)[:3]
            choices = distractors + [current_mol]
            random.shuffle(choices)
            st.session_state.current_choices = choices

            # Kachel-Pool für schweren Modus vorbereiten
            target_word = current_mol['name']
            letters = [c.upper() for c in target_word if c.isalpha()]
            alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            while len(letters) < max(14, len(letters) + 4):
                letters.append(random.choice(alphabet))
            random.shuffle(letters)
            st.session_state.tile_pool = letters

        current_mol = mols[idx]
        target_name = current_mol['name']
        target_smiles = current_mol['smiles']

        # 1. Modus: Name -> Strukturformel
        if mode == "Auswahl-Modus (Name -> Strukturformel)":
            st.write(f"Gesucht ist die Strukturformel zu: **{target_name}**")
            choices = st.session_state.current_choices

            cols = st.columns(2)
            for i, choice_mol in enumerate(choices):
                img_bytes = mol_to_bytes(choice_mol['smiles'], size=(250, 150))
                with cols[i % 2]:
                    if img_bytes:
                        st.image(img_bytes, caption=f"Option {i + 1}")
                    if not st.session_state.checked:
                        if st.button(f"Wählen {i + 1}", key=f"mc_img_{idx}_{i}"):
                            st.session_state.checked = True
                            is_corr = (choice_mol['id'] == current_mol['id'])
                            record_answer(current_mol['id'], is_corr)
                            st.session_state.last_correct = is_corr
                            st.rerun()

        # 2. Modus: Strukturformel -> Name
        elif mode == "Auswahl-Modus (Strukturformel -> Name)":
            img_bytes = mol_to_bytes(target_smiles, size=(400, 250))
            if img_bytes:
                st.image(img_bytes, caption="Strukturformel")

            choices = st.session_state.current_choices
            for i, choice_mol in enumerate(choices):
                if not st.session_state.checked:
                    if st.button(choice_mol['name'], key=f"mc_txt_{idx}_{i}", use_container_width=True):
                        st.session_state.checked = True
                        is_corr = (choice_mol['id'] == current_mol['id'])
                        record_answer(current_mol['id'], is_corr)
                        st.session_state.last_correct = is_corr
                        st.rerun()

        # 3. Modus: Schwerer Kachel-Modus (ganzes Wort)
        elif mode == "Schwerer Kachel-Modus (ganzes Wort)":
            img_bytes = mol_to_bytes(target_smiles, size=(400, 250))
            if img_bytes:
                st.image(img_bytes, caption="Strukturformel")

            letters_only = "".join([c.upper() for c in target_name if c.isalpha()])

            # Anzeige des aktuellen Ratespiels
            display_str = ""
            l_idx = 0
            guessed = st.session_state.user_tile_guess
            for char in target_name:
                if char.isalpha():
                    if l_idx < len(guessed):
                        display_str += guessed[l_idx]
                    else:
                        display_str += "_"
                    l_idx += 1
                else:
                    display_str += char

            st.markdown(f"### `{display_str}`")

            if not st.session_state.checked:
                cols = st.columns(7)
                for t_i, tile_char in enumerate(st.session_state.tile_pool):
                    if cols[t_i % 7].button(tile_char, key=f"tile_{idx}_{t_i}"):
                        if len(st.session_state.user_tile_guess) < len(letters_only):
                            st.session_state.user_tile_guess.append(tile_char)
                            st.rerun()

                c_undo, c_check = st.columns(2)
                with c_undo:
                    if st.button("Rückgängig"):
                        if st.session_state.user_tile_guess:
                            st.session_state.user_tile_guess.pop()
                            st.rerun()
                with c_check:
                    if st.button("Prüfen", type="primary"):
                        st.session_state.checked = True
                        user_word = "".join(st.session_state.user_tile_guess)
                        is_corr = (user_word == letters_only)
                        record_answer(current_mol['id'], is_corr)
                        st.session_state.last_correct = is_corr
                        st.rerun()

        # 4. Modus: Tastatur-Modus (freies Tippen)
        elif mode == "Tastatur-Modus (freies Tippen)":
            img_bytes = mol_to_bytes(target_smiles, size=(400, 250))
            if img_bytes:
                st.image(img_bytes, caption="Strukturformel")

            if not st.session_state.checked:
                user_input = st.text_input("Gib den Namen des Moleküls ein:", key=f"typed_{idx}")
                if st.button("Antwort prüfen"):
                    st.session_state.checked = True
                    is_corr = (user_input.strip().lower() == target_name.lower())
                    record_answer(current_mol['id'], is_corr)
                    st.session_state.last_correct = is_corr
                    st.rerun()

        # Feedback-Auswertung & Weiter-Button
        if st.session_state.checked:
            if st.session_state.last_correct:
                st.success("Richtig!")
            else:
                st.error(f"Falsch! Richtig wäre: **{target_name}**")

            if st.button("Nächstes Molekül", type="primary"):
                st.session_state.curr_idx += 1
                st.session_state.checked = False
                st.rerun()