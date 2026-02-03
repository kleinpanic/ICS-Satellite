const locationSelect = document.getElementById("location");
const bundleList = document.getElementById("bundle-list");
const bundleAdd = document.getElementById("bundle-add");
const bundleRowTemplate = document.getElementById("bundle-row-template");
const buildInfo = document.getElementById("build-info");
const lastUpdatedEl = document.getElementById("last-updated");
const manifestStatusEl = document.getElementById("manifest-status");
const manifestError = document.getElementById("manifest-error");
const toastEl = document.getElementById("toast");
const flowTabs = document.querySelectorAll(".flow-tab");

const requestName = document.getElementById("request-name");
const requestLat = document.getElementById("request-lat");
const requestLon = document.getElementById("request-lon");
const requestBundle = document.getElementById("request-bundle");
const requestPayload = document.getElementById("request-payload");
const requestCopy = document.getElementById("request-copy");
const requestIssue = document.getElementById("request-issue");
const geolocateBtn = document.getElementById("geolocate");
const requestSatellites = document.getElementById("request-satellites");
const requestStatus = document.getElementById("request-status");
const satelliteSearch = document.getElementById("satellite-search");
const satelliteSelectAll = document.getElementById("satellite-select-all");
const satelliteClear = document.getElementById("satellite-clear");
const satelliteCount = document.getElementById("satellite-count");
const satelliteMeta = document.getElementById("satellite-meta");
const satelliteChips = document.getElementById("satellite-chips");
const satelliteRemaining = document.getElementById("satellite-remaining");

const computedSlugEl = document.getElementById("computed-slug");
const expectedHttpsEl = document.getElementById("expected-https");
const expectedWebcalEl = document.getElementById("expected-webcal");
const feedExistsNotice = document.getElementById("feed-exists-notice");
const geoErrorEl = document.getElementById("geo-error");
const allowlistNote = document.getElementById("allowlist-note");
const repoLink = document.getElementById("repo-link");
const satelliteErrorEl = document.getElementById("satellite-error");
const satelliteHelper = document.getElementById("satellite-helper");
const requestCopyHttps = document.getElementById("request-copy-https");
const requestCopyWebcal = document.getElementById("request-copy-webcal");
const statsFeeds = document.getElementById("stats-feeds");
const statsFeatured = document.getElementById("stats-featured");
const statsRequestedLocations = document.getElementById("stats-requested-locations");
const statsBundlesSat = document.getElementById("stats-bundles-sat");
const statsBundlesPlanet = document.getElementById("stats-bundles-planet");
const statsFeedsSat = document.getElementById("stats-feeds-sat");
const statsFeedsPlanet = document.getElementById("stats-feeds-planet");
const statsRequested = document.getElementById("stats-requested");
const statsRequestedNote = document.getElementById("stats-requested-note");
const statsLastFulfilled = document.getElementById("stats-last-fulfilled");
const statsWindow = document.getElementById("stats-window");
const statsRefresh = document.getElementById("stats-refresh");
const statsBuildInfo = document.getElementById("stats-build-info");
const docsRepoLink = document.getElementById("docs-repo");
const docsIssuesLink = document.getElementById("docs-issues");
const locationType = document.getElementById("location-type");

let feedData = null;
let requestFeedExists = false;
const bundleCatalogs = new Map();
const locationIndex = new Map();
let requestSlugOverride = null;
const bundleRows = [];
const feedIndex = new Map();
const locationBundleIndex = new Map();

const PAYLOAD_VERSION = "1";

function baseUrl() {
  const url = new URL(window.location.href);
  let path = url.pathname;
  if (path.endsWith("index.html")) {
    path = path.slice(0, -"index.html".length);
  }
  if (!path.endsWith("/")) {
    path += "/";
  }
  return `${url.origin}${path}`;
}

function toWebcal(url) {
  if (url.startsWith("https://")) {
    return `webcal://${url.slice("https://".length)}`;
  }
  if (url.startsWith("http://")) {
    return `webcal://${url.slice("http://".length)}`;
  }
  return url;
}

function populateSelect(select, options, labelFn = null) {
  select.innerHTML = "";
  options.forEach((option) => {
    const el = document.createElement("option");
    el.value = option.slug;
    el.textContent = labelFn ? labelFn(option) : option.name;
    select.appendChild(el);
  });
}

function populateLocationSelect(select, locations) {
  select.innerHTML = "";
  const featured = locations.filter((loc) => loc.featured !== false);
  const requested = locations.filter((loc) => loc.featured === false);
  const addGroup = (label, items) => {
    if (!items.length) {
      return;
    }
    const group = document.createElement("optgroup");
    group.label = label;
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.slug;
      option.textContent = item.name;
      group.appendChild(option);
    });
    select.appendChild(group);
  };
  addGroup("Featured locations", featured);
  addGroup("Requested locations", requested);
}

