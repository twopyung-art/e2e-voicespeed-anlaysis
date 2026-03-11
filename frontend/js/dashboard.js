/**
 * 대시보드 렌더링 및 상태 관리
 */

// ── 상태 ──────────────────────────────────────────────
const state = {
  folders: {},       // { folderName: { files: [...], results: {} } }
  stats: {},         // { folderName: FolderStats }
  totalFiles: 0,
  completedFiles: 0,
  running: false,
  excelPath: null,
  jsonPath: null,
};

// E2E 등급 기준 (초)
const E2E_GOOD = 3.0;
const E2E_WARN = 5.0;

// ── 초기화 ────────────────────────────────────────────
async function init() {
  await loadFolders();
  setupButtons();
  loadReferenceStatus();

  const ws = new WSClient(handleWSEvent);
  ws.connect();
}

async function loadFolders() {
  try {
    const res = await fetch("/api/folders");
    const data = await res.json();
    renderSidebar(data.folders);
    updateSummaryCards();

    if (data.folders.length === 0) {
      showEmptyState();
    } else {
      showReadyState(data.folders);
    }
  } catch (e) {
    showToast("폴더 목록을 불러오지 못했습니다.", "error");
  }
}

function setupButtons() {
  document.getElementById("btn-analyze").addEventListener("click", startAnalysis);
  document.getElementById("btn-download-excel").addEventListener("click", downloadExcel);
  document.getElementById("btn-download-json").addEventListener("click", downloadJson);

  document.getElementById("modal-overlay").addEventListener("click", closeModal);
}

// ── WebSocket 이벤트 처리 ──────────────────────────────
function handleWSEvent(type, data) {
  switch (type) {
    case "analysis_start":
      state.running = true;
      state.totalFiles = data.total_files;
      state.completedFiles = 0;
      updateSummaryCards();
      setButtonState(true);
      break;

    case "folder_start":
      initFolder(data.folder_name, data.file_count);
      scrollToFolder(data.folder_name);
      break;

    case "file_complete":
      state.completedFiles++;
      updateFileCard(data);
      updateSummaryCards();
      highlightSidebarItem(data.folder_name);
      break;

    case "folder_complete":
      state.stats[data.folder_name] = data;
      updateFolderStats(data);
      updateSidebarBadge(data.folder_name, data.valid_count, data.total_files);
      break;

    case "analysis_complete":
      state.running = false;
      state.excelPath = data.excel_path;
      state.jsonPath = data.json_path;
      setButtonState(false);
      showDownloadButtons(true);
      showToast("분석이 완료되었습니다! Excel 파일을 다운로드하세요.", "success");
      break;

    case "analysis_error":
      showToast(`오류: ${data.folder_name} / ${data.file_name} — ${data.message}`, "error");
      break;
  }
}

// ── 분석 시작 ──────────────────────────────────────────
async function startAnalysis() {
  if (state.running) return;

  // ① 버튼 즉시 비활성화 (클릭 피드백)
  const btn = document.getElementById("btn-analyze");
  btn.disabled = true;
  btn.textContent = "⏳ 분석 준비 중...";

  // ② UI 초기화
  document.getElementById("folder-list").innerHTML = "";
  state.folders = {};
  state.stats = {};
  state.completedFiles = 0;
  showDownloadButtons(false);

  // ③ 폴더 목록을 미리 가져와 섹션 즉시 렌더링 (SocketIO 이벤트 오기 전에 표시)
  try {
    const folderRes = await fetch("/api/folders");
    const folderData = await folderRes.json();
    if (folderData.folders && folderData.folders.length > 0) {
      folderData.folders.forEach(f => initFolder(f.name, f.file_count));
      updateSummaryCards();
    }
  } catch (_) {}

  // ④ 분석 요청
  try {
    const res = await fetch("/api/analyze", { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.error || "분석 시작 실패", "error");
      btn.disabled = false;
      btn.textContent = "▶ 분석 시작";
    }
    // 성공 시 버튼은 analysis_complete 이벤트에서 재활성화
  } catch (e) {
    showToast("서버 연결 오류", "error");
    btn.disabled = false;
    btn.textContent = "▶ 분석 시작";
  }
}

