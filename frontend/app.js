/* ==========================================================================
   F1 RACE INTELLIGENCE — FRONTEND APPLICATION LOGIC
   ========================================================================== */

const API_BASE_URL = window.VITE_API_BASE_URL || window.API_BASE_URL || (
  (window.location.origin && !window.location.origin.startsWith('file:'))
    ? `${window.location.origin}/api`
    : 'http://127.0.0.1:8000/api'
);

// Team Accent Color Mapping
const TEAM_COLORS = {
  mclaren: '#FF8000',
  'red bull': '#3671C6',
  'red bull racing': '#3671C6',
  ferrari: '#E8002D',
  mercedes: '#27F4D2',
  'aston martin': '#229971',
  alpine: '#0093CC',
  williams: '#64C4FF',
  rb: '#6692FF',
  racing_bulls: '#6692FF',
  sauber: '#52E252',
  kick_sauber: '#52E252',
  haas: '#B6BABD',
  'haas f1 team': '#B6BABD'
};

function getTeamColor(teamName) {
  if (!teamName) return 'var(--team-default)';
  const key = teamName.toLowerCase().trim();
  for (const [k, color] of Object.entries(TEAM_COLORS)) {
    if (key.includes(k)) return color;
  }
  return 'var(--team-default)';
}

// Application State
const state = {
  races: [],
  selectedRaceId: null,
  selectedRace: null,
  selectedStage: 'POST_QUALIFYING',
  predictions: [],
  filteredPredictions: [],
  dataAvailability: null,
  searchQuery: '',
  sortBy: 'race_share_probability',
  sortAsc: false,
  selectedDriver: null
};

// DOM Elements
const raceSelect = document.getElementById('raceSelect');
const raceRoundText = document.getElementById('raceRoundText');
const raceCircuitText = document.getElementById('raceCircuitText');
const raceDateText = document.getElementById('raceDateText');
const stageTimeline = document.getElementById('stageTimeline');
const timingTableBody = document.getElementById('timingTableBody');
const searchInput = document.getElementById('searchInput');
const refreshBtn = document.getElementById('refreshBtn');
const apiStatusText = document.getElementById('apiStatusText');

// KPI Banner Elements
const topShareDriver = document.getElementById('topShareDriver');
const topShareValue = document.getElementById('topShareValue');
const topShareTeam = document.getElementById('topShareTeam');

const topPodiumDriver = document.getElementById('topPodiumDriver');
const topPodiumValue = document.getElementById('topPodiumValue');
const topPodiumTeam = document.getElementById('topPodiumTeam');

const top5Driver = document.getElementById('top5Driver');
const top5Value = document.getElementById('top5Value');
const top5Team = document.getElementById('top5Team');

const dataCompletenessText = document.getElementById('dataCompletenessText');
const dataCompletenessValue = document.getElementById('dataCompletenessValue');

// Analytics Chart Elements
const raceShareBarChart = document.getElementById('raceShareBarChart');
const availabilityGrid = document.getElementById('availabilityGrid');

// Modal Elements
const driverModal = document.getElementById('driverModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const closeModalFooterBtn = document.getElementById('closeModalFooterBtn');
const modalDriverName = document.getElementById('modalDriverName');
const modalDriverCode = document.getElementById('modalDriverCode');
const modalTeamPill = document.getElementById('modalTeamPill');
const modalRaceShare = document.getElementById('modalRaceShare');
const modalRawWin = document.getElementById('modalRawWin');
const modalPodium = document.getElementById('modalPodium');
const modalTop5 = document.getElementById('modalTop5');
const modalPredPosition = document.getElementById('modalPredPosition');
const modalTeamName = document.getElementById('modalTeamName');

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadRaces();
});