function populateBundleSelect(select, bundles) {
  select.innerHTML = "";
  const satellite = bundles.filter((bundle) => bundle.kind !== "planetary");
  const planetary = bundles.filter((bundle) => bundle.kind === "planetary");
  const addGroup = (label, items) => {
    if (!items.length) {
      return;
    }
    const group = document.createElement("optgroup");
    group.label = label;
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.slug;
      option.textContent = item.name;
      group.appendChild(option);
    });
    select.appendChild(group);
  };
  addGroup("Satellite bundles", satellite);
  addGroup("Planetary bundles", planetary);
}

function selectedLocation() {
  return locationIndex.get(locationSelect.value) || null;
}

function findFeed(locationSlug, bundleSlug) {
  return feedIndex.get(`${locationSlug}::${bundleSlug}`) || null;
}

function updateLocationBadge() {
  if (!locationType) {
    return;
  }
  const location = selectedLocation();
  if (!location) {
    locationType.classList.add("hidden");
    locationType.textContent = "";
    return;
  }
  locationType.classList.remove("hidden");
  locationType.textContent = location.featured ? "Featured location" : "Requested location";
}

function locationHasFeeds(locationSlug) {
  const bundles = locationBundleIndex.get(locationSlug);
  return bundles && bundles.size > 0;
}

function updateBundleRow(row) {
  if (!feedData) {
    return;
  }
  const locationSlug = locationSelect.value;
  const bundleSlug = row.select.value;
  const feed = findFeed(locationSlug, bundleSlug);

  row.label.textContent = "";
  row.url.textContent = "";
  row.url.removeAttribute("href");
  row.webcal.textContent = "";
  row.webcal.removeAttribute("href");

  if (!feed) {
    row.label.textContent = "No feed available";
    row.subscribe.disabled = true;
    row.download.disabled = true;
    row.copyHttps.disabled = true;
    row.copyWebcal.disabled = true;
    row.missing.classList.remove("hidden");
    row.request.disabled = false;
    if (locationHasFeeds(locationSlug)) {
      row.coverage.classList.remove("hidden");
    } else {
      row.coverage.classList.add("hidden");
    }
    return;
  }

  const url = `${baseUrl()}${feed.path}`;
  const webcalUrl = toWebcal(url);
  row.label.textContent = `${feed.location_name} - ${feed.bundle_name}`;
  row.url.textContent = url;
  row.url.href = url;
  row.webcal.textContent = webcalUrl;
  row.webcal.href = webcalUrl;

  row.subscribe.onclick = () => {
    window.location.href = webcalUrl;
  };
  row.download.onclick = () => {
    window.location.href = url;
  };
  row.copyHttps.onclick = async () => {
    await copyText(url, "HTTPS link copied");
  };
  row.copyWebcal.onclick = async () => {
    await copyText(webcalUrl, "webcal link copied");
  };

  row.subscribe.disabled = false;
  row.download.disabled = false;
  row.copyHttps.disabled = false;
  row.copyWebcal.disabled = false;
  row.missing.classList.add("hidden");
  row.coverage.classList.add("hidden");
}

function updateBundleRows() {
  bundleRows.forEach((row) => updateBundleRow(row));
}

function refreshBundleControls() {
  const allowRemove = bundleRows.length > 1;
  bundleRows.forEach((row) => {
    row.remove.disabled = !allowRemove;
  });
}

function prefillRequestForSelection(location, bundleSlug) {
  if (!location) {
    return;
  }
  requestSlugOverride = location.slug;
  requestName.value = location.name;
  requestLat.value = location.lat.toFixed(4);
  requestLon.value = location.lon.toFixed(4);
  requestBundle.value = bundleSlug;
  requestSatellites.selectedIndex = -1;
  return updateSatelliteOptions().then(() => {
    updateRequestPayload();
    activateTab("request-panel");
    showToast("Prefilled request details");
  });
}

