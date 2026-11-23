import pickle
import re
import networkx as nx


# ==================================================
# 1. PARSING E FILTRAGGIO TEMPORALE
# ==================================================

def parse_year(val):
    """Estrae l'anno come intero da attributi di vario tipo (int, float, str)."""
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
    """Verifica se l'individuo è stato in vita per almeno un anno nell'intervallo [start_year, end_year]."""
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


# ==================================================
# 2. CALCOLO CLUSTERING CON BASELINE CASUALE (C_rand)
# ==================================================

def compute_clustering_with_random_baseline(G_sub, label=""):
    """
    Calcola C, <Ci>, C_rand e il rapporto C / C_rand per un grafo non orientato.
    """
    num_nodes = G_sub.number_of_nodes()
    num_edges = G_sub.number_of_edges()

    print(f"\n  📊 [{label}]")
    print(f"   • Nodi (N): {num_nodes} | Archi totali (E): {num_edges}")

    if num_nodes < 3 or num_edges < 2:
        print("   ⚠️ Nodi o archi insufficienti per un calcolo significativo.")
        return

    G_undirected = nx.Graph(G_sub)

    # 1. Clustering reale sulla rete (Transitività Globale C e Media del Clustering Locale <Ci>)
    global_C = nx.transitivity(G_undirected)
    avg_local_C = nx.average_clustering(G_undirected)

    # 2. Clustering casuale teorico C_rand (Erdős–Rényi G(n,p))
    # Grado medio <k> = 2E / N; C_rand ≈ <k> / (N - 1)
    avg_degree = (2.0 * num_edges) / num_nodes
    c_rand = avg_degree / (num_nodes - 1) if num_nodes > 1 else 0.0

    # 3. Rapporto di arricchimento C / C_rand
    ratio = (global_C / c_rand) if c_rand > 0 else 0.0

    print(f"   • Transitività Globale C:              {global_C:.4f}")
    print(f"   • Clustering Locale Medio <Ci>:         {avg_local_C:.4f}")
    print(f"   • Clustering Casuale Teorico C_rand:    {c_rand:.6f}  (Grado Medio <k> = {avg_degree:.2f})")
    print(f"   • Rapporto di Significatività C/C_rand: {ratio:.2f}x")

    if ratio > 5.0:
        print(
            "   -> ESITO: C >> C_rand (Chiusura triadica fortemente NON CASUALE: elevata endogamia/struttura familiare).")
    elif ratio > 1.2:
        print("   -> ESITO: C > C_rand (Modesta tendenza non casuale alla chiusura triadica).")
    else:
        print("   -> ESITO: C ≈ C_rand (La rete si comporta come un grafo casuale stocastico).")


# ==================================================
# 3. ANALISI INTEGRATA: INTERA RETE + FINESTRE TEMPORALI
# ==================================================

def analyze_full_and_temporal_clustering(G, start_year=2000, min_year=1450, step=50):
    """
    Esegue il calcolo di C, <Ci>, C_rand e C/C_rand sia sull'INTERA RETE GLOBALE (1450-Oggi)
    sia segmentata per FINESTRE TEMPORALI DI 50 ANNI.
    """

    # ------------------------------------------------------------------
    # FASE 1: ANALISI SULL'INTERA RETE GLOBALE (Senza filtri temporali)
    # ------------------------------------------------------------------
    print("\n==================================================================================")
    print("  1. ANALISI CLUSTERING SULL'INTERA RETE GLOBALE (1450 - OGGI)")
    print("==================================================================================")

    G_global_all = nx.Graph()
    G_global_both_monarchs = nx.Graph()
    G_global_at_least_one = nx.Graph()
    G_global_non_monarchs = nx.Graph()

    for u, v, data in G.edges(data=True):
        node_u = G.nodes[u]
        node_v = G.nodes[v]

        # Aggiunta di tutti gli archi alla rete non orientata globale
        G_global_all.add_node(u, **node_u)
        G_global_all.add_node(v, **node_v)
        G_global_all.add_edge(u, v)

        m_u = is_monarch(node_u)
        m_v = is_monarch(node_v)

        if m_u and m_v:
            G_global_both_monarchs.add_node(u, **node_u)
            G_global_both_monarchs.add_node(v, **node_v)
            G_global_both_monarchs.add_edge(u, v)

        if m_u or m_v:
            G_global_at_least_one.add_node(u, **node_u)
            G_global_at_least_one.add_node(v, **node_v)
            G_global_at_least_one.add_edge(u, v)

        if not m_u and not m_v:
            G_global_non_monarchs.add_node(u, **node_u)
            G_global_non_monarchs.add_node(v, **node_v)
            G_global_non_monarchs.add_edge(u, v)

    compute_clustering_with_random_baseline(G_global_all, label="INTERA RETE: Tutti i Matrimoni e Parentele")
    compute_clustering_with_random_baseline(G_global_both_monarchs, label="INTERA RETE: Entrambi Regnanti")
    compute_clustering_with_random_baseline(G_global_at_least_one, label="INTERA RETE: Almeno un Regnante")
    compute_clustering_with_random_baseline(G_global_non_monarchs, label="INTERA RETE: Entrambi Non Regnanti")

    # ------------------------------------------------------------------
    # FASE 2: ANALISI PER FINESTRE TEMPORALI DI 50 ANNI
    # ------------------------------------------------------------------
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print("\n==================================================================================")
    print(f"  2. ANALISI CLUSTERING PER FINESTRE TEMPORALI DI {step} ANNI")
    print("==================================================================================")

    for start_w, end_w in time_windows:
        print(f"\n📅 PERIODO STORICO: {start_w} - {end_w}")
        print(f"----------------------------------------------------------------------------------")

        G_all = nx.Graph()
        G_both_monarchs = nx.Graph()
        G_at_least_one = nx.Graph()
        G_non_monarchs = nx.Graph()

        for u, v, data in G.edges(data=True):
            node_u = G.nodes[u]
            node_v = G.nodes[v]

            if is_alive_in_range(node_u, start_w, end_w) and is_alive_in_range(node_v, start_w, end_w):
                G_all.add_node(u, **node_u)
                G_all.add_node(v, **node_v)
                G_all.add_edge(u, v)

                m_u = is_monarch(node_u)
                m_v = is_monarch(node_v)

                if m_u and m_v:
                    G_both_monarchs.add_node(u, **node_u)
                    G_both_monarchs.add_node(v, **node_v)
                    G_both_monarchs.add_edge(u, v)

                if m_u or m_v:
                    G_at_least_one.add_node(u, **node_u)
                    G_at_least_one.add_node(v, **node_v)
                    G_at_least_one.add_edge(u, v)

                if not m_u and not m_v:
                    G_non_monarchs.add_node(u, **node_u)
                    G_non_monarchs.add_node(v, **node_v)
                    G_non_monarchs.add_edge(u, v)

        if G_all.number_of_edges() == 0:
            print(f"⚠️ Nessun arco trovato nel periodo {start_w}-{end_w}.")
            continue

        compute_clustering_with_random_baseline(G_all, label=f"Tutti gli Archi ({start_w}-{end_w})")
        compute_clustering_with_random_baseline(G_both_monarchs, label=f"Entrambi Regnanti ({start_w}-{end_w})")
        compute_clustering_with_random_baseline(G_at_least_one, label=f"Almeno un Regnante ({start_w}-{end_w})")
        compute_clustering_with_random_baseline(G_non_monarchs, label=f"Entrambi Non Regnanti ({start_w}-{end_w})")


# ==================================================
# 4. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Percorso del file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        analyze_full_and_temporal_clustering(G, start_year=2000, min_year=1450, step=50)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")