function initEventListeners() {
  raceSelect.addEventListener('change', (e) => {
    const raceId = parseInt(e.target.value, 10);
    if (raceId) selectRace(raceId);
  });

  stageTimeline.addEventListener('click', (e) => {
    const btn = e.target.closest('.stage-btn');
    if (!btn) return;
    const stage = btn.dataset.stage;
    if (stage && stage !== state.selectedStage) {
      document.querySelectorAll('.stage-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedStage = stage;
      loadPredictions();
    }
  });

  searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase().trim();
    filterAndRenderPredictions();
  });

  refreshBtn.addEventListener('click', () => {
    loadPredictions();
  });

  closeModalBtn.addEventListener('click', closeModal);
  closeModalFooterBtn.addEventListener('click', closeModal);
  driverModal.addEventListener('click', (e) => {
    if (e.target === driverModal) closeModal();
  });

  // Table Column Sorting
  document.getElementById('sortRaceShare')?.addEventListener('click', () => toggleSort('race_share_probability'));
  document.getElementById('sortRawWin')?.addEventListener('click', () => toggleSort('raw_win_probability'));
  document.getElementById('sortPodium')?.addEventListener('click', () => toggleSort('podium_probability'));
  document.getElementById('sortTop5')?.addEventListener('click', () => toggleSort('top5_probability'));
  document.getElementById('sortFinish')?.addEventListener('click', () => toggleSort('predicted_finish_position'));
}

async function loadRaces() {
  try {
    const res = await fetch(`${API_BASE_URL}/races?season=2025`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const races = await res.json();
    state.races = races;

    if (races.length === 0) {
      raceSelect.innerHTML = '<option value="">No 2025 races found</option>';
      apiStatusText.textContent = 'NO RACE DATA';
      return;
    }

    raceSelect.innerHTML = races.map(r => 
      `<option value="${r.id}">Round ${r.round}: ${r.race_name} (${r.circuit})</option>`
    ).join('');

    // Default select first race
    selectRace(races[0].id);
  } catch (err) {
    console.error('Failed to load races:', err);
    apiStatusText.textContent = 'BACKEND OFFLINE';
    apiStatusText.style.color = 'var(--accent-red)';
  }
}

function selectRace(raceId) {
  const race = state.races.find(r => r.id === raceId);
  if (!race) return;

  state.selectedRaceId = raceId;
  state.selectedRace = race;
  raceSelect.value = raceId;

  raceRoundText.textContent = `2025 · R${race.round}`;
  raceCircuitText.textContent = race.circuit || race.country || 'Circuit';
  raceDateText.textContent = race.race_date ? new Date(race.race_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '2025';

  loadPredictions();
}

async function loadPredictions() {
  if (!state.selectedRaceId) return;

  timingTableBody.innerHTML = `
    <tr>
      <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-muted);">
        <i data-lucide="refresh-cw" class="shimmer" style="width: 20px; height: 20px; vertical-align: middle; margin-right: 8px;"></i>
        Executing ML stage prediction model (${state.selectedStage})...
      </td>
    </tr>
  `;
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE_URL}/races/${state.selectedRaceId}/predictions?stage=${state.selectedStage}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.predictions = data.predictions || [];
    state.dataAvailability = data.data_availability || null;

    apiStatusText.textContent = 'PREDICTION MODEL OK';
    apiStatusText.style.color = 'var(--accent-green)';

    filterAndRenderPredictions();
    updateKPIBanner();
    updateChartsAndAvailability();
  } catch (err) {
    console.error('Failed to load predictions:', err);
    timingTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 30px; color: var(--accent-red);">
          <i data-lucide="alert-triangle" style="width: 18px; height: 18px; display: inline; vertical-align: middle; margin-right: 6px;"></i>
          Prediction service error: ${err.message}
        </td>
      </tr>
    `;
    if (window.lucide) window.lucide.createIcons();
  }
}

function filterAndRenderPredictions() {
  let list = [...state.predictions];

  if (state.searchQuery) {
    list = list.filter(p => 
      p.driver_name.toLowerCase().includes(state.searchQuery) ||
      p.driver_code.toLowerCase().includes(state.searchQuery) ||
      (p.team_name && p.team_name.toLowerCase().includes(state.searchQuery))
    );
  }

  // Sort
  list.sort((a, b) => {
    let valA = a[state.sortBy];
    let valB = b[state.sortBy];
    if (valA === undefined) valA = 0;
    if (valB === undefined) valB = 0;

    if (state.sortBy === 'predicted_finish_position') {
      return state.sortAsc ? valA - valB : valA - valB; // lower position is better
    }
    return state.sortAsc ? valA - valB : valB - valA;
  });

  state.filteredPredictions = list;
  renderTimingBoardTable(list);
}

function renderTimingBoardTable(predictions) {
  if (predictions.length === 0) {
    timingTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 30px; color: var(--text-muted);">
          No driver predictions available for this stage query.
        </td>
      </tr>
    `;
    return;
  }

  timingTableBody.innerHTML = predictions.map((p, idx) => {
    const pos = idx + 1;
    let posClass = '';
    if (pos === 1) posClass = 'p1';
    else if (pos === 2) posClass = 'p2';
    else if (pos === 3) posClass = 'p3';

    const teamColor = getTeamColor(p.team_name);
    const winSharePct = (p.race_share_probability * 100).toFixed(1);
    const rawWinPct = (p.raw_win_probability * 100).toFixed(1);
    const podiumPct = (p.podium_probability * 100).toFixed(1);
    const top5Pct = (p.top5_probability * 100).toFixed(1);
    const predPos = p.predicted_finish_position ? p.predicted_finish_position.toFixed(1) : '—';

    return `
      <tr class="timing-row" data-driver-id="${p.driver_id}">
        <td>
          <div class="pos-badge ${posClass}">${pos}</div>
        </td>
        <td>
          <div class="driver-cell">
            <span class="team-pill" style="background-color: ${teamColor};"></span>
            <span class="driver-code-tag">${p.driver_code}</span>
            <span class="driver-name-text">${p.driver_name}</span>
          </div>
        </td>
        <td class="team-text">${p.team_name || '—'}</td>
        <td>
          <div>
            <span class="prob-number highlight">${winSharePct}%</span>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${Math.min(winSharePct * 2.5, 100)}%; background: var(--accent-cyan);"></div>
            </div>
          </div>
        </td>
        <td class="prob-number">${rawWinPct}%</td>
        <td>
          <div>
            <span class="prob-number">${podiumPct}%</span>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${podiumPct}%; background: var(--accent-green);"></div>
            </div>
          </div>
        </td>
        <td class="prob-number">${top5Pct}%</td>
        <td class="prob-number" style="color: var(--accent-amber);">P${predPos}</td>
      </tr>
    `;
  }).join('');

  // Row Click Listener for Driver Inspector
  document.querySelectorAll('.timing-row').forEach(row => {
    row.addEventListener('click', () => {
      const driverId = parseInt(row.dataset.driverId, 10);
      const driverPred = state.predictions.find(p => p.driver_id === driverId);
      if (driverPred) openDriverModal(driverPred);
    });
  });
}