function createBundleRow(initialSlug = null) {
  const fragment = bundleRowTemplate.content.cloneNode(true);
  const root = fragment.querySelector(".bundle-item");
  const select = root.querySelector(".bundle-select");
  const subscribe = root.querySelector(".bundle-subscribe");
  const download = root.querySelector(".bundle-download");
  const label = root.querySelector(".bundle-label");
  const url = root.querySelector(".bundle-url");
  const webcal = root.querySelector(".bundle-webcal");
  const copyHttps = root.querySelector(".bundle-copy-https");
  const copyWebcal = root.querySelector(".bundle-copy-webcal");
  const missing = root.querySelector(".bundle-missing");
  const coverage = root.querySelector(".bundle-coverage");
  const request = root.querySelector(".bundle-request");
  const remove = root.querySelector(".bundle-remove");

  populateBundleSelect(select, feedData.bundles);
  if (initialSlug) {
    select.value = initialSlug;
  }

  const row = {
    root,
    select,
    subscribe,
    download,
    label,
    url,
    webcal,
    copyHttps,
    copyWebcal,
    missing,
    coverage,
    request,
    remove,
  };

  select.addEventListener("change", () => updateBundleRow(row));
  request.addEventListener("click", () => {
    prefillRequestForSelection(selectedLocation(), select.value);
  });
  remove.addEventListener("click", () => {
    bundleList.removeChild(root);
    const index = bundleRows.indexOf(row);
    if (index >= 0) {
      bundleRows.splice(index, 1);
    }
    refreshBundleControls();
    updateBundleRows();
  });

  return row;
}

function addBundleRow(initialSlug = null) {
  const row = createBundleRow(initialSlug);
  bundleRows.push(row);
  bundleList.appendChild(row.root);
  refreshBundleControls();
  updateBundleRow(row);
}

function updateStats() {
  if (!feedData) {
    return;
  }
  const stats = feedData.stats || {};
  const featuredLocations = feedData.featured_locations || feedData.locations || [];
  const requestedAvailable = feedData.feeds && feedData.feeds.some((feed) => "requested" in feed);
  const requestedFeeds = stats.feeds ? stats.feeds.requested : null;

  if (statsFeeds) {
    statsFeeds.textContent = `${stats.feeds?.total ?? feedData.feeds.length}`;
  }
  if (statsFeedsSat) {
    statsFeedsSat.textContent = `${stats.feeds?.satellite ?? "-"}`;
  }
  if (statsFeedsPlanet) {
    statsFeedsPlanet.textContent = `${stats.feeds?.planetary ?? "-"}`;
  }
  if (statsFeatured) {
    statsFeatured.textContent = `${stats.locations?.featured ?? featuredLocations.length}`;
  }
  if (statsRequestedLocations) {
    statsRequestedLocations.textContent = `${stats.locations?.requested ?? "-"}`;
  }
  if (statsBundlesSat) {
    statsBundlesSat.textContent = `${stats.bundles?.satellite ?? "-"}`;
  }
  if (statsBundlesPlanet) {
    statsBundlesPlanet.textContent = `${stats.bundles?.planetary ?? "-"}`;
  }
  if (statsRequested) {
    statsRequested.textContent = `${requestedFeeds ?? "-"}`;
  }
  if (statsRequestedNote) {
    statsRequestedNote.textContent = requestedAvailable
      ? "Requested feeds are marked in the manifest."
      : "Requested feeds inferred from non-featured locations.";
  }
  if (statsLastFulfilled) {
    statsLastFulfilled.textContent = stats.last_request_fulfilled_at
      ? `Last request fulfilled: ${stats.last_request_fulfilled_at}`
      : "Last request fulfilled: -";
  }
  if (statsBuildInfo) {
    const version = feedData.build?.version || "";
    const sha = feedData.build?.git_sha ? feedData.build.git_sha.slice(0, 8) : "";
    const parts = [];
    if (version) {
      parts.push(`satpass ${version}`);
    }
    if (sha) {
      parts.push(`commit ${sha}`);
    }
    statsBuildInfo.textContent = parts.length ? parts.join(" · ") : "";
  }

  const horizonDays = feedData.defaults?.horizon_days ?? 14;
  const refreshHours = feedData.defaults?.refresh_interval_hours ?? 6;
  if (statsWindow) {
    statsWindow.textContent = `Rolling window: ${horizonDays} days`;
  }
  if (statsRefresh) {
    statsRefresh.textContent = `Refresh cadence: every ${refreshHours} hours`;
  }
}

let toastTimer = null;

function showToast(message, isError = false) {
  if (!toastEl) {
    return;
  }
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  if (isError) {
    toastEl.classList.add("error");
  } else {
    toastEl.classList.remove("error");
  }
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    toastEl.classList.add("hidden");
  }, 2600);
}

async function copyText(text, successMessage = "Copied to clipboard") {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    showToast(successMessage);
    return;
  }
  window.prompt("Copy to clipboard:", text);
  showToast("Copy manually using the prompt");
}

