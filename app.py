import streamlit as st
import datetime
import time
from modules.config import DATABASES
from modules.database import get_connection, run_query, run_transaction
from modules.auth import hash_password, check_password

# Konfiguracja Strony
st.set_page_config(page_title="System Biblioteczny", layout="wide", page_icon="📚")

# Inicjalizacja Sesji
if 'logged_in' not in st.session_state: 
    st.session_state.update({'logged_in': False, 'user_role': None, 'user_id': None, 'user_name': None})

# Panel Boczny - Wybór Węzła
st.sidebar.header("Węzeł Sieci")
selected_db_name = st.sidebar.selectbox("Serwer:", list(DATABASES.keys()))
current_filia_id = DATABASES[selected_db_name]["id"]

# Połączenie z Bazą
conn = get_connection(selected_db_name)
if not conn:
    st.stop()

st.title(f"System Biblioteczny - {selected_db_name}")
st.sidebar.info(f"Lokalne ID: {current_filia_id}")

# Widok Logowania
if not st.session_state['logged_in']:
    tab1, tab2 = st.tabs(["Logowanie", "Aktywacja Konta"])
    
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Hasło", type="password")
        if st.button("Zaloguj"):
            if email == "admin" and password == "admin":
                st.session_state.update({'logged_in': True, 'user_role': 'admin', 'user_name': 'Administrator'})
                st.rerun()
            else:
                sql = "SELECT id_czytelnika, imie, nazwisko, haslo FROM CZYTELNICY_CALOSC WHERE email = :1"
                users = run_query(conn, sql, [email])
                if not users.empty:
                    u = users.iloc[0]
                    if check_password(password, u['HASLO']):
                        st.session_state.update({'logged_in': True, 'user_role': 'reader', 'user_id': int(u['ID_CZYTELNIKA']), 'user_name': f"{u['IMIE']} {u['NAZWISKO']}"})
                        st.rerun()
                    else:
                        st.error("Błędne dane logowania.")
                else:
                    st.error("Nie znaleziono użytkownika.")

    with tab2:
        reg_email = st.text_input("Email rejestracyjny")
        p1 = st.text_input("Ustaw hasło", type="password")
        p2 = st.text_input("Powtórz hasło", type="password")
        
        if st.button("Aktywuj konto"):
            if p1 != p2:
                st.error("Hasła nie są identyczne.")
            else:
                res = run_query(conn, "SELECT id_czytelnika, id_filii FROM CZYTELNICY_CALOSC WHERE email = :1", [reg_email])
                if not res.empty:
                    uid, fid = int(res.iloc[0]['ID_CZYTELNIKA']), int(res.iloc[0]['ID_FILII'])
                    
                    # Wybór bazy docelowej
                    is_local = (fid == current_filia_id)
                    if current_filia_id == 1:
                        target = "CZYTELNICY" if is_local else "CZYTELNICY@filia2_link"
                    else:
                        target = "CZYTELNICY" if is_local else "CZYTELNICY@filia1_link"

                    success, msg = run_transaction(conn, [f"UPDATE {target} SET haslo = :1 WHERE id_czytelnika = :2"], [[hash_password(p1), uid]])
                    if success: st.success("Konto zostało aktywowane.")
                else:
                    st.warning("Nie znaleziono adresu email w rejestrze.")

