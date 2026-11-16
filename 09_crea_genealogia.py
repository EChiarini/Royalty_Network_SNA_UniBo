"""Estrae un DiGraph genitore -> figlio; non effettua richieste di rete."""
import argparse
import csv
import hashlib
import json
import pickle
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parent


def build_genealogy(source):
    """Conserva gli attributi; non deduce discendenza da marriage/blood/throne."""
    graph = nx.DiGraph()
    graph.add_nodes_from((n, dict(a)) for n, a in source.nodes(data=True))
    anomalies = []
    for child, attrs in source.nodes(data=True):
        parents = attrs.get('parents')
        if parents is None:
            parents = []
        if not isinstance(parents, (list, tuple, set)):
            anomalies.append(dict(kind='invalid_parents', parent=str(parents), child=child))
            continue
        seen = set()
        for parent in parents:
            if not isinstance(parent, str):
                anomalies.append(dict(kind='invalid_parent', parent=str(parent), child=child))
                continue
            if parent in seen:
                anomalies.append(dict(kind='duplicate_parent', parent=parent, child=child))
                continue
            seen.add(parent)
            if parent == child:
                anomalies.append(dict(kind='self_parent_excluded', parent=parent, child=child))
            elif parent not in source:
                anomalies.append(dict(kind='missing_parent_excluded', parent=parent, child=child))
            else:
                graph.add_edge(parent, child, relationship='parent_child', evidence='child.parents',
                               present_in_source_edges=source.has_edge(parent, child))
        if len(seen) > 2:
            anomalies.append(dict(kind='more_than_two_parents', parent=' | '.join(sorted(seen)), child=child))
    # Preserve conflicting evidence instead of silently breaking cycles.
    for component in nx.strongly_connected_components(graph):
        if len(component) > 1:
            for parent, child in sorted(graph.subgraph(component).edges):
                anomalies.append(dict(kind='cycle_edge_retained', parent=parent, child=child))
    return graph, anomalies


### VIEWER HTML FACOLTATIVO

