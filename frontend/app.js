/**
 * GeoGuard V1 - Frontend Application Controller
 * Connects exclusively to backend REST API endpoints.
 */

// Initialize Leaflet Map centered on Chennai
const map = L.map('map').setView([13.0827, 80.2707], 11);

// Add standard OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
}).addTo(map);

// Global application state
let floodData = null;
let userLocationMarker = null;
let allShelterMarkers = [];
let activeRoutePolyline = null;
let currentCoords = null;
let currentSelectedShelter = null;
let geoJsonLayer = null;

// Risk Level color mapping
function getRiskColor(risk) {
    const colors = {
        'Low': '#10b981',
        'Moderate': '#f59e0b',
        'High': '#f97316',
        'Severe': '#ef4444'
    };
    return colors[risk] || '#6b7280';
}

// Map Click Listener: allow clicking anywhere to select location
map.on('click', function(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    setUserLocation(lat, lng, `Selected Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
});

/**
 * Update UI telemetry and summary counts
 */
let previousSectorRisks = {};

function updateSummaryTelemetry(features) {
    const stats = { safe: 0, moderate: 0, high: 0, severe: 0, total: 0 };
    const escalations = [];

    features.forEach(feature => {
        const name = feature.properties.place_name;
        const risk = feature.properties.flood_risk;
        const prev = previousSectorRisks[name];

        stats.total++;
        if (risk === 'Low') stats.safe++;
        else if (risk === 'Moderate') stats.moderate++;
        else if (risk === 'High') stats.high++;
        else if (risk === 'Severe') stats.severe++;

        // Detect escalation
        if (prev && prev !== risk) {
            const riskWeight = { 'Low': 0, 'Moderate': 1, 'High': 2, 'Severe': 3 };
            if (riskWeight[risk] > riskWeight[prev] && (risk === 'High' || risk === 'Severe')) {
                escalations.push({ name, from: prev, to: risk });
            }
        }
        previousSectorRisks[name] = risk;
    });

    // Display escalation alert banner if newly elevated
    const toastContainer = document.getElementById('v4EscalationToastContainer');
    if (toastContainer && escalations.length > 0) {
        toastContainer.innerHTML = escalations.map(esc => `
            <div class="v4-escalation-banner">
                <span>⚠️ <strong>RISK ESCALATION DETECTED:</strong> ${esc.name} has escalated from <strong>${esc.from}</strong> to <strong>${esc.to}</strong> risk!</span>
                <button onclick="this.parentElement.remove()" style="background:none; border:none; color:white; font-size:16px; cursor:pointer; font-weight:bold;">&times;</button>
            </div>
        `).join('');
    }

    const timestampStr = new Date().toLocaleTimeString();
    const lastUpdateEl = document.getElementById('lastUpdate');
    const totalZonesEl = document.getElementById('totalZones');
    const highRiskEl = document.getElementById('highRisk');

    if (lastUpdateEl) lastUpdateEl.textContent = timestampStr;
    if (totalZonesEl) totalZonesEl.textContent = stats.total;
    if (highRiskEl) highRiskEl.textContent = stats.high + stats.severe;

    // Top Metric Cards
    const safeEl = document.getElementById('safeZonesMetric');
    const modEl = document.getElementById('moderateRiskMetric');
    const highEl = document.getElementById('highRiskMetric');
    const sevEl = document.getElementById('severeRiskMetric');

    if (safeEl) safeEl.textContent = stats.safe;
    if (modEl) modEl.textContent = stats.moderate;
    if (highEl) highEl.textContent = stats.high;
    if (sevEl) sevEl.textContent = stats.severe;

    // Progress Bars
    const total = stats.total || 1;
    const barSafe = document.getElementById('distBarSafe');
    const barMod = document.getElementById('distBarModerate');
    const barHigh = document.getElementById('distBarHigh');
    const barCrit = document.getElementById('distBarCritical');

    if (barSafe) barSafe.style.width = `${(stats.safe / total) * 100}%`;
    if (barMod) barMod.style.width = `${(stats.moderate / total) * 100}%`;
    if (barHigh) barHigh.style.width = `${(stats.high / total) * 100}%`;
    if (barCrit) barCrit.style.width = `${(stats.severe / total) * 100}%`;

    const cntSafe = document.getElementById('distCountSafe');
    const cntMod = document.getElementById('distCountModerate');
    const cntHigh = document.getElementById('distCountHigh');
    const cntCrit = document.getElementById('distCountCritical');

    if (cntSafe) cntSafe.textContent = stats.safe;
    if (cntMod) cntMod.textContent = stats.moderate;
    if (cntHigh) cntHigh.textContent = stats.high;
    if (cntCrit) cntCrit.textContent = stats.severe;

    // Status Banner
    const bannerEl = document.getElementById('statusBanner');
    const bannerTitleEl = document.getElementById('statusBannerTitle');
    const bannerMsgEl = document.getElementById('statusBannerMessage');
    const bannerTimeEl = document.getElementById('bannerTimestamp');
    const bannerActionsEl = document.getElementById('statusBannerActions');

    if (bannerTimeEl) bannerTimeEl.textContent = timestampStr;

    const aiIndexEl = document.getElementById('aiCurrentIndexText');
    const aiRecEl = document.getElementById('aiRecommendationText');
    const aiDescEl = document.getElementById('aiInsightDescription');

    if (stats.severe > 0 || stats.high > 0) {
        if (bannerEl) bannerEl.className = "status-banner critical";
        if (bannerTitleEl) bannerTitleEl.textContent = "DISASTER WATCH ACTIVE";
        if (bannerMsgEl) bannerMsgEl.textContent = `High flood risk detected in ${stats.severe + stats.high} monitored sectors.`;
        if (bannerActionsEl) bannerActionsEl.style.display = "flex";

        if (aiIndexEl) { aiIndexEl.textContent = "ELEVATED"; aiIndexEl.className = "text-danger"; }
        if (aiRecEl) { aiRecEl.textContent = "ACTIVE EVACUATION"; aiRecEl.className = "text-danger"; }
        if (aiDescEl) aiDescEl.textContent = `Flood risk elevated in ${stats.severe + stats.high} sectors. Low-elevation coastal regions should prepare for potential evacuation.`;
    } else {
        if (bannerEl) bannerEl.className = "status-banner operational";
        if (bannerTitleEl) bannerTitleEl.textContent = "SYSTEM OPERATIONAL";
        if (bannerMsgEl) bannerMsgEl.textContent = "No severe flood threats detected in monitored zones.";
        if (bannerActionsEl) bannerActionsEl.style.display = "none";

        if (aiIndexEl) { aiIndexEl.textContent = "LOW"; aiIndexEl.className = "text-success"; }
        if (aiRecEl) { aiRecEl.textContent = "MONITOR"; aiRecEl.className = "text-success"; }
        if (aiDescEl) aiDescEl.textContent = "Current weather and elevation metrics indicate normal operational conditions across monitored sectors.";
    }
}

/**
 * Populate Sector Selection Dropdown and Zone Table
 */
function populateSectorsAndTable(features) {
    const sectorSelect = document.getElementById('sectorSelect');
    const tableBody = document.getElementById('monitoredZonesTableBody');

    // Populate sector dropdown
    if (sectorSelect) {
        sectorSelect.innerHTML = '<option value="">-- Choose Monitored Sector --</option>';
        features.forEach(f => {
            const props = f.properties;
            const opt = document.createElement('option');
            opt.value = `${props.latitude},${props.longitude},${props.place_name}`;
            opt.textContent = `${props.place_name} [${props.flood_risk}]`;
            sectorSelect.appendChild(opt);
        });
    }

    // Populate Zone Table (sorted by risk severity)
    if (tableBody) {
        const sorted = [...features].sort((a, b) => {
            const weights = { 'Severe': 4, 'High': 3, 'Moderate': 2, 'Low': 1 };
            return (weights[b.properties.flood_risk] || 1) - (weights[a.properties.flood_risk] || 1);
        });

        tableBody.innerHTML = sorted.map(f => {
            const props = f.properties;
            const scorePercent = (props.flood_risk_score * 100).toFixed(1);
            let badgeClass = 'badge-safe';
            if (props.flood_risk === 'Severe') badgeClass = 'badge-critical';
            else if (props.flood_risk === 'High') badgeClass = 'badge-high';
            else if (props.flood_risk === 'Moderate') badgeClass = 'badge-moderate';

            return `
                <tr>
                    <td><strong>${props.place_name}</strong></td>
                    <td><span class="badge ${badgeClass}">${props.flood_risk}</span></td>
                    <td>${scorePercent}%</td>
                    <td>${props.elevation_m} m</td>
                    <td><a href="javascript:void(0)" onclick="zoomToZone(${props.latitude}, ${props.longitude}, '${props.place_name.replace(/'/g, "\\'")}')" class="view-zone-link">Focus</a></td>
                </tr>
            `;
        }).join('');
    }
}

let currentModelEngine = 'ml';

/**
 * Switch Risk Engine between V3 Machine Learning and V2 Deterministic Baseline
 */
function switchRiskEngine(engine) {
    currentModelEngine = engine;
    const btnML = document.getElementById('btnEngineML');
    const btnDet = document.getElementById('btnEngineDet');
    const badge = document.getElementById('engineBadge');

    if (engine === 'ml') {
        if (btnML) { btnML.className = 'btn btn-primary btn-sm'; }
        if (btnDet) { btnDet.className = 'btn btn-secondary btn-sm'; }
        if (badge) {
            badge.innerText = 'Active: Gradient Boosting v3.0.0';
            badge.style.background = 'rgba(37, 99, 235, 0.1)';
            badge.style.color = '#1D4ED8';
            badge.style.border = '1px solid rgba(37, 99, 235, 0.2)';
        }
    } else {
        if (btnML) { btnML.className = 'btn btn-secondary btn-sm'; }
        if (btnDet) { btnDet.className = 'btn btn-primary btn-sm'; }
        if (badge) {
            badge.innerText = 'Active: V2 Deterministic Multi-Criteria';
            badge.style.background = 'rgba(100, 116, 139, 0.1)';
            badge.style.color = '#475569';
            badge.style.border = '1px solid rgba(100, 116, 139, 0.2)';
        }
    }
    loadGridData(currentModelEngine);
}

/**
 * Load Flood Risk Grids from API (ML Forecast or Deterministic Baseline)
 */
function loadGridData(engine = currentModelEngine) {
    console.log(`Fetching /api/grids?model=${engine}...`);
    fetch(`/api/grids?model=${engine}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return res.json();
        })
        .then(data => {
            floodData = data;
            const features = data.features || [];

            updateSummaryTelemetry(features);
            populateSectorsAndTable(features);

            // Remove existing layer if reloading
            if (geoJsonLayer) {
                map.removeLayer(geoJsonLayer);
            }

            geoJsonLayer = L.geoJSON(data, {
                pointToLayer: function(feature, latlng) {
                    return L.circle(latlng, {
                        radius: 1200,
                        fillColor: getRiskColor(feature.properties.flood_risk),
                        weight: 1,
                        opacity: 0.5,
                        color: '#ffffff',
                        fillOpacity: 0.6
                    });
                },
                onEachFeature: function(feature, layer) {
                    const props = feature.properties;
                    const probDisplay = props.ml_probability !== undefined
                        ? (props.ml_probability * 100).toFixed(1) + '%'
                        : (props.flood_risk_score * 100).toFixed(1) + '%';

                    const popupContent = `
                        <div class="popup-title">${props.place_name}</div>
                        <div class="popup-info">
                            <div><strong>Risk Level:</strong> <span style="color: ${getRiskColor(props.flood_risk)}; font-weight: bold;">${props.flood_risk}</span></div>
                            <div><strong>Flood Probability:</strong> ${probDisplay}</div>
                            <div><strong>Measured Rainfall:</strong> ${props.rainfall_mm} mm</div>
                            <div><strong>Elevation:</strong> ${props.elevation_m} m</div>
                            <div><strong>Distance to Water:</strong> ${(props.distance_to_water / 1000).toFixed(2)} km</div>
                            <hr style="margin: 8px 0; border: none; border-top: 1px solid #CBD5E1;">
                            <button class="btn btn-primary btn-sm" style="width: 100%; margin-top: 4px;" onclick="setUserLocation(${props.latitude}, ${props.longitude}, '${props.place_name.replace(/'/g, "\\'")}')">Select for Evacuation</button>
                            <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 6px; background: #0B5E8E; color: white; border: none;" onclick="openPredictionModal(${props.id}, '${props.place_name.replace(/'/g, "\\'")}')">View Risk Factors</button>
                        </div>
                    `;
                    layer.bindPopup(popupContent);
                }
            }).addTo(map);

            if (features.length > 0 && !window._mapCentered) {
                map.fitBounds(geoJsonLayer.getBounds());
                window._mapCentered = true;
            }
        })
        .catch(err => {
            console.error("Error loading grids:", err);
            const tableBody = document.getElementById('monitoredZonesTableBody');
            if (tableBody) {
                tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #DC2626;">Failed to load risk grid API.</td></tr>`;
            }
        });
}