// ── 폴더 초기화 (UI) ───────────────────────────────────
function initFolder(folderName, fileCount) {
  // 이미 렌더링된 섹션이 있으면 state만 업데이트하고 반환
  if (document.getElementById(`folder-${cssId(folderName)}`)) {
    state.folders[folderName] = state.folders[folderName] || { fileCount, results: {} };
    return;
  }
  state.folders[folderName] = { fileCount, results: {} };

  const list = document.getElementById("folder-list");
  const section = document.createElement("div");
  section.className = "folder-section";
  section.id = `folder-${cssId(folderName)}`;
  section.innerHTML = `
    <div class="folder-header">
      <span class="folder-name">📁 ${escHtml(folderName)}</span>
      <span class="file-count" id="fc-count-${cssId(folderName)}">0 / ${fileCount}</span>
    </div>
    <div class="progress-bar-wrap">
      <div class="progress-bar" id="pb-${cssId(folderName)}" style="width:0%"></div>
    </div>

    <div class="result-section-header">
      <span class="rs-icon">📋</span> 개별 분석 결과
      <span class="rs-count">${fileCount}개 파일</span>
    </div>
    <div class="file-cards" id="cards-${cssId(folderName)}"></div>

    ${fileCount >= 10 ? `
    <div class="result-section-header avg-header" style="margin-top:20px">
      <span class="rs-icon">📊</span> 평균 분석 결과
      <span class="rs-note">최대·최소 각 1개 제외 → 8회 평균</span>
    </div>
    <div class="folder-stats-bar" id="stats-${cssId(folderName)}" style="display:none"></div>
    ` : ''}
  `;
  list.appendChild(section);

  // 파일 카드 플레이스홀더 생성 (대기 상태)
  const cardsEl = section.querySelector(`#cards-${cssId(folderName)}`);
  for (let i = 0; i < fileCount; i++) {
    const card = document.createElement("div");
    card.className = "file-card";
    card.id = `card-placeholder-${cssId(folderName)}-${i}`;
    card.innerHTML = `
      <div class="fc-name">대기 중...</div>
      <span class="fc-status waiting">대기</span>
    `;
    cardsEl.appendChild(card);
  }

  // 사이드바 항목 추가
  addSidebarFolder(folderName, fileCount);
}

// ── 파일 카드 업데이트 ─────────────────────────────────
function updateFileCard(data) {
  const folderState = state.folders[data.folder_name];
  if (!folderState) return;

  folderState.results[data.file_name] = data;
  const completedCount = Object.keys(folderState.results).length;

  // 진행률 업데이트
  const pct = Math.round((completedCount / folderState.fileCount) * 100);
  const pb = document.getElementById(`pb-${cssId(data.folder_name)}`);
  if (pb) pb.style.width = pct + "%";

  const countEl = document.getElementById(`fc-count-${cssId(data.folder_name)}`);
  if (countEl) countEl.textContent = `${completedCount} / ${folderState.fileCount}`;

  // 카드 찾기 (순서대로 채움)
  const idx = completedCount - 1;
  const cardEl = document.getElementById(`card-placeholder-${cssId(data.folder_name)}-${idx}`);
  if (!cardEl) return;

  cardEl.id = `card-${cssId(data.folder_name)}-${cssId(data.file_name)}`;

  if (data.error) {
    cardEl.className = "file-card error";
    cardEl.innerHTML = `
      <div class="fc-name" title="${escHtml(data.file_name)}">${escHtml(data.file_name)}</div>
      <span class="fc-status error">오류</span>
      <div style="font-size:10px;color:#991B1B;margin-top:24px">${escHtml(data.error)}</div>
    `;
    return;
  }

  const grade = getE2EGrade(data.E2E);
  const maxT = Math.max(data.T0, data.T1, data.T2, data.T3, 0.01);

  const modeBadge = data.detection_mode === "reference"
    ? `<span class="mode-badge reference">기준음원</span>`
    : `<span class="mode-badge rms">RMS</span>`;

  cardEl.className = "file-card";
  cardEl.innerHTML = `
    <div class="fc-name" title="${escHtml(data.file_name)}">${escHtml(data.file_name)}${modeBadge}</div>
    <span class="fc-status done">완료</span>
    ${data.image_path ? `
      <img class="waveform-img"
           src="/${data.image_path}"
           alt="파형"
           onclick="openModal('/${data.image_path}')"
           onerror="this.style.display='none'">
    ` : ""}
    <div class="timing-bars">
      ${timingRow("T0", data.T0, maxT, "t0")}
      ${timingRow("T1", data.T1, maxT, "t1")}
      ${timingRow("T2", data.T2, maxT, "t2")}
      ${timingRow("T3", data.T3, maxT, "t3")}
    </div>
    <div class="e2e-row">
      <span class="e2e-label">E2E</span>
      <span class="e2e-value">${data.E2E.toFixed(3)}s</span>
      <span class="e2e-grade ${grade.cls}">${grade.label}</span>
    </div>
  `;
}