function toggleSort(columnKey) {
  if (state.sortBy === columnKey) {
    state.sortAsc = !state.sortAsc;
  } else {
    state.sortBy = columnKey;
    state.sortAsc = columnKey === 'predicted_finish_position';
  }
  filterAndRenderPredictions();
}

function updateKPIBanner() {
  if (state.predictions.length === 0) return;

  // Top Share
  const sortedShare = [...state.predictions].sort((a, b) => b.race_share_probability - a.race_share_probability);
  const topS = sortedShare[0];
  topShareDriver.textContent = topS ? `${topS.driver_code}` : '—';
  topShareValue.textContent = topS ? `${(topS.race_share_probability * 100).toFixed(1)}%` : '0.0%';
  topShareTeam.textContent = topS ? `${topS.driver_name} (${topS.team_name || ''})` : '—';

  // Top Podium
  const sortedPodium = [...state.predictions].sort((a, b) => b.podium_probability - a.podium_probability);
  const topP = sortedPodium[0];
  topPodiumDriver.textContent = topP ? `${topP.driver_code}` : '—';
  topPodiumValue.textContent = topP ? `${(topP.podium_probability * 100).toFixed(1)}%` : '0.0%';
  topPodiumTeam.textContent = topP ? `${topP.driver_name} (${topP.team_name || ''})` : '—';

  // Top 5
  const sortedTop5 = [...state.predictions].sort((a, b) => b.top5_probability - a.top5_probability);
  const top5 = sortedTop5[0];
  top5Driver.textContent = top5 ? `${top5.driver_code}` : '—';
  top5Value.textContent = top5 ? `${(top5.top5_probability * 100).toFixed(1)}%` : '0.0%';
  top5Team.textContent = top5 ? `${top5.driver_name} (${top5.team_name || ''})` : '—';

  // Data Completeness
  if (state.dataAvailability) {
    const activeCount = Object.values(state.dataAvailability).filter(Boolean).length;
    const totalCount = Object.keys(state.dataAvailability).length;
    const pct = Math.round((activeCount / totalCount) * 100);
    dataCompletenessText.textContent = `${activeCount}/${totalCount} Feeds Active`;
    dataCompletenessValue.textContent = `${pct}%`;
  }
}