/**
 * Load All Active Shelters from API
 */
function loadAllShelters() {
    fetch('/api/shelters')
        .then(res => {
            if (!res.ok) throw new Error("Failed to fetch shelters");
            return res.json();
        })
        .then(shelters => {
            allShelterMarkers.forEach(m => map.removeLayer(m));
            allShelterMarkers = [];

            let totalCap = 0;
            let availCap = 0;

            shelters.forEach(s => {
                totalCap += s.capacity || 0;
                availCap += s.availableCapacity || 0;

                const marker = L.marker([s.latitude, s.longitude], {
                    icon: L.divIcon({
                        className: 'shelter-marker',
                        html: '<div style="font-size: 20px;">🏛️</div>',
                        iconSize: [24, 24]
                    })
                }).addTo(map);

                marker.bindPopup(`
                    <div class="popup-title">🏛️ ${s.name}</div>
                    <div class="popup-info">
                        <div><strong>Address:</strong> ${s.address}</div>
                        <div><strong>Available Capacity:</strong> ${s.availableCapacity} / ${s.capacity}</div>
                        <div><strong>Risk Level:</strong> <span style="color: ${getRiskColor(s.riskLevel)}; font-weight: bold;">${s.riskLevel}</span></div>
                        <div><strong>Facilities:</strong> ${s.facilities}</div>
                        <div><strong>Contact:</strong> ${s.contact}</div>
                    </div>
                `);
                allShelterMarkers.push(marker);
            });

            // Update shelter metrics
            const totalSheltersEl = document.getElementById('statTotalShelters');
            const totalCapEl = document.getElementById('statTotalCapacity');
            const availCapEl = document.getElementById('statAvailCapacity');
            const occRateEl = document.getElementById('statOccupancyRate');
            const readSheltersEl = document.getElementById('readinessShelters');

            if (totalSheltersEl) totalSheltersEl.textContent = shelters.length;
            if (totalCapEl) totalCapEl.textContent = totalCap.toLocaleString();
            if (availCapEl) availCapEl.textContent = availCap.toLocaleString();
            if (readSheltersEl) readSheltersEl.textContent = `${shelters.length} Available`;

            if (totalCap > 0 && occRateEl) {
                const occPercent = (((totalCap - availCap) / totalCap) * 100).toFixed(0);
                occRateEl.textContent = `${occPercent}%`;
            }
        })
        .catch(err => {
            console.error("Error loading shelters:", err);
        });
}