function activateTab(targetId) {
  flowTabs.forEach((btn) => {
    const isActive = btn.getAttribute("data-target") === targetId;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  document.querySelectorAll(".flow-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === targetId);
  });
}

// Slug computation - mirrors Python implementation
function formatCoordinate(value, precision) {
  const rounded = parseFloat(value.toFixed(precision));
  const sign = rounded < 0 ? "m" : "";
  const absVal = Math.abs(rounded);
  if (precision === 0) {
    return `${sign}${Math.floor(absVal)}`;
  }
  const formatted = absVal.toFixed(precision).replace(".", "p");
  return `${sign}${formatted}`;
}

function computeLocationSlug(lat, lon, precision) {
  const latPart = formatCoordinate(lat, precision);
  const lonPart = formatCoordinate(lon, precision);
  return `lat${latPart}_lon${lonPart}`;
}

function computeFeedSlug(lat, lon, bundleSlug, precision) {
  const locationSlug = computeLocationSlug(lat, lon, precision);
  return `${locationSlug}--${bundleSlug}`;
}

function selectionHash(ids) {
  const payload = ids.join(",");
  let hashVal = 2166136261;
  for (let i = 0; i < payload.length; i += 1) {
    hashVal ^= payload.charCodeAt(i);
    hashVal = (hashVal * 16777619) >>> 0;
  }
  return hashVal.toString(16).padStart(8, "0");
}

function computeRequestFeedSlug(locationSlug, bundleSlug, selectedIds) {
  const base = `${locationSlug}--${bundleSlug}`;
  if (!selectedIds.length) {
    return base;
  }
  const digest = selectionHash(selectedIds);
  return `${base}--sel-${digest}`;
}

function getSlugPrecision() {
  if (feedData && feedData.request_defaults && feedData.request_defaults.slug_precision_decimals) {
    return feedData.request_defaults.slug_precision_decimals;
  }
  return 4;
}

function getMaxSatellites() {
  if (feedData && feedData.request_defaults && feedData.request_defaults.max_satellites_per_request) {
    return feedData.request_defaults.max_satellites_per_request;
  }
  return 12;
}

function catalogUrl(bundle) {
  if (!bundle || !bundle.catalog_available || !bundle.catalog_path) {
    return null;
  }
  return `${baseUrl()}${bundle.catalog_path}`;
}

async function loadBundleCatalog(bundleSlug) {
  if (bundleCatalogs.has(bundleSlug)) {
    return bundleCatalogs.get(bundleSlug);
  }
  const bundle = getBundleBySlug(bundleSlug);
  const url = catalogUrl(bundle);
  if (!url) {
    bundleCatalogs.set(bundleSlug, null);
    return null;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("Catalog not available");
    }
    const data = await response.json();
    bundleCatalogs.set(bundleSlug, data);
    return data;
  } catch (error) {
    bundleCatalogs.set(bundleSlug, null);
    return null;
  }
}

function bundleCatalog(bundleSlug) {
  return bundleCatalogs.has(bundleSlug) ? bundleCatalogs.get(bundleSlug) : null;
}

function normalizeSelectedIds(values) {
  const ids = values
    .map((value) => parseInt(value, 10))
    .filter((value) => !Number.isNaN(value));
  return [...new Set(ids)].sort((a, b) => a - b);
}

function getBundleBySlug(bundleSlug) {
  if (!feedData || !feedData.bundles) {
    return null;
  }
  return feedData.bundles.find((entry) => entry.slug === bundleSlug) || null;
}

function isPlanetaryBundle(bundleSlug) {
  const bundle = getBundleBySlug(bundleSlug);
  return bundle && bundle.kind === "planetary";
}

function getBundleSatelliteIds(bundleSlug) {
  const bundle = getBundleBySlug(bundleSlug);
  if (bundle && bundle.kind === "planetary") {
    return [];
  }
  const catalog = bundleCatalog(bundleSlug);
  if (!catalog || !catalog.satellites) {
    return [];
  }
  return normalizeSelectedIds(catalog.satellites.map((sat) => sat.norad_id));
}

function canonicalizeSelectedIds(bundleSlug, selectedIds) {
  const bundle = getBundleBySlug(bundleSlug);
  if (bundle && bundle.satellites_truncated) {
    return selectedIds;
  }
  const available = getBundleSatelliteIds(bundleSlug);
  if (!selectedIds.length || !available.length) {
    return selectedIds;
  }
  if (selectedIds.length === available.length) {
    const matches = selectedIds.every((value, index) => value === available[index]);
    if (matches) {
      return [];
    }
  }
  return selectedIds;
}

function currentSelectedIds() {
  if (isPlanetaryBundle(requestBundle.value)) {
    return [];
  }
  let selectedIds = normalizeSelectedIds(
    [...requestSatellites.selectedOptions].map((o) => o.value)
  );
  selectedIds = canonicalizeSelectedIds(requestBundle.value, selectedIds);
  return selectedIds;
}