def html_view(graph, destination):
    # Offline viewer: breadth-first levels relative to the selected person.
    data = {'nodes': sorted(graph.nodes), 'edges': sorted(map(list, graph.edges))}
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    template = r'''<!doctype html><html lang="it"><meta charset="utf-8">
<title>Genealogia orientata</title><style>
body{font:15px system-ui;margin:24px;background:#f3f5f9;color:#17233b}button,input,select{font:inherit;padding:8px;margin:4px}svg{background:white;border:1px solid #ccd3df}#canvas{overflow:auto;max-height:78vh}p{max-width:1000px}.edge{stroke:#9aa9c0;stroke-width:1.3;fill:none}text{font:11px system-ui}rect{fill:#e8eef9;stroke:#526f9d} .focus{fill:#ffdf96}
</style><h1>Genealogia · genitore → figlio</h1>
<p>Seleziona una persona e il numero di generazioni. La vista mostra un ramo della rete; un antenato condiviso compare una sola volta. Nomi e relazioni provengono dal grafo: le identità non sono tutte validate. I cicli eventualmente presenti sono segnalati nel registro CSV.</p>
<input id="person" list="names" aria-label="Persona" size="42"><datalist id="names"></datalist>
<select id="direction" aria-label="Direzione"><option value="ancestors">Antenati</option><option value="descendants">Discendenti</option></select>
<input id="depth" type="number" min="1" max="8" value="3" aria-label="Generazioni"><button id="show">Mostra</button><button id="save">Scarica SVG</button><p id="status"></p><div id="canvas"></div>
<script>const data=__DATA__;
const byId=id=>document.getElementById(id), parents=new Map(),children=new Map();
for(const n of data.nodes){parents.set(n,[]);children.set(n,[]);let o=document.createElement('option');o.value=n;byId('names').append(o)}
for(const [p,c] of data.edges){parents.get(c).push(p);children.get(p).push(c)}
byId('person').value=data.nodes.includes('Felipe VI')?'Felipe VI':data.nodes[0];
const ns='http://www.w3.org/2000/svg';function el(tag,attrs,text){let x=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))x.setAttribute(k,v);if(text!==undefined)x.textContent=text;return x}
function render(){const root=byId('person').value,anc=byId('direction').value==='ancestors',depth=Math.min(8,Math.max(1,Number(byId('depth').value)||3));if(!parents.has(root)){byId('status').textContent='Nome non trovato: scegli dalla lista.';return}
const levels=new Map([[root,0]]),queue=[root],adj=anc?parents:children;let capped=false;
for(let i=0;i<queue.length;i++){const n=queue[i],level=levels.get(n);if(level>=depth)continue;for(const next of adj.get(n)){if(levels.has(next))continue;if(levels.size>=500){capped=true;continue}levels.set(next,level+1);queue.push(next)}}
const groups=Array.from({length:depth+1},()=>[]);for(const[n,l]of levels)groups[l].push(n);groups.forEach(g=>g.sort());const width=Math.max(1000,...groups.map(g=>g.length*240)),height=(depth+1)*130+70,positions=new Map();
const svg=el('svg',{xmlns:ns,width,height,viewBox:`0 0 ${width} ${height}`});const defs=el('defs',{}),marker=el('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto'});marker.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#677d9e'}));defs.append(marker);svg.append(defs);
groups.forEach((g,l)=>g.forEach((n,i)=>positions.set(n,[(i+.5)*width/g.length,(anc?depth-l:l)*130+40])));
let edges=0;for(const[p,c]of data.edges){if(!positions.has(p)||!positions.has(c))continue;edges++;const[a,b]=positions.get(p),[x,y]=positions.get(c);svg.append(el('path',{d:`M ${a} ${b+22} L ${x} ${y-22}`,class:'edge','marker-end':'url(#arrow)'}))}
for(const[n,[x,y]]of positions){let g=el('g',{});g.append(el('title',{},n));g.append(el('rect',{x:x-110,y:y-22,width:220,height:44,rx:8,class:n===root?'focus':''}));g.append(el('text',{x,y:y+4,'text-anchor':'middle'},n.length>33?n.slice(0,31)+'…':n));g.style.cursor='pointer';g.onclick=()=>{byId('person').value=n;render()};svg.append(g)}
byId('canvas').replaceChildren(svg);byId('status').textContent=`Rete completa: ${data.nodes.length} nodi, ${data.edges.length} archi. Vista: ${levels.size} nodi, ${edges} archi.`+(capped?' Vista limitata a 500 nodi: riduci le generazioni.':'')}
byId('show').onclick=render;byId('save').onclick=()=>{let svg=byId('canvas').querySelector('svg');if(!svg)return;let copy=svg.cloneNode(true),style=el('style',{});style.textContent=document.querySelector('style').textContent;copy.prepend(style);let url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml'})),a=document.createElement('a');a.href=url;a.download='genealogia.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};render();</script></html>'''
    destination.write_text(template.replace('__DATA__', payload), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=BASE/'dati/graph_all_1450_original_relations_fixed.pkl')
    parser.add_argument('--output', type=Path, default=BASE/'genealogia')
    args = parser.parse_args()
    raw = args.input.read_bytes()
    source = pickle.loads(raw)  # Only load trusted project pickle files.
    if not isinstance(source, nx.Graph):
        raise TypeError('Il file non contiene un grafo NetworkX')
    graph, anomalies = build_genealogy(source)
    out = args.output.resolve()
    targets = ['grafo_genealogico.pkl', 'grafo_genealogico.graphml', 'archi_genitore_figlio.csv',
               'anomalie.csv', 'riepilogo.json', 'genealogia.html']
    if args.input.resolve() in [out/name for name in targets]:
        raise ValueError('La destinazione sovrascriverebbe il file sorgente')
    out.mkdir(parents=True, exist_ok=True)
    (out/targets[0]).write_bytes(pickle.dumps(graph, protocol=4))
    portable = nx.DiGraph()
    for n, attrs in graph.nodes(data=True):
        portable.add_node(n, **{str(k): (v if isinstance(v,(str,int,float,bool)) else json.dumps(v,ensure_ascii=False,sort_keys=True)) for k,v in attrs.items()})
    portable.add_edges_from(graph.edges(data=True))
    nx.write_graphml(portable, out/targets[1])
    with (out/targets[2]).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['parent','child']);writer.writerows(sorted(graph.edges))
    with (out/targets[3]).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['kind','parent','child']);writer.writeheader();writer.writerows(anomalies)
    summary = dict(input=str(args.input.resolve()), input_sha256=hashlib.sha256(raw).hexdigest(),
                   orientation='parent -> child', nodes=len(graph), edges=graph.number_of_edges(),
                   isolated_nodes=nx.number_of_isolates(graph), is_dag=nx.is_directed_acyclic_graph(graph),
                   weak_components=nx.number_weakly_connected_components(graph),
                   anomalies={k:sum(a['kind']==k for a in anomalies) for k in sorted({a['kind'] for a in anomalies})},
                   identity_validation='Not performed: all source nodes retained, including possible non-person entities.',
                   rules='Edges from parents only; absent parents and self-parent links excluded; cycles retained and reported.')
    html_view(graph,out/targets[5])
    summary['output_sha256']={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in targets if n!='riepilogo.json'}
    (out/targets[4]).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
