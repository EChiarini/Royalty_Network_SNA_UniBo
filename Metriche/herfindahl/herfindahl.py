import pickle
import re
import networkx as nx
import pandas as pd


# ==================================================
# 1. FUNZIONI DI PARSING E FILTRAGGIO TEMPORALE
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


def get_max_spouses_birth(node_u_data, node_v_data):
    """
    Restituisce la maggiore data di nascita tra i due coniugi.
    Se entrambe mancano, restituisce None (nessun filtro applicabile).
    """
    b_u = parse_year(node_u_data.get("birth"))
    b_v = parse_year(node_v_data.get("birth"))

    if b_u is not None and b_v is not None:
        return max(b_u, b_v)
    elif b_u is not None:
        return b_u
    elif b_v is not None:
        return b_v
    return None


# ==================================================
# 2. CALCOLO CAMMINI MINIMI E INDICE HERFINDAHL
# ==================================================

def compute_herfindahl_index(distance_counts, total_pairs):
    """
    Calcola l'Indice di Herfindahl-Hirschman: HHI = sum(p_d ^ 2)
    dove p_d = count(d) / total_pairs.
    """
    if total_pairs == 0:
        return 0.0, {}

    hhi = 0.0
    proportions = {}

    for dist, count in distance_counts.items():
        p_d = count / total_pairs
        proportions[dist] = p_d
        hhi += p_d ** 2

    return hhi, proportions


def analyze_marriage_paths_and_herfindahl(G):
    """
    Per ogni coppia di matrimonio (u, v):
    - Determina T_max = max(birth_u, birth_v)
    - Esclude nodi con birth > T_max
    - Calcola la distanza minima in:
      Caso A: Soli archi 'blood'
      Caso B: Tutti gli archi (escludendo l'arco matrimoniale diretto u-v)
    """

    # Separazione preventiva dei grafi base
    G_blood_base = nx.Graph()
    G_all_base = nx.Graph()

    marriage_edges = []

    for u, v, data in G.edges(data=True):
        edge_type = str(data.get("type") or data.get("relationship") or "").lower()

        # Inserimento nei grafi di partenza
        if "blood" in edge_type:
            G_blood_base.add_node(u, **G.nodes[u])
            G_blood_base.add_node(v, **G.nodes[v])
            G_blood_base.add_edge(u, v)

        G_all_base.add_node(u, **G.nodes[u])
        G_all_base.add_node(v, **G.nodes[v])
        G_all_base.add_edge(u, v, **data)

        if "marriage" in edge_type:
            marriage_edges.append((u, v))

    print(f"• Coppie di matrimonio totali trovate: {len(marriage_edges)}")

    distances_blood = {}
    distances_all = {}

    processed_couples = 0

    for u, v in marriage_edges:
        node_u = G.nodes[u]
        node_v = G.nodes[v]

        t_max = get_max_spouses_birth(node_u, node_v)

        # ------------------------------------------------------------------
        # CASO A: SOLI ARCHI 'BLOOD'
        # ------------------------------------------------------------------
        # Filtriamo i nodi validi con birth <= t_max (se t_max è disponibile)
        if t_max is not None:
            valid_blood_nodes = [
                n for n in G_blood_base.nodes()
                if parse_year(G_blood_base.nodes[n].get("birth")) is None
                   or parse_year(G_blood_base.nodes[n].get("birth")) <= t_max
            ]
            G_blood_sub = G_blood_base.subgraph(valid_blood_nodes)
        else:
            G_blood_sub = G_blood_base

        if G_blood_sub.has_node(u) and G_blood_sub.has_node(v) and nx.has_path(G_blood_sub, u, v):
            d_blood = nx.shortest_path_length(G_blood_sub, u, v)
        else:
            d_blood = "Non connessi (∞)"

        distances_blood[d_blood] = distances_blood.get(d_blood, 0) + 1

        # ------------------------------------------------------------------
        # CASO B: TUTTI GLI ARCHI (escluso l'arco matrimoniale diretto u-v)
        # ------------------------------------------------------------------
        if t_max is not None:
            valid_all_nodes = [
                n for n in G_all_base.nodes()
                if parse_year(G_all_base.nodes[n].get("birth")) is None
                   or parse_year(G_all_base.nodes[n].get("birth")) <= t_max
            ]
            G_all_sub = G_all_base.subgraph(valid_all_nodes).copy()
        else:
            G_all_sub = G_all_base.copy()

        # Rimuoviamo il singolo arco matrimoniale diretto u-v per cercare cammini alternativi
        if G_all_sub.has_edge(u, v):
            G_all_sub.remove_edge(u, v)

        if G_all_sub.has_node(u) and G_all_sub.has_node(v) and nx.has_path(G_all_sub, u, v):
            d_all = nx.shortest_path_length(G_all_sub, u, v)
        else:
            d_all = "Non connessi (∞)"

        distances_all[d_all] = distances_all.get(d_all, 0) + 1

        processed_couples += 1

    # ------------------------------------------------------------------
    # 3. CALCOLO INDICE HERFINDAHL ED ESPOSIZIONE RISULTATI
    # ------------------------------------------------------------------
    hhi_blood, prop_blood = compute_herfindahl_index(distances_blood, processed_couples)
    hhi_all, prop_all = compute_herfindahl_index(distances_all, processed_couples)

    print("\n==================================================================================")
    print("  RISULTATI ANALISI HERFINDAHL DEI CAMMINI MATRIMONIALI")
    print("==================================================================================")
    print(f"• Matrimoni analizzati: {processed_couples}\n")

    # Stampa Caso A
    print("🔹 CASO A: SOLI ARCHI 'BLOOD' (Consanguinità Biologica)")
    print(f"   • INDICE DI HERFINDAHL-HIRSCHMAN (HHI): {hhi_blood:.6f}")
    df_blood = pd.DataFrame([
        {"Distanza (d)": k, "Conteggio Coppie": v, "Proporzione (p_d)": f"{v / processed_couples * 100:.2f}%"}
        for k, v in sorted(distances_blood.items(), key=lambda x: str(x[0]))
    ])
    print(df_blood.to_string(index=False))

    print("\n----------------------------------------------------------------------------------")

    # Stampa Caso B
    print("🔹 CASO B: TUTTI GLI ARCHI 'BLOOD' + 'MARRIAGE' (Cammini Alternativi)")
    print(f"   • INDICE DI HERFINDAHL-HIRSCHMAN (HHI): {hhi_all:.6f}")
    df_all = pd.DataFrame([
        {"Distanza (d)": k, "Conteggio Coppie": v, "Proporzione (p_d)": f"{v / processed_couples * 100:.2f}%"}
        for k, v in sorted(distances_all.items(), key=lambda x: str(x[0]))
    ])
    print(df_all.to_string(index=False))

    return hhi_blood, hhi_all


# ==================================================
# 4. ESECUZIONE SUL FILE PICKLE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il percorso del tuo file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        analyze_marriage_paths_and_herfindahl(G)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")