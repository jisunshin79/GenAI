let map;
let markers = [];
let infoWindow;
let dataList = [];

const continentCenters = {
  "All":{lat:20, lng:10},
  "North America": { lat: 37.0902, lng: -95.7129 },
  "Europe": { lat: 54.5260, lng: 15.2551 },
  "Asia": { lat: 24.0479, lng: 100.6197 },
  "Oceania": { lat: -25.2744, lng: 133.7751 },
  "Latin America": { lat: 14.2350, lng: -90.9253 }
};

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
    .catch(error => console.error('JSON file load error', error));
}

// 초기 로드 시 전체 마커 한 번만 생성
function initMarkers() {
  dataList.forEach(univ => {
    const marker = createMarker(univ.lat, univ.lng, univ);
    marker._continent = univ.대륙;
    markers.push(marker);
  });

  map.setCenter(continentCenters["All"]);
  map.setZoom(2);
}

function createMarker(lat, lng, university) {
  const marker = new google.maps.Marker({
    position: { lat, lng },
    map: map,
    visible: true,
  });

  const listRemarks = university.비고
    ? university.비고.split('*')
      .filter((item) => item.trim() !== '')
      .map((item) => `<li>${item.trim()}</li>`)
      .join('')
    : '';

  const summaryRemarks = university.비고
    ? university.비고.split('*')
      .filter((item) => item.trim() !== '')
      .slice(0, 2)
      .map((item) => `<li>${item.trim()}</li>`)
      .join('')
    : '';

  const hoverWindow = new google.maps.InfoWindow({
    content: `
        <div class="hoverWindow">
          <h3>${university.파견기관}</h3>
          <h4 class="smallCity">City: ${university.소재도시}</h4>
          <ul>
            ${summaryRemarks}
          </ul>
        </div>
        `
  });

  const clickWindow = new google.maps.InfoWindow({
    content:
      `
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
            <li><strong>학부/대학원:</strong> ${university["학부 / 대학원"]}</li>
            <li><strong>전공제한:</strong> ${university.전공제한}</li>
            <li><strong>학기제한:</strong> ${university.학기제한}</li>
            ${listRemarks}
          </ul>
        </div>
      </div>
      `
  })

  let openDetailedInfoWindow = null;

  marker.addListener('mouseover', () => {
    if (!openDetailedInfoWindow) {
      hoverWindow.open(map, marker);
    }
  });

  marker.addListener('mouseout', () => {
    if (!openDetailedInfoWindow) {
      hoverWindow.close();
    }
  });

  marker.addListener('click', () => {
    if (openDetailedInfoWindow) {
      openDetailedInfoWindow.close();
    }
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
  markers.forEach(marker => marker.setVisible(true));

  map.setCenter(continentCenters["All"]);
  map.setZoom(2);

  document.querySelectorAll(".continentButtonArea button").forEach(btn => {
    btn.classList.remove("selected");
  });
}

function showContinent(continent, clickedButton) {
  // visibility 토글만 — 마커 새로 생성하지 않음
  markers.forEach(marker => {
    marker.setVisible(marker._continent === continent);
  });

  map.setCenter(continentCenters[continent]);
  map.setZoom(4);

  document.querySelectorAll(".continentButtonArea button").forEach(btn => {
    btn.classList.remove("selected");
  });

  if (clickedButton) clickedButton.classList.add("selected");
}
