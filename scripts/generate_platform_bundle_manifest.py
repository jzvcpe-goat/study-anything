#!/usr/bin/env python3
"""Generate a deterministic manifest for distributing platform integration assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = ROOT / "platform" / "study-anything-platform-tools.json"
BUNDLE_MANIFEST = ROOT / "platform" / "generated" / "study-anything-platform-bundle.json"

FILES: list[tuple[str, str, str]] = [
    (
        "platform/study-anything-platform-tools.json",
        "source_manifest",
        "Source contract for all platform learning tools.",
    ),
    (
        "platform/generated/study-anything-platform-openapi.json",
        "generated_asset",
        "OpenAPI 3.1 import asset for HTTP tool platforms.",
    ),
    (
        "platform/generated/study-anything-openai-tools.json",
        "generated_asset",
        "OpenAI-compatible function tools for Kimi-compatible and other tool-calling agents.",
    ),
    (
        "platform/generated/study-anything-tool-catalog.md",
        "generated_asset",
        "Human-readable tool catalog for platform operators.",
    ),
    (
        "platform/ecosystem-submission.json",
        "submission_manifest",
        "Machine-readable ecosystem submission metadata for platform review.",
    ),
    (
        "platform/generated/study-anything-operator-drill-transcript.json",
        "generated_asset",
        "Deterministic external-platform operator drill transcript.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-contracts.json",
        "generated_asset",
        "Cognitive Loop contract bootstrap verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-cli-artifact.json",
        "generated_asset",
        "Cognitive Loop CLI init, verify, and static HTML artifact verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-run-once-evidence.json",
        "generated_asset",
        "Cognitive Loop run-once LoopRun and DecisionCard evidence verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-project-snapshot.json",
        "generated_asset",
        "Cognitive Loop redacted project snapshot verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-human-gate.json",
        "generated_asset",
        "Cognitive Loop Human Mastery Gate approval and rejection verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-evidence-bundle.json",
        "generated_asset",
        "Cognitive Loop metadata-only evidence bundle verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-event-index.json",
        "generated_asset",
        "Cognitive Loop metadata-only local event index verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-event-store.json",
        "generated_asset",
        "Cognitive Loop local SQLite Event Store verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-watcher-ingest.json",
        "generated_asset",
        "Cognitive Loop manual watcher ingest verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-watcher-runner.json",
        "generated_asset",
        "Cognitive Loop bounded watcher runner-lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-artifact-console.json",
        "generated_asset",
        "Cognitive Loop static HTML Artifact Console Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-personal-plugin-mode.json",
        "generated_asset",
        "Cognitive Loop Personal Plugin Mode Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-evolution-report.json",
        "generated_asset",
        "Cognitive Loop Evolution Report Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-apply-plan.json",
        "generated_asset",
        "Cognitive Loop Governed Apply Plan Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-improvement-comparison.json",
        "generated_asset",
        "Cognitive Loop Measured Improvement Comparator Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-patch-proposal.json",
        "generated_asset",
        "Cognitive Loop Patch Proposal Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-evolution-receipt.json",
        "generated_asset",
        "Cognitive Loop Mastra Evolution Receipt Link Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-evolution-replay.json",
        "generated_asset",
        "Cognitive Loop Mastra Evolution Workflow Replay Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-patch-apply-sandbox.json",
        "generated_asset",
        "Cognitive Loop Governed Patch Apply Sandbox Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-evolution-pack-export.json",
        "generated_asset",
        "Cognitive Loop Professional Evolution Pack Export Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-evolution-pack-consumer.json",
        "generated_asset",
        "Cognitive Loop Professional Evolution Pack zip-only consumer verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-pr-ci-receipt.json",
        "generated_asset",
        "Cognitive Loop PR CI metadata-only receipt verification report with optional GitHub CLI metadata adapter.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-maintainer-acceptance-ledger.json",
        "generated_asset",
        "Cognitive Loop maintainer go/no-go acceptance ledger verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-adapter.json",
        "generated_asset",
        "Cognitive Loop Mastra adapter contract-pack verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-runtime-dry-run.json",
        "generated_asset",
        "Cognitive Loop Mastra runtime dry-run verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-runtime-service.json",
        "generated_asset",
        "Cognitive Loop repository-started Mastra runtime service verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-mastra-runtime-durable.json",
        "generated_asset",
        "Cognitive Loop durable Mastra runtime suspend/resume verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-langfuse-observability.json",
        "generated_asset",
        "Cognitive Loop Langfuse observability DTO mapping verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-study-anything-adapter.json",
        "generated_asset",
        "Cognitive Loop Study Anything Learning Adapter verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-study-adapter-cli.json",
        "generated_asset",
        "Cognitive Loop Study Anything Adapter CLI Lite verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-artifact-doctor.json",
        "generated_asset",
        "Cognitive Loop metadata-only artifact doctor verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-repair-plan.json",
        "generated_asset",
        "Cognitive Loop manual-only repair plan verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-artifact-index.json",
        "generated_asset",
        "Cognitive Loop static local artifact index verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review.json",
        "generated_asset",
        "Cognitive Loop advisory code review verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-prompt.json",
        "generated_asset",
        "External Cognitive Loop Review Agent prompt verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-report.json",
        "generated_asset",
        "External Cognitive Loop Review Agent report handoff verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-handoff-cli.json",
        "generated_asset",
        "External Cognitive Loop Review Agent prepare/validate CLI verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-eval-harness.json",
        "generated_asset",
        "Offline Cognitive Loop Review Agent eval harness verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-ci-receipt.json",
        "generated_asset",
        "External Cognitive Loop Review Agent CI receipt verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json",
        "generated_asset",
        "External Cognitive Loop Review Agent PR comment pack verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json",
        "generated_asset",
        "External Cognitive Loop Review Agent acceptance bundle verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json",
        "generated_asset",
        "External Cognitive Loop Review Agent GitHub workflow template verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
        "generated_asset",
        "External Cognitive Loop Review Agent metadata-only policy gate verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json",
        "generated_asset",
        "External Cognitive Loop Review Agent adoption-pack workflow install smoke verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-review-agent-adoption-drill.json",
        "generated_asset",
        "External Cognitive Loop Review Agent zip-only adoption drill verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json",
        "generated_asset",
        "Cognitive Loop platform-agent adoption cookbook verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-adoption-recipes.json",
        "generated_asset",
        "Machine-readable Cognitive Loop platform-agent adoption recipes.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-replay.json",
        "generated_asset",
        "Cognitive Loop platform-agent recipe replay verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json",
        "generated_asset",
        "Cognitive Loop Skill and platform-pack recipe entrypoint verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-cli.json",
        "generated_asset",
        "Cognitive Loop read-only recipe CLI verification report.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json",
        "generated_asset",
        "Deterministic read-only Cognitive Loop recipe CLI output receipts.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json",
        "generated_asset",
        "Deterministic read-only Cognitive Loop recipe CLI failure receipts.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json",
        "generated_asset",
        "Offline JSON Schemas for Cognitive Loop recipe CLI reports and PR CI receipt/source metadata reports.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json",
        "generated_asset",
        "Negative fixtures proving Cognitive Loop recipe CLI schemas reject drift, unsafe flags, malformed types, and private text probes.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json",
        "generated_asset",
        "Zip-only consumer proof for Cognitive Loop recipe CLI schema evidence in the adoption pack.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json",
        "generated_asset",
        "Tampered adoption-pack failure proof for Cognitive Loop recipe CLI schema evidence.",
    ),
    (
        "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
        "generated_asset",
        "Extracted adoption-pack smoke proof for bundled Cognitive Loop schema consumer checks.",
    ),
    (
        "platform/generated/study-anything-platform-handoff-checklist.json",
        "generated_asset",
        "External platform handoff checklist for import, verification, runtime, and support escalation.",
    ),
    (
        "platform/generated/study-anything-launch-acceptance-ledger.json",
        "generated_asset",
        "Public launch acceptance ledger for GitHub OSS and platform-Agent adoption.",
    ),
    (
        "platform/generated/study-anything-github-launch-operator-guide.json",
        "generated_asset",
        "GitHub launch operator guide proof for release sequence, assets, and local-first boundaries.",
    ),
    (
        "platform/generated/study-anything-release-stack-manifest-fixtures.json",
        "generated_asset",
        "Negative fixtures proving release stack archive manifest boundary checks.",
    ),
    (
        "platform/generated/study-anything-release-stack-intake-candidate.json",
        "generated_asset",
        "Metadata-only release stack intake candidate report for the next PR group.",
    ),
    (
        "platform/generated/study-anything-release-stack-candidate-promotion.json",
        "generated_asset",
        "Metadata-only release stack candidate promotion report for the current PR group.",
    ),
    (
        "platform/generated/study-anything-platform-submission-dry-run.json",
        "generated_asset",
        "External platform submission dry-run readiness report.",
    ),
    (
        "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
        "generated_asset",
        "Manual platform-submission rehearsal and redacted handoff report.",
    ),
    (
        "platform/generated/study-anything-first-lesson-authoring-kit.json",
        "generated_asset",
        "Copyable first-run lesson authoring kit for platform Agents.",
    ),
    (
        "platform/generated/study-anything-external-eval-harness.json",
        "generated_asset",
        "Marketplace-quality external Agent eval harness for platform submissions.",
    ),
    (
        "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
        "generated_asset",
        "Agent eval marketplace enforcement report for optional and required external judge gates.",
    ),
    (
        "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
        "generated_asset",
        "Platform import diagnostics and redacted feedback boundary report.",
    ),
    (
        "platform/generated/study-anything-platform-feedback-package.json",
        "generated_asset",
        "Local-only redacted feedback package manifest for platform adoption support.",
    ),
    (
        "platform/generated/study-anything-platform-feedback-package.zip",
        "generated_asset",
        "Local-only redacted feedback package archive for manual support handoff.",
    ),
    (
        "platform/generated/study-anything-platform-field-rehearsal.json",
        "generated_asset",
        "Redacted field-adoption rehearsal transcript and import quirks report.",
    ),
    (
        "platform/generated/study-anything-platform-support-triage.json",
        "generated_asset",
        "GitHub-first support triage, issue template, and maintainer response playbook report.",
    ),
    (
        "platform/generated/study-anything-platform-onboarding-readiness.json",
        "generated_asset",
        "First external adopter onboarding readiness and maintainer SLA report.",
    ),
    (
        "platform/generated/study-anything-platform-triage-dashboard.json",
        "generated_asset",
        "Generated platform triage dashboard JSON.",
    ),
    (
        "platform/generated/study-anything-platform-triage-dashboard.md",
        "generated_asset",
        "Generated platform triage dashboard Markdown.",
    ),
    (
        "platform/generated/study-anything-public-support-status.json",
        "generated_asset",
        "Public support status report.",
    ),
    (
        "platform/generated/study-anything-public-maintainer-dashboard.json",
        "generated_asset",
        "Public maintainer dashboard JSON.",
    ),
    (
        "platform/generated/study-anything-public-maintainer-dashboard.md",
        "generated_asset",
        "Public maintainer dashboard Markdown.",
    ),
    (
        "platform/generated/study-anything-published-image-evidence.json",
        "generated_asset",
        "Published-image evidence JSON.",
    ),
    (
        "platform/generated/study-anything-published-image-evidence.md",
        "generated_asset",
        "Published-image evidence Markdown.",
    ),
    (
        "platform/generated/study-anything-published-image-evidence.zip",
        "generated_asset",
        "Published-image evidence package.",
    ),
    (
        "platform/generated/study-anything-published-image-evidence.sha256",
        "generated_asset",
        "Published-image evidence checksum.",
    ),
    (
        "platform/generated/study-anything-adopter-evidence-archive.json",
        "generated_asset",
        "External adopter evidence archive JSON.",
    ),
    (
        "platform/generated/study-anything-adopter-evidence-archive.md",
        "generated_asset",
        "External adopter evidence archive Markdown.",
    ),
    (
        "platform/generated/study-anything-adopter-evidence-archive.zip",
        "generated_asset",
        "External adopter evidence archive package.",
    ),
    (
        "platform/generated/study-anything-adopter-evidence-archive.sha256",
        "generated_asset",
        "External adopter evidence archive checksum.",
    ),
    (
        "platform/generated/study-anything-release-asset-adoption.json",
        "generated_asset",
        "GitHub Release asset adoption replay evidence JSON.",
    ),
    (
        "platform/generated/study-anything-release-asset-adoption.md",
        "generated_asset",
        "GitHub Release asset adoption replay evidence Markdown.",
    ),
    (
        "platform/generated/study-anything-release-asset-adoption.zip",
        "generated_asset",
        "GitHub Release asset adoption replay evidence archive.",
    ),
    (
        "platform/generated/study-anything-release-asset-adoption.sha256",
        "generated_asset",
        "GitHub Release asset adoption replay evidence checksum.",
    ),
    (
        "platform/generated/study-anything-release-asset-bootstrap.json",
        "generated_asset",
        "GitHub Release asset bootstrap evidence JSON.",
    ),
    (
        "platform/generated/study-anything-release-asset-bootstrap.md",
        "generated_asset",
        "GitHub Release asset bootstrap evidence Markdown.",
    ),
    (
        "platform/generated/study-anything-release-asset-bootstrap.zip",
        "generated_asset",
        "GitHub Release asset bootstrap evidence archive.",
    ),
    (
        "platform/generated/study-anything-release-asset-bootstrap.sha256",
        "generated_asset",
        "GitHub Release asset bootstrap evidence checksum.",
    ),
    (
        "platform/generated/study-anything-release-cleanroom-bootstrap.json",
        "generated_asset",
        "Release-only cleanroom bootstrap evidence JSON.",
    ),
    (
        "platform/generated/study-anything-release-cleanroom-bootstrap.md",
        "generated_asset",
        "Release-only cleanroom bootstrap evidence Markdown.",
    ),
    (
        "platform/generated/study-anything-release-cleanroom-bootstrap.zip",
        "generated_asset",
        "Release-only cleanroom bootstrap evidence archive.",
    ),
    (
        "platform/generated/study-anything-release-cleanroom-bootstrap.sha256",
        "generated_asset",
        "Release-only cleanroom bootstrap evidence checksum.",
    ),
    (
        "platform/generated/study-anything-platform-agent-replay.json",
        "generated_asset",
        "Platform Agent release replay evidence JSON.",
    ),
    (
        "platform/generated/study-anything-platform-agent-replay.md",
        "generated_asset",
        "Platform Agent release replay evidence Markdown.",
    ),
    (
        "platform/generated/study-anything-platform-agent-replay.zip",
        "generated_asset",
        "Platform Agent release replay evidence archive.",
    ),
    (
        "platform/generated/study-anything-platform-agent-replay.sha256",
        "generated_asset",
        "Platform Agent release replay evidence checksum.",
    ),
    (
        "docs/release-asset-bootstrap.md",
        "operator_doc",
        "GitHub Release asset bootstrap guide for external platform Agents.",
    ),
    (
        "docs/release-cleanroom-bootstrap.md",
        "operator_doc",
        "Release-only cleanroom bootstrap guide for external platform Agents.",
    ),
    (
        "docs/platform-agent-release-replay.md",
        "operator_doc",
        "Platform Agent release replay guide for external tool hosts.",
    ),
    (
        "docs/cognitive-loop-contracts.md",
        "operator_doc",
        "Cognitive Loop local contract bootstrap guide.",
    ),
    (
        "docs/cognitive-loop-code-review.md",
        "operator_doc",
        "Cognitive Loop advisory code review guide.",
    ),
    (
        "platform/prompts/cognitive-loop-review-agent.json",
        "prompt_contract",
        "External Cognitive Loop Review Agent JSON-only prompt contract.",
    ),
    (
        "platform/schemas/cognitive-loop-review-agent-report.schema.json",
        "schema",
        "External Cognitive Loop Review Agent final report JSON Schema.",
    ),
    (
        "platform/schemas/cognitive-loop-pr-ci-receipt.schema.json",
        "schema",
        "Cognitive Loop PR CI receipt JSON Schema for offline platform-Agent validation.",
    ),
    (
        "platform/schemas/cognitive-loop-pr-ci-source.schema.json",
        "schema",
        "Cognitive Loop PR CI source JSON Schema for offline platform-Agent validation.",
    ),
    (
        "fixtures/review-agent/approved.json",
        "fixture",
        "Accepted external Review Agent approved report fixture.",
    ),
    (
        "fixtures/review-agent/needs-review.json",
        "fixture",
        "Accepted external Review Agent needs-review report fixture.",
    ),
    (
        "fixtures/review-agent/needs-fix.json",
        "fixture",
        "Accepted external Review Agent needs-fix report fixture.",
    ),
    (
        "fixtures/review-agent/invalid-low-confidence-final.json",
        "fixture",
        "Rejected external Review Agent low-confidence final finding fixture.",
    ),
    (
        "fixtures/review-agent-receipts/raw-diff-leak.json",
        "fixture",
        "Rejected external Review Agent CI receipt raw-diff leak fixture.",
    ),
    (
        "fixtures/review-agent-pr-comments/raw-diff-leak.json",
        "fixture",
        "Rejected external Review Agent PR comment raw-diff leak fixture.",
    ),
    (
        "fixtures/review-agent-acceptance-bundles/raw-diff-leak/manifest.json",
        "fixture",
        "Rejected external Review Agent acceptance bundle raw-diff leak fixture.",
    ),
    (
        "fixtures/review-agent-github-workflows/unsafe-auto-pr.yml",
        "fixture",
        "Rejected unsafe Review Agent GitHub workflow fixture.",
    ),
    (
        "platform/bootstrap/study_anything_release_bootstrap.py",
        "verification",
        "Standalone release-only cleanroom bootloader.",
    ),
    (
        "scripts/bootstrap_from_release.py",
        "verification",
        "Bootstrap external platform adoption from public GitHub Release assets.",
    ),
    (
        "scripts/generate_release_asset_bootstrap.py",
        "diagnostics",
        "Generate GitHub Release asset bootstrap evidence.",
    ),
    (
        "scripts/generate_release_cleanroom_bootstrap.py",
        "diagnostics",
        "Generate release-only cleanroom bootstrap evidence.",
    ),
    (
        "scripts/replay_platform_agent_from_release.py",
        "verification",
        "Replay platform Agent tool calls from public GitHub Release assets.",
    ),
    (
        "scripts/generate_platform_agent_replay.py",
        "diagnostics",
        "Generate platform Agent release replay evidence.",
    ),
    (
        ".github/ISSUE_TEMPLATE/platform_import_failure.md",
        "support_template",
        "GitHub issue template for external platform import failures.",
    ),
    (
        ".github/ISSUE_TEMPLATE/local_gateway_failure.md",
        "support_template",
        "GitHub issue template for local Agent gateway failures.",
    ),
    (
        ".github/ISSUE_TEMPLATE/published_image_pull_failure.md",
        "support_template",
        "GitHub issue template for published-image pull failures.",
    ),
    (
        ".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md",
        "support_template",
        "GitHub issue template for Agent eval evidence failures.",
    ),
    (
        ".github/ISSUE_TEMPLATE/docs_confusion.md",
        "support_template",
        "GitHub issue template for docs confusion reports.",
    ),
    (
        "fixtures/platform-support-tickets/platform_import_failure.json",
        "support_fixture",
        "Mock privacy-safe support ticket fixture for platform import failure triage.",
    ),
    (
        "fixtures/platform-support-tickets/local_gateway_failure.json",
        "support_fixture",
        "Mock privacy-safe support ticket fixture for local Agent gateway triage.",
    ),
    (
        "fixtures/platform-support-tickets/published_image_pull_failure.json",
        "support_fixture",
        "Mock privacy-safe support ticket fixture for published-image pull triage.",
    ),
    (
        "fixtures/platform-support-tickets/agent_eval_evidence_failure.json",
        "support_fixture",
        "Mock privacy-safe support ticket fixture for Agent eval evidence triage.",
    ),
    (
        "fixtures/platform-support-tickets/docs_confusion.json",
        "support_fixture",
        "Mock privacy-safe support ticket fixture for docs confusion triage.",
    ),
    (
        "fixtures/platform-release-blockers/tool_import_blocker.json",
        "release_blocker_fixture",
        "Mock release blocker fixture for tool import failures.",
    ),
    (
        "fixtures/platform-release-blockers/local_gateway_blocker.json",
        "release_blocker_fixture",
        "Mock release blocker fixture for local gateway failures.",
    ),
    (
        "fixtures/platform-release-blockers/published_image_blocker.json",
        "release_blocker_fixture",
        "Mock release blocker fixture for published-image failures.",
    ),
    (
        "fixtures/platform-release-blockers/agent_eval_blocker.json",
        "release_blocker_fixture",
        "Mock release blocker fixture for Agent eval evidence failures.",
    ),
    (
        "fixtures/platform-release-blockers/support_bundle_privacy_blocker.json",
        "release_blocker_fixture",
        "Mock release blocker fixture for support bundle privacy failures.",
    ),
    (
        "fixtures/platform-status-links/intake.json",
        "status_linkage_fixture",
        "Public status linkage fixture for intake issues.",
    ),
    (
        "fixtures/platform-status-links/needs-repro.json",
        "status_linkage_fixture",
        "Public status linkage fixture for needs-repro issues.",
    ),
    (
        "fixtures/platform-status-links/confirmed.json",
        "status_linkage_fixture",
        "Public status linkage fixture for confirmed issues.",
    ),
    (
        "fixtures/platform-status-links/blocked-by-platform.json",
        "status_linkage_fixture",
        "Public status linkage fixture for blocked-by-platform issues.",
    ),
    (
        "fixtures/platform-status-links/docs-fix.json",
        "status_linkage_fixture",
        "Public status linkage fixture for docs-fix issues.",
    ),
    (
        "fixtures/platform-status-links/release-blocker.json",
        "status_linkage_fixture",
        "Public status linkage fixture for release-blocker issues.",
    ),
    (
        "fixtures/platform-status-links/resolved.json",
        "status_linkage_fixture",
        "Public status linkage fixture for resolved issues.",
    ),
    (
        "fixtures/adopter-evidence-archive/successful-release.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for a successful release handoff.",
    ),
    (
        "fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for local GHCR pull timeout fallback.",
    ),
    (
        "fixtures/adopter-evidence-archive/needs-repro-issue.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for needs-repro support state.",
    ),
    (
        "fixtures/adopter-evidence-archive/release-blocker.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for release blocker support state.",
    ),
    (
        "fixtures/adopter-evidence-archive/platform-blocked.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for platform-blocked support state.",
    ),
    (
        "fixtures/adopter-evidence-archive/resolved-support-case.json",
        "adopter_evidence_fixture",
        "Public evidence fixture for resolved support state.",
    ),
    (
        "fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for local pull timeout fallback.",
    ),
    (
        "fixtures/published-image-evidence/cached-image-missing.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for cached-only local image misses.",
    ),
    (
        "fixtures/published-image-evidence/compose-up-timeout.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for bounded Compose startup timeouts.",
    ),
    (
        "fixtures/published-image-evidence/manifest-only-runtime-unverified.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for manifest-only runtime-unverified handoff.",
    ),
    (
        "fixtures/published-image-evidence/manifest-missing-platform.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for a missing manifest platform.",
    ),
    (
        "fixtures/published-image-evidence/docker-images-failed.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for failed docker-images publishing.",
    ),
    (
        "fixtures/published-image-evidence/ghcr-unavailable.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for GHCR or network unavailability.",
    ),
    (
        "fixtures/published-image-evidence/remote-smoke-pass.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for a passing remote smoke replay.",
    ),
    (
        "fixtures/published-image-evidence/remote-smoke-failed.json",
        "published_image_evidence_fixture",
        "Published-image evidence fixture for runtime smoke failure.",
    ),
    (
        "fixtures/platform-import-failures/schema_mismatch.json",
        "fixture",
        "Mock platform import failure fixture for schema mismatch.",
    ),
    (
        "fixtures/platform-import-failures/missing_local_gateway.json",
        "fixture",
        "Mock platform import failure fixture for missing local gateway.",
    ),
    (
        "fixtures/platform-import-failures/unsupported_auth_mode.json",
        "fixture",
        "Mock platform import failure fixture for unsupported auth mode.",
    ),
    (
        "fixtures/platform-import-failures/tool_naming_drift.json",
        "fixture",
        "Mock platform import failure fixture for tool naming drift.",
    ),
    (
        "fixtures/platform-import-failures/timeout.json",
        "fixture",
        "Mock platform import failure fixture for timeout diagnostics.",
    ),
    (
        "fixtures/platform-import-failures/cors_localhost.json",
        "fixture",
        "Mock platform import failure fixture for browser localhost restrictions.",
    ),
    (
        "fixtures/platform-import-failures/package_corruption.json",
        "fixture",
        "Mock platform import failure fixture for corrupted adoption packages.",
    ),
    (
        "fixtures/platform-import-failures/version_drift.json",
        "fixture",
        "Mock platform import failure fixture for version drift.",
    ),
    (
        "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
        "generated_asset",
        "Copy-ready plugin ecosystem adoption kit for platform submissions.",
    ),
    (
        "platform/generated/study-anything-deployment-hardening.json",
        "generated_asset",
        "Deployment hardening and clean-clone operator path report.",
    ),
    (
        "platform/generated/study-anything-learning-enrichment-bridge.json",
        "generated_asset",
        "Learning Enrichment, NotebookLM, Obsidian, and second-brain operator bridge report.",
    ),
    (
        "platform/packs/README.md",
        "platform_pack",
        "Index for copy-ready platform packs.",
    ),
    (
        "platform/packs/codex/README.md",
        "platform_pack",
        "Codex and terminal-capable Agent setup guide.",
    ),
    (
        "platform/packs/codex/pack.json",
        "platform_pack",
        "Machine-readable Codex pack metadata.",
    ),
    (
        "platform/packs/kimi/README.md",
        "platform_pack",
        "Kimi tool import and gateway setup guide.",
    ),
    (
        "platform/packs/kimi/pack.json",
        "platform_pack",
        "Machine-readable Kimi pack metadata.",
    ),
    (
        "platform/packs/workbuddy/README.md",
        "platform_pack",
        "WorkBuddy-style HTTP tool workspace setup guide.",
    ),
    (
        "platform/packs/workbuddy/pack.json",
        "platform_pack",
        "Machine-readable WorkBuddy pack metadata.",
    ),
    (
        "scripts/openai_compatible_agent_gateway.py",
        "gateway",
        "User-owned OpenAI-compatible HTTP Agent gateway for Kimi and similar providers.",
    ),
    (
        "scripts/setup_env.py",
        "runtime",
        "Generate local .env files with development-safe local secrets.",
    ),
    (
        "scripts/check_env.py",
        "runtime",
        "Validate required local environment variables before launch.",
    ),
    (
        "scripts/doctor.sh",
        "diagnostics",
        "Self-host doctor for Docker, ports, env, Compose config, plugins, and recovery commands.",
    ),
    (
        "scripts/launch_self_host.sh",
        "runtime",
        "Docker Compose self-host launcher for source builds and published GHCR images.",
    ),
    (
        "scripts/stop_self_host.sh",
        "runtime",
        "Docker Compose self-host stop helper.",
    ),
    (
        "scripts/verify_published_image_launch.py",
        "verification",
        "Disposable GHCR published-image launch verifier with local pull-timeout diagnostics.",
    ),
    (
        "scripts/verify_commercial_readiness.py",
        "verification",
        "Commercial-readiness contract verifier for OSS/local-first launch boundaries.",
    ),
    (
        "scripts/verify_adoption_telemetry.py",
        "verification",
        "Aggregate adoption telemetry and PMF readiness verifier.",
    ),
    (
        "scripts/verify_agent_gateway_hardening.py",
        "verification",
        "User-owned Agent gateway hardening and privacy verifier.",
    ),
    (
        "scripts/verify_external_agent_adapter_hardening.py",
        "verification",
        "External Agent eval adapter hardening and bad-output diagnostics verifier.",
    ),
    (
        "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
        "verification",
        "NotebookLM, Obsidian, and Learning Enrichment bridge privacy verifier.",
    ),
    (
        "scripts/verify_plugin_quarantine.py",
        "verification",
        "Plugin trust quarantine and explicit approval verifier.",
    ),
    (
        "scripts/verify_security_recovery_hardening.py",
        "verification",
        "Security recovery, backup manifest, and sync restore privacy verifier.",
    ),
    (
        "scripts/verify_platform_submission_dry_run.py",
        "verification",
        "External platform submission dry-run verifier.",
    ),
    (
        "scripts/verify_platform_manual_submission_rehearsal.py",
        "verification",
        "Manual platform-submission rehearsal verifier.",
    ),
    (
        "scripts/verify_first_lesson_authoring_kit.py",
        "verification",
        "Copyable first-run lesson authoring kit verifier.",
    ),
    (
        "scripts/verify_external_eval_marketplace_harness.py",
        "verification",
        "Marketplace-quality external Agent eval harness verifier.",
    ),
    (
        "scripts/verify_agent_eval_marketplace_enforcement.py",
        "verification",
        "Agent eval marketplace enforcement verifier.",
    ),
    (
        "scripts/verify_platform_adoption_feedback_diagnostics.py",
        "verification",
        "Platform import diagnostics and feedback boundary verifier.",
    ),
    (
        "scripts/generate_platform_feedback_package.py",
        "diagnostics",
        "Generate a local-only redacted platform feedback package.",
    ),
    (
        "scripts/generate_platform_field_rehearsal.py",
        "diagnostics",
        "Generate redacted field-adoption rehearsal transcripts and failed-import fixtures.",
    ),
    (
        "scripts/verify_platform_field_rehearsal.py",
        "verification",
        "Verify field-adoption rehearsals, import quirks, failed-import fixtures, and pack inclusion.",
    ),
    (
        "scripts/generate_platform_support_triage.py",
        "diagnostics",
        "Generate GitHub-first issue templates, support ticket fixtures, and maintainer triage report.",
    ),
    (
        "scripts/verify_platform_support_triage.py",
        "verification",
        "Verify support triage assets, redaction, platform packs, ecosystem metadata, and adoption pack inclusion.",
    ),
    (
        "scripts/generate_platform_onboarding_readiness.py",
        "diagnostics",
        "Generate onboarding readiness, triage dashboard, and release-blocker fixtures.",
    ),
    (
        "scripts/verify_platform_onboarding_readiness.py",
        "verification",
        "Verify onboarding readiness, SLA labels, dashboard, release blockers, packs, submission, and docs.",
    ),
    (
        "scripts/generate_platform_public_support_status.py",
        "diagnostics",
        "Generate public support status, maintainer dashboard, and status-linkage fixtures.",
    ),
    (
        "scripts/verify_platform_public_support_status.py",
        "verification",
        "Verify public support status, dashboard, status-linkage fixtures, packs, submission, and docs.",
    ),
    (
        "scripts/generate_published_image_evidence.py",
        "diagnostics",
        "Generate published-image evidence, checksum, and release fallback fixtures.",
    ),
    (
        "scripts/verify_published_image_evidence.py",
        "verification",
        "Verify published-image evidence, fixtures, platform packs, submission, adoption pack, and docs.",
    ),
    (
        "scripts/generate_adopter_evidence_archive.py",
        "diagnostics",
        "Generate external adopter evidence archive, checksum, and maintainer handoff fixtures.",
    ),
    (
        "scripts/verify_adopter_evidence_archive.py",
        "verification",
        "Verify adopter evidence archive, fixtures, platform packs, submission, adoption pack, and docs.",
    ),
    (
        "scripts/generate_release_asset_adoption.py",
        "diagnostics",
        "Generate GitHub Release asset adoption replay evidence, fixtures, checksum, and archive.",
    ),
    (
        "scripts/verify_release_asset_adoption.py",
        "verification",
        "Verify release assets, sha256 digests, adoption-pack manifest hashes, and replay modes.",
    ),
    (
        "scripts/verify_plugin_ecosystem_adoption_kit.py",
        "verification",
        "Plugin ecosystem sample, registry, and trust-policy adoption verifier.",
    ),
    (
        "scripts/verify_deployment_hardening.py",
        "verification",
        "Deployment hardening and published-image operator path verifier.",
    ),
    (
        "scripts/verify_learning_enrichment_bridge.py",
        "verification",
        "Learning Enrichment operator bridge verifier for platform-agent, NotebookLM, Obsidian, and second-brain handoff.",
    ),
    (
        "scripts/verify_ecosystem_submission_pack.py",
        "verification",
        "Ecosystem submission pack verifier for external platform review readiness.",
    ),
    (
        "scripts/verify_cognitive_loop_contracts.py",
        "verification",
        "Cognitive Loop contract bootstrap verifier.",
    ),
    (
        "scripts/cognitive_loop_cli.py",
        "cli",
        "Local Cognitive Loop contract init, verify, and static HTML artifact CLI.",
    ),
    (
        "scripts/verify_cognitive_loop_cli.py",
        "verification",
        "Cognitive Loop CLI and static HTML artifact verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_run_once.py",
        "verification",
        "Cognitive Loop run-once evidence verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_snapshot.py",
        "verification",
        "Cognitive Loop project snapshot verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_human_gate.py",
        "verification",
        "Cognitive Loop Human Mastery Gate verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_evidence_bundle.py",
        "verification",
        "Cognitive Loop metadata-only evidence bundle verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_event_index.py",
        "verification",
        "Cognitive Loop metadata-only local event index verifier.",
    ),
    (
        "scripts/cognitive_loop_event_store.py",
        "cli",
        "Local SQLite Event Store for validated Cognitive Loop event metadata.",
    ),
    (
        "scripts/verify_cognitive_loop_event_store.py",
        "verification",
        "Cognitive Loop local SQLite Event Store verifier.",
    ),
    (
        "scripts/cognitive_loop_watcher_ingest.py",
        "cli",
        "Manual watcher-event ingest for Cognitive Loop metadata artifacts.",
    ),
    (
        "scripts/verify_cognitive_loop_watcher_ingest.py",
        "verification",
        "Cognitive Loop manual watcher ingest verifier.",
    ),
    (
        "scripts/cognitive_loop_watcher_runner.py",
        "cli",
        "Bounded watcher runner-lite for metadata-only local project signals.",
    ),
    (
        "scripts/verify_cognitive_loop_watcher_runner.py",
        "verification",
        "Cognitive Loop watcher runner-lite verifier.",
    ),
    (
        "scripts/cognitive_loop_artifact_console.py",
        "cli",
        "Static metadata-only Cognitive Loop HTML Artifact Console Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_artifact_console.py",
        "verification",
        "Cognitive Loop HTML Artifact Console Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_personal_mode.py",
        "cli",
        "Read-only Personal Plugin Mode Lite learning artifact builder.",
    ),
    (
        "scripts/verify_cognitive_loop_personal_plugin_mode.py",
        "verification",
        "Cognitive Loop Personal Plugin Mode Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_evolution.py",
        "cli",
        "Read-only Cognitive Loop Evolution Report Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_evolution_report.py",
        "verification",
        "Cognitive Loop Evolution Report Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_apply_plan.py",
        "cli",
        "Governed low-risk Cognitive Loop Apply Plan Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_apply_plan.py",
        "verification",
        "Cognitive Loop Apply Plan Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_improvement_comparator.py",
        "cli",
        "Read-only Cognitive Loop Improvement Comparator Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_improvement_comparator.py",
        "verification",
        "Cognitive Loop Improvement Comparator Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_patch_proposal.py",
        "cli",
        "Read-only Cognitive Loop Patch Proposal Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_patch_proposal.py",
        "verification",
        "Cognitive Loop Patch Proposal Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_mastra_evolution_receipt.py",
        "cli",
        "Read-only Cognitive Loop Mastra Evolution Receipt Link Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_evolution_receipt.py",
        "verification",
        "Cognitive Loop Mastra Evolution Receipt Link Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_mastra_evolution_replay.py",
        "cli",
        "Read-only Cognitive Loop Mastra Evolution Workflow Replay Lite builder.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_evolution_replay.py",
        "verification",
        "Cognitive Loop Mastra Evolution Workflow Replay Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_patch_apply_sandbox.py",
        "cli",
        "Build metadata-only Cognitive Loop governed patch-apply sandbox receipts.",
    ),
    (
        "scripts/verify_cognitive_loop_patch_apply_sandbox.py",
        "verification",
        "Cognitive Loop Governed Patch Apply Sandbox Lite verifier.",
    ),
    (
        "scripts/cognitive_loop_evolution_pack_export.py",
        "cli",
        "Export a metadata-only Cognitive Loop professional evolution evidence pack.",
    ),
    (
        "scripts/verify_cognitive_loop_evolution_pack_export.py",
        "verification",
        "Verify Cognitive Loop professional evolution pack export, zip integrity, and privacy boundaries.",
    ),
    (
        "scripts/verify_cognitive_loop_evolution_pack_consumer.py",
        "verification",
        "Verify Cognitive Loop professional evolution pack zip-only consumer import and privacy boundaries.",
    ),
    (
        "scripts/verify_cognitive_loop_pr_ci_receipt.py",
        "verification",
        "Verify Cognitive Loop PR CI metadata-only receipt decisions, optional GitHub CLI metadata adapter, and privacy boundaries.",
    ),
    (
        "scripts/verify_release_stack_intake_candidate.py",
        "verification",
        "Verify metadata-only release stack intake candidates from PR summary metadata.",
    ),
    (
        "scripts/verify_release_stack_candidate_promotion.py",
        "verification",
        "Verify metadata-only release stack candidate promotion into the manifest.",
    ),
    (
        "fixtures/release-stack/pr-183-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 183.",
    ),
    (
        "fixtures/release-stack/pr-184-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 184.",
    ),
    (
        "fixtures/release-stack/pr-185-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 185.",
    ),
    (
        "fixtures/release-stack/pr-186-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 186.",
    ),
    (
        "fixtures/release-stack/pr-187-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 187.",
    ),
    (
        "fixtures/release-stack/pr-188-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 188.",
    ),
    (
        "fixtures/release-stack/pr-189-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 189.",
    ),
    (
        "fixtures/release-stack/pr-190-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 190.",
    ),
    (
        "fixtures/release-stack/pr-191-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 191.",
    ),
    (
        "fixtures/release-stack/pr-192-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 192.",
    ),
    (
        "fixtures/release-stack/pr-193-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 193.",
    ),
    (
        "fixtures/release-stack/pr-194-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 194.",
    ),
    (
        "fixtures/release-stack/pr-195-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 195.",
    ),
    (
        "fixtures/release-stack/pr-196-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 196.",
    ),
    (
        "fixtures/release-stack/pr-197-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 197.",
    ),
    (
        "fixtures/release-stack/pr-198-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 198.",
    ),
    (
        "fixtures/release-stack/pr-199-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 199.",
    ),
    (
        "fixtures/release-stack/pr-200-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 200.",
    ),
    (
        "fixtures/release-stack/pr-201-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 201.",
    ),
    (
        "fixtures/release-stack/pr-202-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 202.",
    ),
    (
        "fixtures/release-stack/pr-203-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 203.",
    ),
    (
        "fixtures/release-stack/pr-204-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 204.",
    ),
    (
        "fixtures/release-stack/pr-205-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 205.",
    ),
    (
        "fixtures/release-stack/pr-206-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 206.",
    ),
    (
        "fixtures/release-stack/pr-207-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 207.",
    ),
    (
        "fixtures/release-stack/pr-208-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 208.",
    ),
    (
        "fixtures/release-stack/pr-209-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 209.",
    ),
    (
        "fixtures/release-stack/pr-210-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 210.",
    ),
    (
        "fixtures/release-stack/pr-211-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 211.",
    ),
    (
        "fixtures/release-stack/pr-212-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 212.",
    ),
    (
        "fixtures/release-stack/pr-213-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 213.",
    ),
    (
        "fixtures/release-stack/pr-214-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 214.",
    ),
    (
        "fixtures/release-stack/pr-215-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 215.",
    ),
    (
        "fixtures/release-stack/pr-216-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 216.",
    ),
    (
        "fixtures/release-stack/pr-217-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 217.",
    ),
    (
        "fixtures/release-stack/pr-218-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 218.",
    ),
    (
        "fixtures/release-stack/pr-219-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 219.",
    ),
    (
        "fixtures/release-stack/pr-220-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 220.",
    ),
    (
        "fixtures/release-stack/pr-221-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 221.",
    ),
    (
        "fixtures/release-stack/pr-222-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 222.",
    ),
    (
        "fixtures/release-stack/pr-223-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 223.",
    ),
    (
        "fixtures/release-stack/pr-224-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 224.",
    ),
    (
        "fixtures/release-stack/pr-225-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 225.",
    ),
    (
        "fixtures/release-stack/pr-226-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 226.",
    ),
    (
        "fixtures/release-stack/pr-227-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 227.",
    ),
    (
        "fixtures/release-stack/pr-228-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 228.",
    ),
    (
        "fixtures/release-stack/pr-229-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 229.",
    ),
    (
        "fixtures/release-stack/pr-230-intake-candidate.json",
        "fixture",
        "Redacted release stack intake candidate fixture for PR 230.",
    ),
    (
        "scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py",
        "verification",
        "Verify Cognitive Loop maintainer go/no-go acceptance ledger and launch handoff boundaries.",
    ),
    (
        "platform/mastra/README.md",
        "mastra_adapter",
        "Copy-ready Mastra adapter operator guide.",
    ),
    (
        "platform/mastra/manifest.json",
        "mastra_adapter",
        "Machine-readable Mastra adapter contract-pack manifest.",
    ),
    (
        "platform/mastra/cognitive-loop-mastra-adapter.ts",
        "mastra_adapter",
        "TypeScript Mastra workflow scaffold for Cognitive Loop HITL mapping.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_adapter.py",
        "verification",
        "Cognitive Loop Mastra adapter contract-pack verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_runtime_dry_run.py",
        "verification",
        "Cognitive Loop Mastra runtime dry-run verifier.",
    ),
    (
        "platform/mastra-runtime/README.md",
        "mastra_runtime",
        "Repository-started Cognitive Loop Mastra runtime MVP operator notes.",
    ),
    (
        "platform/mastra-runtime/package.json",
        "mastra_runtime",
        "Repository-started Cognitive Loop Mastra runtime package manifest.",
    ),
    (
        "platform/mastra-runtime/package-lock.json",
        "mastra_runtime",
        "Repository-started Cognitive Loop Mastra runtime dependency lockfile.",
    ),
    (
        "platform/mastra-runtime/tsconfig.json",
        "mastra_runtime",
        "Repository-started Cognitive Loop Mastra runtime TypeScript configuration.",
    ),
    (
        "platform/mastra-runtime/src/runtime.ts",
        "mastra_runtime",
        "Repository-started Mastra instance registration for the Cognitive Loop workflow.",
    ),
    (
        "platform/mastra-runtime/src/run-once.ts",
        "mastra_runtime",
        "Deterministic Mastra workflow run covering suspend, resume, bail, and no-gate paths.",
    ),
    (
        "platform/mastra-runtime/src/durable-run.ts",
        "mastra_runtime",
        "Deterministic durable Mastra workflow run covering cross-process resume and bail paths.",
    ),
    (
        "platform/mastra-runtime/src/observability.ts",
        "mastra_runtime",
        "Redacted Langfuse trace, span, generation, and score DTO mapping for Mastra receipts.",
    ),
    (
        "platform/mastra-runtime/src/observability-run.ts",
        "mastra_runtime",
        "Deterministic local Langfuse observability receipt runner.",
    ),
    (
        "platform/mastra-runtime/src/workflows/cognitive-loop-mastra-adapter.ts",
        "mastra_runtime",
        "Runtime-local copy of the Cognitive Loop Mastra workflow adapter kept identical to the public pack.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_runtime_service.py",
        "verification",
        "Cognitive Loop repository-started Mastra runtime service verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_mastra_runtime_durable.py",
        "verification",
        "Cognitive Loop durable Mastra runtime suspend/resume verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_langfuse_observability.py",
        "verification",
        "Cognitive Loop Langfuse observability DTO mapping verifier.",
    ),
    (
        "apps/api/study_anything/core/cognitive_loop_learning_adapter.py",
        "api_core",
        "Study Anything Learning Adapter bridge for Cognitive Loop mastery records.",
    ),
    (
        "scripts/cognitive_loop_study_adapter_cli.py",
        "cli",
        "CLI Lite bridge from Cognitive Loop ProjectEvent/DecisionCard files to Study Anything learning evidence.",
    ),
    (
        "scripts/verify_cognitive_loop_study_anything_adapter.py",
        "verification",
        "Cognitive Loop Study Anything Learning Adapter verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_study_adapter_cli.py",
        "verification",
        "Cognitive Loop Study Anything Adapter CLI Lite verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_artifact_doctor.py",
        "verification",
        "Cognitive Loop metadata-only artifact doctor verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_repair_plan.py",
        "verification",
        "Cognitive Loop manual-only repair plan verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_artifact_index.py",
        "verification",
        "Cognitive Loop static local artifact index verifier.",
    ),
    (
        "scripts/cognitive_loop_review.py",
        "cli",
        "Cognitive Loop advisory code review CLI.",
    ),
    (
        "scripts/verify_cognitive_loop_review.py",
        "verification",
        "Cognitive Loop advisory code review verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_prompt.py",
        "verification",
        "External Cognitive Loop Review Agent prompt verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_report.py",
        "verification",
        "External Cognitive Loop Review Agent report handoff verifier.",
    ),
    (
        "scripts/cognitive_loop_review_agent_handoff.py",
        "cli",
        "External Cognitive Loop Review Agent prepare/validate handoff CLI.",
    ),
    (
        "scripts/cognitive_loop_review_agent_receipt.py",
        "cli",
        "External Cognitive Loop Review Agent metadata-only CI receipt CLI.",
    ),
    (
        "scripts/cognitive_loop_review_agent_pr_comment.py",
        "cli",
        "External Cognitive Loop Review Agent metadata-only PR comment pack CLI.",
    ),
    (
        "scripts/cognitive_loop_review_agent_acceptance_bundle.py",
        "cli",
        "External Cognitive Loop Review Agent metadata-only acceptance bundle CLI.",
    ),
    (
        "platform/workflows/cognitive-loop-review-agent-manual.yml",
        "workflow_template",
        "Manual GitHub Actions template for metadata-only external Review Agent evidence.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_handoff_cli.py",
        "verification",
        "External Cognitive Loop Review Agent handoff CLI verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_eval_harness.py",
        "verification",
        "Offline Cognitive Loop Review Agent eval harness verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_ci_receipt.py",
        "verification",
        "External Cognitive Loop Review Agent CI receipt verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py",
        "verification",
        "External Cognitive Loop Review Agent PR comment pack verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py",
        "verification",
        "External Cognitive Loop Review Agent acceptance bundle verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_github_workflow.py",
        "verification",
        "External Cognitive Loop Review Agent GitHub workflow template verifier.",
    ),
    (
        "scripts/cognitive_loop_review_agent_policy_gate.py",
        "cli",
        "External Cognitive Loop Review Agent metadata-only policy gate CLI.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_policy_gate.py",
        "verification",
        "External Cognitive Loop Review Agent policy gate verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py",
        "verification",
        "External Cognitive Loop Review Agent workflow install smoke verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_review_agent_adoption_drill.py",
        "verification",
        "External Cognitive Loop Review Agent zip-only adoption drill verifier.",
    ),
    (
        "scripts/verify_cognitive_loop_adoption_cookbook.py",
        "verification",
        "Cognitive Loop platform-agent adoption cookbook verifier.",
    ),
    (
        "scripts/generate_cognitive_loop_adoption_recipes.py",
        "verification",
        "Generate machine-readable Cognitive Loop platform-agent adoption recipes.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_replay.py",
        "verification",
        "Verify Cognitive Loop adoption recipes are replay-ready for platform Agents.",
    ),
    (
        "scripts/verify_cognitive_loop_skill_entrypoint.py",
        "verification",
        "Verify Cognitive Loop recipe entrypoints are visible from the Skill and platform packs.",
    ),
    (
        "scripts/cognitive_loop_recipe_cli.py",
        "cli",
        "Read-only Cognitive Loop recipe query CLI for platform Agents.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_cli.py",
        "verification",
        "Verify the read-only Cognitive Loop recipe CLI for platform Agents.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_cli_receipts.py",
        "verification",
        "Generate and verify deterministic Cognitive Loop recipe CLI receipts.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_cli_failures.py",
        "verification",
        "Generate and verify deterministic Cognitive Loop recipe CLI failure receipts.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_cli_schemas.py",
        "verification",
        "Generate and verify offline JSON Schemas for Cognitive Loop recipe CLI reports.",
    ),
    (
        "scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py",
        "verification",
        "Verify negative fixtures for Cognitive Loop recipe CLI JSON Schemas.",
    ),
    (
        "scripts/verify_cognitive_loop_schema_pack_consumer.py",
        "verification",
        "Verify Cognitive Loop schema evidence can be consumed from the adoption pack only.",
    ),
    (
        "scripts/verify_cognitive_loop_schema_pack_consumer_failures.py",
        "verification",
        "Verify Cognitive Loop schema pack consumer failure cases are safe and deterministic.",
    ),
    (
        "scripts/verify_cognitive_loop_pack_extract_smoke.py",
        "verification",
        "Verify the extracted adoption pack can run its included schema consumer checks.",
    ),
    (
        "scripts/verify_platform_handoff_checklist.py",
        "verification",
        "Generate and verify the external platform handoff checklist.",
    ),
    (
        "scripts/verify_launch_acceptance_ledger.py",
        "verification",
        "Generate and verify the public launch acceptance ledger.",
    ),
    (
        "scripts/verify_github_launch_operator_guide.py",
        "verification",
        "Generate and verify the GitHub launch operator guide proof.",
    ),
    (
        "scripts/run_skill_mode_demo.sh",
        "verification",
        "One-command Skill Mode learning-loop smoke for terminal-capable agents.",
    ),
    (
        "scripts/launch_skill_mode.sh",
        "runtime",
        "Local API launcher for Skill Mode and adoption verification.",
    ),
    (
        "scripts/study_anything_cli.py",
        "cli",
        "Command-line learning loop and Agent evidence entrypoint.",
    ),
    (
        "scripts/install_local_plugin.py",
        "cli",
        "CLI for explicit local plugin quarantine and approved install.",
    ),
    (
        "scripts/verify_clean_clone_adoption.py",
        "verification",
        "Disposable clean-clone adoption verifier for external-user smoke testing.",
    ),
    (
        "scripts/verify_openai_compatible_gateway.py",
        "verification",
        "Dry-run verifier for the OpenAI-compatible Agent gateway and API registration flow.",
    ),
    (
        "infra/compose/docker-compose.yml",
        "runtime",
        "Docker Compose source-build stack definition.",
    ),
    (
        "infra/compose/docker-compose.images.yml",
        "runtime",
        "Docker Compose published-image override.",
    ),
    (
        "scripts/verify_platform_lesson_flow.py",
        "verification",
        "End-to-end enriched lesson verifier for platform agents and learning-package export.",
    ),
    (
        "scripts/verify_importer_lesson_flow.py",
        "verification",
        "Importer-to-lesson verifier for Learning Context Package, NotebookLM-style, and Obsidian bridge flows.",
    ),
    (
        "scripts/verify_importer_runtime_retrieval_flow.py",
        "verification",
        "Importer-runtime and retrieval verifier for local Agent platform flows.",
    ),
    (
        "scripts/verify_platform_ecosystem_eval_flow.py",
        "verification",
        "Platform ecosystem verifier for importer, enrichment, retrieval quality, external eval adapters, and export.",
    ),
    (
        "scripts/run_external_agent_evals.py",
        "verification",
        "Wrapper for mature external Agent eval runners such as Promptfoo, DeepEval, and retrieval quality gates.",
    ),
    (
        "scripts/verify_agent_eval_baseline.py",
        "verification",
        "Deterministic Agent eval baseline and regression comparison gate.",
    ),
    (
        "scripts/verify_agent_eval_assets.py",
        "verification",
        "Agent eval asset and adapter contract verifier.",
    ),
    (
        "scripts/generate_platform_adoption_pack.py",
        "verification",
        "Deterministic generator for the distributable external-platform adoption pack.",
    ),
    (
        "scripts/verify_external_adoption.py",
        "verification",
        "Adoption-proof-v1 verifier for external-platform operator handoff.",
    ),
    (
        "scripts/verify_platform_operator_drill.py",
        "verification",
        "Verifier for external platform pack consumption and operator transcript evidence.",
    ),
    (
        "scripts/diagnose_adoption.py",
        "diagnostics",
        "Actionable diagnostics for common external-user adoption blockers.",
    ),
    (
        "evals/promptfoo/agent-eval-artifact.yaml",
        "eval",
        "Promptfoo config for the redacted Agent eval artifact contract.",
    ),
    (
        "evals/README.md",
        "eval",
        "External eval overview and native/optional adapter guide.",
    ),
    (
        "evals/deepeval/study_anything_quality_eval.py",
        "eval",
        "DeepEval custom metric adapter for redacted Study Anything quality reports.",
    ),
    (
        "evals/baselines/study-anything-agent-eval-baseline.json",
        "eval",
        "Committed fast native Agent eval regression baseline.",
    ),
    (
        "evals/fixtures/fake-agent-learning-loop.json",
        "eval_fixture",
        "Fake deterministic Agent eval fixture.",
    ),
    (
        "evals/fixtures/mock-http-agent-learning-loop.json",
        "eval_fixture",
        "Mock HTTP/user-owned Agent eval fixture.",
    ),
    (
        ".cognitive-loop/config.yaml",
        "cognitive_loop_contract",
        "Local-first Cognitive Loop project configuration contract.",
    ),
    (
        ".cognitive-loop/permissions.yaml",
        "cognitive_loop_contract",
        "Cognitive Loop permission and human approval contract.",
    ),
    (
        ".cognitive-loop/evals.yaml",
        "cognitive_loop_contract",
        "Cognitive Loop required eval command contract.",
    ),
    (
        ".cognitive-loop/risk.yaml",
        "cognitive_loop_contract",
        "Cognitive Loop risk and human mastery gate contract.",
    ),
    (
        ".cognitive-loop/watchers.yaml",
        "cognitive_loop_contract",
        "Optional Cognitive Loop manual watcher ingest contract.",
    ),
    (
        "docs/adoption.md",
        "docs",
        "Clean-clone adoption, diagnostics, platform pack, and published-image fallback guide.",
    ),
    (
        "docs/github-launch.md",
        "docs",
        "GitHub launch, tag, release, and published-image verification guide.",
    ),
    (
        "docs/platform-agent-integrations.md",
        "docs",
        "General platform Agent integration guide.",
    ),
    (
        "docs/cognitive-loop-adoption-cookbook.md",
        "docs",
        "Scenario cookbook for local Cognitive Loop operations from platform Agents.",
    ),
    (
        "docs/commercial-readiness.md",
        "docs",
        "Commercial readiness contract, hosted-service boundaries, and local-first launch limits.",
    ),
    (
        "docs/security.md",
        "docs",
        "Local-first security model and recovery hardening guide.",
    ),
    (
        "docs/adoption-telemetry.md",
        "docs",
        "Local aggregate adoption telemetry and PMF readiness privacy contract.",
    ),
    (
        "docs/ecosystem-submission.md",
        "docs",
        "Ecosystem submission metadata, verification, and no-frontend launch guide.",
    ),
    (
        "docs/support-desk.md",
        "docs",
        "GitHub-first support desk, support bundle, and maintainer triage playbook.",
    ),
    (
        "docs/adopter-onboarding.md",
        "docs",
        "First external adopter walkthrough and failure fallback guide.",
    ),
    (
        "docs/maintainer-rotation.md",
        "docs",
        "Maintainer SLA labels, release-blocker handling, and rotation checklist.",
    ),
    (
        "docs/public-support-status.md",
        "docs",
        "Public support status and maintainer dashboard publishing guide.",
    ),
    (
        "docs/adopter-evidence-archive.md",
        "docs",
        "External adopter evidence archive and maintainer handoff guide.",
    ),
    (
        "docs/published-image-evidence.md",
        "docs",
        "Published-image evidence and pull-timeout fallback classification guide.",
    ),
    (
        "docs/release-asset-adoption.md",
        "docs",
        "GitHub Release asset replay verification guide for external platform operators.",
    ),
    (
        "docs/release-checklist.md",
        "docs",
        "Release gate checklist for platform adoption evidence.",
    ),
    (
        "docs/roadmap.md",
        "docs",
        "Roadmap and release track for platform adoption goals.",
    ),
    (
        "docs/learning-enrichment.md",
        "docs",
        "Learning Enrichment Layer context contract and micro-lesson export guide.",
    ),
    (
        "docs/second-brain-handoff.md",
        "docs",
        "Strict Obsidian, NotebookLM-style, and local archive handoff guide.",
    ),
    (
        "docs/obsidian-export.md",
        "docs",
        "Obsidian export privacy and second-brain note guide.",
    ),
    (
        "docs/notebooklm-bridge.md",
        "docs",
        "NotebookLM-style manual bridge contract.",
    ),
    (
        "docs/plugin-sdk.md",
        "docs",
        "Plugin SDK hook, capability, and validation contract.",
    ),
    (
        "docs/plugin-registry.md",
        "docs",
        "Plugin registry digest and local trust policy.",
    ),
    (
        "docs/kimi-agent-gateway.md",
        "docs",
        "Kimi-compatible user-owned HTTP Agent gateway guide.",
    ),
    (
        "docs/use-with-kimi.md",
        "docs",
        "Kimi usage modes for copy-only, HTTP tools, and local Agent gateway.",
    ),
    (
        "docs/operator-drill.md",
        "docs",
        "External platform operator drill and transcript guide.",
    ),
    (
        "docs/agent-eval.md",
        "docs",
        "Agent eval and external evaluation guide.",
    ),
    (
        "docs/eval-frameworks.md",
        "docs",
        "External eval framework selection, adapter boundary, and marketplace harness guide.",
    ),
    (
        "docs/api.md",
        "docs",
        "HTTP API reference for platform workspaces.",
    ),
    (
        "docs/release-notes/v0.3.31-alpha.md",
        "docs",
        "Release notes for the ecosystem submission pack release.",
    ),
    (
        "docs/plugins.md",
        "docs",
        "Plugin and importer manifest guide.",
    ),
    (
        "plugins/registry.json",
        "plugin_registry",
        "Bundled sample plugin registry with source digests.",
    ),
    (
        "plugins/example-note-importer/plugin.json",
        "sample_plugin",
        "Markdown and Obsidian importer manifest.",
    ),
    (
        "plugins/example-note-importer/plugin.py",
        "sample_plugin",
        "Markdown and Obsidian importer template source.",
    ),
    (
        "plugins/example-web-importer/plugin.json",
        "sample_plugin",
        "Web excerpt importer manifest.",
    ),
    (
        "plugins/example-web-importer/plugin.py",
        "sample_plugin",
        "Web excerpt importer template source.",
    ),
    (
        "plugins/example-enrichment-importer/plugin.json",
        "sample_plugin",
        "Learning enrichment importer manifest.",
    ),
    (
        "plugins/example-enrichment-importer/plugin.py",
        "sample_plugin",
        "Learning enrichment importer template source.",
    ),
    (
        "plugins/example-exporter/plugin.json",
        "sample_plugin",
        "Obsidian and second-brain exporter manifest.",
    ),
    (
        "plugins/example-exporter/plugin.py",
        "sample_plugin",
        "Obsidian and second-brain exporter template source.",
    ),
    (
        "plugins/example-agent-provider/plugin.json",
        "sample_plugin",
        "User-owned Agent provider manifest template.",
    ),
    (
        "plugins/example-agent-provider/plugin.py",
        "sample_plugin",
        "User-owned Agent provider template source.",
    ),
    (
        "fixtures/notebooklm/README.md",
        "fixture",
        "NotebookLM-style import/export fixture notes.",
    ),
    (
        "fixtures/notebooklm/notebooklm-style-context-package.json",
        "fixture",
        "Learning Context Package import fixture covering web, document, video, app, Markdown, and Obsidian sources.",
    ),
    (
        "skills/study-anything/SKILL.md",
        "skill",
        "Repo-local Codex Skill entrypoint for terminal-capable agents.",
    ),
]


class BundleManifestError(RuntimeError):
    """Readable bundle manifest failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BundleManifestError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleManifestError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = ROOT / relative_path
    if not path.exists():
        raise BundleManifestError(f"Bundle file is missing: {relative_path}")
    if any(part in {".env", "data", "__pycache__"} for part in path.parts):
        raise BundleManifestError(f"Bundle file is not safe to distribute: {relative_path}")
    return {
        "path": relative_path,
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_manifest() -> dict[str, object]:
    source = load_json(SOURCE_MANIFEST)
    if source.get("schema_version") != "study-anything-platform-tools-v1":
        raise BundleManifestError("Source platform manifest schema drifted.")
    file_paths = [path for path, _kind, _purpose in FILES]
    if len(file_paths) != len(set(file_paths)):
        raise BundleManifestError("Bundle file list contains duplicates.")
    return {
        "schema_version": "study-anything-platform-bundle-v1",
        "name": "study-anything-platform-bundle",
        "description": (
            "Deterministic file manifest for distributing Study Anything platform packs, "
            "tool import assets, Skill instructions, and acceptance evidence."
        ),
        "source_manifest": "platform/study-anything-platform-tools.json",
        "source_manifest_sha256": sha256(SOURCE_MANIFEST),
        "platforms": ["codex", "kimi", "workbuddy"],
        "privacy_contract": source.get("privacy_contract", {}),
        "acceptance_commands": [
            "python3 scripts/generate_platform_agent_assets.py --check",
            "python3 scripts/verify_commercial_readiness.py",
            "python3 scripts/verify_notebooklm_obsidian_bridge_hardening.py",
            "python3 scripts/verify_learning_enrichment_bridge.py --check",
            "python3 scripts/verify_plugin_quarantine.py",
            "python3 scripts/verify_security_recovery_hardening.py",
            "python3 scripts/verify_platform_submission_dry_run.py --check",
            "python3 scripts/verify_platform_manual_submission_rehearsal.py --check",
            "python3 scripts/verify_first_lesson_authoring_kit.py --check",
            "python3 scripts/verify_external_eval_marketplace_harness.py --check",
            "python3 scripts/verify_agent_eval_marketplace_enforcement.py --check",
            "python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check",
            ".venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check",
            "python3 scripts/verify_cognitive_loop_artifact_console.py --check",
            "python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check",
            "python3 scripts/verify_cognitive_loop_evolution_report.py --check",
            "python3 scripts/verify_cognitive_loop_apply_plan.py --check",
            "python3 scripts/verify_cognitive_loop_improvement_comparator.py --check",
            "python3 scripts/verify_cognitive_loop_patch_proposal.py --check",
            "python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check",
            "python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check",
            "python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check",
            "python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check",
            ".venv/bin/python scripts/verify_cognitive_loop_study_adapter_cli.py --check",
            "python3 scripts/generate_platform_feedback_package.py --check",
            "python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check",
            "python3 scripts/verify_deployment_hardening.py --check",
            "python3 scripts/verify_ecosystem_submission_pack.py",
            "python3 scripts/verify_clean_clone_adoption.py --repo .",
            "python3 scripts/verify_platform_ecosystem_packs.py",
            "python3 scripts/generate_release_cleanroom_bootstrap.py --check",
            "python3 platform/bootstrap/study_anything_release_bootstrap.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only",
            "python3 scripts/generate_platform_bundle_manifest.py --check",
            "python3 scripts/generate_platform_adoption_pack.py --check",
            (
                "python3 scripts/verify_external_adoption.py --pack "
                "platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
            "python3 scripts/verify_openai_compatible_gateway.py --gateway-only",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py",
            (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/verify_importer_runtime_retrieval_flow.py"
            ),
            (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/verify_platform_ecosystem_eval_flow.py"
            ),
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py",
            (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool report --create-session --required"
            ),
            (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool deepeval --create-session --allow-native-quality-fallback"
            ),
            (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required"
            ),
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py",
            "python3 scripts/diagnose_adoption.py",
        ],
        "files": [file_record(*item) for item in FILES],
    }


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_manifest() -> None:
    BUNDLE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_MANIFEST.write_text(dump_json(build_manifest()), encoding="utf-8")
    print(f"wrote {BUNDLE_MANIFEST.relative_to(ROOT)}")


def check_manifest() -> None:
    expected = dump_json(build_manifest())
    if not BUNDLE_MANIFEST.exists():
        raise BundleManifestError(
            "Platform bundle manifest is missing. Run "
            "`python3 scripts/generate_platform_bundle_manifest.py`."
        )
    actual = BUNDLE_MANIFEST.read_text(encoding="utf-8")
    if actual != expected:
        raise BundleManifestError(
            "Platform bundle manifest is stale. Run "
            "`python3 scripts/generate_platform_bundle_manifest.py`."
        )
    print("ok    generated platform bundle manifest is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the bundle manifest is stale")
    args = parser.parse_args()
    if args.check:
        check_manifest()
    else:
        write_manifest()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_bundle_manifest failed: {exc}", file=sys.stderr)
        sys.exit(1)
