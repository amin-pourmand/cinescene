"""Render the completed diagnostic JSON as a readable, complete input ledger."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def regrade_identities(report, aliases):
    from evaluation_metrics import expected_rank
    from scripts.broad_retrieval_benchmark import report_metrics, resolve_case_identities
    updated = copy.deepcopy(report)
    changed = 0
    for number, source in enumerate(updated["rows"]):
        if source["kind"] != "retrieval":
            continue
        row = resolve_case_identities([source], aliases)[0]
        for result in row["results"]:
            previous = str(result["id"])
            current = resolve_case_identities([{"expected_ids": [previous]}], aliases)[0]["expected_ids"][0]
            if current != previous:
                result["original_id"] = previous
                result["id"] = current
        rank = expected_rank(row["results"], row)
        if rank != row["rank"]:
            row["previous_rank"] = row["rank"]
            changed += 1
        row["rank"] = rank
        updated["rows"][number] = row
    updated["original_retrieval"] = report["retrieval"]
    updated.update(report_metrics(updated["rows"]))
    updated["identity_resolution"] = aliases
    updated["canonical_regrading"] = {"changed_retrieval_ranks": changed, "inference_repeated": False,
                                      "result_positions_preserved": True,
                                      "scope": "Verified ID normalization only; no sorting, deduplication, query or intended-title edits. Coverage/probes unchanged."}
    return updated


def redact_private_results(report, private_ids):
    public = copy.deepcopy(report)
    aliases = {str(value): f"private-local:{i}" for i, value in enumerate(sorted(private_ids), 1)}
    seen = set()
    for row in public["rows"]:
        targets = list(row.get("expected_ids") or []) + list(row.get("original_expected_ids") or [])
        if set(map(str, targets)) & set(aliases):
            raise ValueError("A benchmark target is private; do not publish its query or label")
        for key in ("results", "catalog_matches", "other_versions"):
            for item in row.get(key, []):
                identities = [str(item.get("id")), str(item.get("original_id"))]
                private = next((identity for identity in identities if identity in aliases), None)
                if private:
                    seen.add(aliases[private])
                    item["id"] = aliases[private]
                    item["title"] = "Private local title " + aliases[private].split(":")[-1]
                    if "original_id" in item:
                        item["original_id"] = aliases[private]
                elif identities[0].startswith("private-local:"):
                    seen.add(identities[0])
    public["publication_redaction"] = {"private_result_identities": len(seen), "rankings_unchanged": True,
                                       "policy": "Non-allowlisted local result IDs/titles are pseudonymized. Raw identities remain in the local checkpoint only."}
    return public


def cell(value):
    return str(value if value is not None else "not found").replace("|", "\\|").replace("\n", " ")


def counts(rows):
    total = len(rows)
    first = sum(row.get("rank") == 1 for row in rows)
    five = sum(row.get("rank") is not None and row["rank"] <= 5 for row in rows)
    return [total, first, f"{100 * first / total:.1f}%" if total else "n/a", five,
            f"{100 * five / total:.1f}%" if total else "n/a"]


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(cell(value) for value in row) + " |" for row in rows], ""]


def render_report(report):
    rows = report["rows"]
    retrieval = [row for row in rows if row["kind"] == "retrieval"]
    lines = ["# CineScene Broad Diagnostic", "",
             f"Completed **{report['completed_inputs']}/{report['planned_inputs']} HTTP inputs** against `{report['engine']['fusion_version']}`. "
             f"Engine unchanged: **{report['engine_unchanged']}**. Technical errors: **{report['technical_errors']}**. "
             f"Retrievals with reduced capabilities: **{report.get('degraded_retrieval', 0)}**.", "",
             "The engine policy is fixed during this run. Cases may have informed earlier development; this is a manual diagnostic sample, not a population accuracy estimate. "
             "All retrieval targets were checked by exact catalog ID before execution. Only the intended title is labeled; other plausible adaptations or related stories were not exhaustively judged. "
             "Source-informed episode checks, when present, are acceptance checks, not independent scene-recognition evidence.", "",
             report.get("description", ""), "",
             "## Retrieval", ""]
    if report.get("publication_redaction"):
        lines[6:6] = ["Publication privacy: non-allowlisted local result labels/IDs are pseudonymized. Rankings and metrics are unchanged; original identities remain in the local checkpoint on E.", ""]
    if report.get("identity_resolution"):
        lines += ["Canonical ID aliases were resolved from the attributed dataset's exact-title/main-cast reconciliation. "
                  "Queries, intended titles and version labels were not rewritten. Remapped cases retain `original_expected_ids` in JSON; "
                  "this is identity normalization, not substring or same-title fallback grading.", ""]
    if report.get("canonical_regrading"):
        lines += [f"Retrospective canonical re-grading of the saved run: **{report['canonical_regrading']['changed_retrieval_ranks']}** retrieval ranks changed. "
                  "No inference was repeated. Original return positions are preserved, including duplicate slots; coverage/probe judgments are unchanged. "
                  "The original report remains separate.", ""]
    groups = [("All retrieval inputs", retrieval), ("Manual inputs only", [row for row in retrieval if row["provenance"] == "manual"])]
    groups.extend((language, [row for row in retrieval if row["language"] == language]) for language in ("en", "fa", "mixed"))
    lines += table(["Group", "Inputs", "First", "Hit@1", "Top five", "Hit@5"], [[name, *counts(selected)] for name, selected in groups])
    lines += ["Category and language groups overlap; do not add their counts together.", ""]
    persian = [row for row in retrieval if row["language"] == "fa"]
    first_choices = Counter(row["results"][0]["title"] for row in persian if row["results"])
    if first_choices:
        title, count = first_choices.most_common(1)[0]
        lines += [f"Persian first-choice concentration: **{cell(title)}** appears first in **{count}/{len(persian)}** queries. "
                  "This is a diagnostic symptom, not proof of a single cause; no title-specific correction was applied.", ""]
    categories = sorted({row["category"] for row in retrieval})
    lines += table(["Category", "Inputs", "First", "Hit@1", "Top five", "Hit@5"],
                   [[category, *counts([row for row in retrieval if row["category"] == category])] for category in categories])
    paired = [row for row in retrieval if row["pair"]]
    pair_count = report["paired_topics"]["complete_pairs"]
    lines += ["## Paired Language Check", "", f"The same {pair_count} target stories were described in English and Persian. This is a stronger language comparison than comparing unrelated language samples.", ""]
    lines += table(["Language", "Inputs", "First", "Hit@1", "Top five", "Hit@5"],
                   [[language, *counts([row for row in paired if row["language"] == language])] for language in ("en", "fa")])
    p = report["paired_topics"]
    lines += [f"Both first: **{p['both_first']}**. English-only first: **{p['english_only_first']}**. "
              f"Persian-only first: **{p['persian_only_first']}**. Neither first: **{p['neither_first']}**.", "",
              "## Coverage Check", "", "Requested titles/versions, when present, deliberately probe coverage, including known weak areas. They are not a random sample of cinema. "
              "Movie remakes require the requested year. Series provider years are not treated as canonical premiere years. Aliases such as La Casa de Papel are resolved exactly.", ""]
    coverage = [row for row in rows if row["kind"] == "coverage"]
    lines += table(["Requested title", "Requested year", "In catalog", "Rank", "Returned results despite absence"],
                   [[row["expected"][0], row["requested_year"], row["catalog_present"], row["rank"], row["returned_results_for_missing_target"]] for row in coverage])
    lines += ["## Non-Retrieval Probes", "", "Negative inputs should produce no movie suggestion or a clear input rejection. Ambiguous-probe passes mean only that the API returned multiple distinct suggestions, not that those suggestions were judged relevant. Invalid inputs must return HTTP 422.", ""]
    lines += table(["Kind", "Inputs", "Passed"], [[kind, values["cases"], values["passed"]] for kind, values in report["probes"].items()])
    lines += ["## Complete Input Ledger", "", "Rank `not found` means absent from the ten returned results, not absent from the catalog. The full JSON retains all ten result identities. No private paths, transcripts or plot text are exported.", ""]
    for kind in ("retrieval", "coverage", "negative", "ambiguous", "invalid"):
        lines += [f"### {kind}", ""]
        data = []
        for row in rows:
            if row["kind"] != kind:
                continue
            query = row.get("query")
            if query and len(query) > 300:
                query = f"[input length {len(query)}; full content in JSON]"
            expected = ", ".join(row.get("expected") or [])
            if row.get("episode") is not None:
                expected += f" S{row['season']:02}E{row['episode']:02}"
            top = row["results"][0]["title"] if row["results"] else "no results"
            data.append([row["id"], row.get("language") or "n/a", query, expected or kind, row["status"], row["rank"], top])
        lines += table(["ID", "Language", "Actual input", "Expected", "HTTP", "Rank", "First result"], data)
    lines += ["## Reproduce", "", "Run the backend first; the runner reuses it and never loads a second copy of the models.", "",
              "```powershell", ".\\.venv\\Scripts\\python.exe scripts/broad_retrieval_benchmark.py --preflight",
              ".\\.venv\\Scripts\\python.exe scripts/broad_retrieval_benchmark.py --output E:/CineSceneCache/cinescene/artifacts/broad-next.json",
              ".\\.venv\\Scripts\\python.exe scripts/summarize_broad_benchmark.py --input benchmarks/broad-latest.json --output benchmarks/broad-report.md", "```", "",
              "Use `--resume` with the same output/checkpoint after interruption; mismatched suites or engines are rejected. "
              "The configured system-drive free-space guard prevents starting another request when space is low. Windows paging can still grow temporarily on C during CPU inference even when model files and checkpoints are on E.", "",
              f"Suite SHA-256: `{report['suite_sha256']}`. Observed HTTP latency: median **{report['retrieval_p50_sec']} s**, p95 **{report['retrieval_p95_sec']} s**. "
              "This is not a controlled throughput/load benchmark, nor a benchmark of all inputs in browser WASM.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="benchmarks/broad-latest.json")
    parser.add_argument("--output", default="benchmarks/broad-report.md")
    parser.add_argument("--public-json", help="Export a privacy-filtered structured report alongside the Markdown")
    parser.add_argument("--private-catalog", default="data/processed/offline_media_enriched.json")
    parser.add_argument("--identity-aliases", help="Explicit retrospective re-grading using a source-verified index report's identity_aliases; never changes source rankings.")
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.identity_aliases:
        report = regrade_identities(report, json.loads(Path(args.identity_aliases).read_text(encoding="utf-8"))["identity_aliases"])
    if args.public_json:
        from scripts.build_pwa_catalog import can_publish_media
        local = json.loads(Path(args.private_catalog).read_text(encoding="utf-8"))
        report = redact_private_results(report, {str(row["id"]) for row in local if not can_publish_media(row)})
        Path(args.public_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.output).write_text(render_report(report), encoding="utf-8")
    print(f"Rendered {report['completed_inputs']} inputs to {args.output}")


if __name__ == "__main__":
    main()