# Główny Widok Aplikacji
else:
    st.sidebar.markdown(f"Użytkownik: **{st.session_state['user_name']}**")
    if st.sidebar.button("Wyloguj"):
        st.session_state['logged_in'] = False
        st.rerun()

    # PANEL CZYTELNIKA
    if st.session_state['user_role'] == 'reader':
        menu = st.radio("Nawigacja", ["Katalog", "Moje Wypożyczenia", "Rezerwacje"], horizontal=True)
        
        if menu == "Katalog":
            st.header("Katalog Książek")
            show_local = st.checkbox("Pokaż tylko książki dostępne lokalnie")
            
            base_sql = """
                SELECT k.id_ksiazki, k.tytul, a.nazwisko as autor, f.nazwa as filia, k.rok_wydania, k.status, k.id_filii
                FROM KSIAZKI_CALOSC k
                JOIN AUTORZY a ON k.id_autora = a.id_autora
                JOIN FILIE f ON k.id_filii = f.id_filii
                WHERE k.status = 'dostępna'
            """
            if show_local:
                base_sql += f" AND k.id_filii = {current_filia_id}"
            
            df = run_query(conn, base_sql)
            
            for _, row in df.iterrows():
                with st.expander(f"{row['TYTUL']} ({row['AUTOR']})"):
                    st.write(f"Rok: {row['ROK_WYDANIA']} | Lokalizacja: {row['FILIA']}")
                    if st.button("Rezerwuj", key=f"r_{row['ID_KSIAZKI']}"):
                        bid, fid, uid = row['ID_KSIAZKI'], int(row['ID_FILII']), st.session_state['user_id']
                        
                        is_local = (fid == current_filia_id)
                        if current_filia_id == 1:
                            suffix = "" if is_local else "@filia2_link"
                            seq = "rezerwacje_seq_f1.NEXTVAL" if is_local else "rezerwacje_seq_f2.NEXTVAL@filia2_link"
                        else:
                            suffix = "" if is_local else "@filia1_link"
                            seq = "rezerwacje_seq_f2.NEXTVAL" if is_local else "rezerwacje_seq_f1.NEXTVAL@filia1_link"

                        success, msg = run_transaction(conn, 
                            [f"UPDATE KSIAZKI{suffix} SET status = 'zarezerwowana' WHERE id_ksiazki = :1",
                             f"INSERT INTO REZERWACJE{suffix} (id_rezerwacji, id_ksiazki, id_czytelnika, id_filii_ksiazki) VALUES ({seq}, :1, :2, :3)"],
                            [[bid], [bid, uid, fid]])
                        
                        if success: 
                            st.success("Zarezerwowano pomyślnie.")
                            time.sleep(1)
                            st.rerun()
                        else: 
                            st.error(msg)

        elif menu == "Moje Wypożyczenia":
            st.header("Aktywne Wypożyczenia")
            st.dataframe(run_query(conn, f"SELECT k.tytul, w.data_wypozyczenia, w.data_plan_zwrotu FROM V_AKTUALNE_WYPOZYCZENIA w JOIN KSIAZKI_CALOSC k ON w.id_ksiazki = k.id_ksiazki WHERE w.id_czytelnika = {st.session_state['user_id']}"), use_container_width=True)
        
        elif menu == "Rezerwacje":
            st.header("Moje Rezerwacje")
            st.dataframe(run_query(conn, f"SELECT k.tytul, r.data_rezerwacji, r.waznosc_do FROM REZERWACJE_CALOSC r JOIN KSIAZKI_CALOSC k ON r.id_ksiazki = k.id_ksiazki WHERE r.id_czytelnika = {st.session_state['user_id']} AND r.status='aktywna'"), use_container_width=True)

    # PANEL ADMINISTRATORA
    elif st.session_state['user_role'] == 'admin':
        admin_menu = st.radio("Zarządzanie", ["Wypożycz", "Zwróć", "Wprowadzanie Danych", "Raporty"], horizontal=True)

        if admin_menu == "Wypożycz":
            st.subheader("Proces Wypożyczenia")
            mode = st.selectbox("Tryb", ["Standardowy", "Z Rezerwacji"])
            
            if mode == "Z Rezerwacji":
                sql = """
                    SELECT r.id_rezerwacji, k.tytul, c.nazwisko, r.id_ksiazki, r.id_czytelnika, r.id_filii_ksiazki
                    FROM REZERWACJE_CALOSC r
                    JOIN KSIAZKI_CALOSC k ON r.id_ksiazki = k.id_ksiazki
                    JOIN CZYTELNICY_CALOSC c ON r.id_czytelnika = c.id_czytelnika
                    WHERE r.status = 'aktywna'
                """
                rez_df = run_query(conn, sql)
                if not rez_df.empty:
                    sel = st.selectbox("Wybierz Rezerwację", rez_df.index, format_func=lambda x: f"{rez_df.iloc[x]['NAZWISKO']} - {rez_df.iloc[x]['TYTUL']}")
                    d = rez_df.iloc[sel]
                    r_date = st.date_input("Data Zwrotu", datetime.date.today() + datetime.timedelta(days=30))
                    
                    if st.button("Zatwierdź Wypożyczenie"):
                        fid = int(d['ID_FILII_KSIAZKI'])
                        is_local = (fid == current_filia_id)
                        
                        if current_filia_id == 1:
                            suffix = "" if is_local else "@filia2_link"
                            seq = "wypozyczenia_seq_f1.NEXTVAL" if is_local else "wypozyczenia_seq_f2.NEXTVAL@filia2_link"
                        else:
                            suffix = "" if is_local else "@filia1_link"
                            seq = "wypozyczenia_seq_f2.NEXTVAL" if is_local else "wypozyczenia_seq_f1.NEXTVAL@filia1_link"

                        success, msg = run_transaction(conn, 
                            [f"UPDATE REZERWACJE{suffix} SET status = 'zrealizowana' WHERE id_rezerwacji = :1",
                             f"UPDATE KSIAZKI{suffix} SET status = 'wypożyczona' WHERE id_ksiazki = :1",
                             f"INSERT INTO WYPOZYCZENIA{suffix} (id_wypozyczenia, id_ksiazki, id_czytelnika, data_plan_zwrotu, id_filii_ksiazki) VALUES ({seq}, :1, :2, :3, :4)"],
                            [[int(d['ID_REZERWACJI'])], [int(d['ID_KSIAZKI'])], [int(d['ID_KSIAZKI']), int(d['ID_CZYTELNIKA']), r_date, fid]])
                        
                        if success: st.success("Wypożyczenie zakończone."); time.sleep(1); st.rerun()
                        else: st.error(msg)
                else:
                    st.info("Brak aktywnych rezerwacji.")
            
            else: # Standard
                c1, c2 = st.columns(2)
                bks = run_query(conn, "SELECT id_ksiazki, tytul, id_filii FROM KSIAZKI_CALOSC WHERE status='dostępna'")
                rds = run_query(conn, "SELECT id_czytelnika, nazwisko FROM CZYTELNICY_CALOSC")
                
                bk_idx = c1.selectbox("Książka", bks.index, format_func=lambda x: bks.iloc[x]['TYTUL']) if not bks.empty else None
                rd_idx = c2.selectbox("Czytelnik", rds.index, format_func=lambda x: rds.iloc[x]['NAZWISKO']) if not rds.empty else None
                r_date = st.date_input("Data Zwrotu", datetime.date.today() + datetime.timedelta(days=30))

                if st.button("Zatwierdź") and bk_idx is not None:
                    bd, rd = bks.iloc[bk_idx], rds.iloc[rd_idx]
                    fid = int(bd['ID_FILII'])
                    is_local = (fid == current_filia_id)
                    
                    if current_filia_id == 1:
                        suffix = "" if is_local else "@filia2_link"
                        seq = "wypozyczenia_seq_f1.NEXTVAL" if is_local else "wypozyczenia_seq_f2.NEXTVAL@filia2_link"
                    else:
                        suffix = "" if is_local else "@filia1_link"
                        seq = "wypozyczenia_seq_f2.NEXTVAL" if is_local else "wypozyczenia_seq_f1.NEXTVAL@filia1_link"

                    success, msg = run_transaction(conn, 
                        [f"UPDATE KSIAZKI{suffix} SET status = 'wypożyczona' WHERE id_ksiazki = :1",
                         f"INSERT INTO WYPOZYCZENIA{suffix} (id_wypozyczenia, id_ksiazki, id_czytelnika, data_plan_zwrotu, id_filii_ksiazki) VALUES ({seq}, :1, :2, :3, :4)"],
                        [[int(bd['ID_KSIAZKI'])], [int(bd['ID_KSIAZKI']), int(rd['ID_CZYTELNIKA']), r_date, fid]])
                    
                    if success: st.success("Wypożyczenie zakończone."); time.sleep(1); st.rerun()
                    else: st.error(msg)

        elif admin_menu == "Zwróć":
            st.subheader("Proces Zwrotu")
            
            rents = run_query(conn, "SELECT * FROM V_AKTUALNE_WYPOZYCZENIA")
            if not rents.empty:
                sel = st.selectbox("Aktywne Wypożyczenie", rents.index, format_func=lambda x: f"{rents.iloc[x]['TYTUL']} ({rents.iloc[x]['CZYTELNIK']}) - Właściciel: {rents.iloc[x]['FILIA_KSIAZKI']}")
                d = rents.iloc[sel]
                
                if st.button("Zatwierdź Zwrot"):
                    det = run_query(conn, f"SELECT id_ksiazki, id_filii_ksiazki FROM WYPOZYCZENIA_CALOSC WHERE id_wypozyczenia = {d['ID_WYPOZYCZENIA']}")
                    if not det.empty:
                        fid = int(det.iloc[0]['ID_FILII_KSIAZKI'])
                        if fid == 1:
                            is_local = selected_db_name.startswith("FILIA 1")
                            suffix = "" if is_local else "@filia1_link"
                        else:
                            is_local = selected_db_name.startswith("FILIA 2")
                            suffix = "" if is_local else "@filia2_link"
                        
                        success, msg = run_transaction(conn,
                            [f"UPDATE KSIAZKI{suffix} SET status = 'dostępna' WHERE id_ksiazki = :1",
                             f"UPDATE WYPOZYCZENIA{suffix} SET data_zwrotu = SYSDATE WHERE id_wypozyczenia = :1"],
                            [[int(det.iloc[0]['ID_KSIAZKI'])], [int(d['ID_WYPOZYCZENIA'])]])
                        
                        if success: st.success("Zwrot przetworzony."); time.sleep(1); st.rerun()
                        else: st.error(msg)
            else: st.info("Brak aktywnych wypożyczeń.")

        elif admin_menu == "Wprowadzanie Danych":
            st.header("Wprowadzanie Danych")
            t1, t2, t3 = st.tabs(["Książka", "Czytelnik", "Autor"])
            
            with t1:
                with st.form("b_form"):
                    tt = st.text_input("Tytuł")
                    yr = st.number_input("Rok", 1900, 2030, 2023)
                    aut_df = run_query(conn, "SELECT id_autora, nazwisko FROM AUTORZY ORDER BY nazwisko")
                    aut_dict = {r['NAZWISKO']: r['ID_AUTORA'] for _, r in aut_df.iterrows()}
                    autor = st.selectbox("Autor", list(aut_dict.keys())) if aut_dict else None
                    filia = st.selectbox("Fizyczna Lokalizacja", ["Filia 1 (Linux)", "Filia 2 (Windows)"])
                    
                    if st.form_submit_button("Dodaj Książkę"):
                        target_fid = 1 if "Linux" in filia else 2
                        is_local = (target_fid == current_filia_id)
                        
                        if current_filia_id == 1:
                            suffix = "" if is_local else "@filia1_link"
                            seq = f"ksiazki_seq_f1.NEXTVAL{suffix}" if target_fid == 1 else "ksiazki_seq_f2.NEXTVAL@filia2_link"
                        else:
                            suffix = "" if is_local else "@filia2_link"
                            seq = f"ksiazki_seq_f2.NEXTVAL{suffix}" if target_fid == 2 else "ksiazki_seq_f1.NEXTVAL@filia1_link"

                        success, msg = run_transaction(conn, 
                            [f"INSERT INTO KSIAZKI{suffix} (id_ksiazki, tytul, rok_wydania, id_autora, id_filii, status) VALUES ({seq}, :1, :2, :3, :4, 'dostępna')"],
                            [[tt, yr, aut_dict[autor], target_fid]])
                        if success: st.success("Dodano książkę."); 
                        else: st.error(msg)

            with t2:
                with st.form("c_form"):
                    nm = st.text_input("Imię"); sn = st.text_input("Nazwisko"); eml = st.text_input("Email"); pw = st.text_input("Hasło startowe", type="password")
                    filia = st.selectbox("Filia Macierzysta", ["Filia 1 (Linux)", "Filia 2 (Windows)"])
                    
                    if st.form_submit_button("Dodaj Czytelnika"):
                        target_fid = 1 if "Linux" in filia else 2
                        is_local = (target_fid == current_filia_id)
                        hashed = hash_password(pw)

                        if current_filia_id == 1:
                            suffix = "" if is_local else "@filia1_link"
                            seq = f"czytelnicy_seq_f1.NEXTVAL{suffix}" if target_fid == 1 else "czytelnicy_seq_f2.NEXTVAL@filia2_link"
                        else:
                            suffix = "" if is_local else "@filia2_link"
                            seq = f"czytelnicy_seq_f2.NEXTVAL{suffix}" if target_fid == 2 else "czytelnicy_seq_f1.NEXTVAL@filia1_link"

                        success, msg = run_transaction(conn,
                            [f"INSERT INTO CZYTELNICY{suffix} (id_czytelnika, imie, nazwisko, email, id_filii, haslo) VALUES ({seq}, :1, :2, :3, :4, :5)"],
                            [[nm, sn, eml, target_fid, hashed]])
                        if success: st.success("Dodano czytelnika."); 
                        else: st.error(msg)

            with t3:
                st.info("Replikacja aktywna: Autor zostanie dodany do obu węzłów.")
                with st.form("a_form"):
                    nm = st.text_input("Imię"); sn = st.text_input("Nazwisko")
                    if st.form_submit_button("Dodaj Autora"):
                        try:
                            id_src = "autorzy_seq_f1.NEXTVAL" if selected_db_name.startswith("FILIA 1") else "autorzy_seq_f1.NEXTVAL@filia1_link"
                            nid = int(run_query(conn, f"SELECT {id_src} FROM DUAL").iloc[0][0])
                            
                            if selected_db_name.startswith("FILIA 1"):
                                t1, t2 = "AUTORZY", "AUTORZY@filia2_link"
                            else:
                                t1, t2 = "AUTORZY", "AUTORZY@filia1_link"
                            
                            success, msg = run_transaction(conn, 
                                [f"INSERT INTO {t1} (id_autora, imie, nazwisko) VALUES (:1, :2, :3)",
                                 f"INSERT INTO {t2} (id_autora, imie, nazwisko) VALUES (:1, :2, :3)"],
                                [[nid, nm, sn], [nid, nm, sn]])
                            if success: st.success("Autor zreplikowany."); 
                            else: st.error(msg)
                        except Exception as e: st.error(f"Błąd: {e}")

        elif admin_menu == "Raporty":
            st.header("Raporty Globalne")
            t1, t2, t3, t4 = st.tabs(["Aktywne Wypożyczenia", "Historia", "Czytelnicy", "Książki"])
            
            with t1:
                st.dataframe(run_query(conn, "SELECT * FROM V_AKTUALNE_WYPOZYCZENIA"), use_container_width=True)
            
            with t2:
                st.dataframe(run_query(conn, "SELECT w.id_wypozyczenia, k.tytul, c.nazwisko, w.data_wypozyczenia, w.data_zwrotu FROM WYPOZYCZENIA_CALOSC w JOIN KSIAZKI_CALOSC k ON w.id_ksiazki=k.id_ksiazki JOIN CZYTELNICY_CALOSC c ON w.id_czytelnika=c.id_czytelnika ORDER BY w.data_wypozyczenia DESC"), use_container_width=True)
            
            with t3:
                st.dataframe(run_query(conn, "SELECT c.imie, c.nazwisko, c.email, f.nazwa as filia FROM CZYTELNICY_CALOSC c JOIN FILIE f ON c.id_filii=f.id_filii"), use_container_width=True)
            
            with t4:
                df = run_query(conn, "SELECT k.tytul, a.nazwisko as autor, k.rok_wydania, k.status, f.nazwa as lokalizacja FROM KSIAZKI_CALOSC k JOIN AUTORZY a ON k.id_autora=a.id_autora JOIN FILIE f ON k.id_filii=f.id_filii")
                def color_status(val):
                    colors = {'dostępna': '#d4edda', 'wypożyczona': '#f8d7da', 'zarezerwowana': '#fff3cd'}
                    return f'background-color: {colors.get(val, "white")}; color: black'
                st.dataframe(df.style.map(color_status, subset=['STATUS']), use_container_width=True)

conn.close()