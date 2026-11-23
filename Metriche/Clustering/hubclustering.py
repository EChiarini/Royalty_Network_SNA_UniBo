import pickle
import re
import networkx as nx
import pandas as pd

# ==================================================
# 1. PARSING E UTILITÀ TEMPORALI
# ==================================================

def parse_year(val):
    """Estrae l'anno come intero da attributi di vario tipo."""
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        match = re.search(r'(-?\d{3,4})', val_str)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def is_alive_in_range(node_data, start_year, end_year, default_current_year=2026):
    """Verifica se l'individuo è stato in vita durante la finestra [start_year, end_year]."""
    birth = parse_year(node_data.get("birth"))
    death = parse_year(node_data.get("death"))

    if birth is None:
        return False
    if death is None:
        death = default_current_year

    return (birth <= end_year) and (death >= start_year)

def is_monarch(node_data):
    """Estrae lo status booleano di regnante ('monarch')."""
    val = node_data.get("monarch")
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ["true", "1", "yes", "t"]
    return False

def get_node_label(node_id, node_data):
    """Genera un'etichetta leggibile per il nodo (Nome + Casata)."""
    name = node_data.get("name") or node_data.get("label") or str(node_id)
    house = node_data.get("house")
    if house and str(house).strip().lower() not in ["none", "unknown", "nan", ""]:
        return f"{name} ({house})"
    return str(name)

# ==================================================
# 2. CALCOLO FORI STRUTTURALI, RIDONDANZA ED EFFECTIVE SIZE
# ==================================================

def compute_node_brokerage_metrics(G_undirected):
    """
    Calcola per ciascun nodo:
    - Grado (d_i)
    - Clustering Locale (C_i)
    - Ridondanza (R_i = C_i * (d_i - 1))
    - Dimensione Effettiva (Effective Size ES_i = d_i - R_i)
    - Indice di Brokerage (Ratio ES_i / d_i = 1 - C_i * (d_i - 1) / d_i)
    """
    clustering_dict = nx.clustering(G_undirected)
    degree_dict = dict(G_undirected.degree())

    metrics = []

    for n in G_undirected.nodes():
        d_i = degree_dict[n]
        c_i = clustering_dict[n]

        # Per nodi con grado <= 1, la ridondanza è 0 e l'effective size equivale a d_i
        if d_i <= 1:
            r_i = 0.0
            es_i = float(d_i)
            brokerage_ratio = 1.0 if d_i == 1 else 0.0
        else:
            r_i = c_i * (d_i - 1)
            es_i = d_i - r_i
            brokerage_ratio = es_i / d_i  # Quanto più è vicino a 1.0, tanto minori sono le ridondanze nei vicini

        node_data = G_undirected.nodes[n]
        metrics.append({
            "node_id": n,
            "label": get_node_label(n, node_data),
            "house": node_data.get("house", "Unknown"),
            "is_monarch": is_monarch(node_data),
            "degree": d_i,
            "clustering_Ci": round(c_i, 4),
            "redundancy_Ri": round(r_i, 4),
            "effective_size_ESi": round(es_i, 4),
            "brokerage_ratio": round(brokerage_ratio, 4)
        })

    return pd.DataFrame(metrics)

# ==================================================
# 3. REPORTISTICA E CLASSIFICA DEI TOP BROKER
# ==================================================

def print_top_brokers(df_metrics, title="TOP BROKER MATRIMONIALI", top_n=10, min_degree=3):
    """
    Filtra i nodi con almeno min_degree vicini e li ordina per Dimensione Effettiva (ES_i).
    I nodi in cima alla classifica hanno molti legami e pochissimo clustering locale (fori strutturali).
    """
    df_filtered = df_metrics[df_metrics["degree"] >= min_degree].copy()
    df_sorted = df_filtered.sort_values(by=["effective_size_ESi", "degree"], ascending=[False, False])

    print(f"\n==================================================================================")
    print(f"  {title} (Grado minimo k >= {min_degree})")
    print(f"==================================================================================")

    if df_sorted.empty:
        print("⚠️ Nessun nodo soddisfa i criteri di grado minimo.")
        return

    top_df = df_sorted.head(top_n)[["label", "is_monarch", "degree", "clustering_Ci", "redundancy_Ri", "effective_size_ESi", "brokerage_ratio"]]
    top_df.columns = ["Individuo / Nodo", "Regnante", "Grado (k)", "Clustering (Ci)", "Ridondanza (Ri)", "Eff. Size (ESi)", "Broker Ratio"]

    print(top_df.to_string(index=False))

# ==================================================
# 4. ANALISI INTEGRATA GLOBALE E TEMPORALE
# ==================================================

def analyze_brokerage_full_and_temporal(G, start_year=2000, min_year=1450, step=50):
    """
    Esegue l'analisi di Brokerage e Structural Holes sia sull'intero grafo integrato
    sia segmentata per finestre temporali di 50 anni.
    """
    # ------------------------------------------------------------------
    # FASE 1: ANALISI SULL'INTERA RETE GLOBALE (Blood + Marriage)
    # ------------------------------------------------------------------
    G_global_combined = nx.Graph()
    for u, v, d in G.edges(data=True):
        G_global_combined.add_node(u, **G.nodes[u])
        G_global_combined.add_node(v, **G.nodes[v])
        G_global_combined.add_edge(u, v)

    print("\n==================================================================================")
    print("  1. FORI STRUTTURALI E BROKERAGE SULL'INTERA RETE GLOBALE (1450 - OGGI)")
    print("==================================================================================")

    df_global = compute_node_brokerage_metrics(G_global_combined)

    print_top_brokers(df_global, title="TOP 10 BROKER GLOBALI (Tutti gli Individui)", top_n=10, min_degree=4)
    print_top_brokers(df_global[df_global["is_monarch"] == True], title="TOP 10 BROKER TRA I REGNANTI (monarch == True)", top_n=10, min_degree=4)
    print_top_brokers(df_global[df_global["is_monarch"] == False], title="TOP 10 BROKER TRA I NON-REGNANTI (monarch == False)", top_n=10, min_degree=4)

    # ------------------------------------------------------------------
    # FASE 2: ANALISI PER FINESTRE TEMPORALI DI 50 ANNI
    # ------------------------------------------------------------------
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print("\n==================================================================================")
    print(f"  2. EVOLUZIONE TEMPORALE DEI BROKER MATRIMONIALI (Finestre di {step} anni)")
    print("==================================================================================")

    for start_w, end_w in time_windows:
        G_win = nx.Graph()

        for u, v, data in G.edges(data=True):
            node_u = G.nodes[u]
            node_v = G.nodes[v]

            if is_alive_in_range(node_u, start_w, end_w) and is_alive_in_range(node_v, start_w, end_w):
                G_win.add_node(u, **node_u)
                G_win.add_node(v, **node_v)
                G_win.add_edge(u, v)

        if G_win.number_of_edges() >= 5:
            df_win = compute_node_brokerage_metrics(G_win)
            print_top_brokers(df_win, title=f"TOP BROKER MATRIMONIALI (Periodo {start_w}-{end_w})", top_n=5, min_degree=3)

# ==================================================
# 5. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il percorso del tuo file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        analyze_brokerage_full_and_temporal(G, start_year=2000, min_year=1450, step=50)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")