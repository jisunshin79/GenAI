let map;
let markers = [];
let dataList = [];

const continentCenters = {
  "All": { lat: 20, lng: 10 },
  "North America": { lat: 37.0902, lng: -95.7129 },
  "Europe": { lat: 54.5260, lng: 15.2551 },
  "Asia": { lat: 24.0479, lng: 100.6197 },
  "Oceania": { lat: -25.2744, lng: 133.7751 },
  "Latin America": { lat: 14.2350, lng: -90.9253 }
};

const CONTINENT_COLORS = {
  "Asia": "#f59f00",
  "North America": "#4dabf7",
  "Europe": "#7048e8",
  "Oceania": "#12b886",
  "Latin America": "#f06595",
};

// 클래식 지도 핀(물방울) 모양 — Material Design "place" 아이콘 경로.
// 끝(꼭짓점)이 실제 좌표를 가리키도록 anchor를 꼭짓점에 맞춘다.
const PIN_PATH = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z";

function continentIcon(continent) {
  return {
    path: PIN_PATH,
    scale: 1.3,
    fillColor: CONTINENT_COLORS[continent] || "#868e96",
    fillOpacity: 0.95,
    strokeColor: "#ffffff",
    strokeWeight: 1,
    anchor: new google.maps.Point(12, 22),
  };
}

function recommendedIcon() {
  return {
    path: PIN_PATH,
    scale: 1.9,
    fillColor: "#7048e8",
    fillOpacity: 1,
    strokeColor: "#ffffff",
    strokeWeight: 1.5,
    anchor: new google.maps.Point(12, 22),
  };
}

// ===== 지도 초기화 =====