function updateSatelliteCount() {
  if (!satelliteCount) {
    return;
  }
  if (isPlanetaryBundle(requestBundle.value)) {
    satelliteCount.textContent = "No satellites needed";
    if (satelliteRemaining) {
      satelliteRemaining.textContent = "";
    }
    renderSatelliteChips([]);
    return;
  }
  const selectedIds = normalizeSelectedIds(
    [...requestSatellites.selectedOptions].map((o) => o.value)
  );
  const maxSatellites = getMaxSatellites();
  const bundle = getBundleBySlug(requestBundle.value);
  const catalog = bundleCatalog(requestBundle.value);
  const total =
    (catalog && catalog.satellites_total) ||
    (bundle && bundle.satellites_total ? bundle.satellites_total : null);
  if (total) {
    satelliteCount.textContent = `${selectedIds.length} selected of ${total}`;
  } else {
    satelliteCount.textContent = `${selectedIds.length} selected`;
  }
  if (satelliteRemaining) {
    const remaining = Math.max(maxSatellites - selectedIds.length, 0);
    satelliteRemaining.textContent = `${remaining} remaining`;
  }
  renderSatelliteChips(selectedIds);
}

function updateSatelliteMeta(bundle, catalog) {
  if (!satelliteMeta) {
    return;
  }
  satelliteMeta.classList.add("hidden");
  satelliteMeta.textContent = "";
  if (!bundle) {
    return;
  }
  if (bundle.kind !== "planetary" && !catalog) {
    satelliteMeta.textContent =
      "Catalog not built yet. Run \"satpass catalog build\" to enable selection.";
    satelliteMeta.classList.remove("hidden");
    return;
  }
  if (bundle.satellites_truncated && bundle.satellites_limit && bundle.satellites_total) {
    satelliteMeta.textContent = `Showing ${bundle.satellites_limit} of ${bundle.satellites_total} satellites.`;
    satelliteMeta.classList.remove("hidden");
  }
}

function renderSatelliteChips(selectedIds) {
  if (!satelliteChips) {
    return;
  }
  satelliteChips.innerHTML = "";
  if (!selectedIds.length) {
    return;
  }
  const catalog = bundleCatalog(requestBundle.value);
  const nameLookup = new Map();
  if (catalog && catalog.satellites) {
    catalog.satellites.forEach((sat) => {
      nameLookup.set(sat.norad_id, sat.name);
    });
  }
  selectedIds.forEach((id) => {
    const chip = document.createElement("div");
    chip.className = "satellite-chip";
    const label = document.createElement("span");
    label.textContent = `${nameLookup.get(id) || "NORAD"} ${id}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${label.textContent}`);
    remove.addEventListener("click", () => {
      [...requestSatellites.options].forEach((option) => {
        if (parseInt(option.value, 10) === id) {
          option.selected = false;
        }
      });
      updateSatelliteCount();
      updateRequestPayload();
    });
    chip.appendChild(label);
    chip.appendChild(remove);
    satelliteChips.appendChild(chip);
  });
}

async function updateSatelliteOptions() {
  if (!feedData) {
    return;
  }
  const bundle = getBundleBySlug(requestBundle.value);
  if (bundle && bundle.kind === "planetary") {
    requestSatellites.innerHTML = "";
    requestSatellites.disabled = true;
    if (satelliteSearch) {
      satelliteSearch.disabled = true;
    }
    if (satelliteSelectAll) {
      satelliteSelectAll.disabled = true;
    }
    if (satelliteClear) {
      satelliteClear.disabled = true;
    }
    if (satelliteHelper) {
      satelliteHelper.textContent = "Planetary bundles do not require satellite selection.";
    }
    updateSatelliteCount();
    updateSatelliteMeta(bundle, null);
    return;
  }
  const catalog = bundle ? await loadBundleCatalog(bundle.slug) : null;
  const satellites = catalog && catalog.satellites ? catalog.satellites : [];
  if (satelliteSelectAll) {
    satelliteSelectAll.disabled = false;
  }
  if (satelliteClear) {
    satelliteClear.disabled = false;
  }
  if (satelliteHelper) {
    satelliteHelper.textContent = `Leave empty to use a default subset (up to ${getMaxSatellites()} satellites).`;
  }
  const selectedIds = new Set(
    normalizeSelectedIds([...requestSatellites.selectedOptions].map((o) => o.value))
  );
  const query = satelliteSearch ? satelliteSearch.value.trim().toLowerCase() : "";
  const filtered = query
    ? satellites.filter(
        (sat) =>
          sat.name.toLowerCase().includes(query) ||
          String(sat.norad_id).includes(query)
      )
    : satellites;

  requestSatellites.innerHTML = "";
  filtered.forEach((sat) => {
    const option = document.createElement("option");
    option.value = sat.norad_id;
    option.textContent = `${sat.name} (${sat.norad_id})`;
    option.selected = selectedIds.has(sat.norad_id);
    requestSatellites.appendChild(option);
  });
  requestSatellites.disabled = satellites.length === 0;
  if (satelliteSearch) {
    satelliteSearch.disabled = satellites.length === 0;
  }
  if (!selectedIds.size) {
    requestSatellites.selectedIndex = -1;
  }
  updateSatelliteCount();
  updateSatelliteMeta(bundle, catalog);
}