function timingRow(label, value, maxVal, cls) {
  const pct = maxVal > 0 ? Math.round((value / maxVal) * 100) : 0;
  return `
    <div class="timing-row">
      <span class="t-label">${label}</span>
      <div class="t-bar-wrap">
        <div class="t-bar ${cls}" style="width:${pct}%"></div>
      </div>
      <span class="t-value">${value.toFixed(3)}s</span>
    </div>
  `;
}

// ── 폴더 통계 업데이트 ─────────────────────────────────
function updateFolderStats(data) {
  // 파일이 10개 미만이면 평균 섹션 표시 안 함
  if (data.total_files < 10) return;

  const el = document.getElementById(`stats-${cssId(data.folder_name)}`);
  if (!el) return;

  const grade = getE2EGrade(data.avg_E2E);

  el.style.display = "flex";
  el.innerHTML = `
    <div class="stat-item">
      <span class="stat-label">T0 평균</span>
      <span class="stat-value">${data.avg_T0.toFixed(3)}s</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">T1 평균</span>
      <span class="stat-value">${data.avg_T1.toFixed(3)}s</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">T2 평균</span>
      <span class="stat-value">${data.avg_T2.toFixed(3)}s</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">T3 평균</span>
      <span class="stat-value">${data.avg_T3.toFixed(3)}s</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat-item stat-highlight">
      <span class="stat-label">E2E 평균 <small>(8회)</small></span>
      <span class="stat-value">${data.avg_E2E.toFixed(3)}s
        <span class="e2e-grade ${grade.cls}" style="font-size:11px;vertical-align:middle;margin-left:6px">${grade.label}</span>
      </span>
    </div>
    <div class="stat-item">
      <span class="stat-label">최소 E2E</span>
      <span class="stat-value" style="color:var(--success)">${data.min_E2E.toFixed(3)}s</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">최대 E2E</span>
      <span class="stat-value" style="color:var(--danger)">${data.max_E2E.toFixed(3)}s</span>
    </div>
    <div class="stat-item" style="margin-left:auto;font-size:11px;color:var(--primary-dark);opacity:0.7;align-self:flex-end">
      유효 ${data.valid_count}개 중 ${data.valid_count >= 2 ? data.valid_count - 2 : data.valid_count}개 평균
    </div>
  `;
}

// ── 요약 카드 업데이트 ─────────────────────────────────
function updateSummaryCards() {
  document.getElementById("sc-total-folders").textContent =
    Object.keys(state.folders).length || "—";
  document.getElementById("sc-total-files").textContent =
    state.totalFiles || "—";
  document.getElementById("sc-completed").textContent =
    state.completedFiles;

  // 전체 평균 E2E
  const allAvg = Object.values(state.stats).filter(s => s.avg_E2E > 0);
  if (allAvg.length) {
    const avg = allAvg.reduce((a, b) => a + b.avg_E2E, 0) / allAvg.length;
    document.getElementById("sc-avg-e2e").textContent = avg.toFixed(3) + "s";
  } else {
    document.getElementById("sc-avg-e2e").textContent = "—";
  }
}

// ── 사이드바 ───────────────────────────────────────────
function renderSidebar(folders) {
  const list = document.getElementById("sidebar-folder-list");
  list.innerHTML = "";

  folders.forEach(f => {
    const item = document.createElement("div");
    item.className = "sidebar-item";
    item.id = `si-${cssId(f.name)}`;
    item.innerHTML = `
      <span class="icon">🎙️</span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(f.name)}</span>
      <span class="badge">${f.file_count}</span>
    `;
    item.onclick = () => scrollToFolder(f.name);
    list.appendChild(item);
  });
}

function addSidebarFolder(folderName, fileCount) {
  const existing = document.getElementById(`si-${cssId(folderName)}`);
  if (existing) return;

  const list = document.getElementById("sidebar-folder-list");
  const item = document.createElement("div");
  item.className = "sidebar-item";
  item.id = `si-${cssId(folderName)}`;
  item.innerHTML = `
    <span class="icon">🎙️</span>
    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(folderName)}</span>
    <span class="badge" id="si-badge-${cssId(folderName)}">${fileCount}</span>
  `;
  item.onclick = () => scrollToFolder(folderName);
  list.appendChild(item);
}