/**
 * Load Active Alerts from API
 */
function loadActiveAlerts() {
    const alertsList = document.getElementById('alertsList');
    if (!alertsList) return;

    fetch('/api/alerts')
        .then(res => res.json())
        .then(alerts => {
            if (!alerts || alerts.length === 0) {
                alertsList.innerHTML = '<div class="alert-operational">✓ No active disaster alerts</div>';
                return;
            }

            alertsList.innerHTML = alerts.map(a => {
                const isCrit = a.severity === 'Critical' || a.severity === 'High';
                const borderStyle = isCrit ? 'border-left: 4px solid #DC2626; background: #FEF2F2; color: #991B1B;' : 'border-left: 4px solid #EA580C; background: #FFF7ED; color: #C2410C;';
                return `
                    <div class="alert-item" style="padding: 10px 12px; margin-bottom: 8px; border-radius: 4px; border: 1px solid #CBD5E1; ${borderStyle}">
                        <strong>[${a.severity.toUpperCase()}] ${a.title}</strong>
                        <p style="margin: 4px 0; font-size: 12px;">${a.message}</p>
                        <small style="opacity: 0.8; font-size: 10px;">Sector: ${a.zone} • ${a.timestamp || 'Active'}</small>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            console.error("Failed to load alerts:", err);
            alertsList.innerHTML = '<div class="alert-operational">✓ Operational monitoring</div>';
        });
}

/**
 * Set user location and query nearby shelters
 */
window.setUserLocation = function(lat, lng, name) {
    currentCoords = { latitude: lat, longitude: lng };

    document.getElementById('userLocationText').innerText = `${name}`;

    if (userLocationMarker) {
        map.removeLayer(userLocationMarker);
    }

    userLocationMarker = L.marker([lat, lng], {
        icon: L.divIcon({
            className: 'user-location-marker',
            html: '<div style="background: #0ea5e9; width: 22px; height: 22px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5);"></div>',
            iconSize: [22, 22]
        })
    }).addTo(map);

    userLocationMarker.bindPopup(`<strong>Selected Evacuation Origin:</strong><br>${name}`).openPopup();

    resetRouteDisplay();
    displayNearbyShelters(lat, lng);
};

/**
 * Zoom to specific zone
 */
window.zoomToZone = function(lat, lng, placeName) {
    map.setView([lat, lng], 14, { animate: true });
    setUserLocation(lat, lng, placeName);
};

/**
 * Select Sector from Dropdown
 */
window.selectPresetSector = function(val) {
    if (!val) return;
    const parts = val.split(',');
    const lat = parseFloat(parts[0]);
    const lng = parseFloat(parts[1]);
    const name = parts.slice(2).join(',');
    setUserLocation(lat, lng, name);
};

/**
 * Fetch and display nearby shelters
 */
function displayNearbyShelters(lat, lng) {
    const listEl = document.getElementById('sheltersList');
    if (!listEl) return;

    listEl.innerHTML = '<div class="panel-placeholder">Searching nearby shelters...</div>';

    fetch(`/api/shelters/nearby?lat=${lat}&lng=${lng}&radius=25&limit=4`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to fetch nearby shelters");
            return res.json();
        })
        .then(shelters => {
            if (!shelters || shelters.length === 0) {
                listEl.innerHTML = '<div class="panel-placeholder">No active shelters within 25 km.</div>';
                return;
            }

            listEl.innerHTML = shelters.map((s, idx) => `
                <div class="shelter-item" style="cursor: pointer;" onclick="focusShelter(${s.latitude}, ${s.longitude}, '${s.name.replace(/'/g, "\\'")}')">
                    <div class="title">${idx + 1}. ${s.name}</div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Distance: ${s.distance.toFixed(2)} km</div>
                    <div style="font-size: 12px; color: #64748b;">Capacity: <strong style="color: ${s.availableCapacity > 0 ? '#16A34A' : '#DC2626'};">${s.availableCapacity}</strong> / ${s.capacity} available</div>
                    <div style="font-size: 11px; color: #0B5E8E; margin-top: 3px;">Tel: ${s.contact}</div>
                </div>
            `).join('');
        })
        .catch(err => {
            listEl.innerHTML = '<div class="panel-placeholder text-danger">Error loading nearby shelters.</div>';
        });
}

function focusShelter(lat, lng, name) {
    map.setView([lat, lng], 15, { animate: true });
}

/**
 * Reset Route UI Display
 */
function resetRouteDisplay() {
    document.getElementById('routeDetails').style.display = 'none';
    document.getElementById('startEvacuationBtn').style.display = 'none';
    document.getElementById('recalculateRouteBtn').style.display = 'none';
    document.getElementById('findSafeRouteBtn').style.display = 'block';

    if (activeRoutePolyline) {
        map.removeLayer(activeRoutePolyline);
        activeRoutePolyline = null;
    }
}

/**
 * Find Safest Evacuation Route via Backend API
 */
window.findSafeRoute = function() {
    if (!currentCoords) {
        alert("Please select your location first by clicking on the map, using 'My Location', or picking a Chennai sector.");
        return;
    }

    const btn = document.getElementById('findSafeRouteBtn');
    btn.innerText = "Calculating Safe Route...";
    btn.disabled = true;

    fetch('/api/routes/safe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentCoords)
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(e => { throw new Error(e.error || "Server error"); });
        }
        return res.json();
    })
    .then(data => {
        btn.innerText = "FIND SAFE ROUTE";
        btn.disabled = false;

        currentSelectedShelter = data.shelter;

        // Render route card
        document.getElementById('routeDetails').style.display = 'block';
        document.getElementById('recShelterName').innerText = `🏛️ ${data.shelter.name}`;
        document.getElementById('recDistance').innerText = `${data.route.dist_km} km`;
        document.getElementById('recTime').innerText = `${data.route.duration_mins} mins`;

        const risk = data.shelter.riskLevel;
        document.getElementById('recRisk').innerHTML = `<span style="color: ${getRiskColor(risk)}; font-weight: 700;">${risk}</span>`;

        const safetyScorePercent = Math.round(data.route.safetyScore * 100);
        document.getElementById('recSafety').innerText = `● Safe Path (${safetyScorePercent}%)`;
        document.getElementById('recCapacity').innerText = `${data.shelter.availableCapacity} / ${data.shelter.capacity} Available`;
        document.getElementById('recReason').innerText = `Stance Recommendation: "${data.reason}"`;

        btn.style.display = 'none';
        document.getElementById('startEvacuationBtn').style.display = 'block';
        document.getElementById('recalculateRouteBtn').style.display = 'block';

        // Draw Polyline
        if (activeRoutePolyline) {
            map.removeLayer(activeRoutePolyline);
        }

        const coordinates = data.route.geometry.coordinates.map(coord => [coord[1], coord[0]]);
        activeRoutePolyline = L.featureGroup([
            L.polyline(coordinates, { color: '#1e3a8a', weight: 8, opacity: 0.4, lineCap: 'round', lineJoin: 'round' }),
            L.polyline(coordinates, { color: '#2563eb', weight: 5, opacity: 0.9, lineCap: 'round', lineJoin: 'round' })
        ]).addTo(map);

        map.fitBounds(activeRoutePolyline.getBounds());
    })
    .catch(err => {
        btn.innerText = "FIND SAFE ROUTE";
        btn.disabled = false;
        alert(`Safe route calculation failed: ${err.message}`);
    });
};

/**
 * Start Evacuation and decrement shelter capacity
 */
window.startEvacuation = function() {
    if (!currentSelectedShelter) return;

    const btn = document.getElementById('startEvacuationBtn');
    btn.innerText = "Initiating...";
    btn.disabled = true;

    fetch('/api/evacuation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shelter_id: currentSelectedShelter.id })
    })
    .then(res => {
        if (!res.ok) return res.json().then(e => { throw new Error(e.error || "Server error"); });
        return res.json();
    })
    .then(data => {
        btn.innerText = "START EVACUATION";
        btn.disabled = false;

        currentSelectedShelter = data.shelter;
        document.getElementById('recCapacity').innerText = `${data.shelter.availableCapacity} / ${data.shelter.capacity} Available`;

        // Refresh nearby list
        if (currentCoords) {
            displayNearbyShelters(currentCoords.latitude, currentCoords.longitude);
        }

        alert("Evacuation process confirmed! Follow the designated safe path on the map.\n\n" + data.message);
    })
    .catch(err => {
        btn.innerText = "START EVACUATION";
        btn.disabled = false;
        alert(`Failed to start evacuation: ${err.message}`);
    });
};

/**
 * Recalculate Route
 */
window.recalculateRoute = function() {
    window.findSafeRoute();
};

/**
 * Trigger Operational Intelligence Cycle (Weather + Features + ML + Alerts)
 */
window.triggerOperationalCycle = function() {
    const btn = document.getElementById('syncWeatherBtn');
    if (!btn) return;
    btn.disabled = true;
    btn.innerText = "RUNNING...";

    fetch('/api/operations/run-cycle', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerText = "RUN CYCLE";
            if (data.status === 'skipped') {
                console.warn("Cycle skipped:", data.reason);
            } else if (data.status === 'failed') {
                alert("Cycle error: " + data.error);
            } else {
                console.log("Operational cycle completed in", data.latency_ms, "ms");
            }
            loadGridData(currentModelEngine);
            fetchOperationalStatus();
            loadActiveAlerts();
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerText = "RUN CYCLE";
            alert("Operational cycle failed: " + err.message);
        });
};

// Backward-compatible alias for existing sync button
window.syncWeather = window.triggerOperationalCycle;

/**
 * My Location handler with Geolocation API
 */
document.getElementById('myLocationBtn')?.addEventListener('click', function() {
    const btn = this;
    btn.textContent = '⌛ Locating...';
    btn.disabled = true;

    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        btn.textContent = 'MY LOCATION';
        btn.disabled = false;
        return;
    }

    navigator.geolocation.getCurrentPosition(
        pos => {
            btn.textContent = 'MY LOCATION';
            btn.disabled = false;
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            map.setView([lat, lng], 14);
            setUserLocation(lat, lng, `GPS Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
        },
        err => {
            btn.textContent = 'MY LOCATION';
            btn.disabled = false;
            alert(`Unable to retrieve GPS location: ${err.message}`);
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
});

// Search input handling
const searchInput = document.getElementById('locationSearch');
const searchResults = document.getElementById('searchResults');

if (searchInput && searchResults) {
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        if (query.length < 2 || !floodData) {
            searchResults.classList.remove('active');
            searchResults.innerHTML = '';
            return;
        }

        const matches = (floodData.features || []).filter(f =>
            f.properties.place_name.toLowerCase().includes(query)
        );

        if (matches.length > 0) {
            searchResults.innerHTML = matches.map(f => `
                <div class="search-result-item" onclick="zoomToZone(${f.properties.latitude}, ${f.properties.longitude}, '${f.properties.place_name.replace(/'/g, "\\'")}')">
                    ${f.properties.place_name} [${f.properties.flood_risk}]
                </div>
            `).join('');
            searchResults.classList.add('active');
        } else {
            searchResults.innerHTML = '<div class="search-result-item">No matching sectors found</div>';
            searchResults.classList.add('active');
        }
    });

    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.remove('active');
        }
    });
}

