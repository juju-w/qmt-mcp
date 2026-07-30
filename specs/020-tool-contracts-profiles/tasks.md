# Tasks: Tool Contracts and Profiles

## Phase 1 - Specification and policy

- [x] T001 Record tool-schema, result-adapter, annotation, and profile decisions.
- [x] T002 Define the common tool and result wire contract.
- [x] T003 Add dependency-light unit tests for profile parsing and filtering.

## Phase 2 - Registry contracts

- [x] T004 Add the common output-envelope validation model.
- [x] T005 Adapt audited dictionaries to exact `structuredContent`, JSON text,
  and `isError` at the MCP registration boundary.
- [x] T006 Extend registry metadata with title and standard behavior hints.
- [x] T007 Reject mutation-like registrations mislabeled read-only.
- [x] T008 Preserve unit-tier imports when the MCP runtime is absent.

## Phase 3 - Profiles and existing tools

- [x] T009 Add full/readonly/market/account/core/custom profile configuration.
- [x] T010 Add allowlist and denylist glob parsing and validation.
- [x] T011 Keep core tools visible under all policies.
- [x] T012 Report profile and visible/hidden counts in capabilities.
- [x] T013 Annotate quote subscription/cache/history mutation tools.
- [x] T014 Annotate reference-data download tools.
- [x] T015 Annotate custom-sector mutation tools.
- [x] T016 Annotate formula generation/subscription mutation tools.

## Phase 4 - Wire tests and docs

- [x] T017 Verify every visible tool has complete metadata and output schema.
- [x] T018 Verify successful structured/text result equivalence.
- [x] T019 Verify execution error payload and `isError=true`.
- [x] T020 Verify modern and legacy tool contracts.
- [x] T021 Verify hidden tools are absent and uncallable.
- [x] T022 Update env examples, README, client docs, AGENT, and ops skills.

## Phase 5 - Verification and delivery

- [x] T023 Run ruff and Python unit/integration tests.
- [x] T024 Run Go test/vet/build and cross-compilation regression.
- [x] T025 Run selected modern/legacy official conformance.
- [x] T026 Run release-policy tests, actionlint, diff/secret review, and native
  linux/amd64 appliance build.
- [x] T027 Record evidence in `VERIFICATION.md` and close tasks accurately.
