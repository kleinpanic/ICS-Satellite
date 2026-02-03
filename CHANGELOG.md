# Changelog

## 1.11.0 - 2026-02-02

### Added
- Planetary bundles (eight planets + all planets) with ephemeris caching and ICS output
- Multi-bundle subscription UI with bundle grouping by type and coverage notes
- Coordinate-based request dedupe, slug validation for IssueOps, and reset-requests tooling
- Build metadata + stats in the manifest (bundle/feed counts, fulfillment timestamps)

### Changed
- Satellite pass rise/set now uses horizon crossings while filtering by peak elevation
- Atomic writes for feeds, catalogs, and manifest output
- CLI preview supports requested locations and planetary bundles

### Fixed
- Request slug handling mismatch that caused “feed not available” for existing requested feeds

## 1.10.0 - 2026-01-30

### Added
- Expanded seeded request feeds for GNSS bundles and additional locations
- Manifest test coverage for expanded seeded request feeds

### Changed
- CI workflow output now groups steps and reports tool versions
- `make test` installs dev dependencies, reports pytest version, and always cleans up its venv

## 1.9.0 - 2026-01-30

### Added
- CI workflow to run lint and tests on push and pull requests
- Expanded seed requests and featured bundles for larger index coverage
- Seed file test enforcing coverage of additional bundles

### Changed
- Test target now provisions a venv, installs pytest + project, runs tests, and cleans up
- Lint/test output now includes clearer step headers

## 1.8.0 - 2026-01-30

### Added
- Bundle mismatch now halts IssueOps processing with explicit failure feedback
- Processing status comment now appears on edited requests as well

### Changed
- IssueOps payload validation fixes JSON parsing and outputs mismatch status consistently
- Issue template copy now requires bundle dropdown to match JSON payload

## 1.7.0 - 2026-01-30

### Added
- IssueOps processing feedback with labels and comments for processing/success/failure
- Request bundle mismatch detection with explicit issue feedback
- Test coverage for non-featured requested bundle inclusion and multi-request DB retention

### Changed
- IssueOps workflow triggers on opened/edited/labeled events and uses a dedicated concurrency group
- Issue template clarifies JSON payload as the source of truth for bundle selection
- Request DB persistence now verifies inserts and fails on exhausted retries

## 1.6.0 - 2026-01-30

### Added
- Seeded Blacksburg, VA as a featured location and request-style ISS/Popular feeds
- Release workflow that publishes `site.zip` and `site.tar.gz` on tags

### Changed
- IssueOps workflow now persists requests with retry-safe DB updates to avoid dropped requests

## 1.5.0 - 2026-01-29

### Added
- Per-bundle satellite catalog generation with a dedicated `satpass catalog build` command
- Default selection semantics for empty request selections (deterministic, capped subsets)
- UI satellite selection chips, remaining-capacity indicator, and lazy catalog loading

### Changed
- Build now fetches TLEs only for featured/requested bundles, with progress output
- Manifest references catalog files instead of embedding satellite lists
- Seed data and docs updated to reflect catalog workflow and safer request defaults

### Fixed
- Request handling accepts slug-less payloads with deterministic slug derivation

## 1.4.0 - 2026-01-29

### Added
- Expanded bundle catalog with satellite listing limits for large groups
- Seed pipeline (`satpass seed`) and seed data for popular request combinations
- Smoke workflow script for local build, serve, curl, and request simulation

### Changed
- UI polish with improved layout, controls, and satellite selection tools
- Featured locations expanded for a more useful default experience
- Manifest now reports satellite listing totals and truncation metadata

### Fixed
- Satellite selection defaults to no subset and avoids full-selection hash slugs
- Manifest feed list dedupes entries by path and merges metadata

## 1.3.0 - 2026-01-29

### Added
- Featured locations support for curated default feeds, with optional featured bundles
- Manifest now includes featured_locations for UI defaults
- Request workflow outputs DB path for safer commits

### Changed
- Config semantics now separate featured_locations from DB-backed requests (locations remains supported for compatibility)
- Request storage is now SQLite-first; YAML requests are treated as legacy imports
- IssueOps workflow writes to the DB and avoids hardcoded requester identity strings
- Subscription instructions moved below the main panels and remain collapsed by default
- Request UI disables issue creation when a feed already exists and shows inline status
- Site footer now links back to the GitHub repository and geolocation errors stay inline

### Fixed
- PRODID now reflects the package version at build time
- Config validation no longer rejects duplicate NORAD IDs across bundles
- IssueOps uses the venv Python when loading YAML config

## 1.2.0 - 2026-01-29

### Added
- SQLite-backed request database with deterministic dedupe keys
- Bundle satellite listings in the manifest for advanced selection
- Optional satellite subset selection in request payloads
- `make dev` target for one-step local setup

### Changed
- Request pipeline now reads from the request DB and imports YAML requests
- Location request workflow dedupes existing requests and skips rebuilds
- Request defaults include max satellites per request and allowlist state
- Site UX moves subscription instructions to a collapsible section at the bottom

### Fixed
- Geolocation errors now render inline instructions instead of alerts
- TLE parsing preserves names when available and adds NORAD fallback

## 1.1.0 - 2026-01-28

### Added
- IssueOps workflow for automated location requests
- Custom location UI with geolocation support
- Deterministic slug generation for custom coordinates
- Request persistence in `config/requests/` directory
- Allowlist-based access control for location requests
- `make doctor` target for diagnosing Python availability
- Comprehensive tests for slug generation and request handling

### Changed
- Makefile now uses `PYTHON_SYS` variable (defaults to `python3`) for venv creation
- `.gitignore` updated to properly ignore `/site/` output directory
- Issue form now includes machine-parseable JSON payload field
- Manifest now includes `request_defaults` for site JS

### Fixed
- Fixed venv creation on Debian where `python` command may not exist
- Fixed `repo_url` placeholder detection (derives from `GITHUB_REPOSITORY` env var)
- Fixed favicon 404 by adding empty favicon link

## 1.0.0 - 2026-01-28
- Initial release.
