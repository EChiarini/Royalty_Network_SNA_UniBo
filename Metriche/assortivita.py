import pickle
import networkx as nx
import numpy


def is_valid_value(val):
    """
    Verifica se il valore dell'attributo è presente e valido
    (esclude None, stringhe vuote o valori sconosciuti).
    """
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str not in ["", "none", "unknown", "nan", "null", "n/a", "missing"]

def is_monarch(node_data):
    """
    Estrae il valore booleano dell'attributo 'monarch'.
    """
    val = node_data.get("monarch")
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ["true", "1", "yes", "t"]
    return False


def compute_subgraph_assortativity(G_sub, attribute_name, label):
    """
    Calcola e stampa il coefficiente di assortatività per un determinato sottografo.
    """
    num_edges = G_sub.number_of_edges()
    print(f"\n--- {label} ---")
    print(f"• Numero di matrimoni analizzati: {num_edges}")

    if num_edges < 2:
        print("  ⚠️ Numero di matrimoni insufficiente per un calcolo significativo dell'assortatività.")
        return None

    # Verifica la presenza di almeno 2 categorie distinte per l'attributo
    unique_attrs = set(nx.get_node_attributes(G_sub, attribute_name).values())
    if len(unique_attrs) <= 1:
        print(
            f"  ⚠️ Impossibile calcolare r: tutti i nodi nel sottografo appartengono all'unica categoria '{list(unique_attrs)}'.")
        return None

    try:
        r = nx.attribute_assortativity_coefficient(G_sub, attribute_name)
        print(f"• Coefficiente di Assortatività r ({attribute_name}): {r:.4f}")

        return r
    except Exception as e:
        print(f"  ❌ Errore durante il calcolo dell'assortatività: {e}")
        return None


def analyze_assortativity_by_monarch_status(G, attribute_name):
    """
    Filtra gli archi 'marriage' validi e li suddivide in base allo status di regnante dei nodi.
    """
    # Inizializziamo i 4 grafi per le diverse casistiche
    G_all = nx.Graph()
    G_both_monarchs = nx.Graph()
    G_at_least_one_monarch = nx.Graph()
    G_non_monarchs = nx.Graph()

    total_marriages = 0
    valid_marriages = 0

    for u, v, data in G.edges(data=True):
        # Filtro per archi di tipo matrimonio
        edge_type = data.get("type") or data.get("relationship") or ""
        if str(edge_type).lower() == "marriage" or str(edge_type).lower() == "blood_&_marriage":
            total_marriages += 1

            node_u_data = G.nodes[u]
            node_v_data = G.nodes[v]

            attr_u = node_u_data.get(attribute_name)
            attr_v = node_v_data.get(attribute_name)

            # CONDIZIONE FONDAMENTALE: entrambi i coniugi devono avere l'attributo valido
            if is_valid_value(attr_u) and is_valid_value(attr_v):
                valid_marriages += 1

                val_u_str = str(attr_u).strip()
                val_v_str = str(attr_v).strip()

                # Aggiunta al grafo generale dei matrimoni validi
                G_all.add_node(u, **{attribute_name: val_u_str})
                G_all.add_node(v, **{attribute_name: val_v_str})
                G_all.add_edge(u, v)

                # Controllo dello status di regnante
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

    print(f"\n==================================================================")
    print(f"  ANALISI COMPARATIVA ASSORTATIVITÀ PER: '{attribute_name}'")
    print(f"==================================================================")
    print(f"• Archi 'marriage' totali nel dataset: {total_marriages}")
    print(f"• Matrimoni validi (con entrambi i dati presenti): {valid_marriages}")
    print(f"• Percentuale di nodi analizzati: {(valid_marriages/total_marriages*100):.2f}%")

    if valid_marriages == 0:
        print("⚠️ Nessun matrimonio valido trovato per questo attributo.")
        return

    # Esecuzione dei calcoli sui 4 sottogruppi
    compute_subgraph_assortativity(G_all, attribute_name, "1. TUTTI I MATRIMONI VALIDI")
    compute_subgraph_assortativity(G_both_monarchs, attribute_name, "2. MATRIMONI TRA REGNANTI (Entrambi Regnanti)")
    compute_subgraph_assortativity(G_at_least_one_monarch, attribute_name,
                                   "3. MATRIMONI COINVOLGENTI UN REGNANTE (Almeno uno Regnante)")
    compute_subgraph_assortativity(G_non_monarchs, attribute_name,
                                   "4. MATRIMONI TRA NON REGNANTI (Entrambi Non Regnanti)")


# ==================================================
# ESECUZIONE SUL FILE PICKLE (.pkl)
# ==================================================
if __name__ == "__main__":
    file_pickle = "datasetprova.pkl"  # Sostituisci con il nome/percorso del tuo file .pkl

    try:
        with open(file_pickle, "rb") as f:
            G = pickle.load(f)
        print(f"Grafo caricato con successo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi.")

        # 1. Analisi per Religione
        analyze_assortativity_by_monarch_status(G, "religion")

        # 2. Analisi per Paese di Nascita
        analyze_assortativity_by_monarch_status(G, "birth_country")

    except FileNotFoundError:
        print(f"File '{file_pickle}' non trovato. Verifica il percorso del file pickle.")
