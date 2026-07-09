# Legacy v0.1.0 snapshot

Frozen 2026-05-04. Replaced by the v0.2.0 redesign at `src/skill_doctor/`.

This directory keeps the original 14-file / 3927-line implementation as a reference
for rule logic that may need to be reintroduced. None of these modules are imported
by the new code path.

The `runtime_registry.py` was kept at the package root because its runtime path
whitelist remains directly reusable.

The redesign rationale lived in `research/SKILL_DOCTOR_FINAL_PLAN.md`, an
internal planning doc no longer kept in the public repo (still available in
git history).