/**
 * Fetch and display live operational status indicators
 */
function fetchOperationalStatus() {
    fetch('/api/operations/status')
        .then(res => res.json())
        .then(data => {
            const weatherDot = document.getElementById('v4WeatherDot');
            const weatherText = document.getElementById('v4WeatherText');
            const engineDot = document.getElementById('v4EngineDot');
            const engineText = document.getElementById('v4EngineText');
            const lastUpdateEl = document.getElementById('lastUpdate');
            const highRiskEl = document.getElementById('highRisk');

            if (weatherDot && weatherText) {
                if (data.weather_status === 'healthy') {
                    weatherDot.className = 'v4-status-dot v4-dot-live';
                    weatherText.innerText = 'Live';
                } else if (data.weather_status === 'degraded') {
                    weatherDot.className = 'v4-status-dot v4-dot-degraded';
                    weatherText.innerText = 'Degraded';
                } else {
                    weatherDot.className = 'v4-status-dot v4-dot-unavailable';
                    weatherText.innerText = 'Offline';
                }
            }

            if (engineDot && engineText) {
                if (data.fallback_active) {
                    engineDot.className = 'v4-status-dot v4-dot-degraded';
                    engineText.innerText = 'Fallback (Det)';
                } else {
                    engineDot.className = 'v4-status-dot v4-dot-live';
                    engineText.innerText = 'V3 ML';
                }
            }

            if (lastUpdateEl && data.last_prediction_run) {
                try {
                    const dt = new Date(data.last_prediction_run);
                    lastUpdateEl.innerText = dt.toLocaleTimeString();
                } catch(e) {}
            }

            if (highRiskEl && data.high_risk_grids !== undefined) {
                highRiskEl.innerText = data.high_risk_grids;
            }
        })
        .catch(err => {
            console.debug("Failed to fetch operational status:", err);
        });
}