function updateRequestPreview() {
  if (!feedData) {
    return;
  }

  const lat = parseFloat(requestLat.value);
  const lon = parseFloat(requestLon.value);
  const bundleSlug = requestBundle.value;
  let selectedIds = currentSelectedIds();
  const maxSatellites = getMaxSatellites();
  const precision = getSlugPrecision();
  const locationSlug =
    requestSlugOverride || (isNaN(lat) || isNaN(lon) ? null : computeLocationSlug(lat, lon, precision));
  const locationKey =
    isNaN(lat) || isNaN(lon) ? null : computeLocationSlug(lat, lon, precision);
  satelliteErrorEl.classList.add("hidden");
  satelliteErrorEl.textContent = "";

  // Validate inputs
  const validLat = !isNaN(lat) && lat >= -90 && lat <= 90;
  const validLon = !isNaN(lon) && lon >= -180 && lon <= 180;

  if ((!validLat || !validLon) && !requestSlugOverride) {
    computedSlugEl.textContent = "-";
    expectedHttpsEl.textContent = "-";
    expectedHttpsEl.removeAttribute("href");
    expectedWebcalEl.textContent = "-";
    expectedWebcalEl.removeAttribute("href");
    feedExistsNotice.classList.add("hidden");
    requestFeedExists = false;
    requestIssue.disabled = true;
    requestIssue.textContent = "Request this feed";
    setRequestStatus("", false);
    if (requestCopyHttps) {
      requestCopyHttps.disabled = true;
    }
    if (requestCopyWebcal) {
      requestCopyWebcal.disabled = true;
    }
    return;
  }

  if (!bundleSlug || !locationSlug) {
    computedSlugEl.textContent = "-";
    expectedHttpsEl.textContent = "-";
    expectedHttpsEl.removeAttribute("href");
    expectedWebcalEl.textContent = "-";
    expectedWebcalEl.removeAttribute("href");
    feedExistsNotice.classList.add("hidden");
    requestFeedExists = false;
    requestIssue.disabled = true;
    requestIssue.textContent = "Request this feed";
    setRequestStatus("", false);
    if (requestCopyHttps) {
      requestCopyHttps.disabled = true;
    }
    if (requestCopyWebcal) {
      requestCopyWebcal.disabled = true;
    }
    return;
  }

  if (selectedIds.length > maxSatellites) {
    satelliteErrorEl.textContent = `Select up to ${maxSatellites} satellites.`;
    satelliteErrorEl.classList.remove("hidden");
    computedSlugEl.textContent = "-";
    expectedHttpsEl.textContent = "-";
    expectedHttpsEl.removeAttribute("href");
    expectedWebcalEl.textContent = "-";
    expectedWebcalEl.removeAttribute("href");
    feedExistsNotice.classList.add("hidden");
    requestFeedExists = false;
    requestIssue.disabled = true;
    requestIssue.textContent = "Request this feed";
    setRequestStatus("", false);
    if (requestCopyHttps) {
      requestCopyHttps.disabled = true;
    }
    if (requestCopyWebcal) {
      requestCopyWebcal.disabled = true;
    }
    return;
  }

  selectedIds = canonicalizeSelectedIds(bundleSlug, selectedIds);
  const feedSlug = computeRequestFeedSlug(locationSlug, bundleSlug, selectedIds);
  const filename = `${feedSlug}.ics`;
  const httpsUrl = `${baseUrl()}feeds/${filename}`;
  const webcalUrl = toWebcal(httpsUrl);

  computedSlugEl.textContent = feedSlug;
  expectedHttpsEl.textContent = httpsUrl;
  expectedHttpsEl.href = httpsUrl;
  expectedWebcalEl.textContent = webcalUrl;
  expectedWebcalEl.href = webcalUrl;
  if (requestCopyHttps) {
    requestCopyHttps.disabled = false;
  }
  if (requestCopyWebcal) {
    requestCopyWebcal.disabled = false;
  }

  // Check if feed already exists by looking for the location_slug and bundle
  const existingFeed = feedData.feeds.find((feed) => {
    if (feed.path === `feeds/${filename}`) {
      return true;
    }
    if (locationKey && feed.location_key === locationKey && feed.bundle_slug === bundleSlug) {
      return true;
    }
    return false;
  });
  if (existingFeed) {
    feedExistsNotice.classList.remove("hidden");
    requestFeedExists = true;
    requestIssue.disabled = true;
    requestIssue.textContent = "Feed already exists";
    setRequestStatus("This feed already exists. Subscribe using the URLs above.", false);
  } else {
    feedExistsNotice.classList.add("hidden");
    requestFeedExists = false;
    requestIssue.disabled = false;
    requestIssue.textContent = "Request this feed";
    setRequestStatus("", false);
  }
}

