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

// ===== 지도 초기화 =====

function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: continentCenters["All"],
    zoom: 2,
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
  const marker = new google.maps.Marker({
    position: { lat, lng },
    map: map,
    visible: true,
  });

  const listRemarks = university.비고
    ? university.비고.split('*')
        .filter(item => item.trim() !== '')
        .map(item => `<li>${item.trim()}</li>`)
        .join('')
    : '';

  const summaryRemarks = university.비고
    ? university.비고.split('*')
        .filter(item => item.trim() !== '')
        .slice(0, 2)
        .map(item => `<li>${item.trim()}</li>`)
        .join('')
    : '';

  const hoverWindow = new google.maps.InfoWindow({
    content: `
      <div class="hoverWindow">
        <h3>${university.파견기관}</h3>
        <h4 class="smallCity">City: ${university.소재도시}</h4>
        <ul>${summaryRemarks}</ul>
      </div>`
  });

  const clickWindow = new google.maps.InfoWindow({
    content: `
      <div class="hoverWindow">
        <h3 class="universityName">${university.파견기관}</h3>
        <div class="infoSection">
          <ul class="infoList">
            <li><strong>국가:</strong> ${university.국가}</li>
            <li><strong>소재도시:</strong> ${university.소재도시}</li>
            <li><strong>강의언어:</strong> ${university.강의언어}</li>
            <li><strong>CGPA:</strong> ${university.CGPA}</li>
            <li><strong>어학 기준:</strong> ${university["어학 기준(총점)"]}</li>
            <li><strong>파견인원:</strong> ${university["파견인원(학기당)"]}</li>
            <li><strong>학부/대학원:</strong> ${university["학부/대학원"]}</li>
            <li><strong>전공제한:</strong> ${university.전공제한}</li>
            <li><strong>학기제한:</strong> ${university.학기제한}</li>
            ${listRemarks}
          </ul>
        </div>
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

function showAllMarkers() {
  markers.forEach(marker => {
    marker.setVisible(true);
    marker.setIcon(null);
  });
  map.setCenter(continentCenters["All"]);
  map.setZoom(2);
  document.querySelectorAll(".continentButtonArea button").forEach(btn => {
    btn.classList.remove("selected");
  });
}

function showContinent(continent, clickedButton) {
  markers.forEach(marker => {
    marker.setIcon(null);
    marker.setVisible(marker._continent === continent);
  });
  map.setCenter(continentCenters[continent]);
  map.setZoom(4);
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
    marker.setIcon(isRecommended ? {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 11,
      fillColor: '#339af0',
      fillOpacity: 1,
      strokeColor: '#1971c2',
      strokeWeight: 2,
    } : null);
  });

  // 지도 범위를 추천 마커들에 맞게 조정
  const bounds = new google.maps.LatLngBounds();
  markers.filter(m => m.getVisible()).forEach(m => bounds.extend(m.getPosition()));
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60 });

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
  markers.forEach(marker => {
    marker.setVisible(true);
    marker.setIcon(null);
  });
  map.setCenter(continentCenters['All']);
  map.setZoom(2);
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