function updateChartsAndAvailability() {
  if (state.predictions.length === 0) return;

  // Bar Chart (Top 6 Race Share)
  const top6 = [...state.predictions]
    .sort((a, b) => b.race_share_probability - a.race_share_probability)
    .slice(0, 6);

  const maxShare = top6[0]?.race_share_probability || 1.0;

  raceShareBarChart.innerHTML = top6.map(p => {
    const pct = (p.race_share_probability * 100).toFixed(1);
    const fillWidth = Math.min((p.race_share_probability / maxShare) * 100, 100);
    const teamColor = getTeamColor(p.team_name);

    return `
      <div class="bar-chart-row">
        <div class="bar-label">${p.driver_code}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${fillWidth}%; background-color: ${teamColor};">
            <span class="bar-value">${pct}%</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Data Availability Grid
  if (state.dataAvailability) {
    availabilityGrid.innerHTML = `
      <div class="avail-item ${state.dataAvailability.historical_form ? 'active' : ''}">
        <div class="avail-label">FORM</div>
        <div class="avail-status ${state.dataAvailability.historical_form ? 'active' : 'inactive'}">
          ${state.dataAvailability.historical_form ? 'ACTIVE' : 'MASKED'}
        </div>
      </div>
      <div class="avail-item ${state.dataAvailability.fp1 ? 'active' : ''}">
        <div class="avail-label">FP1</div>
        <div class="avail-status ${state.dataAvailability.fp1 ? 'active' : 'inactive'}">
          ${state.dataAvailability.fp1 ? 'ACTIVE' : 'MASKED'}
        </div>
      </div>
      <div class="avail-item ${state.dataAvailability.fp2 ? 'active' : ''}">
        <div class="avail-label">FP2</div>
        <div class="avail-status ${state.dataAvailability.fp2 ? 'active' : 'inactive'}">
          ${state.dataAvailability.fp2 ? 'ACTIVE' : 'MASKED'}
        </div>
      </div>
      <div class="avail-item ${state.dataAvailability.fp3 ? 'active' : ''}">
        <div class="avail-label">FP3</div>
        <div class="avail-status ${state.dataAvailability.fp3 ? 'active' : 'inactive'}">
          ${state.dataAvailability.fp3 ? 'ACTIVE' : 'MASKED'}
        </div>
      </div>
      <div class="avail-item ${state.dataAvailability.qualifying ? 'active' : ''}">
        <div class="avail-label">QUALI</div>
        <div class="avail-status ${state.dataAvailability.qualifying ? 'active' : 'inactive'}">
          ${state.dataAvailability.qualifying ? 'ACTIVE' : 'MASKED'}
        </div>
      </div>
    `;
  }
}

function openDriverModal(p) {
  state.selectedDriver = p;

  modalDriverName.textContent = p.driver_name;
  modalDriverCode.textContent = p.driver_code;
  modalTeamPill.style.backgroundColor = getTeamColor(p.team_name);
  modalTeamName.textContent = p.team_name || 'Constructor Team';

  modalRaceShare.textContent = `${(p.race_share_probability * 100).toFixed(1)}%`;
  modalRawWin.textContent = `${(p.raw_win_probability * 100).toFixed(1)}%`;
  modalPodium.textContent = `${(p.podium_probability * 100).toFixed(1)}%`;
  modalTop5.textContent = `${(p.top5_probability * 100).toFixed(1)}%`;
  modalPredPosition.textContent = p.predicted_finish_position ? `P${p.predicted_finish_position.toFixed(1)}` : '—';

  driverModal.classList.add('active');
}

function closeModal() {
  driverModal.classList.remove('active');
}