function updateRequestPayload() {
  if (!feedData) {
    return;
  }

  const lat = requestLat.value.trim();
  const lon = requestLon.value.trim();
  let selectedIds = currentSelectedIds();

  const payload = {
    version: PAYLOAD_VERSION,
    name: requestName.value.trim() || null,
    lat: lat ? parseFloat(lat) : null,
    lon: lon ? parseFloat(lon) : null,
    slug: requestSlugOverride || null,
    bundle_slug: requestBundle.value,
    selected_norad_ids: selectedIds.length ? selectedIds : [],
    requested_by: null,
  };

  requestPayload.value = JSON.stringify(payload, null, 2);
  updateRequestPreview();
}

function issueUrl() {
  if (!feedData || !feedData.repo_url) {
    return null;
  }

  const payloadText = requestPayload.value;
  const titleBase = requestName.value.trim() || "Custom location";
  const lat = requestLat.value.trim();
  const lon = requestLon.value.trim();
  const bundleSlug = requestBundle.value;

  // Prefill form fields using query params matching the form input IDs
  const params = new URLSearchParams({
    template: "location_request.yml",
    title: `Location request: ${titleBase}`,
    name: requestName.value.trim(),
    lat: lat,
    lon: lon,
    bundle_slug: bundleSlug,
    payload: payloadText,
  });

  return `${feedData.repo_url}/issues/new?${params.toString()}`;
}

function setRequestStatus(message, isError) {
  if (!requestStatus) {
    return;
  }
  if (!message) {
    requestStatus.classList.add("hidden");
    requestStatus.textContent = "";
    requestStatus.classList.remove("error");
    return;
  }
  requestStatus.textContent = message;
  requestStatus.classList.remove("hidden");
  if (isError) {
    requestStatus.classList.add("error");
  } else {
    requestStatus.classList.remove("error");
  }
}

geolocateBtn.addEventListener("click", () => {
  geoErrorEl.classList.add("hidden");
  geoErrorEl.textContent = "";
  if (!navigator.geolocation) {
    geoErrorEl.textContent = "Geolocation is not supported by your browser.";
    geoErrorEl.classList.remove("hidden");
    return;
  }

  geolocateBtn.disabled = true;
  geolocateBtn.textContent = "Locating...";

  navigator.geolocation.getCurrentPosition(
    (position) => {
      clearRequestSlugOverride();
      requestLat.value = position.coords.latitude.toFixed(4);
      requestLon.value = position.coords.longitude.toFixed(4);
      updateRequestPayload();
      geolocateBtn.disabled = false;
      geolocateBtn.textContent = "Use my location";
    },
    (error) => {
      let message = "Unable to get your location.";
      if (error.code === error.PERMISSION_DENIED) {
        message =
          "Enable location permissions for this site in your browser settings, or enter coordinates manually.";
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        message = "Location unavailable. You can enter coordinates manually.";
      } else if (error.code === error.TIMEOUT) {
        message = "Location request timed out. Try again or enter coordinates manually.";
      }
      geoErrorEl.textContent = message;
      geoErrorEl.classList.remove("hidden");
      geolocateBtn.disabled = false;
      geolocateBtn.textContent = "Use my location";
    },
    {
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 300000,
    }
  );
});

requestCopy.addEventListener("click", async () => {
  await copyText(requestPayload.value, "Payload copied");
});

requestIssue.addEventListener("click", () => {
  const url = issueUrl();
  if (requestFeedExists) {
    setRequestStatus("This feed already exists. No request is needed.", false);
    return;
  }
  if (url) {
    const originalText = requestIssue.textContent;
    requestIssue.disabled = true;
    requestIssue.textContent = "Opening issue...";
    window.open(url, "_blank");
    showToast("Opened GitHub issue form");
    window.setTimeout(() => {
      requestIssue.disabled = false;
      requestIssue.textContent = originalText;
    }, 1500);
  } else {
    setRequestStatus("Repository URL not configured. Unable to open an issue.", true);
    showToast("Repository URL not configured", true);
  }
});

