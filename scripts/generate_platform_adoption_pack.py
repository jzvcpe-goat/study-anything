#!/usr/bin/env python3
"""Generate the distributable platform adoption pack archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
MANIFEST_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.json"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.zip"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"


PACK_FILES: list[tuple[str, str, str]] = [
    ("README.md", "root_doc", "Repository overview and local-first launch entrypoint."),
    ("docs/adoption.md", "operator_doc", "Clean-clone and published-image adoption guide."),
    ("docs/github-launch.md", "operator_doc", "GitHub launch, tag, release, and published-image verification guide."),
    ("docs/platform-agent-integrations.md", "operator_doc", "General external platform Agent integration guide."),
    ("docs/cognitive-loop-adoption-cookbook.md", "operator_doc", "Scenario cookbook for Kimi, Codex, WorkBuddy, and private platform Agent Cognitive Loop operations."),
    ("docs/platform-agent-release-replay.md", "operator_doc", "Release-asset platform Agent replay simulator guide."),
    ("docs/learning-enrichment.md", "operator_doc", "Learning Enrichment Layer context contract and micro-lesson export guide."),
    ("docs/second-brain-handoff.md", "operator_doc", "Strict Obsidian, NotebookLM-style, and local archive handoff guide."),
    ("docs/obsidian-export.md", "operator_doc", "Obsidian export privacy and second-brain note guide."),
    ("docs/notebooklm-bridge.md", "operator_doc", "NotebookLM-style manual bridge contract."),
    ("docs/plugin-sdk.md", "operator_doc", "Plugin SDK hook, capability, and validation contract."),
    ("docs/plugin-registry.md", "operator_doc", "Plugin registry digest and local trust policy."),
    ("docs/plugins.md", "operator_doc", "Plugin examples, manifest, quarantine, and sample install guide."),
    ("docs/kimi-agent-gateway.md", "operator_doc", "Kimi-compatible HTTP Agent gateway guide."),
    ("docs/use-with-kimi.md", "operator_doc", "Kimi usage modes for copy-only, HTTP tools, and local Agent gateway."),
    ("docs/operator-drill.md", "operator_doc", "External platform operator drill and transcript guide."),
    ("docs/self-hosting.md", "operator_doc", "Docker/Skill Mode self-hosting guide."),
    ("docs/security.md", "operator_doc", "Local-first security model and recovery hardening guide."),
    ("docs/commercial-readiness.md", "operator_doc", "Commercial readiness contract, hosted-service boundaries, and local-first launch limits."),
    ("docs/adoption-telemetry.md", "operator_doc", "Local aggregate adoption telemetry and PMF readiness privacy contract."),
    ("docs/ecosystem-submission.md", "operator_doc", "Ecosystem submission metadata, verification, and no-frontend launch guide."),
    ("docs/support-desk.md", "operator_doc", "GitHub-first support desk, support bundle, and maintainer triage playbook."),
    ("docs/adopter-onboarding.md", "operator_doc", "First external adopter walkthrough and failure fallback guide."),
    ("docs/maintainer-rotation.md", "operator_doc", "Maintainer SLA labels, release blocker handling, and rotation checklist."),
    ("docs/public-support-status.md", "operator_doc", "Public support status and maintainer dashboard publishing guide."),
    ("docs/adopter-evidence-archive.md", "operator_doc", "External adopter evidence archive and maintainer handoff guide."),
    ("docs/published-image-evidence.md", "operator_doc", "Published-image evidence and pull-timeout fallback classification guide."),
    ("docs/release-asset-adoption.md", "operator_doc", "GitHub Release asset adoption replay guide."),
    ("docs/release-asset-bootstrap.md", "operator_doc", "GitHub Release asset bootstrap entrypoint for external platform Agents."),
    ("docs/release-cleanroom-bootstrap.md", "operator_doc", "Release-only cleanroom bootloader guide for repo-free external adoption."),
    ("docs/release-checklist.md", "operator_doc", "Release gate checklist for platform adoption evidence."),
    ("docs/roadmap.md", "operator_doc", "Roadmap and release track for platform adoption goals."),
    ("docs/cognitive-loop-contracts.md", "operator_doc", "Cognitive Loop local contract bootstrap and privacy boundary guide."),
    (".cognitive-loop/watchers.yaml", "cognitive_loop_contract", "Optional Cognitive Loop manual watcher ingest contract."),
    ("platform/mastra/README.md", "mastra_adapter", "Copy-ready Mastra adapter operator guide."),
    ("platform/mastra/manifest.json", "mastra_adapter", "Machine-readable Mastra adapter contract-pack manifest."),
    ("platform/mastra/cognitive-loop-mastra-adapter.ts", "mastra_adapter", "TypeScript Mastra workflow scaffold for Cognitive Loop HITL mapping."),
    ("docs/cognitive-loop-code-review.md", "operator_doc", "Cognitive Loop advisory code review guide."),
    ("docs/github-review-agent-workflow.md", "operator_doc", "Manual GitHub Actions workflow template guide for external Review Agent evidence."),
    ("docs/agent-eval.md", "operator_doc", "Agent and retrieval eval guide."),
    ("docs/eval-frameworks.md", "operator_doc", "External eval framework selection, adapter boundary, and marketplace harness guide."),
    ("docs/api.md", "operator_doc", "HTTP API reference for platform workspaces."),
    ("docs/release-notes/v0.3.31-alpha.md", "release_doc", "Release notes for this adoption pack."),
    ("evals/README.md", "eval", "External eval overview and native/optional adapter guide."),
    ("evals/review-agent/README.md", "eval", "Offline Cognitive Loop Review Agent eval fixture guide."),
    ("evals/review-agent/cases/approved-docs.json", "eval_fixture", "Review Agent approved decision synthetic diff case."),
    ("evals/review-agent/cases/needs-review-test-gap.json", "eval_fixture", "Review Agent needs-review synthetic diff case."),
    ("evals/review-agent/cases/needs-fix-command-injection.json", "eval_fixture", "Review Agent needs-fix critical security synthetic diff case."),
    ("evals/review-agent/golden/approved-docs.json", "eval_fixture", "Review Agent approved golden report."),
    ("evals/review-agent/golden/needs-review-test-gap.json", "eval_fixture", "Review Agent needs-review golden report."),
    ("evals/review-agent/golden/needs-fix-command-injection.json", "eval_fixture", "Review Agent needs-fix golden report."),
    ("evals/review-agent/bad/privacy-leak.json", "eval_fixture", "Review Agent negative privacy-leak report fixture."),
    ("platform/study-anything-platform-tools.json", "tool_manifest", "Source platform tool contract."),
    ("platform/ecosystem-submission.json", "submission_manifest", "Machine-readable ecosystem submission metadata."),
    ("platform/prompts/cognitive-loop-review-agent.json", "prompt_contract", "External Cognitive Loop Review Agent JSON-only prompt contract."),
    ("platform/schemas/cognitive-loop-review-agent-report.schema.json", "schema", "External Cognitive Loop Review Agent final report JSON Schema."),
    ("platform/schemas/cognitive-loop-pr-ci-receipt.schema.json", "schema", "Cognitive Loop PR CI receipt JSON Schema for offline platform-Agent validation."),
    ("platform/schemas/cognitive-loop-pr-ci-source.schema.json", "schema", "Cognitive Loop PR CI source JSON Schema for offline platform-Agent validation."),
    ("scripts/cognitive_loop_review_agent_handoff.py", "cli", "Prepare ephemeral external Review Agent handoff requests and validate returned JSON reports."),
    ("scripts/cognitive_loop_review_agent_receipt.py", "cli", "Build and validate metadata-only external Review Agent CI receipts."),
    ("scripts/cognitive_loop_review_agent_pr_comment.py", "cli", "Build and validate metadata-only external Review Agent PR comment packs."),
    ("scripts/cognitive_loop_review_agent_acceptance_bundle.py", "cli", "Build and validate metadata-only external Review Agent acceptance bundles."),
    ("platform/workflows/cognitive-loop-review-agent-manual.yml", "workflow_template", "Manual GitHub Actions template for metadata-only external Review Agent evidence."),
    ("scripts/cognitive_loop_review_agent_policy_gate.py", "cli", "Evaluate metadata-only Review Agent evidence against advisory, soft, or strict policy gates."),
    ("scripts/verify_cognitive_loop_review_agent_policy_gate.py", "verification", "Verify metadata-only Review Agent policy gate behavior and privacy boundaries."),
    ("scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py", "verification", "Verify external adopters can install the Review Agent workflow from the adoption pack and reproduce policy gate behavior."),
    ("scripts/verify_cognitive_loop_review_agent_adoption_drill.py", "verification", "Verify the full zip-only Review Agent adoption drill from acceptance bundle through policy gate and workflow install."),
    ("platform/generated/study-anything-platform-openapi.json", "tool_import", "OpenAPI 3.1 import asset."),
    ("platform/generated/study-anything-openai-tools.json", "tool_import", "OpenAI-compatible function tools."),
    ("platform/generated/study-anything-tool-catalog.md", "tool_catalog", "Human-readable platform tool catalog."),
    ("platform/generated/study-anything-platform-bundle.json", "bundle_manifest", "Source file manifest for platform assets."),
    ("platform/generated/study-anything-cognitive-loop-contracts.json", "submission_report", "Cognitive Loop contract bootstrap verification report."),
    ("platform/generated/study-anything-cognitive-loop-cli-artifact.json", "submission_report", "Cognitive Loop CLI init, verify, and static HTML artifact verification report."),
    ("platform/generated/study-anything-cognitive-loop-run-once-evidence.json", "submission_report", "Cognitive Loop run-once LoopRun and DecisionCard evidence verification report."),
    ("platform/generated/study-anything-cognitive-loop-project-snapshot.json", "submission_report", "Cognitive Loop redacted project snapshot verification report."),
    ("platform/generated/study-anything-cognitive-loop-human-gate.json", "submission_report", "Cognitive Loop Human Mastery Gate approval and rejection verification report."),
    ("platform/generated/study-anything-cognitive-loop-evidence-bundle.json", "submission_report", "Cognitive Loop metadata-only evidence bundle verification report."),
    ("platform/generated/study-anything-cognitive-loop-event-index.json", "submission_report", "Cognitive Loop metadata-only local event index verification report."),
    ("platform/generated/study-anything-cognitive-loop-event-store.json", "submission_report", "Cognitive Loop local SQLite Event Store verification report."),
    ("platform/generated/study-anything-cognitive-loop-watcher-ingest.json", "submission_report", "Cognitive Loop manual watcher ingest verification report."),
    ("platform/generated/study-anything-cognitive-loop-watcher-runner.json", "submission_report", "Cognitive Loop bounded watcher runner-lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-adapter.json", "submission_report", "Cognitive Loop Mastra adapter contract-pack verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-dry-run.json", "submission_report", "Cognitive Loop Mastra runtime dry-run verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-service.json", "submission_report", "Cognitive Loop repository-started Mastra runtime service verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-durable.json", "submission_report", "Cognitive Loop durable Mastra runtime suspend/resume verification report."),
    ("platform/generated/study-anything-cognitive-loop-langfuse-observability.json", "submission_report", "Cognitive Loop Langfuse observability DTO mapping verification report."),
    ("platform/generated/study-anything-cognitive-loop-study-anything-adapter.json", "submission_report", "Cognitive Loop Study Anything Learning Adapter verification report."),
    ("platform/generated/study-anything-cognitive-loop-study-adapter-cli.json", "submission_report", "Cognitive Loop Study Anything Adapter CLI Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-doctor.json", "submission_report", "Cognitive Loop metadata-only artifact doctor verification report."),
    ("platform/generated/study-anything-cognitive-loop-repair-plan.json", "submission_report", "Cognitive Loop manual-only repair plan verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-index.json", "submission_report", "Cognitive Loop static local artifact index verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-console.json", "submission_report", "Cognitive Loop static HTML Artifact Console Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-personal-plugin-mode.json", "submission_report", "Cognitive Loop Personal Plugin Mode Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-report.json", "submission_report", "Cognitive Loop Evolution Report Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-apply-plan.json", "submission_report", "Cognitive Loop Governed Apply Plan Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-improvement-comparison.json", "submission_report", "Cognitive Loop Measured Improvement Comparator Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-patch-proposal.json", "submission_report", "Cognitive Loop Patch Proposal Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-evolution-receipt.json", "submission_report", "Cognitive Loop Mastra Evolution Receipt Link Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-evolution-replay.json", "submission_report", "Cognitive Loop Mastra Evolution Workflow Replay Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-patch-apply-sandbox.json", "submission_report", "Cognitive Loop Governed Patch Apply Sandbox Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-pack-export.json", "submission_report", "Cognitive Loop Professional Evolution Pack Export Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-pack-consumer.json", "submission_report", "Cognitive Loop Professional Evolution Pack zip-only consumer verification report."),
    ("platform/generated/study-anything-cognitive-loop-pr-ci-receipt.json", "submission_report", "Cognitive Loop PR CI metadata-only receipt verification report with optional GitHub CLI metadata adapter."),
    ("platform/generated/study-anything-cognitive-loop-maintainer-acceptance-ledger.json", "submission_report", "Cognitive Loop maintainer go/no-go acceptance ledger verification report."),
    ("platform/generated/study-anything-cognitive-loop-review.json", "submission_report", "Cognitive Loop advisory code review verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-prompt.json", "submission_report", "External Cognitive Loop Review Agent prompt verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-report.json", "submission_report", "External Cognitive Loop Review Agent report handoff verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-handoff-cli.json", "submission_report", "External Cognitive Loop Review Agent prepare/validate CLI verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-eval-harness.json", "submission_report", "Offline Cognitive Loop Review Agent eval harness verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-ci-receipt.json", "submission_report", "External Cognitive Loop Review Agent CI receipt verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json", "submission_report", "External Cognitive Loop Review Agent PR comment pack verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json", "submission_report", "External Cognitive Loop Review Agent acceptance bundle verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json", "submission_report", "External Cognitive Loop Review Agent GitHub workflow template verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json", "submission_report", "External Cognitive Loop Review Agent policy gate verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json", "submission_report", "External Cognitive Loop Review Agent workflow install smoke verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-adoption-drill.json", "submission_report", "External Cognitive Loop Review Agent zip-only adoption drill verification report."),
    ("platform/generated/study-anything-cognitive-loop-adoption-cookbook.json", "submission_report", "Cognitive Loop platform-agent adoption cookbook verification report."),
    ("platform/generated/study-anything-cognitive-loop-adoption-recipes.json", "submission_report", "Machine-readable Cognitive Loop platform-agent adoption recipes."),
    ("platform/generated/study-anything-cognitive-loop-recipe-replay.json", "submission_report", "Cognitive Loop platform-agent recipe replay verification report."),
    ("platform/generated/study-anything-cognitive-loop-skill-entrypoint.json", "submission_report", "Cognitive Loop Skill and platform-pack recipe entrypoint verification report."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli.json", "submission_report", "Cognitive Loop read-only recipe CLI verification report."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json", "submission_report", "Deterministic read-only Cognitive Loop recipe CLI output receipts."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json", "submission_report", "Deterministic read-only Cognitive Loop recipe CLI failure receipts."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json", "submission_report", "Offline JSON Schemas for Cognitive Loop recipe CLI reports and PR CI receipt/source metadata reports."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json", "submission_report", "Negative fixtures proving Cognitive Loop recipe CLI schemas reject drift, unsafe flags, malformed types, and private text probes."),
    ("platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json", "submission_report", "Zip-only consumer proof for Cognitive Loop recipe CLI schema evidence in the adoption pack."),
    ("platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json", "submission_report", "Tampered adoption-pack failure proof for Cognitive Loop recipe CLI schema evidence."),
    ("platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json", "submission_report", "Extracted adoption-pack smoke proof for bundled Cognitive Loop schema consumer checks."),
    ("platform/generated/study-anything-platform-handoff-checklist.json", "submission_report", "External platform handoff checklist for import, verification, runtime, and support escalation."),
    ("platform/generated/study-anything-launch-acceptance-ledger.json", "submission_report", "Public launch acceptance ledger for GitHub OSS and platform-Agent adoption."),
    ("platform/generated/study-anything-github-launch-operator-guide.json", "submission_report", "GitHub launch operator guide proof for release sequence, assets, and local-first boundaries."),
    ("platform/generated/study-anything-release-stack-manifest-fixtures.json", "submission_report", "Negative fixtures proving release stack archive manifest boundary checks."),
    ("platform/generated/study-anything-release-stack-intake-candidate.json", "submission_report", "Metadata-only release stack intake candidate report for the next PR group."),
    ("platform/generated/study-anything-release-stack-candidate-promotion.json", "submission_report", "Metadata-only release stack candidate promotion report for the current PR group."),
    ("platform/generated/study-anything-operator-drill-transcript.json", "submission_report", "External platform operator drill transcript."),
    ("platform/generated/study-anything-platform-submission-dry-run.json", "submission_report", "External platform submission dry-run readiness report."),
    ("platform/generated/study-anything-platform-manual-submission-rehearsal.json", "submission_report", "Manual platform-submission rehearsal and redacted handoff report."),
    ("platform/generated/study-anything-first-lesson-authoring-kit.json", "submission_report", "Copyable first-run lesson authoring kit for platform Agents."),
    ("platform/generated/study-anything-external-eval-harness.json", "submission_report", "Marketplace-quality external Agent eval harness for platform submissions."),
    ("platform/generated/study-anything-agent-eval-marketplace-enforcement.json", "submission_report", "Agent eval marketplace enforcement report for optional and required external judge gates."),
    ("platform/generated/study-anything-platform-adoption-feedback-diagnostics.json", "submission_report", "Platform import diagnostics and redacted feedback boundary report."),
    ("platform/generated/study-anything-platform-feedback-package.json", "feedback_package", "Local-only redacted feedback package manifest."),
    ("platform/generated/study-anything-platform-feedback-package.zip", "feedback_package", "Local-only redacted feedback package archive."),
    ("platform/generated/study-anything-platform-field-rehearsal.json", "submission_report", "Redacted field-adoption rehearsal transcript and import quirks report."),
    ("platform/generated/study-anything-platform-support-triage.json", "submission_report", "GitHub-first support triage report for external platform adoption failures."),
    ("platform/generated/study-anything-platform-onboarding-readiness.json", "submission_report", "First-adopter onboarding readiness and maintainer SLA report."),
    ("platform/generated/study-anything-platform-triage-dashboard.json", "submission_report", "Generated platform triage dashboard JSON."),
    ("platform/generated/study-anything-platform-triage-dashboard.md", "submission_report", "Generated platform triage dashboard Markdown."),
    ("platform/generated/study-anything-public-support-status.json", "submission_report", "Public support status report."),
    ("platform/generated/study-anything-public-maintainer-dashboard.json", "submission_report", "Public maintainer dashboard JSON."),
    ("platform/generated/study-anything-public-maintainer-dashboard.md", "submission_report", "Public maintainer dashboard Markdown."),
    ("platform/generated/study-anything-published-image-evidence.json", "submission_report", "Published-image evidence JSON."),
    ("platform/generated/study-anything-published-image-evidence.md", "submission_report", "Published-image evidence Markdown."),
    ("platform/generated/study-anything-published-image-evidence.zip", "submission_report", "Published-image evidence package."),
    ("platform/generated/study-anything-published-image-evidence.sha256", "submission_report", "Published-image evidence checksum."),
    ("platform/generated/study-anything-release-asset-adoption.json", "submission_report", "GitHub Release asset adoption replay evidence JSON."),
    ("platform/generated/study-anything-release-asset-adoption.md", "submission_report", "GitHub Release asset adoption replay evidence Markdown."),
    ("platform/generated/study-anything-release-asset-adoption.zip", "submission_report", "GitHub Release asset adoption replay evidence package."),
    ("platform/generated/study-anything-release-asset-adoption.sha256", "submission_report", "GitHub Release asset adoption replay evidence checksum."),
    ("platform/generated/study-anything-release-asset-bootstrap.json", "submission_report", "GitHub Release asset bootstrap evidence JSON."),
    ("platform/generated/study-anything-release-asset-bootstrap.md", "submission_report", "GitHub Release asset bootstrap evidence Markdown."),
    ("platform/generated/study-anything-release-asset-bootstrap.zip", "submission_report", "GitHub Release asset bootstrap evidence package."),
    ("platform/generated/study-anything-release-asset-bootstrap.sha256", "submission_report", "GitHub Release asset bootstrap evidence checksum."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.json", "submission_report", "Release-only cleanroom bootstrap evidence JSON."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.md", "submission_report", "Release-only cleanroom bootstrap evidence Markdown."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.zip", "submission_report", "Release-only cleanroom bootstrap evidence package."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.sha256", "submission_report", "Release-only cleanroom bootstrap evidence checksum."),
    ("platform/generated/study-anything-platform-agent-replay.json", "submission_report", "Platform Agent release replay evidence JSON."),
    ("platform/generated/study-anything-platform-agent-replay.md", "submission_report", "Platform Agent release replay evidence Markdown."),
    ("platform/generated/study-anything-platform-agent-replay.zip", "submission_report", "Platform Agent release replay evidence package."),
    ("platform/generated/study-anything-platform-agent-replay.sha256", "submission_report", "Platform Agent release replay evidence checksum."),
    ("platform/generated/study-anything-adopter-evidence-archive.json", "submission_report", "External adopter evidence archive JSON."),
    ("platform/generated/study-anything-adopter-evidence-archive.md", "submission_report", "External adopter evidence archive Markdown."),
    ("platform/generated/study-anything-adopter-evidence-archive.zip", "submission_report", "External adopter evidence archive package."),
    ("platform/generated/study-anything-adopter-evidence-archive.sha256", "submission_report", "External adopter evidence archive checksum."),
    ("fixtures/platform-import-failures/schema_mismatch.json", "fixture", "Mock platform import failure fixture for schema mismatch."),
    ("fixtures/platform-import-failures/missing_local_gateway.json", "fixture", "Mock platform import failure fixture for missing local gateway."),
    ("fixtures/platform-import-failures/unsupported_auth_mode.json", "fixture", "Mock platform import failure fixture for unsupported auth mode."),
    ("fixtures/platform-import-failures/tool_naming_drift.json", "fixture", "Mock platform import failure fixture for tool naming drift."),
    ("fixtures/platform-import-failures/timeout.json", "fixture", "Mock platform import failure fixture for timeout diagnostics."),
    ("fixtures/platform-import-failures/cors_localhost.json", "fixture", "Mock platform import failure fixture for browser localhost restrictions."),
    ("fixtures/platform-import-failures/package_corruption.json", "fixture", "Mock platform import failure fixture for corrupted adoption packages."),
    ("fixtures/platform-import-failures/version_drift.json", "fixture", "Mock platform import failure fixture for version drift."),
    (".github/ISSUE_TEMPLATE/platform_import_failure.md", "support_template", "GitHub issue template for platform import failures."),
    (".github/ISSUE_TEMPLATE/local_gateway_failure.md", "support_template", "GitHub issue template for local Agent gateway failures."),
    (".github/ISSUE_TEMPLATE/published_image_pull_failure.md", "support_template", "GitHub issue template for published-image pull failures."),
    (".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md", "support_template", "GitHub issue template for Agent eval evidence failures."),
    (".github/ISSUE_TEMPLATE/docs_confusion.md", "support_template", "GitHub issue template for docs confusion reports."),
    ("fixtures/platform-support-tickets/platform_import_failure.json", "support_fixture", "Mock support ticket fixture for platform import failure triage."),
    ("fixtures/platform-support-tickets/local_gateway_failure.json", "support_fixture", "Mock support ticket fixture for local Agent gateway triage."),
    ("fixtures/platform-support-tickets/published_image_pull_failure.json", "support_fixture", "Mock support ticket fixture for published-image pull triage."),
    ("fixtures/platform-support-tickets/agent_eval_evidence_failure.json", "support_fixture", "Mock support ticket fixture for Agent eval evidence triage."),
    ("fixtures/platform-support-tickets/docs_confusion.json", "support_fixture", "Mock support ticket fixture for docs confusion triage."),
    ("fixtures/platform-release-blockers/tool_import_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for platform tool import failures."),
    ("fixtures/platform-release-blockers/local_gateway_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for local Agent gateway failures."),
    ("fixtures/platform-release-blockers/published_image_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for published-image launch failures."),
    ("fixtures/platform-release-blockers/agent_eval_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for Agent eval evidence failures."),
    ("fixtures/platform-release-blockers/support_bundle_privacy_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for unsafe support bundle privacy reports."),
    ("fixtures/release-stack/pr-183-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 183."),
    ("fixtures/release-stack/pr-184-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 184."),
    ("fixtures/release-stack/pr-185-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 185."),
    ("fixtures/release-stack/pr-186-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 186."),
    ("fixtures/release-stack/pr-187-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 187."),
    ("fixtures/release-stack/pr-188-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 188."),
    ("fixtures/release-stack/pr-189-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 189."),
    ("fixtures/release-stack/pr-190-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 190."),
    ("fixtures/release-stack/pr-191-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 191."),
    ("fixtures/release-stack/pr-192-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 192."),
    ("fixtures/release-stack/pr-193-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 193."),
    ("fixtures/release-stack/pr-194-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 194."),
    ("fixtures/release-stack/pr-195-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 195."),
    ("fixtures/release-stack/pr-196-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 196."),
    ("fixtures/release-stack/pr-197-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 197."),
    ("fixtures/release-stack/pr-198-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 198."),
    ("fixtures/release-stack/pr-199-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 199."),
    ("fixtures/release-stack/pr-200-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 200."),
    ("fixtures/release-stack/pr-201-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 201."),
    ("fixtures/release-stack/pr-202-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 202."),
    ("fixtures/release-stack/pr-203-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 203."),
    ("fixtures/release-stack/pr-204-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 204."),
    ("fixtures/release-stack/pr-205-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 205."),
    ("fixtures/release-stack/pr-206-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 206."),
    ("fixtures/release-stack/pr-207-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 207."),
    ("fixtures/release-stack/pr-208-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 208."),
    ("fixtures/release-stack/pr-209-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 209."),
    ("fixtures/release-stack/pr-210-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 210."),
    ("fixtures/release-stack/pr-211-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 211."),
    ("fixtures/release-stack/pr-212-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 212."),
    ("fixtures/release-stack/pr-213-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 213."),
    ("fixtures/release-stack/pr-214-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 214."),
    ("fixtures/release-stack/pr-215-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 215."),
    ("fixtures/release-stack/pr-216-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 216."),
    ("fixtures/release-stack/pr-217-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 217."),
    ("fixtures/release-stack/pr-218-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 218."),
    ("fixtures/release-stack/pr-219-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 219."),
    ("fixtures/release-stack/pr-220-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 220."),
    ("fixtures/release-stack/pr-221-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 221."),
    ("fixtures/release-stack/pr-222-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 222."),
    ("fixtures/release-stack/pr-223-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 223."),
    ("fixtures/release-stack/pr-224-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 224."),
    ("fixtures/release-stack/pr-225-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 225."),
    ("fixtures/release-stack/pr-226-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 226."),
    ("fixtures/release-stack/pr-227-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 227."),
    ("fixtures/release-stack/pr-228-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 228."),
    ("fixtures/release-stack/pr-229-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 229."),
    ("fixtures/release-stack/pr-230-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 230."),
    ("fixtures/release-stack/pr-231-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 231."),
    ("fixtures/release-stack/pr-232-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 232."),
    ("fixtures/release-stack/pr-233-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 233."),
    ("fixtures/release-stack/pr-234-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 234."),
    ("scripts/verify_release_stack_intake_candidate.py", "verification", "Verify metadata-only release stack intake candidates from PR summary metadata."),
    ("scripts/verify_release_stack_candidate_promotion.py", "verification", "Verify metadata-only release stack candidate promotion into the manifest."),
    ("fixtures/platform-status-links/intake.json", "status_linkage_fixture", "Public status linkage fixture for intake issues."),
    ("fixtures/platform-status-links/needs-repro.json", "status_linkage_fixture", "Public status linkage fixture for needs-repro issues."),
    ("fixtures/platform-status-links/confirmed.json", "status_linkage_fixture", "Public status linkage fixture for confirmed issues."),
    ("fixtures/platform-status-links/blocked-by-platform.json", "status_linkage_fixture", "Public status linkage fixture for blocked-by-platform issues."),
    ("fixtures/platform-status-links/docs-fix.json", "status_linkage_fixture", "Public status linkage fixture for docs-fix issues."),
    ("fixtures/platform-status-links/release-blocker.json", "status_linkage_fixture", "Public status linkage fixture for release-blocker issues."),
    ("fixtures/platform-status-links/resolved.json", "status_linkage_fixture", "Public status linkage fixture for resolved issues."),
    ("fixtures/review-agent/approved.json", "review_agent_fixture", "Accepted external Review Agent approved report fixture."),
    ("fixtures/review-agent/needs-review.json", "review_agent_fixture", "Accepted external Review Agent needs-review report fixture."),
    ("fixtures/review-agent/needs-fix.json", "review_agent_fixture", "Accepted external Review Agent needs-fix report fixture."),
    ("fixtures/review-agent/invalid-low-confidence-final.json", "review_agent_fixture", "Rejected external Review Agent low-confidence final finding fixture."),
    ("fixtures/review-agent-receipts/raw-diff-leak.json", "review_agent_receipt_fixture", "Rejected external Review Agent CI receipt raw-diff leak fixture."),
    ("fixtures/review-agent-pr-comments/raw-diff-leak.json", "review_agent_pr_comment_fixture", "Rejected external Review Agent PR comment raw-diff leak fixture."),
    ("fixtures/review-agent-acceptance-bundles/raw-diff-leak/manifest.json", "review_agent_acceptance_bundle_fixture", "Rejected external Review Agent acceptance bundle raw-diff leak fixture."),
    ("fixtures/review-agent-github-workflows/unsafe-auto-pr.yml", "review_agent_github_workflow_fixture", "Rejected unsafe Review Agent GitHub workflow fixture."),
    ("fixtures/adopter-evidence-archive/successful-release.json", "adopter_evidence_fixture", "Public evidence fixture for a successful release handoff."),
    ("fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json", "adopter_evidence_fixture", "Public evidence fixture for local GHCR pull timeout fallback."),
    ("fixtures/adopter-evidence-archive/needs-repro-issue.json", "adopter_evidence_fixture", "Public evidence fixture for needs-repro support state."),
    ("fixtures/adopter-evidence-archive/release-blocker.json", "adopter_evidence_fixture", "Public evidence fixture for release-blocker support state."),
    ("fixtures/adopter-evidence-archive/platform-blocked.json", "adopter_evidence_fixture", "Public evidence fixture for platform-blocked support state."),
    ("fixtures/adopter-evidence-archive/resolved-support-case.json", "adopter_evidence_fixture", "Public evidence fixture for resolved support state."),
    ("fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json", "published_image_evidence_fixture", "Published-image evidence fixture for local pull timeout fallback."),
    ("fixtures/published-image-evidence/cached-image-missing.json", "published_image_evidence_fixture", "Published-image evidence fixture for cached-only local image misses."),
    ("fixtures/published-image-evidence/compose-up-timeout.json", "published_image_evidence_fixture", "Published-image evidence fixture for bounded Compose startup timeouts."),
    ("fixtures/published-image-evidence/manifest-only-runtime-unverified.json", "published_image_evidence_fixture", "Published-image evidence fixture for manifest-only runtime-unverified handoff."),
    ("fixtures/published-image-evidence/manifest-missing-platform.json", "published_image_evidence_fixture", "Published-image evidence fixture for a missing manifest platform."),
    ("fixtures/published-image-evidence/docker-images-failed.json", "published_image_evidence_fixture", "Published-image evidence fixture for failed docker-images publishing."),
    ("fixtures/published-image-evidence/ghcr-unavailable.json", "published_image_evidence_fixture", "Published-image evidence fixture for GHCR or network unavailability."),
    ("fixtures/published-image-evidence/remote-smoke-pass.json", "published_image_evidence_fixture", "Published-image evidence fixture for a passing remote smoke replay."),
    ("fixtures/published-image-evidence/remote-smoke-failed.json", "published_image_evidence_fixture", "Published-image evidence fixture for runtime smoke failure."),
    ("fixtures/release-asset-adoption/asset-only-pass.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a passing asset-only replay."),
    ("fixtures/release-asset-adoption/asset-missing.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a missing release asset."),
    ("fixtures/release-asset-adoption/digest-mismatch.json", "release_asset_adoption_fixture", "Release asset adoption fixture for digest mismatch."),
    ("fixtures/release-asset-adoption/pack-corrupted.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a corrupted adoption pack."),
    ("fixtures/release-asset-adoption/published-evidence-missing.json", "release_asset_adoption_fixture", "Release asset adoption fixture for missing published-image evidence."),
    ("fixtures/release-asset-adoption/network-unavailable.json", "release_asset_adoption_fixture", "Release asset adoption fixture for GitHub release network unavailability."),
    ("fixtures/cognitive-loop-study-adapter/project-event.json", "cognitive_loop_fixture", "ProjectEvent fixture for the Study Anything adapter CLI."),
    ("fixtures/cognitive-loop-study-adapter/decision-card.json", "cognitive_loop_fixture", "DecisionCard fixture for the Study Anything adapter CLI."),
    ("platform/generated/study-anything-plugin-ecosystem-adoption-kit.json", "submission_report", "Copy-ready plugin ecosystem adoption kit for platform submissions."),
    ("platform/generated/study-anything-deployment-hardening.json", "submission_report", "Deployment hardening and clean-clone operator path report."),
    ("platform/generated/study-anything-learning-enrichment-bridge.json", "submission_report", "Learning Enrichment operator bridge report for platform Agents, NotebookLM, Obsidian, and second-brain handoff."),
    ("platform/packs/README.md", "platform_pack", "Platform pack index."),
    ("platform/packs/kimi/README.md", "platform_pack", "Kimi Work and Kimi-compatible setup."),
    ("platform/packs/kimi/pack.json", "platform_pack", "Machine-readable Kimi pack."),
    ("platform/packs/codex/README.md", "platform_pack", "Codex setup and command flow."),
    ("platform/packs/codex/pack.json", "platform_pack", "Machine-readable Codex pack."),
    ("platform/packs/workbuddy/README.md", "platform_pack", "WorkBuddy-style HTTP workspace setup."),
    ("platform/packs/workbuddy/pack.json", "platform_pack", "Machine-readable WorkBuddy pack."),
    ("skills/study-anything/SKILL.md", "skill", "Codex Skill entrypoint."),
    ("skills/study-anything/agents/openai.yaml", "skill", "OpenAI-compatible Skill agent metadata."),
    ("scripts/openai_compatible_agent_gateway.py", "gateway", "User-owned local HTTP Agent gateway."),
    ("scripts/mock_http_agent.py", "gateway", "Deterministic mock HTTP Agent for smoke tests."),
    ("scripts/setup_env.py", "runtime", "Generate local .env files with development-safe local secrets."),
    ("scripts/check_env.py", "runtime", "Validate required local environment variables before launch."),
    ("scripts/doctor.sh", "diagnostics", "Self-host doctor for Docker, ports, env, and Compose config."),
    ("scripts/launch_self_host.sh", "runtime", "Docker Compose self-host launcher."),
    ("scripts/stop_self_host.sh", "runtime", "Docker Compose self-host stop helper."),
    ("scripts/verify_published_image_launch.py", "verification", "Disposable GHCR published-image launch verifier."),
    ("scripts/launch_skill_mode.sh", "runtime", "Local Skill Mode API launcher."),
    ("scripts/stop_skill_mode.sh", "runtime", "Local Skill Mode API stop helper."),
    ("scripts/run_skill_mode_demo.sh", "verification", "One-command Skill Mode demo and eval gate."),
    ("scripts/study_anything_cli.py", "cli", "CLI for learning loop and evidence commands."),
    ("scripts/install_local_plugin.py", "cli", "CLI for explicit local plugin quarantine and approved install."),
    ("scripts/verify_external_adoption.py", "verification", "Adoption-proof-v1 verifier for external operators."),
    ("scripts/verify_clean_clone_adoption.py", "verification", "Disposable clean-clone Skill Mode and gateway adoption verifier."),
    ("scripts/verify_adoption_telemetry.py", "verification", "Aggregate adoption telemetry and PMF readiness verifier."),
    ("scripts/verify_agent_gateway_hardening.py", "verification", "User-owned Agent gateway hardening and privacy verifier."),
    ("scripts/verify_external_agent_adapter_hardening.py", "verification", "External Agent eval adapter hardening and bad-output diagnostics verifier."),
    ("scripts/verify_notebooklm_obsidian_bridge_hardening.py", "verification", "NotebookLM, Obsidian, and Learning Enrichment bridge privacy verifier."),
    ("scripts/verify_plugin_quarantine.py", "verification", "Plugin trust quarantine and explicit approval verifier."),
    ("scripts/verify_security_recovery_hardening.py", "verification", "Security recovery, backup manifest, and sync restore privacy verifier."),
    ("scripts/verify_platform_submission_dry_run.py", "verification", "External platform submission dry-run verifier."),
    ("scripts/verify_platform_manual_submission_rehearsal.py", "verification", "Manual platform-submission rehearsal verifier."),
    ("scripts/verify_first_lesson_authoring_kit.py", "verification", "Copyable first-run lesson authoring kit verifier."),
    ("scripts/verify_external_eval_marketplace_harness.py", "verification", "Marketplace-quality external Agent eval harness verifier."),
    ("scripts/verify_agent_eval_marketplace_enforcement.py", "verification", "Agent eval marketplace enforcement verifier."),
    ("scripts/verify_platform_adoption_feedback_diagnostics.py", "verification", "Platform import diagnostics and feedback boundary verifier."),
    ("scripts/generate_platform_feedback_package.py", "diagnostics", "Generate a local-only redacted platform feedback package."),
    ("scripts/generate_platform_field_rehearsal.py", "diagnostics", "Generate redacted field-adoption rehearsal transcripts and failed-import fixtures."),
    ("scripts/verify_platform_field_rehearsal.py", "verification", "Verify field-adoption rehearsals, import quirks, failed-import fixtures, and pack inclusion."),
    ("scripts/generate_platform_support_triage.py", "diagnostics", "Generate GitHub-first issue templates, support ticket fixtures, and support triage report."),
    ("scripts/verify_platform_support_triage.py", "verification", "Verify support triage redaction, actionability, pack inclusion, and docs."),
    ("scripts/generate_platform_onboarding_readiness.py", "diagnostics", "Generate first-adopter onboarding, triage dashboard, and release-blocker fixtures."),
    ("scripts/verify_platform_onboarding_readiness.py", "verification", "Verify onboarding readiness, SLA labels, dashboard, release blockers, packs, submission, and docs."),
    ("scripts/generate_platform_public_support_status.py", "diagnostics", "Generate public support status, maintainer dashboard, and status-linkage fixtures."),
    ("scripts/verify_platform_public_support_status.py", "verification", "Verify public support status, dashboard, status-linkage fixtures, packs, submission, and docs."),
    ("scripts/generate_published_image_evidence.py", "diagnostics", "Generate published-image evidence, checksum, and release fallback fixtures."),
    ("scripts/verify_published_image_evidence.py", "verification", "Verify published-image evidence, fixtures, platform packs, submission, adoption pack, and docs."),
    ("scripts/generate_release_asset_adoption.py", "diagnostics", "Generate GitHub Release asset adoption replay evidence and fixtures."),
    ("scripts/verify_release_asset_adoption.py", "verification", "Verify GitHub Release asset download, digest, pack, evidence, and runtime replay."),
    ("scripts/bootstrap_from_release.py", "verification", "Bootstrap external platform adoption from public GitHub Release assets."),
    ("scripts/generate_release_asset_bootstrap.py", "diagnostics", "Generate GitHub Release asset bootstrap evidence."),
    ("platform/bootstrap/study_anything_release_bootstrap.py", "verification", "Standalone release-only cleanroom bootstrapper."),
    ("scripts/generate_release_cleanroom_bootstrap.py", "diagnostics", "Generate release-only cleanroom bootstrap evidence."),
    ("scripts/replay_platform_agent_from_release.py", "verification", "Replay platform Agent tool calls from public GitHub Release assets."),
    ("scripts/generate_platform_agent_replay.py", "diagnostics", "Generate platform Agent release replay evidence."),
    ("scripts/generate_adopter_evidence_archive.py", "diagnostics", "Generate external adopter evidence archive, checksum, and maintainer handoff fixtures."),
    ("scripts/verify_adopter_evidence_archive.py", "verification", "Verify adopter evidence archive, fixtures, platform packs, submission, adoption pack, and docs."),
    ("scripts/verify_plugin_ecosystem_adoption_kit.py", "verification", "Plugin ecosystem sample, registry, and trust-policy adoption verifier."),
    ("scripts/verify_deployment_hardening.py", "verification", "Deployment hardening and published-image operator path verifier."),
    ("scripts/verify_learning_enrichment_bridge.py", "verification", "Learning Enrichment operator bridge verifier."),
    ("scripts/verify_ecosystem_submission_pack.py", "verification", "Ecosystem submission pack verifier for external platform review."),
    ("scripts/verify_cognitive_loop_contracts.py", "verification", "Cognitive Loop contract bootstrap verifier."),
    ("scripts/cognitive_loop_cli.py", "cli", "Local Cognitive Loop contract init, verify, and static HTML artifact CLI."),
    ("scripts/verify_cognitive_loop_cli.py", "verification", "Cognitive Loop CLI and static HTML artifact verifier."),
    ("scripts/verify_cognitive_loop_run_once.py", "verification", "Cognitive Loop run-once evidence verifier."),
    ("scripts/verify_cognitive_loop_snapshot.py", "verification", "Cognitive Loop project snapshot verifier."),
    ("scripts/verify_cognitive_loop_human_gate.py", "verification", "Cognitive Loop Human Mastery Gate verifier."),
    ("scripts/verify_cognitive_loop_evidence_bundle.py", "verification", "Cognitive Loop metadata-only evidence bundle verifier."),
    ("scripts/verify_cognitive_loop_event_index.py", "verification", "Cognitive Loop metadata-only local event index verifier."),
    ("scripts/cognitive_loop_event_store.py", "cli", "Local SQLite Event Store for validated Cognitive Loop event metadata."),
    ("scripts/verify_cognitive_loop_event_store.py", "verification", "Verify the local SQLite Event Store, idempotent rebuild, HTML export, and privacy rejection path."),
    ("scripts/cognitive_loop_watcher_ingest.py", "cli", "Manual watcher-event ingest for Cognitive Loop metadata artifacts."),
    ("scripts/verify_cognitive_loop_watcher_ingest.py", "verification", "Verify manual watcher ingest, Event Index classification, Event Store projection, and privacy boundaries."),
    ("scripts/cognitive_loop_watcher_runner.py", "cli", "Bounded watcher runner-lite for metadata-only local project signals."),
    ("scripts/verify_cognitive_loop_watcher_runner.py", "verification", "Verify watcher runner-lite debounce, Event Store idempotency, Study Adapter gate, and privacy boundaries."),
    ("scripts/cognitive_loop_artifact_console.py", "cli", "Build a static metadata-only Cognitive Loop HTML Artifact Console Lite."),
    ("scripts/verify_cognitive_loop_artifact_console.py", "verification", "Verify Artifact Console Lite aggregation, links, degradation, mobile shell, and privacy boundaries."),
    ("scripts/cognitive_loop_personal_mode.py", "cli", "Build read-only Personal Plugin Mode Lite learning artifacts."),
    ("scripts/verify_cognitive_loop_personal_plugin_mode.py", "verification", "Verify Personal Plugin Mode Lite file, README, webpage, diff-summary, report, and privacy boundaries."),
    ("scripts/cognitive_loop_evolution.py", "cli", "Build read-only Cognitive Loop Evolution Report Lite artifacts."),
    ("scripts/verify_cognitive_loop_evolution_report.py", "verification", "Verify Evolution Report Lite clustering, gating, degradation, and privacy boundaries."),
    ("scripts/cognitive_loop_apply_plan.py", "cli", "Build governed low-risk Cognitive Loop Apply Plan Lite artifacts."),
    ("scripts/verify_cognitive_loop_apply_plan.py", "verification", "Verify Apply Plan Lite dry-run, explicit receipt apply, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_improvement_comparator.py", "cli", "Build read-only Cognitive Loop Improvement Comparator Lite artifacts."),
    ("scripts/verify_cognitive_loop_improvement_comparator.py", "verification", "Verify Improvement Comparator Lite status classification, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_patch_proposal.py", "cli", "Build read-only Cognitive Loop Patch Proposal Lite artifacts."),
    ("scripts/verify_cognitive_loop_patch_proposal.py", "verification", "Verify Patch Proposal Lite categories, manual-only degradation, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_mastra_evolution_receipt.py", "cli", "Build read-only Cognitive Loop Mastra Evolution Receipt Link Lite artifacts."),
    ("scripts/verify_cognitive_loop_mastra_evolution_receipt.py", "verification", "Verify Mastra Evolution Receipt Link Lite readiness, blocking, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_mastra_evolution_replay.py", "cli", "Build read-only Cognitive Loop Mastra Evolution Workflow Replay Lite artifacts."),
    ("scripts/verify_cognitive_loop_mastra_evolution_replay.py", "verification", "Verify Mastra Evolution Workflow Replay Lite replay readiness, blocking, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_patch_apply_sandbox.py", "cli", "Build metadata-only Cognitive Loop governed patch-apply sandbox receipts."),
    ("scripts/verify_cognitive_loop_patch_apply_sandbox.py", "verification", "Verify Patch Apply Sandbox Lite readiness, rollback proof, read-only boundaries, and privacy rejection paths."),
    ("scripts/cognitive_loop_evolution_pack_export.py", "cli", "Export a metadata-only Cognitive Loop professional evolution evidence pack."),
    ("scripts/verify_cognitive_loop_evolution_pack_export.py", "verification", "Verify Evolution Pack Export Lite zip integrity, manifest hashes, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_evolution_pack_consumer.py", "verification", "Verify Evolution Pack zip-only consumer import, tamper rejection, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_pr_ci_receipt.py", "verification", "Verify PR CI receipt decisions, required checks, optional GitHub CLI metadata adapter, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py", "verification", "Verify maintainer go/no-go acceptance ledger evidence, CI fixture, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_mastra_adapter.py", "verification", "Verify the Cognitive Loop Mastra adapter contract pack and privacy boundary."),
    ("scripts/verify_cognitive_loop_mastra_runtime_dry_run.py", "verification", "Verify the Cognitive Loop Mastra runtime dry-run harness and privacy boundary."),
    ("platform/mastra-runtime/README.md", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime MVP operator notes."),
    ("platform/mastra-runtime/package.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime package manifest."),
    ("platform/mastra-runtime/package-lock.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime dependency lockfile."),
    ("platform/mastra-runtime/tsconfig.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime TypeScript configuration."),
    ("platform/mastra-runtime/src/runtime.ts", "mastra_runtime", "Repository-started Mastra instance registration for the Cognitive Loop workflow."),
    ("platform/mastra-runtime/src/run-once.ts", "mastra_runtime", "Deterministic Mastra workflow run covering suspend, resume, bail, and no-gate paths."),
    ("platform/mastra-runtime/src/durable-run.ts", "mastra_runtime", "Deterministic durable Mastra workflow run covering cross-process resume and bail paths."),
    ("platform/mastra-runtime/src/observability.ts", "mastra_runtime", "Redacted Langfuse DTO mapping for Cognitive Loop Mastra receipts."),
    ("platform/mastra-runtime/src/observability-run.ts", "mastra_runtime", "Deterministic local Langfuse observability receipt runner."),
    ("platform/mastra-runtime/src/workflows/cognitive-loop-mastra-adapter.ts", "mastra_runtime", "Runtime-local copy of the Cognitive Loop Mastra workflow adapter kept identical to the public pack."),
    ("apps/api/study_anything/core/cognitive_loop_learning_adapter.py", "api_core", "Study Anything Learning Adapter bridge for Cognitive Loop mastery records."),
    ("scripts/cognitive_loop_study_adapter_cli.py", "cli", "CLI Lite bridge from Cognitive Loop ProjectEvent/DecisionCard files to Study Anything learning evidence."),
    ("scripts/verify_cognitive_loop_mastra_runtime_service.py", "verification", "Verify the repository-started Cognitive Loop Mastra runtime service and privacy boundary."),
    ("scripts/verify_cognitive_loop_mastra_runtime_durable.py", "verification", "Verify the durable Cognitive Loop Mastra runtime suspend/resume privacy boundary."),
    ("scripts/verify_cognitive_loop_langfuse_observability.py", "verification", "Verify redacted Langfuse observability DTO mapping for Cognitive Loop Mastra receipts."),
    ("scripts/verify_cognitive_loop_study_anything_adapter.py", "verification", "Verify Cognitive Loop Study Anything Learning Adapter mastery projection."),
    ("scripts/verify_cognitive_loop_study_adapter_cli.py", "verification", "Verify the Study Anything adapter CLI Lite evidence and HTML output."),
    ("scripts/verify_cognitive_loop_artifact_doctor.py", "verification", "Cognitive Loop metadata-only artifact doctor verifier."),
    ("scripts/verify_cognitive_loop_repair_plan.py", "verification", "Cognitive Loop manual-only repair plan verifier."),
    ("scripts/verify_cognitive_loop_artifact_index.py", "verification", "Cognitive Loop static local artifact index verifier."),
    ("scripts/cognitive_loop_review.py", "cli", "Cognitive Loop advisory code review CLI."),
    ("scripts/verify_cognitive_loop_review.py", "verification", "Cognitive Loop advisory code review verifier."),
    ("scripts/verify_cognitive_loop_review_agent_prompt.py", "verification", "External Cognitive Loop Review Agent prompt verifier."),
    ("scripts/verify_cognitive_loop_review_agent_report.py", "verification", "External Cognitive Loop Review Agent report handoff verifier."),
    ("scripts/verify_cognitive_loop_review_agent_handoff_cli.py", "verification", "External Cognitive Loop Review Agent handoff CLI verifier."),
    ("scripts/verify_cognitive_loop_review_agent_eval_harness.py", "verification", "Offline Cognitive Loop Review Agent eval harness verifier."),
    ("scripts/verify_cognitive_loop_review_agent_ci_receipt.py", "verification", "External Cognitive Loop Review Agent CI receipt verifier."),
    ("scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py", "verification", "External Cognitive Loop Review Agent PR comment pack verifier."),
    ("scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py", "verification", "External Cognitive Loop Review Agent acceptance bundle verifier."),
    ("scripts/verify_cognitive_loop_review_agent_github_workflow.py", "verification", "External Cognitive Loop Review Agent GitHub workflow template verifier."),
    ("scripts/verify_cognitive_loop_adoption_cookbook.py", "verification", "Cognitive Loop platform-agent adoption cookbook verifier."),
    ("scripts/generate_cognitive_loop_adoption_recipes.py", "verification", "Generate machine-readable Cognitive Loop platform-agent adoption recipes."),
    ("scripts/verify_cognitive_loop_recipe_replay.py", "verification", "Verify Cognitive Loop adoption recipes are replay-ready for platform Agents."),
    ("scripts/verify_cognitive_loop_skill_entrypoint.py", "verification", "Verify Cognitive Loop recipe entrypoints are visible from the Skill and platform packs."),
    ("scripts/cognitive_loop_recipe_cli.py", "cli", "Read-only Cognitive Loop recipe query CLI for platform Agents."),
    ("scripts/verify_cognitive_loop_recipe_cli.py", "verification", "Verify the read-only Cognitive Loop recipe CLI for platform Agents."),
    ("scripts/verify_cognitive_loop_recipe_cli_receipts.py", "verification", "Generate and verify deterministic Cognitive Loop recipe CLI receipts."),
    ("scripts/verify_cognitive_loop_recipe_cli_failures.py", "verification", "Generate and verify deterministic Cognitive Loop recipe CLI failure receipts."),
    ("scripts/verify_cognitive_loop_recipe_cli_schemas.py", "verification", "Generate and verify offline JSON Schemas for Cognitive Loop recipe CLI reports."),
    ("scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py", "verification", "Verify negative fixtures for Cognitive Loop recipe CLI JSON Schemas."),
    ("scripts/verify_cognitive_loop_schema_pack_consumer.py", "verification", "Verify Cognitive Loop schema evidence can be consumed from the adoption pack only."),
    ("scripts/verify_cognitive_loop_schema_pack_consumer_failures.py", "verification", "Verify Cognitive Loop schema pack consumer failure cases are safe and deterministic."),
    ("scripts/verify_cognitive_loop_pack_extract_smoke.py", "verification", "Verify the extracted adoption pack can run its included schema consumer checks."),
    ("scripts/verify_platform_handoff_checklist.py", "verification", "Generate and verify the external platform handoff checklist."),
    ("scripts/verify_launch_acceptance_ledger.py", "verification", "Generate and verify the public launch acceptance ledger."),
    ("scripts/verify_github_launch_operator_guide.py", "verification", "Generate and verify the GitHub launch operator guide proof."),
    ("scripts/verify_platform_operator_drill.py", "verification", "External platform pack consumption verifier."),
    ("scripts/verify_platform_agent_tools.py", "verification", "Platform tool manifest runtime verifier."),
    ("scripts/verify_platform_ecosystem_eval_flow.py", "verification", "Full platform ecosystem learning/eval/export verifier."),
    ("scripts/verify_importer_lesson_flow.py", "verification", "NotebookLM-style importer lesson verifier."),
    ("scripts/verify_importer_runtime_retrieval_flow.py", "verification", "Importer runtime plus retrieval verifier."),
    ("scripts/verify_platform_lesson_flow.py", "verification", "Enriched platform lesson verifier."),
    ("scripts/verify_agent_eval_flow.py", "verification", "Agent eval artifact verifier."),
    ("scripts/verify_agent_eval_assets.py", "verification", "Agent eval asset and adapter contract verifier."),
    ("scripts/verify_agent_eval_baseline.py", "verification", "Agent eval baseline and regression gate verifier."),
    ("scripts/run_external_agent_evals.py", "verification", "Promptfoo/DeepEval/retrieval eval runner."),
    ("scripts/verify_openai_compatible_gateway.py", "verification", "OpenAI-compatible gateway dry-run verifier."),
    ("infra/compose/docker-compose.yml", "runtime", "Docker Compose source-build stack definition."),
    ("infra/compose/docker-compose.images.yml", "runtime", "Docker Compose published-image override."),
    ("scripts/diagnose_adoption.py", "diagnostics", "Adoption diagnostics and remediation hints."),
    ("evals/promptfoo/agent-eval-artifact.yaml", "eval", "Promptfoo eval config."),
    ("evals/deepeval/study_anything_quality_eval.py", "eval", "DeepEval-compatible native quality adapter."),
    ("evals/baselines/study-anything-agent-eval-baseline.json", "eval", "Deterministic Agent eval regression baseline."),
    ("evals/fixtures/fake-agent-learning-loop.json", "eval_fixture", "Fake deterministic Agent eval fixture."),
    ("evals/fixtures/mock-http-agent-learning-loop.json", "eval_fixture", "Mock HTTP/user-owned Agent eval fixture."),
    (".cognitive-loop/config.yaml", "cognitive_loop_contract", "Local-first Cognitive Loop project configuration contract."),
    (".cognitive-loop/permissions.yaml", "cognitive_loop_contract", "Cognitive Loop permission and human approval contract."),
    (".cognitive-loop/evals.yaml", "cognitive_loop_contract", "Cognitive Loop required eval command contract."),
    (".cognitive-loop/risk.yaml", "cognitive_loop_contract", "Cognitive Loop risk and human mastery gate contract."),
    ("fixtures/notebooklm/README.md", "fixture", "NotebookLM fixture notes."),
    ("fixtures/notebooklm/notebooklm-style-context-package.json", "fixture", "NotebookLM-style context package fixture."),
    ("plugins/registry.json", "plugin_registry", "Bundled sample plugin registry with source digests."),
    ("plugins/example-note-importer/plugin.json", "sample_plugin", "Markdown and Obsidian importer manifest."),
    ("plugins/example-note-importer/plugin.py", "sample_plugin", "Markdown and Obsidian importer template source."),
    ("plugins/example-web-importer/plugin.json", "sample_plugin", "Web excerpt importer manifest."),
    ("plugins/example-web-importer/plugin.py", "sample_plugin", "Web excerpt importer template source."),
    ("plugins/example-enrichment-importer/plugin.json", "sample_plugin", "Learning enrichment importer manifest."),
    ("plugins/example-enrichment-importer/plugin.py", "sample_plugin", "Learning enrichment importer template source."),
    ("plugins/example-exporter/plugin.json", "sample_plugin", "Obsidian and second-brain exporter manifest."),
    ("plugins/example-exporter/plugin.py", "sample_plugin", "Obsidian and second-brain exporter template source."),
    ("plugins/example-agent-provider/plugin.json", "sample_plugin", "User-owned Agent provider manifest template."),
    ("plugins/example-agent-provider/plugin.py", "sample_plugin", "User-owned Agent provider template source."),
]

REQUIRED_PLATFORM_TOOLS = [
    "study_anything_deployment_guide",
    "study_anything_commercial_readiness",
    "study_anything_adoption_telemetry",
    "study_anything_pmf_readiness",
    "study_anything_health",
    "study_anything_eval_policy",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_plugin_sdk",
    "study_anything_plugin_capabilities",
    "study_anything_validate_plugin_package",
    "study_anything_run_importer",
    "study_anything_add_enrichment",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_retrieval_search",
    "study_anything_retrieval_quality_eval",
    "study_anything_teaching_layers",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_agent_eval_report",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
]


class AdoptionPackError(RuntimeError):
    """Readable adoption-pack generation failure."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdoptionPackError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc


