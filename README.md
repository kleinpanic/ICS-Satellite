# Satellite Pass Calendar

Generate subscribable iCalendar (ICS) feeds for satellite overhead passes at multiple locations, and publish a static GitHub Pages site that helps people subscribe.

## What it does
- Fetches TLE data from CelesTrak.
- Computes satellite passes over featured locations and requested locations for a rolling horizon.
- Computes planetary rise, transit, and set events for all eight planets (no Sun/Moon).
- Generates one `.ics` feed per (location x bundle), including request-specific selections.
- Publishes a static site that lets users subscribe or copy links.
- Supports automated location requests via IssueOps pipeline.

## Using the website

- Subscribe: choose a featured location and bundle, then copy the HTTPS URL for most apps.
  Apple Calendar uses the `webcal://` link.
- Subscribe (multi-bundle): add multiple bundles for the same location and subscribe to each feed independently.
- Request: if a feed does not exist yet, the site opens a GitHub issue with a JSON payload.
  The manifest (`feeds/index.json`) is authoritative for what exists on the site.
- About: the About tab summarizes how the rolling window refreshes and how IssueOps works.
- Stats: the sidebar reports feed counts, featured/requested locations, bundle types, and request fulfillment.
- Feeds refresh automatically every 6 hours and include a rolling 14 day window on GitHub Pages.
  You do not need to re-subscribe after a refresh.

## Local quickstart

On Debian/Ubuntu systems, `python` may not be available; the Makefile defaults to `python3`.
You can override with `PYTHON_SYS=python make dev` if needed.

```bash
# Diagnose Python availability
make doctor

# Create virtual environment + install dev dependencies
make dev

# Validate config
.venv/bin/satpass validate --config config/config.yaml

# Build the site and feeds
make build

# Build satellite catalogs (lazy-loaded by the UI)
make catalog

# Seed the request database from the committed seed file
make seed

# Start local server
make serve
```

Then open `http://localhost:8000`.

Note: `make test` creates and removes its own `.venv`. Use `make dev` when you need a
persistent local environment.

## CLI usage

```bash
# Build site with feeds
.venv/bin/satpass build --config config/config.yaml --out site/

# Build bundle catalogs
.venv/bin/satpass catalog build --config config/config.yaml --out site/

# Validate config
.venv/bin/satpass validate --config config/config.yaml

# Preview passes for a location/bundle
.venv/bin/satpass preview --config config/config.yaml --location new-york --bundle iss --days 3

# Preview with coordinates (requested or custom locations)
.venv/bin/satpass preview --config config/config.yaml --lat 37.2296 --lon -80.4139 --bundle iss --days 3

# Preview planetary bundle
.venv/bin/satpass preview --config config/config.yaml --location new-york --bundle planets-all --days 3

# Generate YAML snippet for a new location
.venv/bin/satpass add-location --name "Portland, OR" --lat 45.5152 --lon -122.6784

# Reset requested feeds (feature-only baseline)
.venv/bin/satpass reset-requests --config config/config.yaml --out site/ --yes
```

The `add-location` command prints a YAML snippet you can paste under `featured_locations` in
`config/config.yaml`.

## Configuration

The config lives in `config/config.yaml` and defines:
- Site metadata and repo URL
- Featured locations (slug, name, lat/lon/elevation) shown by default on the site
- Optional featured bundles (subset of bundles to build by default)
- Satellite bundles (CelesTrak group, optional NORAD IDs)
- Planetary bundles (set `kind: planetary` and `planet_targets`)
- Global defaults (horizon, cache TTL, thresholds)
- `allowed_requesters`: GitHub usernames allowed to request custom locations
- `request_defaults`: Settings for the IssueOps pipeline (slug precision, etc.)
- `request_db_path`: SQLite database for persistent requests
- `defaults.horizon_days`: rolling window length (currently 14 days)

`locations` is still accepted for backwards compatibility, but it is treated as `featured_locations`.
If `featured_bundles` is omitted, all bundles are built for featured locations.

### Favicon assets

Favicon files live in `src/satpass/assets/site/` and are copied into the built `site/` directory
by the build process. Update `favicon.ico`, `favicon.svg`, and `apple-touch-icon.png` there when
refreshing branding assets.

### Request storage

Custom location requests are stored in a SQLite database (`data/requests.sqlite`).
The DB is canonical; YAML files in `config/requests/` are treated as legacy imports only.
When a YAML request omits `slug`, it is derived from the latitude and longitude using the
configured slug precision.

### Seed pipeline

The repo ships with a seed dataset and a deterministic seeding command:

```bash
make seed
```

This loads `config/seeds/seed_requests.yaml` into `data/requests.sqlite` with canonical
request keys. Use the seed pipeline for any updates to the committed DB.

To remove custom locations, either delete the record from the database or use
`satpass reset-requests` to reset to featured-only feeds.

### Satellite catalogs

Satellite selections are loaded from per-bundle catalogs in `site/catalog/`. The main
manifest (`site/feeds/index.json`) references these catalog files so it stays small and
fast to load. Catalogs are built separately and cached:

```bash
make catalog
```

Catalogs are refreshed only when stale by default. Use `satpass catalog build --mode all`
to force a rebuild.

If a bundle's catalog would be too large, the catalog is capped (default 1000 entries) or
by `satellite_listing_limit` in `config/config.yaml`.

## How to find the correct feed URL

