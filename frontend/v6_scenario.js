/**
 * GeoGuard V6 — Scenario Lab & Resilience Intelligence Module
 *
 * Provides interactive flood scenario simulation, spatial risk propagation,
 * shelter capacity stress testing, adaptive evacuation routes, and resilience monitoring.
 */

const V6_STATE = {
    simulationMode: false,
    comparisonMode: false,
    activeScenario: null,
    scenarioResults: null,
    rainfallMultiplier: 1.5,
    horizon: '6h',
    demandFactor: 1.25,
    baselineSectors: null,
    simulatedSectors: null,
};

// Preset Multiplier Mapping
function onPresetSelect(preset) {
    const slider = document.getElementById('v6RainMultiplier');
    const valSpan = document.getElementById('v6MultiplierValue');
    let mult = 1.5;

    if (preset === 'current') mult = 1.0;
    else if (preset === 'plus25') mult = 1.25;
    else if (preset === 'plus50') mult = 1.5;
    else if (preset === 'plus75') mult = 1.75;
    else if (preset === 'plus100') mult = 2.0;

    V6_STATE.rainfallMultiplier = mult;
    if (slider) slider.value = mult;
    if (valSpan) valSpan.textContent = mult.toFixed(2) + 'x';
}

function onMultiplierSliderChange(val) {
    const mult = parseFloat(val);
    V6_STATE.rainfallMultiplier = mult;
    const valSpan = document.getElementById('v6MultiplierValue');
    if (valSpan) valSpan.textContent = mult.toFixed(2) + 'x';
    const presetSelect = document.getElementById('v6ScenarioPreset');
    if (presetSelect) presetSelect.value = 'custom';
}

function selectV6Horizon(horizon) {
    V6_STATE.horizon = horizon;
    document.querySelectorAll('.v6-horizon-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.horizon === horizon);
    });
}

function selectV6Demand(factor) {
    V6_STATE.demandFactor = parseFloat(factor);
    document.querySelectorAll('.v6-demand-btn').forEach(btn => {
        btn.classList.toggle('active', parseFloat(btn.dataset.demand) === V6_STATE.demandFactor);
    });
}

function toggleScenarioLab() {
    const lab = document.getElementById('v6ScenarioLabPanel');
    const btn = document.getElementById('btnToggleScenarioLab');
    if (!lab) return;

    const isHidden = lab.style.display === 'none' || !lab.style.display;
    lab.style.display = isHidden ? 'block' : 'none';
    if (btn) {
        btn.classList.toggle('active', isHidden);
        btn.style.backgroundColor = isHidden ? '#7C3AED' : '#4F46E5';
    }
}

// Execute Scenario Simulation
async function runV6Simulation() {
    const runBtn = document.getElementById('v6RunSimBtn');
    const originalText = runBtn ? runBtn.innerHTML : 'RUN SIMULATION';
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = `
            <svg class="animate-spin" style="width:16px;height:16px;display:inline-block;vertical-align:middle;animation:spin 1s linear infinite;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" style="opacity:0.25;"></circle>
                <path fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" style="opacity:0.75;"></path>
            </svg> Simulating Stress Scenario...
        `;
    }

    const payload = {
        name: `Simulation Stress (${V6_STATE.rainfallMultiplier}x, ${V6_STATE.horizon})`,
        rainfall_multiplier: V6_STATE.rainfallMultiplier,
        horizon: V6_STATE.horizon,
        simulation_demand_factor: V6_STATE.demandFactor,
        description: `Simulating ${V6_STATE.rainfallMultiplier}x precipitation surge across ${V6_STATE.horizon} forecast horizon`,
        operator: 'Command Center Operator',
    };

    try {
        const resp = await fetch('/api/v6/scenarios/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Simulation execution failed');
        }

        const data = await resp.json();
        V6_STATE.activeScenario = data.scenario;
        V6_STATE.scenarioResults = data;
        V6_STATE.simulationMode = true;

        // Render results
        renderSimulationResults(data);
        renderSimulationMap(data.sectors);
        renderShelterStress(data.shelters);
        renderRouteResilience(data.routes);
        renderResilienceBreakdown(data.resilience);
        loadDecisionLog();

        // Reveal simulation mode banner
        showSimulationModeBanner(data.scenario);

    } catch (error) {
        console.error('Simulation error:', error);
        alert(`Scenario Simulation Failed: ${error.message}`);
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = originalText;
        }
    }
}

