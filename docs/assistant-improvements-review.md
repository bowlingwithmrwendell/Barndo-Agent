# Assistant improvements: review before deployment

The October 13 visitor review found premature use of regional cost examples, overbroad sequencing advice and unclear estimator design limits. This change asks for location, living/shop split and scope before cost totals; qualifies sequencing and conflicting sources; and labels estimator results as preliminary quantities throughout the widget and tool/API results.

## Changes

- `backend/app/agent/service.py`: revised model instructions and estimator tool description. No model, credentials, endpoint or rate-limit changes.
- `backend/app/estimator.py`: two leading assumptions describing budget/design limits. Quantity formulas and defaults are unchanged.
- `backend/app/static/barndo-agent.js`: visible notice before calculation, expanded assumptions before quantities, result notice and clearer estimator-to-chat context.
- `backend/tests/test_public_agent.py`: verifies limits reach public and model tool results, unchanged summary values, and revised guidance is sent with conversation history.

## Validation

55 backend tests passed. Ruff and JavaScript syntax checks passed. Prior local widget preview with fixed responses confirmed notices and expanded assumptions render above quantities. Automated model tests use a mocked Anthropic transport: they verify wiring, not compliance or answer accuracy. No live model API key was configured for this local checkout, and no real-model evaluation was attempted.

`agent-regression-cases.json` contains the six real-answer cases to run in a nonproduction environment before calling model behavior verified. Do not use the existing live site to claim these changes work until the candidate version is deployed to an approved test environment.

## Separate source corrections

Page 363 (Start Here) still contains the older foundation/sequence/insulation passages. Exact proposed replacements and the baseline are in the parent workspace's `shared/outputs/barndo-agent-source-replacements-2026-10-13.json` and `agent-roadmap-before-2026-10-13.json`. These WordPress changes require separate explicit approval together with the app deployment. Other pricing and supplier claims on that page were not re-verified in this scope.

## Release sequence after approval

1. Confirm repository and WordPress baselines have not changed, preserve rollback versions, and deploy only the reviewed app changes through the normal release path.
2. Apply the three approved WordPress paragraph replacements without unrelated edits.
3. Use the existing authenticated `POST /admin/kb/refresh`, or wait for the documented 12-hour refresh. Verify the affected retrieved excerpts reflect the approved source changes. Never put an admin key in the widget.
4. Run the six answer cases, a real estimate, error handling, mobile readability and Starter Kit routing. Confirm that notices remain visible and cost answers clarify scope.
5. If the app must be reverted, restore its prior version. Preserve source corrections unless those changes themselves fail review; do not roll back unrelated Starter Kit tracking repairs.

Status: local changes only. Nothing committed, pushed, deployed or changed in WordPress by this implementation.
