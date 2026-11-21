import pickle
import re
import networkx as nx

# ==================================================
# 1. FUNZIONI DI UTILITÀ E PARSING DELLE DATE
# ==================================================

def parse_year(val):
    """
    Estrae l'anno come intero da attributi di vario tipo (int, float, str).
    Gestisce casi come '1948', 1948, '1948-11-14' o float.
    Ritorna None se il valore è assente o non valido.
    """
    if val is None:
        return None
    try:
        # Se è già un numero intero o float
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        # Cerca la prima sequenza di 3 o 4 cifre (es. '1948')
        match = re.search(r'(-?\d{3,4})', val_str)
        if match:
            return int(match.group(1))
        return None
    except Exception:
        return None

def is_alive_in_range(node_data, start_year, end_year, default_current_year=2026):
    """
    Verifica se il nodo è stato vivo per almeno un anno all'interno di [start_year, end_year].
    Un individuo è considerato vivo se: (birth <= end_year) AND (death >= start_year).
    Se la data di morte manca (nodo vivente/dato omesso), viene impostata all'anno attuale.
    """
    birth = parse_year(node_data.get("birth"))
    death = parse_year(node_data.get("death"))

    # Se la data di nascita è sconosciuta, non possiamo collocare l'individuo con certezza
    if birth is None:
        return False

    # Se la data di morte manca, assumiamo sia ancora in vita o deceduto recentemente
    if death is None:
        death = default_current_year

    # Condizione di sovrapposizione dell'intervallo di vita con la finestra temporale
    return (birth <= end_year) and (death >= start_year)

def is_valid_value(val):
    """
    Verifica che l'attributo categoriale (es. religion, birth_country) sia valido.
    """
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]

def is_monarch(node_data):
    """
    Estrae lo status booleano di regnante ('monarch').
    """
    val = node_data.get("monarch")
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ["true", "1", "yes", "t"]
    return False


# ==================================================
# 2. CALCOLO DELL'ASSORTATIVITÀ SU SOTTOGRAFI
# ==================================================

def compute_subgraph_assortativity(G_sub, attribute_name, label):
    """
    Calcola il coefficiente di assortatività (r) per un determinato sottografo.
    """
    num_edges = G_sub.number_of_edges()
    print(f"  [{label}]")
    print(f"   • Matrimoni analizzati: {num_edges}")

    if num_edges < 2:
        print("   ⚠️ Matrimoni insufficienti per calcolare l'assortatività.")
        return None

    # Verifica la presenza di almeno 2 distinte categorie nell'attributo
    unique_attrs = set(nx.get_node_attributes(G_sub, attribute_name).values())
    if len(unique_attrs) <= 1:
        print(f"   ⚠️ Categoria unica trovata ({list(unique_attrs)}): assortatività non definibile.")
        return None

    try:
        r = nx.attribute_assortativity_coefficient(G_sub, attribute_name)
        print(f"   • Assortatività r ({attribute_name}): {r:.4f}")
        return r
    except Exception as e:
        print(f"   ❌ Errore durante il calcolo: {e}")
        return None


# ==================================================
# 3. ANALISI TEMPORALE SCORREVOLE (50 ANNI)
# ==================================================

def analyze_assortativity_temporal(G, attribute_name, start_year=2000, min_year=1450, step=50):
    """
    Segmenta la rete in archi temporali di 50 anni e calcola l'assortatività per ciascuna epoca
    e per ciascun sottogruppo (Tutti, Entrambi Regnanti, Almeno un Regnante, Non Regnanti).
    """
    # Generazione degli intervalli temporali: (1950, 2000), (1900, 1950), ..., (1450, 1500)
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print(f"\n==================================================================================")
    print(f"  ANALISI TEMPORALE DELL'ASSORTATIVITÀ PER: '{attribute_name}' (Finestre di {step} anni)")
    print(f"==================================================================================")

    for start_w, end_w in time_windows:
        print(f"\n📅 PERIODO STORICO: {start_w} - {end_w}")
        print(f"----------------------------------------------------------------------------------")

        # Inizializzazione dei grafi temporali per la finestra corrente
        G_all = nx.Graph()
        G_both_monarchs = nx.Graph()
        G_at_least_one_monarch = nx.Graph()
        G_non_monarchs = nx.Graph()

        total_window_marriages = 0

        for u, v, data in G.edges(data=True):
            edge_type = data.get("type") or data.get("relationship") or ""
            edge_str = str(edge_type).lower()

            if edge_str == "marriage" or edge_str == "blood_&_marriage":
                node_u_data = G.nodes[u]
                node_v_data = G.nodes[v]

                # CONDIZIONE 1: Entrambi i coniugi devono avere l'attributo valido
                attr_u = node_u_data.get(attribute_name)
                attr_v = node_v_data.get(attribute_name)

                if is_valid_value(attr_u) and is_valid_value(attr_v):

                    # CONDIZIONE 2: Entrambi i coniugi devono essere stati vivi durante il periodo [start_w, end_w]
                    if is_alive_in_range(node_u_data, start_w, end_w) and is_alive_in_range(node_v_data, start_w, end_w):
                        total_window_marriages += 1

                        val_u_str = str(attr_u).strip()
                        val_v_str = str(attr_v).strip()

                        # Aggiunta al grafo temporale generale
                        G_all.add_node(u, **{attribute_name: val_u_str})
                        G_all.add_node(v, **{attribute_name: val_v_str})
                        G_all.add_edge(u, v)

                        # Controllo status di regnante
                        m_u = is_monarch(node_u_data)
                        m_v = is_monarch(node_v_data)

                        # CASO A: Entrambi Regnanti
                        if m_u and m_v:
                            G_both_monarchs.add_node(u, **{attribute_name: val_u_str})
                            G_both_monarchs.add_node(v, **{attribute_name: val_v_str})
                            G_both_monarchs.add_edge(u, v)

                        # CASO B: Almeno un Regnante
                        if m_u or m_v:
                            G_at_least_one_monarch.add_node(u, **{attribute_name: val_u_str})
                            G_at_least_one_monarch.add_node(v, **{attribute_name: val_v_str})
                            G_at_least_one_monarch.add_edge(u, v)

                        # CASO C: Entrambi Non Regnanti
                        if not m_u and not m_v:
                            G_non_monarchs.add_node(u, **{attribute_name: val_u_str})
                            G_non_monarchs.add_node(v, **{attribute_name: val_v_str})
                            G_non_monarchs.add_edge(u, v)

        if total_window_marriages == 0:
            print(f"⚠️ Nessun matrimonio valido con entrambi i coniugi in vita nel periodo {start_w}-{end_w}.")
            continue

        # Calcolo dell'assortatività sui 4 gruppi per la finestra temporale attiva
        compute_subgraph_assortativity(G_all, attribute_name, "1. Tutti i Matrimoni Validi")
        compute_subgraph_assortativity(G_both_monarchs, attribute_name, "2. Entrambi Regnanti")
        compute_subgraph_assortativity(G_at_least_one_monarch, attribute_name, "3. Almeno un Regnante")
        compute_subgraph_assortativity(G_non_monarchs, attribute_name, "4. Entrambi Non Regnanti")


# ==================================================
# 4. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il percorso del tuo file .pkl

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        # 1. Analisi temporale per Religione
        analyze_assortativity_temporal(G, attribute_name="religion", start_year=2000, min_year=1450, step=50)

        # 2. Analisi temporale per Paese di Nascita
        analyze_assortativity_temporal(G, attribute_name="birth_country", start_year=2000, min_year=1450, step=50)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")