if (requestCopyHttps) {
  requestCopyHttps.addEventListener("click", async () => {
    await copyText(expectedHttpsEl.textContent, "HTTPS link copied");
  });
}

if (requestCopyWebcal) {
  requestCopyWebcal.addEventListener("click", async () => {
    await copyText(expectedWebcalEl.textContent, "webcal link copied");
  });
}

function clearRequestSlugOverride() {
  requestSlugOverride = null;
}

requestName.addEventListener("input", () => {
  clearRequestSlugOverride();
  updateRequestPayload();
});
requestLat.addEventListener("input", () => {
  clearRequestSlugOverride();
  updateRequestPayload();
});
requestLon.addEventListener("input", () => {
  clearRequestSlugOverride();
  updateRequestPayload();
});
requestBundle.addEventListener("change", async () => {
  if (satelliteSearch) {
    satelliteSearch.value = "";
  }
  requestSatellites.selectedIndex = -1;
  await updateSatelliteOptions();
  updateRequestPayload();
});
requestSatellites.addEventListener("change", () => {
  updateSatelliteCount();
  updateRequestPayload();
});
satelliteSearch.addEventListener("input", () => {
  void updateSatelliteOptions();
});
satelliteSelectAll.addEventListener("click", async () => {
  if (satelliteSearch) {
    satelliteSearch.value = "";
  }
  await updateSatelliteOptions();
  const maxSatellites = getMaxSatellites();
  let selected = 0;
  [...requestSatellites.options].forEach((option) => {
    if (selected < maxSatellites) {
      option.selected = true;
      selected += 1;
    } else {
      option.selected = false;
    }
  });
  updateSatelliteCount();
  updateRequestPayload();
});
satelliteClear.addEventListener("click", () => {
  requestSatellites.selectedIndex = -1;
  updateSatelliteCount();
  updateRequestPayload();
});

locationSelect.addEventListener("change", () => {
  updateLocationBadge();
  updateBundleRows();
});

async function init() {
  document.body.classList.add("js");
  flowTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activateTab(tab.getAttribute("data-target"));
    });
  });

  try {
    const response = await fetch("feeds/index.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Manifest unavailable");
    }
    feedData = await response.json();
  } catch (error) {
    if (manifestError) {
      manifestError.classList.remove("hidden");
    }
    setRequestStatus("Unable to load the manifest.", true);
    if (locationSelect) {
      locationSelect.disabled = true;
    }
    if (bundleAdd) {
      bundleAdd.disabled = true;
    }
    requestIssue.disabled = true;
    requestCopy.disabled = true;
    return;
  }

  document.title = feedData.site.title;

  const locations = feedData.locations || feedData.featured_locations || [];
  locationIndex.clear();
  locations.forEach((location) => {
    locationIndex.set(location.slug, location);
  });
  populateLocationSelect(locationSelect, locations);
  populateBundleSelect(requestBundle, feedData.bundles);

  feedIndex.clear();
  locationBundleIndex.clear();
  feedData.feeds.forEach((feed) => {
    feedIndex.set(`${feed.location_slug}::${feed.bundle_slug}`, feed);
    if (!locationBundleIndex.has(feed.location_slug)) {
      locationBundleIndex.set(feed.location_slug, new Set());
    }
    locationBundleIndex.get(feed.location_slug).add(feed.bundle_slug);
  });

  if (feedData.request_defaults && feedData.request_defaults.allowlist_enabled) {
    allowlistNote.classList.remove("hidden");
  }

  const repoFallback = "https://github.com";
  repoLink.href = feedData.repo_url || repoFallback;

  if (feedData.generated_at) {
    const version = feedData.build?.version ? ` · satpass ${feedData.build.version}` : "";
    const sha = feedData.build?.git_sha ? ` (${feedData.build.git_sha.slice(0, 8)})` : "";
    buildInfo.textContent = `Last updated: ${feedData.generated_at}${version}${sha}`;
    if (lastUpdatedEl) {
      lastUpdatedEl.textContent = feedData.generated_at;
    }
  }
  if (manifestStatusEl && feedData.feeds) {
    manifestStatusEl.textContent = `${feedData.feeds.length} feeds`;
  }

  if (docsRepoLink) {
    docsRepoLink.href = feedData.repo_url || repoFallback;
  }
  if (docsIssuesLink) {
    const repo = feedData.repo_url || repoFallback;
    docsIssuesLink.href = `${repo}/issues`;
  }

  if (bundleAdd) {
    bundleAdd.addEventListener("click", () => {
      addBundleRow();
    });
  }
  addBundleRow();

  updateStats();
  updateLocationBadge();

  await updateSatelliteOptions();
  updateRequestPayload();
  updateBundleRows();
}

init();