// 차분한 모노톤 스타일 — 기본 Google Maps의 알록달록한 POI/도로 색을 줄이고
// 학교 마커가 시각적으로 도드라지도록 배경을 단순화한다.
const MAP_STYLE = [
  { elementType: "geometry", stylers: [{ color: "#f5f3ee" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#6b6b6b" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#f5f3ee" }] },
  { featureType: "administrative.country", elementType: "geometry.stroke", stylers: [{ color: "#c9c4b8" }] },
  { featureType: "administrative.province", elementType: "geometry.stroke", stylers: [{ color: "#d8d4c8", weight: 0.5 }] },
  { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#f5f3ee" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "road", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#d4e4ec" }] },
  { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#9fb8c4" }] },
];

function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: continentCenters["All"],
    zoom: 2,
    styles: MAP_STYLE,
    disableDefaultUI: true,
    zoomControl: true,
  });

  fetch("data.json")
    .then(res => res.json())
    .then(data => {
      dataList = data;
      initMarkers();
    })
    .catch(error => console.error('data.json 로드 오류:', error));

  setupAiPanel();
}

// ===== 마커 시스템 =====

// 초기 로드 시 전체 마커 한 번만 생성
function initMarkers() {
  dataList.forEach(univ => {
    const marker = createMarker(univ.lat, univ.lng, univ);
    marker._data = univ;
    marker._continent = univ.대륙;
    markers.push(marker);
  });
}

function createMarker(lat, lng, university) {
  const icon = continentIcon(university.대륙);
  const accent = CONTINENT_COLORS[university.대륙] || "#868e96";

  const marker = new google.maps.Marker({
    position: { lat, lng },
    map: map,
    visible: true,
    icon,
  });
  marker._icon = icon;

  const remarkItems = university.비고
    ? university.비고.split('*').map(item => item.trim()).filter(Boolean)
    : [];

  const hoverWindow = new google.maps.InfoWindow({
    content: `
      <div class="popupCard popupCard--hover" style="border-top-color:${accent}">
        <h3 class="popupTitle">${university.파견기관}</h3>
        <div class="popupCity">📍 ${university.소재도시}</div>
        ${remarkItems.slice(0, 2).map(t => `<div class="popupNote">${t}</div>`).join('')}
      </div>`
  });

  const infoPills = [
    ['국가', university.국가],
    ['강의언어', university.강의언어],
    ['CGPA', university.CGPA],
    ['어학 기준', university["어학 기준(총점)"]],
    ['파견인원', university["파견인원(학기당)"]],
    ['학부/대학원', university["학부/대학원"]],
    ['전공제한', university.전공제한],
    ['학기제한', university.학기제한],
  ];

  const clickWindow = new google.maps.InfoWindow({
    maxWidth: 660,
    content: `
      <div class="popupCard popupCard--detail" style="border-top-color:${accent}">
        <h3 class="popupTitle">${university.파견기관}</h3>
        <div class="popupCity">📍 ${university.소재도시}</div>
        <div class="popupGrid">
          ${infoPills.map(([label, value]) => `
            <div class="popupPill">
              <span class="popupPillLabel">${label}</span>
              <span class="popupPillValue">${value || '-'}</span>
            </div>`).join('')}
        </div>
        ${remarkItems.length ? `<div class="popupNotes">${remarkItems.map(t => `<div class="popupNote">${t}</div>`).join('')}</div>` : ''}
      </div>`
  });

  let openDetailedInfoWindow = null;

  marker.addListener('mouseover', () => {
    if (!openDetailedInfoWindow) hoverWindow.open(map, marker);
  });

  marker.addListener('mouseout', () => {
    if (!openDetailedInfoWindow) hoverWindow.close();
  });

  marker.addListener('click', () => {
    if (openDetailedInfoWindow) openDetailedInfoWindow.close();
    hoverWindow.close();
    clickWindow.open(map, marker);
    openDetailedInfoWindow = clickWindow;
    google.maps.event.addListener(clickWindow, 'closeclick', () => {
      openDetailedInfoWindow = null;
    });
  });

  return marker;
}

// fitBounds에 큰 padding을 주면(특히 상단) 전세계처럼 위도 폭이 넓은 bounds에서는
// 지도가 필요 이상으로 축소되어 북극 위쪽의 빈 캔버스가 화면 절반을 차지하는 문제가
// 생긴다. 그래서 padding은 작게 주고, 그 결과 zoom이 너무 낮아지면 한 번만 보정한다.
const MAP_FIT_PADDING = 30;
const MIN_ALL_ZOOM = 2;

function fitToBounds(bounds, { minZoom } = {}) {
  if (bounds.isEmpty()) return;
  map.fitBounds(bounds, MAP_FIT_PADDING);
  if (minZoom == null) return;
  const listener = map.addListener('idle', () => {
    if (map.getZoom() < minZoom) map.setZoom(minZoom);
    google.maps.event.removeListener(listener);
  });
}

function showAllMarkers() {
  const bounds = new google.maps.LatLngBounds();
  markers.forEach(marker => {
    marker.setVisible(true);
    marker.setIcon(marker._icon);
    bounds.extend(marker.getPosition());
  });
  fitToBounds(bounds, { minZoom: MIN_ALL_ZOOM });
  document.querySelectorAll(".continentButtonArea button").forEach(btn => {
    btn.classList.remove("selected");
  });
}

function showContinent(continent, clickedButton) {
  const bounds = new google.maps.LatLngBounds();
  markers.forEach(marker => {
    marker.setIcon(marker._icon);
    const visible = marker._continent === continent;
    marker.setVisible(visible);
    if (visible) bounds.extend(marker.getPosition());
  });
  fitToBounds(bounds);
  document.querySelectorAll(".continentButtonArea button").forEach(btn => {
    btn.classList.remove("selected");
  });
  if (clickedButton) clickedButton.classList.add("selected");
}

// ===== AI 패널 =====

function setupAiPanel() {
  document.getElementById('aiToggleBtn').addEventListener('click', toggleAiPanel);
  document.getElementById('aiCloseBtn').addEventListener('click', toggleAiPanel);
  document.getElementById('chatSubmitBtn').addEventListener('click', submitChat);
  document.getElementById('profileForm').addEventListener('submit', submitProfile);
  document.querySelectorAll('.ai-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function toggleAiPanel() {
  document.getElementById('aiPanel').classList.toggle('open');
}

function switchTab(tabName) {
  document.querySelectorAll('.ai-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.ai-tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`.ai-tab-btn[data-tab="${tabName}"]`).classList.add('active');
  document.getElementById(tabName + 'Tab').classList.add('active');
}

function fillExample(text) {
  document.getElementById('chatInput').value = text;
  document.getElementById('chatInput').focus();
}

async function submitChat() {
  const query = document.getElementById('chatInput').value.trim();
  if (!query) return;
  await callAI({ query });
}

async function submitProfile(e) {
  e.preventDefault();
  const form = e.target;
  const profile = {
    cgpa: form.cgpa.value,
    cgpaScale: form.cgpaScale.value,
    region: form.region.value,
    language: form.language.value,
    toefl: form.toefl.value,
    ielts: form.ielts.value,
    major: form.major.value,
    notes: form.notes.value,
  };
  await callAI({ profile });
}

async function callAI(body) {
  setLoading(true);
  document.getElementById('aiResults').classList.add('hidden');

  try {
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    showAiResults(data);
  } catch (err) {
    alert('오류: ' + err.message);
  } finally {
    setLoading(false);
  }
}

function showAiResults({ recommendations, explanation }) {
  const recommendedSet = new Set(recommendations);

  // 추천된 마커만 표시, 하이라이트 아이콘 적용
  markers.forEach(marker => {
    const isRecommended = recommendedSet.has(marker._data.파견기관);
    marker.setVisible(isRecommended);
    marker.setIcon(isRecommended ? recommendedIcon() : marker._icon);
  });

  // 지도 범위를 추천 마커들에 맞게 조정
  const bounds = new google.maps.LatLngBounds();
  markers.filter(m => m.getVisible()).forEach(m => bounds.extend(m.getPosition()));
  fitToBounds(bounds);

  // 설명 텍스트
  document.getElementById('aiExplanation').textContent = explanation;

  // 추천 대학 카드 목록
  const listEl = document.getElementById('aiUnivList');
  listEl.innerHTML = '';
  recommendations.forEach((name, i) => {
    const univ = dataList.find(u => u.파견기관 === name);
    const card = document.createElement('div');
    card.className = 'ai-univ-card';
    card.innerHTML = `
      <div class="ai-univ-rank">${i + 1}</div>
      <div class="ai-univ-info">
        <div class="ai-univ-name">${name}</div>
        <div class="ai-univ-sub">${univ ? univ.국가 + ' · ' + univ.강의언어 : ''}</div>
      </div>
      <div class="ai-univ-arrow">›</div>`;
    card.addEventListener('click', () => {
      const marker = markers.find(m => m._data.파견기관 === name);
      if (marker) {
        map.panTo(marker.getPosition());
        map.setZoom(8);
      }
    });
    listEl.appendChild(card);
  });

  document.getElementById('aiResults').classList.remove('hidden');
}

function resetAiResults() {
  const bounds = new google.maps.LatLngBounds();
  markers.forEach(marker => {
    marker.setVisible(true);
    marker.setIcon(marker._icon);
    bounds.extend(marker.getPosition());
  });
  fitToBounds(bounds, { minZoom: MIN_ALL_ZOOM });
  document.getElementById('aiResults').classList.add('hidden');
  document.querySelectorAll('.continentButtonArea button').forEach(btn => {
    btn.classList.remove('selected');
  });
}

function setLoading(show) {
  document.getElementById('aiLoading').classList.toggle('hidden', !show);
  document.querySelectorAll('.ai-submit-btn').forEach(btn => {
    btn.disabled = show;
  });
}
