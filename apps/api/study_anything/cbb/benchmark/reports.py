"""Human-readable benchmark reports with an explicit claim boundary."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping

from study_anything.cbb.benchmark.models import BenchmarkResultV1


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown_report(
    *,
    result: BenchmarkResultV1,
    manifest: Mapping[str, Any],
    failures: Mapping[str, Any],
    ablation_summary: Mapping[str, Any],
    power_analysis: Mapping[str, Any],
    cost_effect_analysis: Mapping[str, Any],
    trials: int,
) -> str:
    mechanism = result.evidence_basis == "mechanism_fixture"
    banner = (
        "MECHANISM REHEARSAL ONLY. These numbers validate benchmark plumbing and do not "
        "measure Delivery Clearance effectiveness."
        if mechanism
        else "OBSERVED 40-CASE PILOT. This estimates effects only for the frozen personal-local "
        "tasks, model, budget, and review protocol recorded here."
    )
    lines = [
        "# Native Agent vs Delivery Clearance Benchmark v0.1",
        "",
        f"> **{banner}**",
        "",
        "## Run status",
        "",
        f"- Status: `{result.status}`",
        f"- Reviewer execution evidence: `{result.evidence_basis}`",
        f"- Candidate scorer evidence: `{result.candidate_evidence_basis}`",
        f"- Reference adjudication evidence: `{result.reference_evidence_basis}`",
        f"- Cases: `{result.case_count}`",
        f"- Trials per case: `{trials}`",
        f"- Evaluated paired runs: `{result.evaluated_paired_run_count}`",
        f"- Completed paired runs: `{result.completed_paired_run_count}`",
        f"- Tool traces: `{result.tool_trace_count}`; complete: "
        f"`{str(result.tool_trace_coverage_complete).lower()}`",
        f"- Failed, missing, or inconclusive records: `{failures['failure_count']}`",
        "",
        "## Decision metrics",
        "",
        "| Arm | False clearance | 95% CI | False block | 95% CI | Severe escape | Scope expansion | Median cost | Median latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for metric in result.arm_metrics:
        lines.append(
            "| "
            + " | ".join(
                [
                    metric.arm.value,
                    f"{metric.false_clearance_count}/{metric.dangerous_case_count} ({_percent(metric.false_clearance_rate)})",
                    f"{_percent(metric.false_clearance_ci_low)} to {_percent(metric.false_clearance_ci_high)}",
                    f"{metric.false_block_count}/{metric.safe_case_count} ({_percent(metric.false_block_rate)})",
                    f"{_percent(metric.false_block_ci_low)} to {_percent(metric.false_block_ci_high)}",
                    f"{metric.severe_escape_count} ({_percent(metric.severe_escape_rate)})",
                    f"{metric.scope_expansion_count} ({_percent(metric.scope_expansion_rate)})",
                    f"${metric.median_cost_usd:.4f}",
                    f"{metric.median_wall_time_ms:.0f} ms",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Paired comparisons with independent clearance",
            "",
            "| Baseline | FCR difference | 95% paired bootstrap CI | Exact McNemar p | False-block difference | Practical threshold |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for analysis in result.pairwise_analyses:
        lines.append(
            "| "
            + " | ".join(
                [
                    analysis.baseline_arm.value,
                    _percent(analysis.false_clearance_rate_difference),
                    f"{_percent(analysis.bootstrap_ci_low)} to {_percent(analysis.bootstrap_ci_high)}",
                    f"{analysis.mcnemar_exact_p_value:.4f}",
                    _percent(analysis.false_block_rate_difference),
                    str(analysis.practical_significance_threshold_met).lower(),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Human review load",
            "",
            f"- Full-review reference median: `{result.full_review_reference_median_ms}` ms",
            f"- Boundary-reconstruction median: `{result.boundary_reconstruction_median_ms}` ms",
            f"- Review compression ratio: `{result.review_compression_ratio}`",
            "- Five boundary questions are aggregated; raw answers and attention streams are not stored.",
            "",
            "## Ablation",
            "",
            f"- Evidence basis: `{result.ablation_evidence_basis}`",
            f"- Six variants complete: `{str(result.ablation_complete).lower()}`",
            f"- Claim boundary: {ablation_summary['claim_boundary']}",
            "",
            "| Variant | Observations | Authorized | Evidence |",
            "|---|---:|---:|---|",
        ]
    )
    for item in ablation_summary["variants"]:
        lines.append(
            f"| {item['variant']} | {item['observation_count']} | "
            f"{item['authorized_count']} | {item['evidence_origin']} |"
        )
    primary_power = power_analysis["comparisons"][0]
    target_band = power_analysis["initial_confirmatory_target_band"]
    lines.extend(
        [
            "",
            "## Confirmatory power planning",
            "",
            f"- Status: `{power_analysis['status']}`",
            f"- Primary dangerous pairs: `{primary_power['completed_dangerous_pair_count']}` / "
            f"`{primary_power['expected_dangerous_pair_count']}`",
            f"- Observed direction: `{primary_power['observed_direction']}`",
            "- Required balanced total cases at 80% power: "
            f"`{primary_power['required_balanced_total_cases_80_power']}`",
            "- Required balanced total cases at 90% power: "
            f"`{primary_power['required_balanced_total_cases_90_power']}`",
            f"- Recommended fresh confirmatory total: `{target_band['recommended_total_cases']}`",
            f"- Claim boundary: {power_analysis['claim_boundary']}",
            "",
            "## Safety and cost",
            "",
            f"- Status: `{cost_effect_analysis['status']}`",
            "- Perspective: "
            f"`{cost_effect_analysis['economic_evaluation_plan']['evaluation_perspective']}`",
            "- Recorded monetary cost complete: "
            f"`{str(cost_effect_analysis['recorded_monetary_cost_complete']).lower()}`",
            "- Reviewer time value: "
            f"`{cost_effect_analysis['economic_evaluation_plan']['reviewer_time_value_usd_per_hour']}` USD/hour",
            "- Delivery delay value: "
            f"`{cost_effect_analysis['economic_evaluation_plan']['delivery_delay_value_usd_per_hour']}` USD/hour",
            f"- Cost bases: `{cost_effect_analysis['cost_basis_counts']}`",
            "",
            "| Baseline | Complete pairs | Net false clearances avoided | 95% mean-effect CI | Net false blocks added | Guardrail | Median latency delta | Total incremental cost |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for comparison in cost_effect_analysis["comparisons"]:
        lines.append(
            f"| {comparison['baseline_arm']} | {comparison['completed_pair_count']} | "
            f"{comparison['net_false_clearances_avoided']} | "
            f"{comparison['mean_false_clearances_avoided_ci_low']:.3f} to "
            f"{comparison['mean_false_clearances_avoided_ci_high']:.3f} | "
            f"{comparison['net_false_blocks_added']} | "
            f"{str(comparison['false_block_guardrail_met']).lower()} | "
            f"{comparison['median_incremental_wall_time_ms']:.0f} ms | "
            f"{comparison['total_incremental_cost_usd']} |"
        )
    human_review = cost_effect_analysis["human_review"]
    lines.extend(
        [
            "",
            "### Incremental human-review comparison",
            "",
            f"- Complete full-review/boundary pairs: `{human_review['completed_pair_count']}` / "
            f"`{human_review['expected_pair_count']}`",
            f"- Total review time saved: `{human_review['total_review_time_saved_ms']}` ms",
            "- Mean boundary accuracy difference: "
            f"`{human_review['mean_boundary_accuracy_difference']}`",
            f"- Accuracy guardrail met: `{str(human_review['accuracy_guardrail_met']).lower()}`",
            f"- Classification: `{human_review['economic_classification']}`",
            "- Reviewer identity is not collected; role matching cannot establish reviewer independence.",
            f"- Claim boundary: {cost_effect_analysis['claim_boundary']}",
        ]
    )
    lines.extend(
        [
            "",
            "## Public source provenance",
            "",
            "| Source | Task data revision | Scorer revision | License scope | Vendored |",
            "|---|---|---|---|---:|",
        ]
    )
    for source in manifest["sources"]:
        lines.append(
            f"| {source['benchmark_id']} | `{source['task_data_revision']}` | "
            f"`{source['scorer_source_revision']}` | "
            f"{source['license_id']} / {source['license_use_scope']} | "
            f"{str(source['upstream_payload_vendored']).lower()} |"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            result.claim_boundary.current_claim,
            "",
            "Maximum scope: `personal_local`.",
            "",
            "This report does not claim:",
        ]
    )
    lines.extend(f"- {claim}" for claim in result.claim_boundary.not_claimed)
    lines.extend(
        [
            "",
            "A confirmatory claim requires fresh hidden tasks, blinded adjudication, frozen analysis code, and a preregistered power analysis.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html_report(markdown: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Native Agent vs Delivery Clearance Benchmark v0.1</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:32px;"
        "color:#161616;background:#fff}pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;"
        "font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;border-left:4px solid "
        "#d92d20;padding-left:20px} @media(max-width:640px){body{padding:18px}}</style></head><body>"
        f"<pre>{escape(markdown)}</pre></body></html>\n"
    )