// Render Results onto Dashboard
function renderSimulationResults(data) {
    const scen = data.scenario;
    const resultsPanel = document.getElementById('v6ResultsContainer');
    if (resultsPanel) resultsPanel.style.display = 'block';

    // Update KPI summary cards
    const setElem = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setElem('v6KpiTransitioned', scen.sectors_deteriorated + scen.sectors_improved);
    setElem('v6KpiCritical', scen.sectors_critical);
    setElem('v6KpiHighRisk', scen.sectors_high);
    setElem('v6KpiOverloadedShelters', scen.shelters_overloaded);
    setElem('v6KpiUnsafeRoutes', scen.routes_unsafe + scen.routes_blocked);
    setElem('v6KpiResilience', scen.resilience.overall + '/100');

    // Render Sector Table
    const tbody = document.getElementById('v6SectorResultsTbody');
    if (tbody && data.sectors) {
        tbody.innerHTML = '';
        data.sectors.forEach(sec => {
            const tr = document.createElement('tr');
            const deltaClass = sec.probability_delta > 0 ? 'text-critical' : (sec.probability_delta < 0 ? 'text-success' : '');
            const deltaSign = sec.probability_delta > 0 ? '+' : '';
            const propColor = sec.spatial_propagation_type === 'DIRECT' ? '#DC2626' : (sec.spatial_propagation_type === 'NEIGHBOR' ? '#F59E0B' : '#6B7280');

            tr.innerHTML = `
                <td style="font-weight:600;">${sec.grid_name}</td>
                <td><span class="v6-badge v6-badge-${sec.baseline_risk.toLowerCase()}">${sec.baseline_risk}</span></td>
                <td><span class="v6-badge v6-badge-${sec.simulated_risk.toLowerCase()}">${sec.simulated_risk}</span></td>
                <td class="${deltaClass}" style="font-weight:700;">${deltaSign}${(sec.probability_delta * 100).toFixed(1)}%</td>
                <td><span style="font-size:11px;font-weight:700;color:${propColor};">${sec.spatial_propagation_type}</span></td>
                <td><span class="v6-priority-pill v6-p-${sec.priority_category.toLowerCase()}">${sec.priority_category}</span></td>
            `;
            tbody.appendChild(tr);
        });
    }
}

// Render Shelter Capacity Stress
function renderShelterStress(shelters) {
    const container = document.getElementById('v6ShelterStressGrid');
    if (!container || !shelters) return;
    container.innerHTML = '';

    shelters.forEach(sh => {
        const card = document.createElement('div');
        card.className = `v6-shelter-card v6-stress-${sh.stress_status.toLowerCase()}`;
        const pctOccupied = Math.min(100, Math.round((sh.simulated_demand / Math.max(1, sh.total_capacity)) * 100));

        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                <strong style="font-size:13px;color:#0F172A;">${sh.shelter_name}</strong>
                <span class="v6-status-badge v6-status-${sh.stress_status.toLowerCase()}">${sh.stress_status}</span>
            </div>
            <div style="font-size:11px;color:#64748B;margin-bottom:8px;">
                Surrounding Risk: <strong>${sh.surrounding_flood_risk}</strong> | Suitability: <strong>${sh.suitability_score}</strong>
            </div>
            <div class="v6-capacity-bar-bg">
                <div class="v6-capacity-bar-fill v6-fill-${sh.stress_status.toLowerCase()}" style="width:${pctOccupied}%;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-top:4px;">
                <span>Demand: <strong>${sh.simulated_demand}</strong></span>
                <span>Remaining: <strong>${sh.remaining_simulated_capacity}</strong></span>
            </div>
            ${sh.alternative_shelter_name ? `
                <div style="margin-top:6px;font-size:10px;padding:4px 8px;background:#F1F5F9;border-radius:4px;color:#334155;">
                    Backup: <strong>${sh.alternative_shelter_name}</strong>
                </div>
            ` : ''}
        `;
        container.appendChild(card);
    });
}

// Render Route Resilience & Alternatives
function renderRouteResilience(routes) {
    const container = document.getElementById('v6RouteResilienceList');
    if (!container || !routes) return;
    container.innerHTML = '';

    if (routes.length === 0) {
        container.innerHTML = '<div style="padding:16px;text-align:center;color:#64748B;">No critical evacuation routes require re-routing under this scenario.</div>';
        return;
    }

    routes.forEach(r => {
        const item = document.createElement('div');
        item.className = `v6-route-item v6-route-${r.route_status.toLowerCase()}`;
        const statusColors = {
            'AVAILABLE': '#10B981',
            'CAUTION': '#F59E0B',
            'UNSAFE': '#EF4444',
            'BLOCKED_BY_SIMULATION': '#7C3AED',
        };

        item.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div>
                    <strong style="font-size:13px;color:#0F172A;">${r.origin_grid_name || 'Zone'} &rarr; ${r.destination_shelter_name || 'Shelter'}</strong>
                    <span style="font-size:10px;font-weight:700;color:#64748B;margin-left:6px;text-transform:uppercase;">[${r.route_role}]</span>
                </div>
                <span class="v6-status-badge" style="background:${statusColors[r.route_status] || '#64748B'};color:#FFF;">${r.route_status}</span>
            </div>
            <div style="display:flex;gap:16px;font-size:11px;color:#475569;margin-bottom:6px;">
                <span>Distance: <strong>${r.distance_km} km</strong></span>
                <span>Travel Time: <strong>${r.duration_min} min</strong></span>
                <span>Peak Hazard: <strong>${r.simulated_peak_risk}</strong></span>
                <span>Hazard Exposure: <strong>${r.high_risk_exposure_pct}%</strong></span>
            </div>
            <div style="font-size:11px;color:#334155;background:#F8FAFC;padding:6px 10px;border-radius:4px;border-left:3px solid ${statusColors[r.route_status] || '#64748B'};">
                ${r.advisory_message}
            </div>
        `;
        container.appendChild(item);
    });
}

