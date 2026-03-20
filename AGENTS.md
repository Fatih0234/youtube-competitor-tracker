# AGENTS.md

## Project identity

This repository is the **foundation layer** for a YouTube channel and video ingestion system.

The current goal is **not** to build a finished end-user product.
The current goal is to build a **clean, reliable, maintainable base** that can later support:
- competitor tracking
- content analysis
- topic clustering
- trend analysis
- dashboards
- AI-assisted ideation
- other downstream creator-intelligence workflows

Agents working in this repository should behave like engineers building a strong internal platform, not like product designers chasing surface features.

---

## Primary objective

Build and maintain a Python project that can:
- register tracked YouTube channels
- fetch public channel metadata
- discover and fetch videos for those channels
- persist canonical channel/video records
- persist periodic metric snapshots
- run refresh syncs safely and repeatedly
- expose the system through a clean developer-oriented CLI

---

## Working style

### 1. Be boring in a good way
Prefer:
- clear module boundaries
- explicit code
- predictable behavior
- straightforward schemas
- low-friction local development

Avoid:
- clever abstractions
- speculative frameworks
- unnecessary indirection
- premature generalization
- trendy architecture for its own sake

### 2. Protect maintainability
Every change should make the project easier to reason about, test, and extend.

Favor:
- type hints
- docstrings where useful
- focused functions
- isolated side effects
- explicit configuration
- informative logging
- small cohesive modules

### 3. Preserve clean boundaries
Keep these concerns separate:
- API access
- parsing / normalization
- persistence
- sync orchestration
- CLI layer

Do not tightly couple raw HTTP behavior directly to database writes or CLI commands.

### 4. Optimize for idempotent sync
A repeated sync should not create duplicate canonical records.

Agents should think carefully about:
- upserts
- uniqueness constraints
- repeatable runs
- failure handling
- partial sync safety
- snapshot semantics

### 5. Design for testability
Prefer code that can be tested without a live YouTube API key.

Use:
- client abstractions
- dependency injection where helpful
- mocked API responses
- predictable service boundaries

---

## Technical preferences

- Language: Python
- Package manager: uv
- Prefer `src/` layout
- Prefer SQLAlchemy 2.x for DB access
- Prefer SQLite as the default local DB unless a strong reason exists otherwise
- Use environment variables for secrets and config
- Keep the project runnable locally with minimal setup

---

## Current in-scope areas

Agents should prioritize work in these areas:
- repository bootstrap
- project layout
- configuration
- database schema
- migrations if chosen
- YouTube client abstraction
- channel ingestion
- video ingestion
- snapshot recording
- sync logging
- CLI workflows
- tests
- docs

---

## Explicitly out of scope for now

Do not expand into these areas unless the user directly asks for them:
- frontend/UI
- dashboards
- transcript ingestion
- comment ingestion
- thumbnail asset pipelines
- LLM enrichment
- recommendation engines
- notification systems
- workflow automation beyond basic scheduling readiness
- multi-platform ingestion
- multi-tenant auth systems
- microservices or distributed infrastructure

---

## Data model guidance

The core system should revolve around a small number of stable entities:
- channels
- videos
- video stats snapshots
- channel stats snapshots
- sync runs

Agents may refine field names and relationships, but should preserve the spirit of:
- one canonical current-state record per channel
- one canonical current-state record per video
- separate time-series snapshot tables for changing metrics
- separate operational logging for sync execution

When unsure, choose schemas that are:
- simple
- queryable
- migration-friendly
- useful for future analytics

---

## Sync workflow expectations

Agents should think in terms of these flows:

### add-channel
Resolve a user-provided channel reference into a canonical YouTube channel and store it.

### initial-backfill
Fetch all discoverable videos for a tracked channel, upsert them, and create initial snapshots.

### refresh
Update channel metadata, detect new videos, refresh video metadata, and create new snapshots.

### reconciliation
Optionally perform a deeper re-sync to repair drift or recover missing records.

All sync flows should leave useful operational traces.

---

## Decision rules

When there is a tradeoff, prefer in this order:
1. correctness
2. clarity
3. maintainability
4. ease of local development
5. extensibility
6. performance optimization

Do not optimize for scale prematurely.

---

## Documentation behavior

When agents add features, they should also update the relevant docs.

Minimum expected docs hygiene:
- setup instructions remain accurate
- env vars are documented
- CLI examples are documented
- schema changes are reflected where appropriate

---

## Migration and change discipline

If changing the schema or sync semantics:
- preserve data integrity
- update tests
- update docs
- explain the reason briefly in commit or PR notes

Do not make silent structural changes that make future reasoning harder.

---

## What good looks like

A good contribution in this repo usually has these properties:
- easier to understand after the change than before
- easier to test after the change than before
- easier to extend after the change than before
- does not introduce speculative complexity
- improves the core ingestion foundation

If a change is flashy but weakens maintainability, it is the wrong change.
