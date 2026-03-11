"""
JSON 결과 저장 모듈
"""
import os
import json
from datetime import datetime
import config


def export(folder_results: dict, folder_stats: dict, output_path: str = None) -> str:
    """
    분석 결과를 JSON 파일로 저장합니다.

    Returns:
        저장된 파일 경로
    """
    if output_path is None:
        os.makedirs(config.JSON_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config.JSON_DIR, f"E2E_분석결과_{timestamp}.json")

    data = {
        "generated_at": datetime.now().isoformat(),
        "summary": {},
        "details": {},
    }

    for command, results in folder_results.items():
        stats = folder_stats.get(command)
        data["details"][command] = [_result_to_dict(r) for r in results]
        if stats:
            data["summary"][command] = _stats_to_dict(stats)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def _result_to_dict(r) -> dict:
    return {
        "file_name": r.file_name,
        "command": r.command,
        "T0": r.T0,
        "T1": r.T1,
        "T2": r.T2,
        "T3": r.T3,
        "E2E": r.E2E,
        "audio_duration": r.audio_duration,
        "segments": r.segments,
        "segment_labels": r.segment_labels,
        "error": r.error,
    }


def _stats_to_dict(s) -> dict:
    return {
        "command": s.command,
        "total_files": s.total_files,
        "valid_count": s.valid_count,
        "avg_T0": s.avg_T0,
        "avg_T1": s.avg_T1,
        "avg_T2": s.avg_T2,
        "avg_T3": s.avg_T3,
        "avg_E2E": s.avg_E2E,
        "min_E2E": s.min_E2E,
        "max_E2E": s.max_E2E,
        "excluded_indices": s.excluded_indices,
        "error_files": s.error_files,
    }
