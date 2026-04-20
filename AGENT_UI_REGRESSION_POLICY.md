# Agent UI Regression Policy

Use this document from `TOOL.md`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, or similar repo instructions. It is written to prevent accidental UI removals, broken workflows, and expensive rework.

## Purpose

The agent must preserve existing user-visible behavior unless the user explicitly approves a change. New code should not silently remove buttons, actions, fields, tabs, menus, dialogs, or workflow steps.

## Required Rules

1. Treat the current UI as a contract.
Before changing an existing screen, identify the current user-visible controls and flows on that screen. Assume they must be preserved unless the user explicitly requests removal or redesign.

2. Never remove UI affordances implicitly.
Do not remove, hide, rename, disable, or relocate existing buttons, links, menu items, tabs, fields, or dialogs unless:
- the user explicitly asked for that exact change, or
- the change is required to fix a verified bug and the impact is explained.

3. Protect critical screens with regression tests.
For every important screen, add or maintain tests that verify critical controls remain present and usable. Prefer assertions on accessible names or stable test ids.

4. Test outcomes, not just clicks.
Do not write low-value tests that only click controls. Verify the expected user-visible result of each important interaction.

5. Add a regression test for every meaningful bug fix.
If a bug removed or broke UI behavior, add a test that fails without the fix and passes with it.

6. Use visual protection for layout-sensitive screens.
For important screens, use screenshot-based or visual snapshot checks when practical. These help catch missing controls, spacing collapse, and partial renders that functional tests may miss.

7. Do not update tests to match unintended breakage.
If existing tests fail because controls disappeared, first determine whether the product intentionally changed. Do not rewrite snapshots or assertions just to make failing tests pass.

8. Call out uncertainty before proceeding.
If the agent cannot tell whether a UI element is intentional, stop and say which controls or flows appear at risk.

## Required Workflow For Existing UI Screens

When modifying an existing screen, follow this sequence:

1. Inspect the current implementation and existing tests.
2. Enumerate the key user-visible controls and workflows affected by the change.
3. Preserve those controls unless removal is explicitly approved.
4. Add or update regression coverage for the critical controls and flows.
5. Run the relevant test suite after the change.
6. In the final summary, explicitly mention any user-visible controls that changed.

## Minimum Test Expectations

Use a layered approach instead of testing every pixel or every click path.

- Unit tests: business logic, state transforms, validation, visibility rules.
- Integration tests: screen-level rendering and critical interactions.
- End-to-end tests: a small number of high-value journeys.
- Visual regression tests: key screens where missing UI must be caught quickly.

## Screen Contract Test Standard

Each important screen should have a contract-style test that verifies the presence of its critical controls for the expected state.

Example expectations for an edit screen:

- renders `Save`
- renders `Cancel`
- renders `Delete`
- renders `Duplicate`
- renders `Archive`
- renders `Preview`

The exact list depends on the product, but the principle is stable: important screens must declare what actions they expose.

## Prompt Snippet For Agents

Use this text in repo instructions when assigning UI work:

> Before modifying any existing UI, identify the current user-visible actions and preserve them unless I explicitly approve removals. Treat buttons, links, tabs, menus, fields, and dialogs as part of the UI contract. Add or update regression tests for critical controls and workflows. Do not change tests or snapshots merely to accept unintended UI loss. If any user-visible action must change, call it out explicitly.

## Short Reference Snippet

Use this shorter version when you only want a one-line reference in another file:

> Follow `AGENT_UI_REGRESSION_POLICY.md` for any UI change. Existing user-visible controls are considered part of the contract and must not be removed or altered without explicit approval and regression coverage.

## What This Prevents

This policy is specifically intended to prevent:

- accidental removal of buttons or actions from existing screens
- silent workflow regressions during refactors
- snapshot churn that hides real UI loss
- agents making large UI assumptions without checking the current screen contract