/**
 * Fetch and render active emergency advisories in the V4 alerts panel
 */
function loadActiveAlerts() {
    fetch('/api/alerts/active')
        .then(res => res.json())
        .then(alerts => {
            const listEl = document.getElementById('v4AlertsList');
            const badgeEl = document.getElementById('v4AlertCountBadge');
            if (!listEl) return;

            if (!alerts || alerts.length === 0) {
                if (badgeEl) badgeEl.style.display = 'none';
                listEl.innerHTML = `
                    <div class="v4-no-alerts">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        <span>No critical or warning advisories active. Operational flood monitoring active.</span>
                    </div>
                `;
                return;
            }

            if (badgeEl) {
                badgeEl.innerText = alerts.length;
                badgeEl.style.display = 'inline-block';
            }

            listEl.innerHTML = alerts.map(a => {
                const sevClass = (a.severity || 'low').toLowerCase();
                const prob = a.probability ? ` | Risk Prob: ${(a.probability * 100).toFixed(1)}%` : '';
                const timeStr = a.timestamp || a.created_at || '';
                return `
                    <div class="v4-alert-card ${sevClass}">
                        <div class="v4-alert-info">
                            <div class="v4-alert-top">
                                <span class="badge badge-${sevClass === 'critical' ? 'critical' : sevClass === 'warning' || sevClass === 'high' ? 'high' : sevClass === 'moderate' ? 'moderate' : 'safe'}">${a.severity.toUpperCase()}</span>
                                <span class="v4-alert-zone">${a.zone || a.title}</span>
                            </div>
                            <p class="v4-alert-msg">${a.message}</p>
                            <div class="v4-alert-meta">
                                <span>${prob.replace(/^ \| /, '')}</span>
                                <span>Issued: ${timeStr}</span>
                            </div>
                        </div>
                        <div class="v4-alert-status-badge">
                            <span class="v4-advisory-pill">LIVE ADVISORY</span>
                        </div>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            console.debug("Failed to fetch active alerts:", err);
        });
}

/**
 * Acknowledge an active alert
 */
window.acknowledgeAlert = function(alertId) {
    fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            loadActiveAlerts();
            fetchOperationalStatus();
        })
        .catch(err => {
            alert("Failed to acknowledge alert: " + err.message);
        });
};

// ========================================================
// V5 PREDICTIVE INTELLIGENCE & DECISION SUPPORT CONTROLLER
// ========================================================
let currentHorizon = 'nowcast';

/**
 * Switch Prediction Horizon (nowcast, 6h, 12h, 24h)
 */
window.switchHorizon = function(horizon) {
    currentHorizon = horizon;
    
    // Update button states
    ['nowcast', '6h', '12h', '24h'].forEach(h => {
        const btnId = 'btnHorizon' + (h === 'nowcast' ? 'Nowcast' : h.toUpperCase());
        const btn = document.getElementById(btnId);
        if (btn) {
            if (h === horizon) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });

    const badge = document.getElementById('horizonBadge');
    if (badge) {
        badge.innerText = `Horizon: ${horizon.toUpperCase()}`;
    }

    loadV5Forecast(horizon);
};

/**
 * Load V5 Forecast for specified horizon
 */
function loadV5Forecast(horizon = currentHorizon) {
    fetch(`/api/predictions/forecast?horizon=${horizon}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            return res.json();
        })
        .then(data => {
            const predictions = data.predictions || [];
            if (!predictions.length) return;

            const predMap = {};
            let critCount = 0;
            let highCount = 0;
            let modCount = 0;
            let safeCount = 0;
            let sumConf = 0;

            predictions.forEach(p => {
                predMap[p.grid_id] = p;
                const risk = p.risk_level || p.prediction || 'Low';
                if (risk === 'Severe' || risk === 'Critical') critCount++;
                else if (risk === 'High') highCount++;
                else if (risk === 'Moderate') modCount++;
                else safeCount++;
                sumConf += (p.confidence !== undefined ? p.confidence : 0.85);
            });

            // Update KPI cards
            const critEl = document.getElementById('severeRiskMetric');
            const highEl = document.getElementById('highRiskMetric');
            const modEl = document.getElementById('moderateRiskMetric');
            const safeEl = document.getElementById('safeZonesMetric');
            const confEl = document.getElementById('confidenceMetric');
            const confSub = document.getElementById('confidenceCategorySub');

            if (critEl) critEl.innerText = critCount;
            if (highEl) highEl.innerText = highCount;
            if (modEl) modEl.innerText = modCount;
            if (safeEl) safeEl.innerText = safeCount;
            if (confEl && predictions.length > 0) {
                const avgConf = (sumConf / predictions.length * 100).toFixed(0);
                confEl.innerText = `${avgConf}%`;
                if (confSub) {
                    confSub.innerText = avgConf >= 75 ? 'High Confidence' : avgConf >= 55 ? 'Moderate Confidence' : 'Low Confidence';
                }
            }

            // Update Map Layer colors based on forecasted risk levels
            if (geoJsonLayer) {
                geoJsonLayer.eachLayer(layer => {
                    const f = layer.feature;
                    if (!f || !f.properties) return;
                    const p = predMap[f.properties.id];
                    if (p) {
                        const newRisk = p.risk_level || p.prediction || 'Low';
                        layer.setStyle({
                            fillColor: getRiskColor(newRisk)
                        });
                        const prob = p.probability !== undefined ? p.probability : 0;
                        const probPct = (prob * 100).toFixed(1);
                        const confVal = p.confidence !== undefined ? p.confidence : 0.85;
                        const confCat = p.confidence_category || (confVal >= 0.75 ? 'High' : 'Moderate');
                        layer.setPopupContent(`
                            <div class="popup-title">${f.properties.place_name}</div>
                            <div class="popup-info">
                                <div><strong>Forecast Horizon:</strong> <span style="font-weight: bold; color: #0284C7;">${horizon.toUpperCase()}</span></div>
                                <div><strong>Risk Level:</strong> <span style="color: ${getRiskColor(newRisk)}; font-weight: bold;">${newRisk}</span></div>
                                <div><strong>Flood Probability:</strong> ${probPct}%</div>
                                <div><strong>Confidence:</strong> ${(confVal * 100).toFixed(0)}% (${confCat})</div>
                                <div><strong>Elevation:</strong> ${f.properties.elevation_m} m</div>
                                <hr style="margin: 8px 0; border: none; border-top: 1px solid #CBD5E1;">
                                <button class="btn btn-primary btn-sm" style="width: 100%; margin-top: 4px;" onclick="setUserLocation(${f.properties.latitude}, ${f.properties.longitude}, '${f.properties.place_name.replace(/'/g, "\\'")}')">Select for Evacuation</button>
                                <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 6px; background: #0B5E8E; color: white; border: none;" onclick="openPredictionModal(${f.properties.id}, '${f.properties.place_name.replace(/'/g, "\\'")}')">View Risk Factors</button>
                            </div>
                        `);
                    }
                });
            }
        })
        .catch(err => {
            console.warn("Could not load horizon forecast:", err);
        });
}

/**
 * Load Prioritized Sector Triage from API
 */
function loadZonePriorities() {
    fetch('/api/priorities')
        .then(res => res.json())
        .then(priorities => {
            const tbody = document.getElementById('v5PriorityTableBody');
            const detMetric = document.getElementById('deterioratingMetric');

            if (!priorities || !priorities.length) {
                if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#64748B;">No zone priorities calculated.</td></tr>';
                return;
            }

            let detCount = 0;
            priorities.forEach(p => {
                if (p.trend_classification === 'DETERIORATING' || p.trend_classification === 'SUDDEN_DETERIORATION') {
                    detCount++;
                }
            });
            if (detMetric) detMetric.innerText = detCount;

            if (tbody) {
                tbody.innerHTML = priorities.map((p, idx) => {
                    const catClass = (p.priority_category || 'low').toLowerCase();
                    const trendClass = (p.trend_classification || 'stable').toLowerCase();
                    const confPct = ((p.model_confidence || 0.85) * 100).toFixed(0);
                    const probPct = ((p.flood_probability || 0) * 100).toFixed(1);

                    return `
                        <tr>
                            <td><span class="v5-prio-badge v5-prio-${catClass}">#${p.priority_rank || idx+1} ${p.priority_category}</span></td>
                            <td><strong>${p.place_name}</strong></td>
                            <td><span class="badge ${p.flood_probability > 0.6 ? 'badge-critical' : p.flood_probability > 0.3 ? 'badge-high' : 'badge-safe'}">${p.flood_probability > 0.6 ? 'Severe' : p.flood_probability > 0.3 ? 'High' : 'Low'}</span></td>
                            <td><strong>${(p.priority_score * 100).toFixed(0)}</strong>/100 <span style="font-size:10px; color:#64748B;">(Prob: ${probPct}%)</span></td>
                            <td><span class="v5-trend-badge v5-trend-${trendClass}">${p.trend_classification || 'STABLE'}</span></td>
                            <td><span class="v5-conf-badge v5-conf-high">${confPct}%</span></td>
                            <td><button class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size: 11px;" onclick="openPredictionModal(${p.grid_id}, '${p.place_name.replace(/'/g, "\\'")}')">Inspect</button></td>
                        </tr>
                    `;
                }).join('');
            }
        })
        .catch(err => {
            console.debug("Could not fetch zone priorities:", err);
        });
}

/**
 * Load Operational Timeline from API
 */
function loadOperationalTimeline() {
    fetch('/api/operations/timeline?limit=8')
        .then(res => res.json())
        .then(events => {
            const container = document.getElementById('v5TimelineList');
            if (!container) return;

            if (!events || !events.length) {
                container.innerHTML = '<div style="text-align: center; color: #64748B; font-size: 12px; padding: 12px;">No recent operational events logged.</div>';
                return;
            }

            container.innerHTML = events.map(ev => {
                const timeStr = ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : 'Just now';
                const sevBadge = ev.severity ? `<span style="font-size:9px; padding:1px 4px; border-radius:3px; font-weight:700; background:#FEE2E2; color:#DC2626;">${ev.severity}</span>` : '';
                return `
                    <div class="v5-timeline-item">
                        <div class="v5-timeline-top">
                            <span class="v5-timeline-type">${ev.event_type.replace('_', ' ')}</span>
                            <div>${sevBadge} <span class="v5-timeline-time">${timeStr}</span></div>
                        </div>
                        <div style="font-size: 11px; font-weight: 700; color: #1E293B;">${ev.title}</div>
                        <div class="v5-timeline-msg">${ev.description}</div>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            console.debug("Could not load timeline:", err);
        });
}

/**
 * Load Shelter Intelligence Telemetry
 */
function loadShelterIntelligence() {
    fetch('/api/shelters/intelligence')
        .then(res => res.json())
        .then(shelters => {
            if (!shelters || !shelters.length) return;
            let totalAvail = 0;
            shelters.forEach(s => {
                totalAvail += (s.available_capacity || 0);
            });
            const capMetric = document.getElementById('shelterCapacityMetric');
            if (capMetric) {
                capMetric.innerText = totalAvail.toLocaleString();
            }
        })
        .catch(err => {
            console.debug("Could not fetch shelter intelligence:", err);
        });
}

/**
 * Open V5 Prediction Detail & Explainability Modal
 */
window.openPredictionModal = function(gridId, placeName) {
    const modal = document.getElementById('v5PredictionModal');
    if (!modal) return;

    document.getElementById('v5ModalSectorName').innerText = `${placeName} — Predictive Risk Intelligence`;
    document.getElementById('v5ModalHorizon').innerText = currentHorizon.toUpperCase();
    modal.style.display = 'flex';

    // Fetch Horizon Prediction Detail
    fetch(`/api/predictions/forecast?horizon=${currentHorizon}&grid_id=${gridId}`)
        .then(res => res.json())
        .then(data => {
            const pred = (data.predictions && data.predictions[0]) ? data.predictions[0] : null;
            if (!pred) return;

            const probVal = pred.probability !== undefined ? pred.probability : (pred.predicted_flood_probability || 0);
            const probPct = (probVal * 100).toFixed(1) + '%';
            document.getElementById('v5ModalProb').innerText = probPct;
            document.getElementById('v5ModalProb').style.color = probVal > 0.6 ? '#DC2626' : probVal > 0.3 ? '#EA580C' : '#16A34A';

            const trendClass = (pred.trend_classification || 'stable').toLowerCase();
            document.getElementById('v5ModalTrend').innerHTML = `<span class="v5-trend-badge v5-trend-${trendClass}">${pred.trend_classification || 'STABLE'}</span>`;

            const confCat = (pred.confidence_category || 'High confidence');
            const confVal = pred.confidence !== undefined ? pred.confidence : (pred.model_confidence || 0.85);
            const confPct = (confVal * 100).toFixed(0);
            document.getElementById('v5ModalConfidence').innerHTML = `<span class="v5-conf-badge v5-conf-high">${confCat} (${confPct}%)</span>`;

            document.getElementById('v5ConfMargin').innerText = ((pred.confidence_margin || 0.7) * 100).toFixed(0) + '%';
            document.getElementById('v5ConfComplete').innerText = ((pred.feature_completeness || 1.0) * 100).toFixed(0) + '%';
            document.getElementById('v5ConfFresh').innerText = ((pred.telemetry_freshness || 1.0) * 100).toFixed(0) + '%';

            // Feature Breakdown
            const tbody = document.getElementById('v5ModalFeatureTableBody');
            if (tbody) {
                const feats = pred.contributing_features || (pred.feature_attributions ? Object.entries(pred.feature_attributions).map(([k, v]) => ({ name: k.replace(/_/g, ' ').toUpperCase(), ...v })) : []);
                if (feats.length > 0) {
                    tbody.innerHTML = feats.map(item => {
                        const name = item.name || (item.feature ? item.feature.replace(/_/g, ' ').toUpperCase() : 'Feature');
                        const val = item.value !== null && item.value !== undefined ? item.value : 'N/A';
                        const weight = item.relative_importance !== undefined ? item.relative_importance : (item.weight || 0);
                        const weightSign = (typeof weight === 'number') ? (weight >= 0 ? `+${weight.toFixed(3)}` : weight.toFixed(3)) : weight;
                        const dir = item.direction || 'Normal';
                        const dirClass = dir.toLowerCase().includes('hazard') ? 'v5-dir-hazard' : dir.toLowerCase().includes('protective') ? 'v5-dir-protective' : 'v5-dir-moderate';
                        return `
                            <tr>
                                <td><strong>${name}</strong></td>
                                <td>${val}</td>
                                <td><code>${weightSign}</code></td>
                                <td class="${dirClass}">● ${dir}</td>
                            </tr>
                        `;
                    }).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #64748B;">Baseline parameters nominal.</td></tr>';
                }
            }

            if (pred.actionable_recommendation) {
                document.getElementById('v5ModalAdvisoryAction').innerHTML = `<strong>OPERATIONAL RECOMMENDATION:</strong> ${pred.actionable_recommendation}`;
            }
        })
        .catch(err => {
            console.error("Error loading forecast detail:", err);
        });

    // Fetch Temporal Trend & Cycle-over-Cycle Deltas
    fetch(`/api/risk/trends/${gridId}`)
        .then(res => res.json())
        .then(trend => {
            const deltaEl = document.getElementById('v5ModalDeltaContent');
            if (!deltaEl) return;

            const deltaProb = trend.delta_probability !== undefined ? (trend.delta_probability > 0 ? `+${(trend.delta_probability * 100).toFixed(1)}%` : `${(trend.delta_probability * 100).toFixed(1)}%`) : '0.0%';
            deltaEl.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center;">
                    <div style="background: white; padding: 6px; border-radius: 4px; border: 1px solid #E2E8F0;">
                        <span style="font-size: 10px; color: #64748B;">Cycle Delta:</span>
                        <div style="font-weight: 700; color: ${trend.delta_probability > 0 ? '#DC2626' : '#16A34A'};">${deltaProb}</div>
                    </div>
                    <div style="background: white; padding: 6px; border-radius: 4px; border: 1px solid #E2E8F0;">
                        <span style="font-size: 10px; color: #64748B;">Previous Level:</span>
                        <div style="font-weight: 700; color: #334155;">${trend.previous_risk_level || 'Low'}</div>
                    </div>
                    <div style="background: white; padding: 6px; border-radius: 4px; border: 1px solid #E2E8F0;">
                        <span style="font-size: 10px; color: #64748B;">Classification:</span>
                        <div style="font-weight: 700; color: #2563EB;">${trend.classification || 'STABLE'}</div>
                    </div>
                </div>
            `;
        })
        .catch(err => {
            console.debug("Error fetching trend delta:", err);
        });
};

/**
 * Close V5 Prediction Detail Modal
 */
window.closePredictionModal = function() {
    const modal = document.getElementById('v5PredictionModal');
    if (modal) modal.style.display = 'none';
};

// Initial Data Load and Background Auto-Refresh Setup
document.addEventListener('DOMContentLoaded', () => {
    loadGridData();
    loadAllShelters();
    loadShelterIntelligence();
    loadActiveAlerts();
    fetchOperationalStatus();
    loadZonePriorities();
    loadOperationalTimeline();

    // Auto-refresh operational data every 15 seconds without full page reload
    setInterval(() => {
        fetchOperationalStatus();
        loadActiveAlerts();
        loadGridData(currentModelEngine);
        loadShelterIntelligence();
        loadZonePriorities();
        loadOperationalTimeline();
    }, 15000);
});