def assert_safe_path(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.exists():
        raise AdoptionPackError(f"Adoption pack file is missing: {relative_path}")
    if path.is_dir():
        raise AdoptionPackError(f"Adoption pack file must not be a directory: {relative_path}")
    if any(part in {".git", ".env", ".venv", "data", "__pycache__"} for part in path.parts):
        raise AdoptionPackError(f"Unsafe adoption pack path: {relative_path}")
    return path


def file_record(relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = assert_safe_path(relative_path)
    return {
        "path": relative_path,
        "archive_path": f"{ARCHIVE_ROOT}/{relative_path}",
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_source_contract() -> None:
    tools = read_json(ROOT / "platform" / "study-anything-platform-tools.json")
    if tools.get("schema_version") != "study-anything-platform-tools-v1":
        raise AdoptionPackError("Platform tool manifest schema drifted.")
    names = {tool.get("name") for tool in tools.get("tools", [])}
    missing = [name for name in REQUIRED_PLATFORM_TOOLS if name not in names]
    if missing:
        raise AdoptionPackError(f"Platform tool manifest is missing adoption tools: {missing}")


def pack_readme() -> str:
    return """# Study Anything Platform Adoption Pack

This archive is the copy-ready integration bundle for Kimi Work, Codex,
WorkBuddy-style HTTP tool workspaces, and other platform Agents.

Use it when the platform Agent owns browsing, files, video slicing, outside
tools, real model credentials, and conversation. Study Anything owns the
source-bound learning workflow, state, audit, eval evidence, retrieval quality,
and Obsidian/NotebookLM handoff.

## Quick Start

1. Start Study Anything locally with Skill Mode or the published Docker image.
2. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json` into your platform.
3. Follow the operator guide for your platform under `platform/packs/`.
4. Run:

```bash
python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree
```

The verifier emits `adoption-proof-v1` JSON. Treat that JSON as the minimum
acceptance evidence before claiming an external platform integration works.
The generated `adopter-evidence-archive-v1` package is the public maintainer
handoff bundle for release proof, checksums, and local GHCR pull-timeout
fallback evidence.

## Privacy

Do not put real model API keys in Study Anything. Keep real model credentials
inside the user's own Agent or platform runtime. The adoption evidence is
designed to be redacted and must not include raw source text, long answers,
agent endpoints with secrets, or platform-private browsing/video context.
"""


def manifest_payload() -> dict[str, object]:
    validate_source_contract()
    file_paths = [path for path, _kind, _purpose in PACK_FILES]
    if len(file_paths) != len(set(file_paths)):
        raise AdoptionPackError("Adoption pack file list contains duplicates.")
    return {
        "schema_version": "study-anything-platform-adoption-pack-v1",
        "name": "study-anything-platform-adoption-pack",
        "version": "v0.3.31-alpha",
        "archive_name": ARCHIVE_PATH.name,
        "archive_root": ARCHIVE_ROOT,
        "description": (
            "Copy-ready platform adoption pack for Kimi Work, Codex, WorkBuddy-style "
            "HTTP workspaces, NotebookLM/Obsidian handoff, and external Agent eval proof."
        ),
        "supported_platforms": ["kimi-work", "codex", "workbuddy-style-http", "generic-http-tools"],
        "runtime_modes": ["skill-mode", "published-image"],
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
        "required_tool_names": REQUIRED_PLATFORM_TOOLS,
        "acceptance": {
            "proof_schema": "adoption-proof-v1",
            "command": (
                "python3 scripts/verify_external_adoption.py --pack "
                "platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
            "target_minutes": 15,
            "must_verify": [
                "archive sha256 manifest",
                "OpenAPI/OpenAI tool import assets",
                "Kimi/Codex/WorkBuddy operator packs",
                "Skill Mode or published-image runtime",
                "external platform Agent learning flow",
                "external platform pack consumption drill",
                "retrieval-quality-eval-v1",
                "agent-eval-policy-v1",
                "agent-eval-report-v1",
                "agent-quality-eval-v1",
                "study-anything-agent-eval-regression-report-v1",
                "obsidian-markdown-export-v1",
                "learning-package-v1",
                "second-brain-handoff-v1",
                "plugin-sdk-v1",
                "plugin-capability-index-v1",
                "plugin-package-validation-v1",
                "plugin-quarantine-verification-v1",
                "deployment-guide-v1",
                "commercial-readiness-v1",
                "adoption-telemetry-v1",
                "pmf-readiness-v1",
                "adoption-telemetry-verification-v1",
                "agent-gateway-hardening-verification-v1",
                "notebooklm-obsidian-bridge-hardening-v1",
                "learning-enrichment-bridge-verification-v1",
                "security-recovery-hardening-verification-v1",
                "platform-submission-dry-run-v1",
                "platform-manual-submission-rehearsal-v1",
                "first-run-lesson-authoring-kit-v1",
                "external-eval-marketplace-harness-v1",
                "agent-eval-marketplace-enforcement-v1",
                "cognitive-loop-review-agent-eval-harness-v1",
                "cognitive-loop-review-agent-ci-receipt-v1",
                "cognitive-loop-review-agent-pr-comment-pack-v1",
                "cognitive-loop-review-agent-acceptance-bundle-v1",
                "platform-adoption-feedback-diagnostics-v1",
                "platform-feedback-package-v1",
                "platform-field-adoption-rehearsal-v1",
                "platform-import-failure-fixture-v1",
                "platform-support-triage-v1",
                "platform-support-ticket-fixture-v1",
                "platform-support-issue-template-v1",
                "platform-onboarding-readiness-v1",
                "first-external-adopter-walkthrough-v1",
                "maintainer-sla-labels-v1",
                "maintainer-rotation-checklist-v1",
                "platform-triage-dashboard-v1",
                "platform-release-blocker-fixture-v1",
                "public-support-status-v1",
                "public-maintainer-dashboard-v1",
                "public-status-linkage-fixture-v1",
                "published-image-evidence-v1",
                "published-image-evidence-fixture-v1",
                "release-asset-adoption-v1",
                "release-asset-adoption-fixture-v1",
                "release-asset-adoption-proof-v1",
                "release-asset-bootstrap-v1",
                "release-asset-bootstrap-transcript-v1",
                "platform-agent-release-replay-v1",
                "adopter-evidence-archive-v1",
                "adopter-evidence-fixture-v1",
                "plugin-ecosystem-adoption-kit-v1",
                "deployment-hardening-verification-v1",
                "ecosystem-submission-v1",
                "ecosystem-submission-verification-v1",
                "cognitive-loop-pr-ci-receipt-v1",
                "cognitive-loop-maintainer-acceptance-ledger-v1",
            ],
        },
        "privacy_contract": {
            "must_not_store": [
                "real model API keys",
                "platform private browser traces",
                "raw long source text in eval evidence",
                "raw answer text in eval evidence",
                "agent endpoint secrets",
            ],
            "user_owned_exports_may_include": [
                "learner answers",
                "review history",
                "Obsidian markdown selected by the learner",
            ],
        },
        "files": [file_record(*item) for item in PACK_FILES],
    }


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def archive_bytes(manifest: dict[str, object]) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in [
            (f"{ARCHIVE_ROOT}/ADOPTION_PACK_README.md", pack_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(manifest).encode("utf-8")),
        ]:
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
        for record in sorted(manifest["files"], key=lambda item: str(item["path"])):  # type: ignore[index]
            relative_path = str(record["path"])
            source = ROOT / relative_path
            info = zipfile.ZipInfo(str(record["archive_path"]))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def build_outputs() -> tuple[str, bytes]:
    archive_manifest = manifest_payload()
    archive = archive_bytes(archive_manifest)
    enriched = dict(archive_manifest)
    enriched["archive_sha256"] = sha256_bytes(archive)
    enriched["archive_bytes"] = len(archive)
    return dump_json(enriched), archive


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_text, archive = build_outputs()
    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_manifest, expected_archive = build_outputs()
    missing = [
        str(path.relative_to(ROOT))
        for path in [MANIFEST_PATH, ARCHIVE_PATH]
        if not path.exists()
    ]
    stale = []
    if MANIFEST_PATH.exists() and MANIFEST_PATH.read_text(encoding="utf-8") != expected_manifest:
        stale.append(str(MANIFEST_PATH.relative_to(ROOT)))
    if ARCHIVE_PATH.exists() and ARCHIVE_PATH.read_bytes() != expected_archive:
        stale.append(str(ARCHIVE_PATH.relative_to(ROOT)))
    if missing or stale:
        raise AdoptionPackError(
            "Platform adoption pack is stale. Run "
            "`python3 scripts/generate_platform_adoption_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform adoption pack is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_adoption_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