// Render 5-Component Resilience Breakdown
function renderResilienceBreakdown(resilience) {
    if (!resilience) return;
    const scores = resilience.subscores || {};
    const setScore = (id, val) => {
        const el = document.getElementById(id);
        const bar = document.getElementById(id + 'Bar');
        if (el) el.textContent = val + '/100';
        if (bar) bar.style.width = Math.min(100, Math.max(0, val)) + '%';
    };

    setScore('v6ResShelter', scores.shelter || 0);
    setScore('v6ResRoute', scores.route || 0);
    setScore('v6ResData', scores.data || 0);
    setScore('v6ResModel', scores.model || 0);
    setScore('v6ResOps', scores.operational || 0);

    const overall = document.getElementById('v6ResOverallScore');
    const cat = document.getElementById('v6ResOverallCategory');
    if (overall) overall.textContent = resilience.overall_resilience_score;
    if (cat) cat.textContent = resilience.category || 'Robust';
}

// Update Map with Simulated Sectors
function renderSimulationMap(sectors) {
    if (!sectors || !window.map || !window.floodLayer) return;
    const colorMap = {
        'Low': '#10b981',
        'Moderate': '#f59e0b',
        'High': '#f97316',
        'Severe': '#ef4444',
    };

    const simLookup = {};
    sectors.forEach(s => {
        simLookup[s.grid_id] = s;
    });

    window.floodLayer.eachLayer(layer => {
        const gid = layer.feature && layer.feature.properties ? layer.feature.properties.id : null;
        if (gid && simLookup[gid]) {
            const sim = simLookup[gid];
            layer.setStyle({
                fillColor: colorMap[sim.simulated_risk] || '#6B7280',
                fillOpacity: 0.75,
                color: sim.spatial_propagation_type === 'DIRECT' ? '#DC2626' : (sim.spatial_propagation_type === 'NEIGHBOR' ? '#F59E0B' : '#FFFFFF'),
                weight: sim.spatial_propagation_type !== 'UNAFFECTED' ? 3 : 1,
            });

            // Update popup
            layer.bindPopup(`
                <div style="font-family:sans-serif;min-width:200px;">
                    <div style="font-weight:700;font-size:13px;color:#1E293B;margin-bottom:4px;">${sim.grid_name}</div>
                    <div style="font-size:11px;color:#EF4444;font-weight:700;margin-bottom:6px;">SIMULATED SCENARIO</div>
                    <table style="width:100%;font-size:11px;border-collapse:collapse;">
                        <tr><td style="color:#64748B;">Baseline:</td><td><strong>${sim.baseline_risk} (${(sim.baseline_probability * 100).toFixed(1)}%)</strong></td></tr>
                        <tr><td style="color:#64748B;">Simulated:</td><td><strong>${sim.simulated_risk} (${(sim.simulated_probability * 100).toFixed(1)}%)</strong></td></tr>
                        <tr><td style="color:#64748B;">Change:</td><td><strong style="color:${sim.probability_delta > 0 ? '#DC2626' : '#10B981'};">${(sim.probability_delta * 100).toFixed(1)}%</strong></td></tr>
                        <tr><td style="color:#64748B;">Propagation:</td><td><strong>${sim.spatial_propagation_type}</strong></td></tr>
                        <tr><td style="color:#64748B;">Priority:</td><td><strong>${sim.priority_category} (Rank #${sim.priority_rank})</strong></td></tr>
                    </table>
                </div>
            `);
        }
    });
}

