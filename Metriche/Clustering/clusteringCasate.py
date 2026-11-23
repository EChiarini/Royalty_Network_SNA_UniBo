import pickle
import re
import networkx as nx


# ==================================================
# 1. PARSING E FILTRAGGIO TEMPORALE
# ==================================================

def parse_year(val):
    """Estrae l'anno come intero da attributi int, float o str."""
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


def is_valid_house(val):
    """Verifica che l'attributo house sia una stringa valida e non nulla."""
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]


# ==================================================
# 2. COSTRUZIONE DEL GRAFO CONTRATTO PER CASATA
# ==================================================

def build_house_contracted_graph(G, start_year=None, end_year=None):
    """
    Contrae la rete dei singoli individui in un grafo pesato non orientato di Casate (house).
    Ogni nodo è una Casata reale. Gli archi rappresentano le unioni inter-casata
    e il peso ('weight') misura il numero di matrimoni/legami intercorsi.
    """
    G_house = nx.Graph()

    for u, v, data in G.edges(data=True):
        node_u = G.nodes[u]
        node_v = G.nodes[v]

        # Se richiesta, applichiamo la condizione temporale sugli individui
        if start_year is not None and end_year is not None:
            if not (is_alive_in_range(node_u, start_year, end_year) and is_alive_in_range(node_v, start_year,
                                                                                          end_year)):
                continue

        h_u = node_u.get("house")
        h_v = node_v.get("house")

        # Entrambi i nodi devono avere una casata valida e le casate devono essere distinte (alleanza inter-casata)
        if is_valid_house(h_u) and is_valid_house(h_v):
            house_a = str(h_u).strip()
            house_b = str(h_v).strip()

            if house_a != house_b:
                if G_house.has_edge(house_a, house_b):
                    G_house[house_a][house_b]["weight"] += 1
                else:
                    G_house.add_edge(house_a, house_b, weight=1)

    return G_house


# ==================================================
# 3. CALCOLO CLUSTERING E BASELINE CASUALE SUL GRAFO DELLE CASATE
# ==================================================

def compute_house_clustering_metrics(G_house, label=""):
    """
    Calcola le metriche di clustering (non pesato e pesato) e la significatività (C / C_rand)
    sul grafo contratto delle Casate.
    """
    num_houses = G_house.number_of_nodes()
    num_edges = G_house.number_of_edges()
    total_weight = sum(d.get("weight", 1) for u, v, d in G_house.edges(data=True))

    print(f"\n  🏰 [{label}]")
    print(f"   • Numero di Casate (Nodi N):          {num_houses}")
    print(f"   • Numero di Alleanze uniche (Archi E): {num_edges}")
    print(f"   • Legami matrimoniali/sangue totali:  {total_weight}")

    if num_houses < 3 or num_edges < 2:
        print("   ⚠️ Casate o alleanze insufficienti per il calcolo del clustering.")
        return

    # 1. Transitività Topologica (C) e Clustering Locale Medio Pesato (<Ci_weighted>)
    global_C = nx.transitivity(G_house)
    avg_local_C_unweighted = nx.average_clustering(G_house)
    avg_local_C_weighted = nx.average_clustering(G_house, weight="weight")

    # 2. Baseline casuale teorica C_rand (Erdős–Rényi G(n,p))
    avg_degree = (2.0 * num_edges) / num_houses
    c_rand = avg_degree / (num_houses - 1) if num_houses > 1 else 0.0

    # 3. Rapporto di arricchimento / significatività
    ratio = (global_C / c_rand) if c_rand > 0 else 0.0

    print(f"   • Transitività Globale C (Topologica):  {global_C:.4f}")
    print(f"   • Clustering Locale Medio <Ci> (Semplice): {avg_local_C_unweighted:.4f}")
    print(f"   • Clustering Locale Medio <Ci> (Pesato):   {avg_local_C_weighted:.4f}")
    print(f"   • Baseline Casuale Teorico C_rand:      {c_rand:.6f}  (Grado medio <k> = {avg_degree:.2f})")
    print(f"   • Rapporto di Significatività C/C_rand:   {ratio:.2f}x")

    if ratio > 5.0:
        print("   -> ESITO: C >> C_rand (Le casate formano blocchi geopolitici altamente strutturati e non casuali).")
    elif ratio > 1.2:
        print("   -> ESITO: C > C_rand (Modesta tendenza alla formazione di triangoli inter-casata).")
    else:
        print("   -> ESITO: C ≈ C_rand (La rete delle casate si comporta come un grafo casuale stocastico).")

    # Stampa delle 5 Casate più connesse (più influenti nella rete delle alleanze)
    degrees = dict(G_house.degree(weight="weight"))
    top_houses = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = ", ".join([f"{h} ({w} legami)" for h, w in top_houses])
    print(f"   • Top 5 Casate per centralità di legame: [{top_str}]")


# ==================================================
# 4. ANALISI INTEGRATA: GLOBALE E TEMPORALE
# ==================================================

def analyze_house_graph_full_and_temporal(G, start_year=2000, min_year=1450, step=50):
    """
    Esegue l'analisi sul Grafo Contratto per Casata sia sull'intero dataset (1450-Oggi)
    sia segmentata in intervalli temporali di 50 anni.
    """
    # ------------------------------------------------------------------
    # FASE 1: GRAFO DELLE CASATE GLOBALE (Senza filtri temporali)
    # ------------------------------------------------------------------
    print("\n==================================================================================")
    print("  1. CLUSTERING SUL GRAFO CONTRATTO DELLE CASATE - GLOBALE (1450 - OGGI)")
    print("==================================================================================")

    G_house_global = build_house_contracted_graph(G)
    compute_house_clustering_metrics(G_house_global, label="Grafo delle Casate Reali (Globale)")

    # ------------------------------------------------------------------
    # FASE 2: GRAFO DELLE CASATE PER FINESTRE TEMPORALI DI 50 ANNI
    # ------------------------------------------------------------------
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print("\n==================================================================================")
    print(f"  2. CLUSTERING SUL GRAFO CONTRATTO DELLE CASATE - FINESTRE DI {step} ANNI")
    print("==================================================================================")

    for start_w, end_w in time_windows:
        print(f"\n📅 PERIODO STORICO: {start_w} - {end_w}")
        print(f"----------------------------------------------------------------------------------")

        G_house_temporal = build_house_contracted_graph(G, start_year=start_w, end_year=end_w)

        if G_house_temporal.number_of_edges() == 0:
            print(f"⚠️ Nessuna alleanza tra casate trovata per il periodo {start_w}-{end_w}.")
            continue

        compute_house_clustering_metrics(G_house_temporal, label=f"Alleanze tra Casate ({start_w}-{end_w})")


# ==================================================
# 5. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il percorso del tuo file pickle

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(
            f"Grafo originale caricato con successo: {G.number_of_nodes()} nodi individuali, {G.number_of_edges()} archi.")

        # Esecuzione dell'analisi sul grafo contratto delle Casate
        analyze_house_graph_full_and_temporal(G, start_year=2000, min_year=1450, step=50)

    except FileNotFoundError:
        print(f"❌ Impossibile trovare il file '{file_pickle}'. Verifica il percorso del file pickle.")