function updateSidebarBadge(folderName, done, total) {
  const badge = document.getElementById(`si-badge-${cssId(folderName)}`);
  if (badge) badge.textContent = `${done}/${total}`;
}

function highlightSidebarItem(folderName) {
  document.querySelectorAll(".sidebar-item").forEach(el => el.classList.remove("active"));
  const el = document.getElementById(`si-${cssId(folderName)}`);
  if (el) el.classList.add("active");
}

function scrollToFolder(folderName) {
  const el = document.getElementById(`folder-${cssId(folderName)}`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  highlightSidebarItem(folderName);
}

// ── 모달 (파형 이미지 확대) ───────────────────────────
function openModal(src) {
  const overlay = document.getElementById("modal-overlay");
  document.getElementById("modal-img").src = src;
  overlay.classList.add("open");
}

function closeModal() {
  document.getElementById("modal-overlay").classList.remove("open");
}

// ── 기준 음원 상태 ─────────────────────────────────────
async function loadReferenceStatus() {
  try {
    const res = await fetch("/api/reference/status");
    const data = await res.json();
    renderRefStatus(data);
  } catch (_) {}
}

async function reloadReference() {
  try {
    const res = await fetch("/api/reference/reload", { method: "POST" });
    const data = await res.json();
    renderRefStatus(data);
    showToast(
      data.available ? "기준 음원을 재로드했습니다." : "기준 음원 파일이 없습니다.",
      data.available ? "success" : ""
    );
  } catch (_) {
    showToast("재로드 실패", "error");
  }
}

function renderRefStatus(data) {
  const recogEl  = document.getElementById("ref-recog-status");
  const middleEl = document.getElementById("ref-middle-status");
  if (!recogEl || !middleEl) return;

  recogEl.innerHTML  = statusDot(data.recog_loaded)  + ` 인식음 <span class="ref-label">${data.recog_loaded  ? "로드됨" : "미로드"}</span>`;
  middleEl.innerHTML = statusDot(data.middle_loaded) + ` 중간음 <span class="ref-label">${data.middle_loaded ? "로드됨" : "미로드"}</span>`;
}

function statusDot(loaded) {
  return `<span class="ref-dot ${loaded ? "ref-dot-on" : "ref-dot-off"}"></span>`;
}

// ── 사용 가이드 모달 ──────────────────────────────────
function openGuide() {
  document.getElementById("guide-overlay").classList.add("open");
}

function closeGuide(e) {
  // 배경 클릭 시 닫기 (모달 내부 클릭은 무시)
  if (e && e.target !== document.getElementById("guide-overlay")) return;
  document.getElementById("guide-overlay").classList.remove("open");
}

// ── 다운로드 ───────────────────────────────────────────
function downloadExcel() {
  window.location.href = "/api/download/excel";
}

function downloadJson() {
  window.location.href = "/api/download/json";
}

function showDownloadButtons(show) {
  document.getElementById("btn-download-excel").style.display = show ? "" : "none";
  document.getElementById("btn-download-json").style.display = show ? "" : "none";
}

// ── 유틸 ───────────────────────────────────────────────
function setButtonState(running) {
  const btn = document.getElementById("btn-analyze");
  btn.disabled = running;
  btn.textContent = running ? "⏳ 분석 중..." : "▶ 분석 시작";
}

function getE2EGrade(e2e) {
  if (e2e < E2E_GOOD) return { cls: "good", label: "빠름" };
  if (e2e < E2E_WARN) return { cls: "warning", label: "보통" };
  return { cls: "danger", label: "느림" };
}

function showEmptyState() {
  document.getElementById("folder-list").innerHTML = `
    <div class="empty-state">
      <div class="icon">📂</div>
      <h3>audio 폴더가 비어 있습니다</h3>
      <p>audio/ 폴더 안에 명령어 폴더를 만들고<br>녹음 파일(m4a, wav, mp3 등)을 넣어주세요.<br><a href="#" onclick="openGuide();return false;" style="color:var(--primary)">📖 사용 가이드 보기</a></p>
    </div>
  `;
}

function showReadyState(folders) {
  const totalFiles = folders.reduce((s, f) => s + f.file_count, 0);
  document.getElementById("sc-total-folders").textContent = folders.length;
  document.getElementById("sc-total-files").textContent = totalFiles;
  state.totalFiles = totalFiles;
}

function showToast(msg, type = "") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function cssId(str) {
  return str.replace(/[^a-zA-Z0-9가-힣]/g, "_");
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// 시작
document.addEventListener("DOMContentLoaded", init);
