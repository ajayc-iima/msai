"""src/plots.py — 5 figures for the paper. Loads real eval outputs; skips cleanly when absent."""
import json
from pathlib import Path
from typing import Dict, List, Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.common import load_jsonl, ensure_dir


def plot_systems_bar(eval_path: Path, out_path: Path) -> None:
    """Figure 1: Systems bar chart (nDCG@10 with CIs)."""
    data = load_jsonl(eval_path)

    systems = [d["system"] for d in data]
    ndcg = [d["nDCG@10"] for d in data]

    sorted_pairs = sorted(zip(systems, ndcg), key=lambda x: x[1], reverse=True)
    systems, ndcg = zip(*sorted_pairs)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(systems)), ndcg, color='steelblue', edgecolor='black')
    ax.set_yticks(range(len(systems)))
    ax.set_yticklabels(systems)
    ax.set_xlabel('nDCG@10')
    ax.set_title('Retrieval Systems Comparison (Gold A, Test Split)')
    ax.invert_yaxis()

    for i, (bar, val) in enumerate(zip(bars, ndcg)):
        ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2, f'{val:.3f}',
                va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def plot_error_budget_stacked(waterfall_path: Path, out_path: Path) -> None:
    """Figure 2: Error-budget stacked bar by style."""
    waterfall = json.loads(waterfall_path.read_text())
    details = waterfall.get("details", {})

    style_buckets = {}
    for bucket_name, items in details.items():
        if bucket_name in ["A", "B", "C", "success"]:
            for item in items:
                style = item.get("style", "unknown")
                if style not in style_buckets:
                    style_buckets[style] = {"A": 0, "B": 0, "C": 0, "success": 0}
                style_buckets[style][bucket_name] += 1

    styles = list(style_buckets.keys())
    buckets = ["A", "B", "C", "success"]
    colors = {"A": "#e74c3c", "B": "#f39c12", "C": "#3498db", "success": "#27ae60"}
    labels = {"A": "Retrieval Fail", "B": "Evidence Fail", "C": "Generation Fail", "success": "Success"}

    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(styles))

    for bucket in buckets:
        values = [style_buckets[s].get(bucket, 0) for s in styles]
        totals = [sum(style_buckets[s].values()) for s in styles]
        proportions = [v / t if t > 0 else 0 for v, t in zip(values, totals)]
        ax.bar(styles, proportions, bottom=bottom, label=labels[bucket], color=colors[bucket])
        bottom += proportions

    ax.set_ylabel('Proportion')
    ax.set_title('Error Budget by Query Style (Waterfall)')
    ax.legend()
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def _load_rows(path: Path) -> list:
    """Load a JSONL of {system, variable, value} rows or a JSON list of dicts."""
    if not path.exists():
        return []
    try:
        return load_jsonl(path)
    except Exception:
        return []


