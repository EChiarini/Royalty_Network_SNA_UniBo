import pickle
import math
import re
import networkx as nx


# ==================================================
# 1. PARSING E FILTRAGGIO TEMPORALE
# ==================================================

def parse_year(val):
    """Estrae l'anno come intero da vari tipi di dato."""
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
    """Verifica se l'individuo è stato in vita nell'intervallo [start_year, end_year]."""
    birth = parse_year(node_data.get("birth"))
    death = parse_year(node_data.get("death"))

    if birth is None:
        return False
    if death is None:
        death = default_current_year

    return (birth <= end_year) and (death >= start_year)


def is_valid_house(val):
    """Verifica la validità dell'attributo house."""
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]


# ==================================================
# 2. CALCOLO METRICHE SMALL-WORLD (GCC)
# ==================================================

def compute_small_world_metrics(G_sub, label=""):
    """
    Estrae la Componente Gigante Connessa (GCC) e calcola:
    - Clustering locale medio (C) e Transitività globale
    - Distanza media dei cammini minimi (L) e Diametro
    - Baseline casuali Erdős-Rényi (C_rand, L_rand)
    - Coefficiente di Small-Worldness (sigma)
    """
    if G_sub.number_of_nodes() < 4 or G_sub.number_of_edges() < 3:
        print(f"  [{label}] ⚠️ Troppi pochi nodi/archi per l'analisi Small-World.")
        return

    # Convertiamo in grafo non orientato semplice
    G_undirected = nx.Graph(G_sub)

    # Estrazione della Giant Connected Component (GCC)
    gcc_nodes = max(nx.connected_components(G_undirected), key=len)
    G_gcc = G_undirected.subgraph(gcc_nodes).copy()

    n_gcc = G_gcc.number_of_nodes()
    e_gcc = G_gcc.number_of_edges()
    avg_k = (2.0 * e_gcc) / n_gcc

    if n_gcc < 4 or avg_k <= 1.0:
        print(f"  [{label}] ⚠️ La GCC è troppo piccola o scarsamente connessa (grado medio <= 1).")
        return

    # 1. Clustering reale (C) e Distanza media reale (L)
    C_obs = nx.average_clustering(G_gcc)
    L_obs = nx.average_shortest_path_length(G_gcc)
    diameter = nx.diameter(G_gcc)

    # 2. Baseline Casuale Teorica (Erdős–Rényi G(N, p))
    C_rand = avg_k / (n_gcc - 1)

    # Approssimazione teorica L_rand = ln(N) / ln(<k>)
    if avg_k > 1.0:
        L_rand = math.log(n_gcc) / math.log(avg_k)
    else:
        L_rand = L_obs

    # 3. Calcolo del Coefficiente di Small-Worldness (Sigma)
    gamma = C_obs / C_rand if C_rand > 0 else 0.0  # Arricchimento di clustering
    lambda_ratio = L_obs / L_rand if L_rand > 0 else 1.0  # Ratio di cammino medio
    sigma = gamma / lambda_ratio if lambda_ratio > 0 else 0.0

    print(f"\n  🌐 [{label}]")
    print(
        f"   • Nodi Totali Sottografo: {G_undirected.number_of_nodes()} | Nodi nella GCC: {n_gcc} ({n_gcc / G_undirected.number_of_nodes() * 100:.1f}%)")
    print(f"   • Archi GCC: {e_gcc} | Grado Medio <k>: {avg_k:.2f}")
    print(f"   -------------------------------------------------------------------------")
    print(f"   • Clustering Medio Reale (C):         {C_obs:.4f}")
    print(f"   • Clustering Casuale Teorico (C_rand): {C_rand:.6f}  (Rapporto C/C_rand = {gamma:.2f}x)")
    print(f"   • Distanza Media Reale (L):            {L_obs:.4f}  (Diametro = {diameter})")
    print(f"   • Distanza Media Casuale (L_rand):     {L_rand:.4f}  (Rapporto L/L_rand = {lambda_ratio:.2f}x)")
    print(f"   -------------------------------------------------------------------------")
    print(f"   • COEFFICIENTE SMALL-WORLDNESS (σ):    {sigma:.4f}")

    if sigma > 1.0:
        print("   -> ESITO: PROPRIETÀ SMALL-WORLD CONFERMATA (σ > 1). La rete mostra alto clustering e cammini brevi.")
    else:
        print("   -> ESITO: PROPRIETÀ SMALL-WORLD NON PRESENTE (σ <= 1).")


# ==================================================
# 3. ANALISI TEMPORALE ED INTEGRATA
# ==================================================

def analyze_small_world_full_and_temporal(G, start_year=2000, min_year=1450, step=50):
    """Esegue l'analisi Small-World sulla rete globale, su finestre di 50 anni e sul grafo delle Casate."""

    # ----------------------------------------------------
    # A. GRAFO GLOBALE INDIVIDUI (Blood + Marriage)
    # ----------------------------------------------------
    G_global_combined = nx.Graph()
    for u, v, d in G.edges(data=True):
        G_global_combined.add_node(u, **G.nodes[u])
        G_global_combined.add_node(v, **G.nodes[v])
        G_global_combined.add_edge(u, v)

    print("\n==================================================================================")
    print("  1. ANALISI SMALL-WORLD SULL'INTERA RETE GLOBALE DEGLI INDIVIDUI (1450 - OGGI)")
    print("==================================================================================")
    compute_small_world_metrics(G_global_combined, label="Rete Globale Individui (Blood + Marriage)")

    # ----------------------------------------------------
    # B. GRAFO CONTRATTO DELLE CASATE (House Aggregation)
    # ----------------------------------------------------
    G_house = nx.Graph()
    for u, v, data in G.edges(data=True):
        h_u = G.nodes[u].get("house")
        h_v = G.nodes[v].get("house")
        if is_valid_house(h_u) and is_valid_house(h_v) and str(h_u).strip() != str(h_v).strip():
            G_house.add_edge(str(h_u).strip(), str(h_v).strip())

    print("\n==================================================================================")
    print("  2. ANALISI SMALL-WORLD SUL GRAFO CONTRATTO DELLE CASATE (House Network)")
    print("==================================================================================")
    compute_small_world_metrics(G_house, label="Rete Contratta per Casata (Macro-Alleanze)")

    # ----------------------------------------------------
    # C. FINESTRE TEMPORALI DI 50 ANNI
    # ----------------------------------------------------
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print("\n==================================================================================")
    print(f"  3. ANALISI SMALL-WORLD PER FINESTRE TEMPORALI DI {step} ANNI")
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
            compute_small_world_metrics(G_win, label=f"Finestra Temporale {start_w}-{end_w}")


# ==================================================
# 4. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Percorso del file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        analyze_small_world_full_and_temporal(G, start_year=2000, min_year=1450, step=50)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")