import pickle
import re
import networkx as nx
from collections import Counter

# Prova ad importare python-louvain se presente, altrimenti usa il modulo nativo nx.community
try:
    import community as community_louvain
except ImportError:
    community_louvain = None


# ==================================================
# 1. FUNZIONI DI PARSING E FILTRAGGIO TEMPORALE
# ==================================================

def parse_year(val):
    """Estrae l'anno come intero da stringhe, int, float o date."""
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
    """Verifica se il nodo è stato vivo per almeno un anno nell'intervallo [start_year, end_year]."""
    birth = parse_year(node_data.get("birth"))
    death = parse_year(node_data.get("death"))

    if birth is None:
        return False
    if death is None:
        death = default_current_year

    return (birth <= end_year) and (death >= start_year)


def is_valid_value(val):
    """Verifica la validità dell'attributo."""
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]


# ==================================================
# 2. ALGORITMO DI COMMUNITY DETECTION (LOUVAIN)
# ==================================================

def run_community_detection(G_sub, label=""):
    """
    Esegue l'algoritmo di Louvain sul sottografo fornito,
    calcola la Modularità Q e restituisce la partizione delle comunità.
    """
    if G_sub.number_of_nodes() < 3 or G_sub.number_of_edges() < 2:
        print(f"  [{label}] ⚠️ Troppi pochi nodi o archi per eseguire la Community Detection.")
        return None, 0.0

    # Louvain richiede un grafo non orientato
    G_undirected = G_sub.to_undirected()

    # Esecuzione Louvain nativo NetworkX (versione >= 2.8) o fallback su python-louvain
    try:
        communities_list = nx.community.louvain_communities(G_undirected, seed=42)
        modularity_q = nx.community.modularity(G_undirected, communities_list)

        # Mappatura nodo -> id_comunità
        partition = {}
        for comm_id, comm_nodes in enumerate(communities_list):
            for node in comm_nodes:
                partition[node] = comm_id

    except AttributeError:
        if community_louvain is not None:
            partition = community_louvain.best_partition(G_undirected, random_state=42)
            modularity_q = community_louvain.modularity(partition, G_undirected)
            # Raggruppiamo i nodi per comunità
            comm_dict = {}
            for n, c in partition.items():
                comm_dict.setdefault(c, set()).add(n)
            communities_list = list(comm_dict.values())
        else:
            print("❌ Errore: Nessun algoritmo Louvain disponibile. Aggiorna NetworkX o installa 'python-louvain'.")
            return None, 0.0

    print(f"\n  📊 {label}")
    print(f"   • Nodi: {G_undirected.number_of_nodes()} | Archi: {G_undirected.number_of_edges()}")
    print(f"   • Numero di Comunità Rilevate: {len(communities_list)}")
    print(f"   • Modularità Q: {modularity_q:.4f}")

    if modularity_q > 0.3:
        print("   -> Struttura a Comunità FORTE e ben separata (Q > 0.3).")
    elif modularity_q > 0:
        print("   -> Struttura a Comunità MODERATA.")
    else:
        print("   -> Nessuna divisione significativa in comunità.")

    # Stampa dettagli dei cluster principali (top 5 comunità per dimensione)
    sorted_communities = sorted(communities_list, key=len, reverse=True)
    for idx, comm in enumerate(sorted_communities[:5]):
        # Estraiamo le casate reali prevalenti all'interno del cluster
        houses = [G_undirected.nodes[n].get("house") for n in comm if
                  is_valid_value(G_undirected.nodes[n].get("house"))]
        top_houses = Counter(houses).most_common(3) if houses else []
        #top_houses = nx.utils.groups.counter(houses).most_common(3) if houses else []
        houses_str = ", ".join([f"{h} ({cnt})" for h, cnt in top_houses])
        print(f"     └─ Comunità {idx + 1}: {len(comm)} nodi | Casate principali: [{houses_str}]")

    return partition, modularity_q


# ==================================================
# 3. COMMUNITY DETECTION PER FINESTRE TEMPORALI (50 ANNI)
# ==================================================

