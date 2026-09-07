from pathlib import Path
import os


def root(explicit=None):
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
    elif os.environ.get("FLOWREVIEW_DATA_ROOT"):
        candidate = Path(os.environ["FLOWREVIEW_DATA_ROOT"]).expanduser().resolve()
    else:
        choices = [Path.cwd(), *Path(__file__).resolve().parents]
        candidate = next((p for p in choices if (p / 'data/assembly').is_dir()), None)
    if candidate is None or not (candidate / 'data/assembly').is_dir():
        raise ValueError('Dataset not found. Run from the repository or set FLOWREVIEW_DATA_ROOT.')
    return candidate


def paired_graphs(graphs, limit):
    """Keep complete policy pairs. Never truncate individual runs before pairing."""
    groups = {}
    for graph in graphs:
        key = tuple(graph.get(k) for k in ("scenario_id", "team_id", "N", "Q", "provenance_treatment"))
        groups.setdefault(key, []).append(graph)
    selected = []
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        if {g["P"] for g in group} != {"ALLOW", "DENY"} or len(group) != 2:
            raise ValueError(f"Expected one DENY/ALLOW pair for {key}")
        selected.append(sorted(group, key=lambda g: g["P"]))
    return selected if limit == 0 else selected[:limit]