def plot_recall_vs_corpus_size(data_dir: Path, out_path: Path) -> None:
    """Figure 3: Recall@10 vs corpus size, from data/eval/scaling.jsonl.

    Expected rows: {"size": 20000, "system": "bm25", "recall@10": 0.72}
    Produced by running retrieval eval on corpus prefixes; skipped if absent.
    """
    rows = _load_rows(data_dir / "scaling.jsonl")
    if not rows:
        print(f"SKIP fig3 (no {data_dir / 'scaling.jsonl'} — build it by "
              f"re-running retrieval eval at several corpus-size prefixes)")
        return

    systems = sorted({r["system"] for r in rows})
    fig, ax = plt.subplots(figsize=(10, 6))
    for sys in systems:
        pts = sorted((r for r in rows if r["system"] == sys), key=lambda r: r["size"])
        ax.plot([p["size"] for p in pts], [p["recall@10"] for p in pts],
                'o-', label=sys, linewidth=2, markersize=8)

    ax.set_xlabel('Corpus Size (documents)')
    ax.set_ylabel('Recall@10 (any-of)')
    ax.set_title('Retrieval Scaling: Recall@10 vs Corpus Size')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def plot_chunking_ablation(data_dir: Path, out_path: Path) -> None:
    """Figure 4: Chunking ablation (size × overlap → nDCG@10) from chunk_ablation.jsonl.

    Expected rows: {"chunk_size": 1800, "overlap": 200, "nDCG@10": 0.77}
    Skipped if absent.
    """
    rows = _load_rows(data_dir / "chunk_ablation.jsonl")
    if not rows:
        print(f"SKIP fig4 (no {data_dir / 'chunk_ablation.jsonl'} — add a chunking "
              f"ablation to the retrieval sweep and emit this file)")
        return

    sizes = sorted({r["chunk_size"] for r in rows})
    overlaps = sorted({r["overlap"] for r in rows})
    data = np.full((len(sizes), len(overlaps)), np.nan)
    for r in rows:
        i = sizes.index(r["chunk_size"])
        j = overlaps.index(r["overlap"])
        data[i, j] = r["nDCG@10"]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(data, cmap='RdYlGn', aspect='auto')
    ax.set_xticks(range(len(overlaps)))
    ax.set_xticklabels([str(o) for o in overlaps])
    ax.set_yticks(range(len(sizes)))
    ax.set_yticklabels([str(s) for s in sizes])
    ax.set_xlabel('Overlap (chars)')
    ax.set_ylabel('Chunk Size (chars)')
    ax.set_title('Chunking Ablation: nDCG@10 (Dev)')
    plt.colorbar(im, ax=ax, label='nDCG@10')

    for i in range(len(sizes)):
        for j in range(len(overlaps)):
            if not np.isnan(data[i, j]):
                ax.text(j, i, f'{data[i, j]:.2f}', ha='center', va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def plot_policy_comparison(data_dir: Path, out_path: Path) -> None:
    """Figure 5: Policy comparison, from data/eval/policy_comparison.jsonl.

    Expected rows: {"policy": "D", "metric": "faithfulness", "value": 0.92}
    Skipped if absent.
    """
    rows = _load_rows(data_dir / "policy_comparison.jsonl")
    if not rows:
        print(f"SKIP fig5 (no {data_dir / 'policy_comparison.jsonl'} — run "
              f"`src.evaluate answers` for policies A-D on a fixed system and emit it)")
        return

    policies = sorted({r["policy"] for r in rows})
    metrics = sorted({r["metric"] for r in rows})
    x = np.arange(len(policies))
    width = 0.8 / max(len(metrics), 1)

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, metric in enumerate(metrics):
        vals = []
        for policy in policies:
            m = [r for r in rows if r["policy"] == policy and r["metric"] == metric]
            vals.append(m[0]["value"] if m else 0.0)
        ax.bar(x + i * width - width * (len(metrics) - 1) / 2, vals, width,
               label=metric)

    ax.set_xticks(x)
    ax.set_xticklabels(policies)
    ax.set_ylabel('Score')
    ax.set_title('Policy Comparison (Exp. 2)')
    ax.legend()
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", default="data/eval")
    ap.add_argument("--plots-dir", default="data/plots")
    ap.add_argument("--waterfall", default="data/eval/score_bm25_D.json")
    a = ap.parse_args()

    eval_dir = Path(a.eval_dir)
    plots_dir = Path(a.plots_dir)
    ensure_dir(plots_dir)

    # Figure 1: Systems bar
    eval_file = eval_dir / "eval_gold_A.json"
    if eval_file.exists():
        plot_systems_bar(eval_file, plots_dir / "fig1_systems_bar.png")
    else:
        print(f"SKIP fig1 (missing {eval_file})")

    # Figure 2: Error budget stacked
    if Path(a.waterfall).exists():
        plot_error_budget_stacked(Path(a.waterfall), plots_dir / "fig2_error_budget.png")
    else:
        print(f"SKIP fig2 (missing {a.waterfall})")

    # Figures 3-5: real data only; skip cleanly if not yet produced
    plot_recall_vs_corpus_size(eval_dir, plots_dir / "fig3_recall_vs_size.png")
    plot_chunking_ablation(eval_dir, plots_dir / "fig4_chunking_ablation.png")
    plot_policy_comparison(eval_dir, plots_dir / "fig5_policy_comparison.png")

    print(f"\nAll available plots saved to {plots_dir}/")


if __name__ == "__main__":
    main()