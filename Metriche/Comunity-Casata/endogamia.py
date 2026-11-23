import pickle
import math
import collections
import networkx as nx
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score


# ==================================================
# 1. FUNZIONI DI UTILITÀ METRICA
# ==================================================

def is_valid_value(val):
    """Verifica la validità dell'attributo house."""
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]


def calculate_entropy(probabilities):
    """Calcola l'entropia di Shannon H(C) per una comunità."""
    return -sum(p * math.log2(p) for p in probabilities if p > 0)


def compare_communities_with_houses(G_sub, label=""):
    """
    Esegue la Community Detection e calcola la Purità, l'Entropia, NMI e ARI
    rispetto all'attributo 'house'.
    """
    # Filtriamo solo i nodi che hanno un attributo 'house' valido
    valid_nodes = [n for n in G_sub.nodes() if is_valid_value(G_sub.nodes[n].get("house"))]
    G_valid = G_sub.subgraph(valid_nodes).to_undirected()

    if G_valid.number_of_nodes() < 5 or G_valid.number_of_edges() < 2:
        print(f"⚠️ [{label}] Nodi sufficienti con 'house' valida troppo esigui per l'analisi.")
        return

    # 1. Esecuzione Louvain
    communities_list = nx.community.louvain_communities(G_valid, seed=42)
    modularity_q = nx.community.modularity(G_valid, communities_list)

    # Prepartizione dati per NMI / ARI
    y_true = []  # Casate reali
    y_pred = []  # Comunità assegnate

    node_to_comm = {}
    for comm_id, comm_nodes in enumerate(communities_list):
        for n in comm_nodes:
            node_to_comm[n] = comm_id

    for n in G_valid.nodes():
        y_true.append(str(G_valid.nodes[n]["house"]).strip())
        y_pred.append(node_to_comm[n])

    # Calcolo NMI e ARI
    nmi = normalized_mutual_info_score(y_true, y_pred)
    ari = adjusted_rand_score(y_true, y_pred)

    print(f"\n==================================================================================")
    print(f"  ANALISI COMPARATIVA: COMUNITÀ vs CASATA ({label})")
    print(f"==================================================================================")
    print(f"• Nodi validi analizzati: {G_valid.number_of_nodes()} | Archi: {G_valid.number_of_edges()}")
    print(f"• Numero Comunità Trovate: {len(communities_list)}")
    print(f"• Modularità Q del Grafo: {modularity_q:.4f}")
    print(f"• Normalized Mutual Information (NMI): {nmi:.4f}  (1.0 = perfetta corrispondenza)")
    print(f"• Adjusted Rand Index (ARI):            {ari:.4f}  (1.0 = perfetta corrispondenza)")
    print(f"----------------------------------------------------------------------------------")

    # 2. Analisi di Purità ed Entropia per ogni comunità
    total_nodes_count = G_valid.number_of_nodes()
    weighted_purity_sum = 0
    report_rows = []

    sorted_communities = sorted(communities_list, key=len, reverse=True)

    for comm_id, comm in enumerate(sorted_communities):
        houses_in_comm = [str(G_valid.nodes[n]["house"]).strip() for n in comm]
        counts = collections.Counter(houses_in_comm)
        comm_size = len(comm)

        # Casata dominante e purità
        dominant_house, dominant_count = counts.most_common(1)[0]
        purity = dominant_count / comm_size
        weighted_purity_sum += dominant_count

        # Entropia
        probs = [cnt / comm_size for cnt in counts.values()]
        entropy = calculate_entropy(probs)

        # Prime 3 casate nel cluster
        top_houses_str = ", ".join([f"{h} ({c})" for h, c in counts.most_common(3)])

        report_rows.append({
            "ID Comunità": f"Comunità {comm_id + 1}",
            "Dimensione": comm_size,
            "Casata Dominante": dominant_house,
            "Purità (%)": f"{purity * 100:.1f}%",
            "Entropia H": round(entropy, 3),
            "Composizione (Top Casate)": top_houses_str
        })

    global_purity = (weighted_purity_sum / total_nodes_count) * 100
    print(f"• PURITÀ GLOBALE DELLE COMUNITÀ: {global_purity:.2f}%\n")

    # Stampa Tabella Riquadro Dettagliato
    df_report = pd.DataFrame(report_rows)
    print(df_report.to_string(index=False))


# ==================================================
# 2. ESECUZIONE PRINCIPALE SUL FILE PICKLE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Inserisci il nome del tuo file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato correttamente: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        # Estraiamo il grafo dei soli matrimoni
        G_marriage = nx.Graph()
        for u, v, d in G.edges(data=True):
            edge_type = str(d.get("type") or d.get("relationship") or "").lower()
            if "marriage" in edge_type:
                G_marriage.add_node(u, **G.nodes[u])
                G_marriage.add_node(v, **G.nodes[v])
                G_marriage.add_edge(u, v)

        # Analisi sul Grafo Globale dei Matrimoni
        compare_communities_with_houses(G_marriage, label="Grafo Globale dei Matrimoni")

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso.")