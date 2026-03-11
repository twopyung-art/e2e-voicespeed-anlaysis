"""
Flask + SocketIO 메인 서버
음성 E2E 속도 자동 측정기
"""
import os
import threading
import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, send_from_directory, request, send_file, abort
from flask_socketio import SocketIO

import config
from core.audio_loader import scan_audio_folder, load_audio, normalize_audio
from core.waveform_analyzer import analyze
from core.statistics import calculate_folder_stats
from core.reference_detector import get_detector, reload_detector
from exporters import image_exporter, excel_exporter, json_exporter
from websocket.event_emitter import EventEmitter

app = Flask(__name__, static_folder="frontend", static_url_path="", template_folder="frontend")
app.config["SECRET_KEY"] = "e2e-analyzer-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
emitter = EventEmitter(socketio)

# 분석 세션 상태 저장
_session = {
    "running": False,
    "folder_results": {},
    "folder_stats": {},
    "excel_path": None,
    "json_path": None,
}


# ── REST API ──────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/folders")
def get_folders():
    """audio/ 폴더 목록 및 파일 수 반환"""
    folders = scan_audio_folder()
    result = []
    for name, files in folders.items():
        result.append({
            "name": name,
            "file_count": len(files),
            "files": [os.path.basename(f) for f in files],
        })
    return jsonify({"folders": result})


@app.route("/api/analyze", methods=["POST"])
def start_analyze():
    """분석 작업 시작"""
    if _session["running"]:
        return jsonify({"error": "이미 분석이 진행 중입니다."}), 409

    data = request.get_json(silent=True) or {}
    selected = data.get("folders", None)  # None이면 전체

    all_folders = scan_audio_folder()
    if selected:
        folders = {k: v for k, v in all_folders.items() if k in selected}
    else:
        folders = all_folders

    if not folders:
        return jsonify({"error": "audio/ 폴더에 분석할 파일이 없습니다."}), 400

    # 이전 세션 초기화
    _session.update({
        "running": True,
        "folder_results": {},
        "folder_stats": {},
        "excel_path": None,
        "json_path": None,
    })

    thread = threading.Thread(target=_run_analysis, args=(folders,), daemon=True)
    thread.start()

    return jsonify({"status": "started", "total_folders": len(folders)})


@app.route("/api/results")
def get_results():
    """현재 분석 결과 반환"""
    if _session["running"]:
        return jsonify({"status": "running"})

    return jsonify({
        "status": "complete",
        "excel_path": _session.get("excel_path"),
        "json_path": _session.get("json_path"),
    })


@app.route("/api/reference/status")
def get_reference_status():
    """기준 음원 파일 로드 상태 반환"""
    detector = get_detector()
    return jsonify(detector.status())


@app.route("/api/reference/reload", methods=["POST"])
def reload_reference():
    """reference/ 파일 변경 후 재로드"""
    detector = reload_detector()
    return jsonify(detector.status())


@app.route("/api/download/excel")
def download_excel():
    path = _session.get("excel_path")
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


@app.route("/api/download/json")
def download_json():
    path = _session.get("json_path")
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


@app.route("/results/<path:filename>")
def serve_result_file(filename):
    """results/ 폴더 정적 파일 서빙 (파형 이미지 등)"""
    return send_from_directory(config.RESULTS_DIR, filename)


# ── 분석 작업 ─────────────────────────────────────────────

def _run_analysis(folders: dict):
    """백그라운드 스레드에서 실행되는 분석 파이프라인"""
    total_files = sum(len(v) for v in folders.values())
    emitter.analysis_start(len(folders), total_files)
    socketio.sleep(0)  # eventlet에게 제어권 반환 → 메시지 즉시 전송

    folder_results = {}
    folder_stats = {}

    for idx, (command, file_paths) in enumerate(folders.items()):
        emitter.folder_start(command, len(file_paths), idx)
        socketio.sleep(0)
        results = []

        for file_path in file_paths:
            try:
                result = analyze(file_path)

                # 파형 이미지 저장
                image_path = None
                if result.error is None:
                    try:
                        y, _ = load_audio(file_path)
                        y = normalize_audio(y)
                        image_path = image_exporter.export_waveform(result, y)
                    except Exception as img_err:
                        pass  # 이미지 실패는 분석 결과에 영향 없음

                results.append(result)
                emitter.file_complete(result, image_path)
                socketio.sleep(0)  # 파일 완료 즉시 UI에 전달

            except Exception as e:
                emitter.error(command, os.path.basename(file_path), str(e))
                socketio.sleep(0)

        folder_results[command] = results
        stats = calculate_folder_stats(results)
        folder_stats[command] = stats
        emitter.folder_complete(stats)
        socketio.sleep(0)

    # 결과 파일 저장
    excel_path = excel_exporter.export(folder_results, folder_stats)
    json_path = json_exporter.export(folder_results, folder_stats)

    # 요약 데이터
    summary = {
        cmd: {
            "avg_E2E": s.avg_E2E,
            "min_E2E": s.min_E2E,
            "max_E2E": s.max_E2E,
        }
        for cmd, s in folder_stats.items()
    }

    _session.update({
        "running": False,
        "folder_results": folder_results,
        "folder_stats": folder_stats,
        "excel_path": excel_path,
        "json_path": json_path,
    })

    emitter.analysis_complete(excel_path, json_path, summary)


# ── 진입점 ────────────────────────────────────────────────

if __name__ == "__main__":
    # 결과 디렉토리 생성
    for d in [config.EXCEL_DIR, config.IMAGES_DIR, config.JSON_DIR]:
        os.makedirs(d, exist_ok=True)

    print("=" * 50)
    print(" 음성 스피커 E2E 속도 측정기")
    print(f" 브라우저에서 http://localhost:{config.PORT} 접속")
    print("=" * 50)

    socketio.run(app, host=config.HOST, port=config.PORT, debug=config.DEBUG)
