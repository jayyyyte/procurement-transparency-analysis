"""Optional §7.3: bid-solicitor <-> contractor network, Louvain communities, exclusive clusters."""
from __future__ import annotations

import networkx as nx
import pandas as pd


def run(df: pd.DataFrame, cfg, logger) -> dict:
    seed = cfg["model"]["random_state"]
    d = df.dropna(subset=["nha_thau_trung_thau", "ma_ben_moi_thau"])
    if len(d) < cfg["model"]["min_rows"]:
        logger.warning("network skipped: only %d packages with a winner", len(d))
        return {"skipped": True}
    d = d.assign(winner=d["ma_nha_thau_trung_thau"].fillna(d["nha_thau_trung_thau"]))
    edges = d.groupby(["ma_ben_moi_thau", "winner"]).agg(w=("ma_tbmt", "size"), value=("gia_trung_thau", "sum"))
    if edges.empty:
        return {"skipped": True}
    G = nx.Graph()
    for (bmt, nt), r in edges.iterrows():
        G.add_edge(f"B:{bmt}", f"N:{nt}", weight=int(r["w"]), value=float(r["value"]))
    comms = nx.community.louvain_communities(G, weight="weight", seed=seed)
    names = d.drop_duplicates("winner").set_index("winner")["nha_thau_trung_thau"]
    bmt_names = d.drop_duplicates("ma_ben_moi_thau").set_index("ma_ben_moi_thau")["ben_moi_thau"]
    rows = []
    for i, c in enumerate(comms):
        sub = G.subgraph(c)
        b = [n[2:] for n in c if n.startswith("B:")]
        n = [x[2:] for x in c if x.startswith("N:")]
        if len(b) < 2 or len(n) < 1:
            continue
        inside = sum(dd["weight"] for _, _, dd in sub.edges(data=True))
        total = sum(dd["weight"] for x in c if x.startswith("N:") for _, _, dd in G.edges(x, data=True))
        rows.append({"community": i, "so_ben_moi_thau": len(b), "so_nha_thau": len(n), "so_goi": inside,
                     "tong_gia_trung_ty": sum(dd["value"] for _, _, dd in sub.edges(data=True)) / 1e9,
                     # share of the community's contractors' wins that happen inside the community
                     "ty_le_khep_kin": inside / total if total else 0.0,
                     "nha_thau_tieu_bieu": ", ".join(names.get(x, x) for x in n[:3]),
                     "ben_moi_thau_tieu_bieu": ", ".join(str(bmt_names.get(x, x)) for x in b[:3])})
    if not rows:
        logger.warning("network: no community with >= 2 bid solicitors")
        return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "communities": len(comms)}
    out = pd.DataFrame(rows).sort_values(["ty_le_khep_kin", "so_goi"], ascending=False)
    out.round(4).to_csv(cfg.path("tables_dir") / "network_communities.csv", index=False, encoding="utf-8-sig")
    logger.info("network: %d nodes, %d edges, %d communities (%d with >=2 solicitors)",
                G.number_of_nodes(), G.number_of_edges(), len(comms), len(out))
    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "communities": len(comms)}