Do not curl wildcard URLs like `/feeds/*.ics`. Instead, use the exact feed path from
the manifest generated by a build:

Request-style URLs (lat/lon slugs) will return 404 until a build has generated them.
The manifest is the authoritative list of feeds that exist on the site.

1. Run `make build` (or `satpass build ...`).
2. Open `site/feeds/index.json`.
3. Copy the `path` for the feed you want (for example, `feeds/seattle--stations.ics`).
4. Use the full URL on the site, or the local path when testing:
   - Local: `http://127.0.0.1:8000/feeds/seattle--stations.ics`
   - Pages: `https://<user>.github.io/<repo>/feeds/seattle--stations.ics`

The output of a build always includes `site/feeds/index.json` and the matching `.ics` files
under `site/feeds/`.

## GitHub Pages deployment

The Pages workflow runs on pushes to `main` and on a schedule (every 6 hours). It:
1. Creates a virtual environment
2. Runs `satpass build --config config/config.yaml --out site/`
3. Uploads `site/` as the Pages artifact

Enable Pages in the repository settings and select GitHub Actions as the source.

## Release archives

Tagging a release (for example, `v1.6.0`) builds the site and publishes `site.zip` and
`site.tar.gz` as GitHub Release assets. The same files are also uploaded as workflow
artifacts on the release workflow run. Archives contain the generated `site/` output.
Release tags must be annotated and use the `vX.Y.Z` format.

## How to subscribe
- Apple (iOS/macOS): tap Subscribe (Apple) on the site, or use the `webcal://` URL directly.
- Android/desktop: copy the HTTPS URL and use "Subscribe by URL" in your calendar app, or download the `.ics` file.
Feed URLs are listed in `site/feeds/index.json` after a build; there are no wildcard URLs.
Feeds show the next ~14 days of passes and refresh automatically; you do not need to re-subscribe.

### Switching locations
Unsubscribe from the old calendar and subscribe to the new location feed from the site.

### Custom locations (IssueOps)

The site supports requesting feeds for any location worldwide:

1. Go to the website and use the "Custom location / Request a location" section
2. Enter coordinates (or use "Use my location" for geolocation)
3. Select a satellite bundle
4. Optionally select a subset of satellites
5. Click "Request this feed" to open a GitHub issue

Planetary bundles do not require satellite selections.

The JSON payload in the issue body is the source of truth. The issue form includes a
`bundle_slug` field for manual entries; if it differs from the JSON payload, the automation
uses the JSON payload and posts a warning comment.

If a feed already exists for the selected location/bundle/selection, the site will surface the
existing URLs and disable issue creation.

If you select every satellite in a bundle, the request is treated as "no subset" to avoid
creating redundant feed slugs. If you leave the selection empty, the system will choose a
deterministic default subset capped by `max_satellites_per_request`.

If you're on the allowlist, the automation will:
- Validate your request
- Store the request in the SQLite database
- Coalesce Pages deploys and comment on the issue with subscription URLs and the workflow status

IssueOps applies labels to show status (`processing`, `processed`, `failed`) and comments on the
issue when validation or persistence finishes.

Pages deployment happens in the dedicated Pages workflow. If a deploy is already running, the
request is still persisted and the workflow will catch up after it finishes. Feed URLs may 404
until the Pages workflow completes. To retry a request after editing, remove and re-add the
`location-request` label (or rerun the workflow manually).

If the request already exists, the automation will comment with the existing feed URLs
and close the issue without creating duplicates.

The feed will be regenerated automatically every 6 hours.

## Troubleshooting

### Geolocation permission denied
If the browser blocks location access, allow location permissions for this site in your
browser settings or enter latitude and longitude manually in the request form.

### GitHub Pages
The site is deployed from `site/` via GitHub Actions. Do not change repository Pages
settings in this run; use the existing workflows and settings.

### Pushing without SSH keys
If you do not have SSH keys, use an HTTPS remote:

```bash
git remote set-url origin https://github.com/<user>/<repo>.git
git push origin <branch>
```

## Development

```bash
# Format code
make format

# Run linter and type checker
make lint

# Run tests
make test

# Run smoke workflow (build + serve + curl + request simulation)
make smoke

# Build bundle catalogs (stale-only)
make catalog
```

## CI

On every push and pull request, the CI workflow runs:
- `make dev` + `make lint`
- `make test`

`make test` is the authoritative test entrypoint and always recreates its own `.venv`.

## Project structure

```
config/
  config.yaml          # Main configuration
  requests/            # Legacy YAML imports for requests (optional)
  seeds/
    seed_requests.yaml # Seed dataset for the request DB
site/
  catalog/             # Per-bundle satellite catalogs (generated)
data/
  requests.sqlite      # Canonical request database
src/satpass/
  cli.py               # CLI entry point
  config.py            # Config loading and validation
  build.py             # Feed generation orchestration
  passes.py            # Pass computation using Skyfield
  ics.py               # ICS calendar generation
  site.py              # Static site generation
  slug.py              # Deterministic slug generation
  tle.py               # TLE fetching from CelesTrak
  assets/site/         # Static site assets (HTML, CSS, JS)
  assets/site/favicon.ico
  assets/site/favicon.svg
  assets/site/apple-touch-icon.png
.github/
  workflows/
    ci.yml             # Lint and test on PRs
    pages.yml          # Build and deploy Pages
    location_request.yml  # IssueOps request pipeline
  ISSUE_TEMPLATE/
    location_request.yml  # Issue form for location requests
```