def analyze_communities_temporal(G, start_year=2000, min_year=1450, step=50):
    """Calcola la Community Detection per ciascuna finestra temporale di 50 anni."""
    time_windows = [(y - step, y) for y in range(start_year, min_year, -step)]

    print("\n==================================================================================")
    print(f"  1. COMMUNITY DETECTION TEMPORALE SUI MATRIMONI (Finestre di {step} anni)")
    print("==================================================================================")

    for start_w, end_w in time_windows:
        G_win = nx.Graph()

        for u, v, data in G.edges(data=True):
            edge_type = str(data.get("type") or data.get("relationship") or "").lower()
            if "marriage" in edge_str_check(edge_type):
                node_u = G.nodes[u]
                node_v = G.nodes[v]

                if is_alive_in_range(node_u, start_w, end_w) and is_alive_in_range(node_v, start_w, end_w):
                    G_win.add_node(u, **node_u)
                    G_win.add_node(v, **node_v)
                    G_win.add_edge(u, v)

        if G_win.number_of_edges() >= 3:
            run_community_detection(G_win, label=f"Periodo {start_w} - {end_w}")


def edge_str_check(val):
    return str(val).lower()


# ==================================================
# 4. COMMUNITY DETECTION SUL GRAFO CONTRATTO PER CASATA
# ==================================================

def analyze_communities_by_house(G):
    """
    Aggrega i nodi per 'house' ed esegue la Community Detection sul grafo delle Casate.
    Gli archi pesati indicano il numero di matrimoni inter-casata.
    """
    print("\n==================================================================================")
    print("  2. COMMUNITY DETECTION SUL GRAFO CONTRATTO PER CASATA (Macro-Coalizioni)")
    print("==================================================================================")

    G_house = nx.Graph()

    for u, v, data in G.edges(data=True):
        edge_type = str(data.get("type") or data.get("relationship") or "").lower()
        if "marriage" in edge_str_check(edge_type):
            h_u = G.nodes[u].get("house")
            h_v = G.nodes[v].get("house")

            # Entrambe le casate devono essere valide e distinte (matrimoni inter-casata)
            if is_valid_value(h_u) and is_valid_value(h_v) and str(h_u).strip() != str(h_v).strip():
                house_a = str(h_u).strip()
                house_b = str(h_v).strip()

                if G_house.has_edge(house_a, house_b):
                    G_house[house_a][house_b]["weight"] += 1
                else:
                    G_house.add_edge(house_a, house_b, weight=1)

    print(
        f"• Grafo delle Casate creato: {G_house.number_of_nodes()} Casate, {G_house.number_of_edges()} Legami matrimoniali.")

    if G_house.number_of_edges() >= 3:
        try:
            communities_list = nx.community.louvain_communities(G_house, weight="weight", seed=42)
            q = nx.community.modularity(G_house, communities_list, weight="weight")

            print(f"\n  📊 Cluster di Casate (Macro-Coalizioni Dinastiche):")
            print(f"   • Numero di Coalizioni: {len(communities_list)}")
            print(f"   • Modularità Q (Pesata): {q:.4f}")

            sorted_comms = sorted(communities_list, key=len, reverse=True)
            for idx, comm in enumerate(sorted_comms[:5]):
                casate_list = list(comm)[:6]  # Prime 6 casate del cluster
                print("Cappato a 6, se 6 controllare e aggiustare...")
                print(f"     └─ Coalizione {idx + 1} ({len(comm)} Casate): {', '.join(casate_list)}...")
        except Exception as e:
            print(f"❌ Errore durante il calcolo: {e}")


# ==================================================
# 5. ESECUZIONE PRINCIPALE
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il nome/percorso del tuo file .pkl

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        # A. Community Detection sul Grafo Globale dei Matrimoni
        G_marriage_global = nx.Graph()
        for u, v, d in G.edges(data=True):
            if "marriage" in str(d.get("type") or d.get("relationship") or "").lower():
                G_marriage_global.add_node(u, **G.nodes[u])
                G_marriage_global.add_node(v, **G.nodes[v])
                G_marriage_global.add_edge(u, v)

        print("\n==================================================================================")
        print("  0. COMMUNITY DETECTION SULL'INTERO GRAFO DEI MATRIMONI (1450 - Oggi)")
        print("==================================================================================")
        run_community_detection(G_marriage_global, label="Grafo Globale dei Matrimoni")

        # B. Community Detection su Finestre Temporali di 50 Anni
        analyze_communities_temporal(G, start_year=2000, min_year=1450, step=50)

        # C. Community Detection sul Grafo Contratto delle Casate
        analyze_communities_by_house(G)

    except FileNotFoundError:
        print(f"❌ File '{file_pickle}' non trovato. Verifica il percorso.")