// Simulation Mode Banner
function showSimulationModeBanner(scen) {
    let banner = document.getElementById('v6SimModeBanner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'v6SimModeBanner';
        banner.className = 'v6-sim-banner';
        const header = document.querySelector('.header');
        if (header && header.parentNode) {
            header.parentNode.insertBefore(banner, header.nextSibling);
        }
    }

    banner.style.display = 'flex';
    banner.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <span class="v6-pulse-dot"></span>
            <strong style="color:#F59E0B;letter-spacing:0.5px;">SIMULATION MODE ACTIVE:</strong>
            <span style="color:#E2E8F0;font-size:12px;">${scen.name} (${scen.rainfall_multiplier}x precipitation, ${scen.horizon} horizon)</span>
            <span style="background:rgba(239,68,68,0.2);color:#FCA5A5;border:1px solid rgba(239,68,68,0.4);padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;">
                SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA
            </span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <button class="btn btn-sm btn-secondary" onclick="toggleBaselineComparison()" style="padding:3px 10px;font-size:11px;">
                ${V6_STATE.comparisonMode ? 'View Simulated' : 'Compare Baseline'}
            </button>
            <button class="btn btn-sm btn-danger" onclick="resetToLiveMonitoring()" style="padding:3px 10px;font-size:11px;">
                Exit Simulation
            </button>
        </div>
    `;
}

// Toggle Baseline vs Scenario Comparison
function toggleBaselineComparison() {
    V6_STATE.comparisonMode = !V6_STATE.comparisonMode;
    const btn = document.querySelector('#v6SimModeBanner button');
    if (btn) btn.textContent = V6_STATE.comparisonMode ? 'View Simulated' : 'Compare Baseline';

    if (V6_STATE.comparisonMode) {
        // Render baseline on map
        if (window.floodData && window.floodLayer) {
            const colorMap = {
                'Low': '#10b981',
                'Moderate': '#f59e0b',
                'High': '#f97316',
                'Severe': '#ef4444',
            };
            window.floodLayer.eachLayer(layer => {
                const risk = layer.feature && layer.feature.properties ? layer.feature.properties.flood_risk : 'Low';
                layer.setStyle({
                    fillColor: colorMap[risk] || '#6B7280',
                    fillOpacity: 0.65,
                    color: '#FFFFFF',
                    weight: 1,
                });
            });
        }
    } else if (V6_STATE.scenarioResults) {
        renderSimulationMap(V6_STATE.scenarioResults.sectors);
    }
}

// Reset Back to Live Operations
function resetToLiveMonitoring() {
    V6_STATE.simulationMode = false;
    V6_STATE.comparisonMode = false;
    V6_STATE.activeScenario = null;
    V6_STATE.scenarioResults = null;

    const banner = document.getElementById('v6SimModeBanner');
    if (banner) banner.style.display = 'none';

    const resultsPanel = document.getElementById('v6ResultsContainer');
    if (resultsPanel) resultsPanel.style.display = 'none';

    // Restore live map
    if (typeof loadFloodData === 'function') {
        loadFloodData();
    }
}

// Switch Results Tab
function switchV6Tab(tabName) {
    document.querySelectorAll('.v6-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.v6-tab-content').forEach(tab => {
        tab.style.display = tab.id === `v6Tab-${tabName}` ? 'block' : 'none';
    });
}

// Fetch and Render Decision Audit Log
async function loadDecisionLog() {
    const tbody = document.getElementById('v6DecisionLogTbody');
    if (!tbody) return;

    try {
        const resp = await fetch('/api/v6/decision-log?limit=25');
        if (!resp.ok) return;
        const logs = await resp.json();

        tbody.innerHTML = '';
        logs.forEach(log => {
            const tr = document.createElement('tr');
            const timeStr = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '--';
            tr.innerHTML = `
                <td style="color:#64748B;font-size:11px;">${timeStr}</td>
                <td style="font-weight:700;font-size:11px;color:#2563EB;">${log.event_type}</td>
                <td style="font-size:11px;">${log.action_taken}</td>
                <td style="font-size:11px;color:#475569;">${log.operator}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Failed to load decision log:', e);
    }
}

// Attach event listeners when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    onPresetSelect('plus50');
    loadDecisionLog();
});
