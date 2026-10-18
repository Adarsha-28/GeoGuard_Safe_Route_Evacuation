/**
 * GeoGuard V1 - Chennai Area Risk Directory
 * Consumes /api/grids endpoint.
 */

let areasData = [];
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', function() {
    console.log("Loading flood risk areas from /api/grids...");

    fetch('/api/grids')
        .then(response => {
            if (!response.ok) throw new Error("HTTP " + response.status);
            return response.json();
        })
        .then(data => {
            areasData = (data.features || []).map((feature, index) => {
                const props = feature.properties;
                let riskLabel = props.flood_risk;
                if (riskLabel === 'Low') riskLabel = 'Safe';

                return {
                    id: props.id || index + 1,
                    name: props.place_name,
                    lat: props.latitude,
                    lng: props.longitude,
                    risk: riskLabel,
                    score: props.flood_risk_score,
                    rainfall: props.rainfall_mm,
                    elevation: props.elevation_m,
                    waterDist: parseFloat((props.distance_to_water / 1000).toFixed(2)),
                };
            });

            updateSummaryCounts();

            // Check URL parameters for filter
            const urlParams = new URLSearchParams(window.location.search);
            const filterParam = urlParams.get('filter');

            if (filterParam && ['Safe', 'Moderate', 'High', 'Severe', 'Low'].includes(filterParam)) {
                const mappedFilter = filterParam === 'Low' ? 'Safe' : filterParam;
                currentFilter = mappedFilter;
                const filtered = areasData.filter(area => area.risk === mappedFilter);
                displayAreas(filtered);

                document.querySelectorAll('.filter-btn').forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.textContent.includes(mappedFilter)) {
                        btn.classList.add('active');
                    }
                });
            } else {
                displayAreas(areasData);
            }
        })
        .catch(err => {
            console.error("Failed to load areas:", err);
            document.getElementById('areasGrid').innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #DC2626; font-weight: bold;">
                    Failed to load flood risk areas from API. Please ensure the server is running.
                </div>
            `;
        });
});

function updateSummaryCounts() {
    const counts = { Safe: 0, Moderate: 0, High: 0, Severe: 0 };
    areasData.forEach(area => {
        if (counts[area.risk] !== undefined) {
            counts[area.risk]++;
        }
    });

    const safeEl = document.getElementById('countSafe');
    const modEl = document.getElementById('countModerate');
    const highEl = document.getElementById('countHigh');
    const sevEl = document.getElementById('countSevere');

    if (safeEl) safeEl.textContent = counts.Safe;
    if (modEl) modEl.textContent = counts.Moderate;
    if (highEl) highEl.textContent = counts.High;
    if (sevEl) sevEl.textContent = counts.Severe;
}

function displayAreas(areas) {
    const grid = document.getElementById('areasGrid');
    if (!grid) return;

    if (areas.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #64748B;">No matching areas found.</div>';
        return;
    }

    grid.innerHTML = areas.map(area => {
        let badgeClass = 'safe';
        let cardBorder = '#22C55E';
        if (area.risk === 'Severe') {
            badgeClass = 'severe';
            cardBorder = '#EF4444';
        } else if (area.risk === 'High') {
            badgeClass = 'high';
            cardBorder = '#F97316';
        } else if (area.risk === 'Moderate') {
            badgeClass = 'moderate';
            cardBorder = '#EAB308';
        }

        return `
            <div class="area-card" style="border-top: 4px solid ${cardBorder}; background: #FFFFFF; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div>
                        <h3 style="font-size: 16px; font-weight: 700; color: #1E293B; margin-bottom: 2px;">${area.name}</h3>
                        <small style="color: #64748B;">Coords: ${area.lat.toFixed(4)}, ${area.lng.toFixed(4)}</small>
                    </div>
                    <span class="badge ${badgeClass}" style="padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">${area.risk.toUpperCase()}</span>
                </div>
                <div style="font-size: 12px; color: #475569; line-height: 1.6; border-top: 1px solid #F1F5F9; padding-top: 10px;">
                    <div><strong>Risk Score:</strong> ${(area.score * 100).toFixed(1)}%</div>
                    <div><strong>Precipitation:</strong> ${area.rainfall} mm</div>
                    <div><strong>Elevation:</strong> ${area.elevation} m</div>
                    <div><strong>Distance to Water:</strong> ${area.waterDist} km</div>
                </div>
                <div style="margin-top: 14px;">
                    <a href="index.html" class="btn btn-primary btn-sm" style="display: block; text-align: center; text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600;">Open on Map</a>
                </div>
            </div>
        `;
    }).join('');
}

window.filterAreas = function(risk) {
    currentFilter = risk;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (risk === 'all' && btn.textContent.includes('All')) {
            btn.classList.add('active');
        } else if (btn.textContent.includes(risk)) {
            btn.classList.add('active');
        }
    });

    if (risk === 'all') {
        displayAreas(areasData);
    } else {
        const filtered = areasData.filter(a => a.risk === risk);
        displayAreas(filtered);
    }
};

window.searchAreas = function() {
    const query = document.getElementById('areaSearch').value.toLowerCase().trim();
    let filtered = areasData;

    if (currentFilter !== 'all') {
        filtered = filtered.filter(a => a.risk === currentFilter);
    }

    if (query.length > 0) {
        filtered = filtered.filter(a => a.name.toLowerCase().includes(query));
    }

    displayAreas(filtered);
};
