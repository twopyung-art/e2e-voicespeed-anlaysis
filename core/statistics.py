"""
통계 계산 모듈
- 최대/최소 제외 8회 평균 (Trimmed Mean)
- 폴더별 통계 집계
"""
from dataclasses import dataclass, field
from typing import List, Optional
import config


@dataclass
class FolderStats:
    command: str
    total_files: int = 0
    valid_count: int = 0        # 분석 성공한 파일 수
    excluded_indices: list = field(default_factory=list)  # 제외된 파일 인덱스 (최대/최소)
    avg_T0: float = 0.0
    avg_T1: float = 0.0
    avg_T2: float = 0.0
    avg_T3: float = 0.0
    avg_E2E: float = 0.0
    min_E2E: float = 0.0
    max_E2E: float = 0.0
    error_files: list = field(default_factory=list)


def trimmed_mean(values: list, trim: int = None) -> float:
    """
    최대/최소 각 trim개를 제외한 평균을 계산합니다.
    유효 값이 trim*2개 이하면 그냥 전체 평균을 반환합니다.
    """
    if trim is None:
        trim = config.TRIM_COUNT

    if not values:
        return 0.0

    sorted_vals = sorted(values)
    if len(sorted_vals) <= trim * 2:
        return round(sum(sorted_vals) / len(sorted_vals), 3)

    trimmed = sorted_vals[trim:-trim]
    return round(sum(trimmed) / len(trimmed), 3)


def get_trim_indices(values: list, trim: int = None) -> list:
    """
    제외할 인덱스 목록(최대/최소 각 trim개)을 반환합니다.
    """
    if trim is None:
        trim = config.TRIM_COUNT

    if len(values) <= trim * 2:
        return []

    # (값, 원본인덱스) 정렬
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    excluded = set()
    for i in range(trim):
        excluded.add(indexed[i][0])           # 최소 trim개
        excluded.add(indexed[-(i + 1)][0])    # 최대 trim개
    return sorted(excluded)


def calculate_folder_stats(results: list) -> FolderStats:
    """
    폴더 내 분석 결과 목록으로 통계를 계산합니다.

    Args:
        results: list[AnalysisResult]

    Returns:
        FolderStats
    """
    if not results:
        return FolderStats(command="")

    command = results[0].command
    stats = FolderStats(command=command, total_files=len(results))

    valid = [(i, r) for i, r in enumerate(results) if r.error is None]
    error_files = [r.file_name for r in results if r.error is not None]

    stats.valid_count = len(valid)
    stats.error_files = error_files

    if not valid:
        return stats

    e2e_values = [r.E2E for _, r in valid]
    excluded_local_indices = get_trim_indices(e2e_values)

    # 전체 results 인덱스로 변환
    stats.excluded_indices = [valid[i][0] for i in excluded_local_indices]

    # 제외 후 유효 결과만으로 평균 계산
    included = [r for i, (_, r) in enumerate(valid) if i not in excluded_local_indices]

    if not included:
        return stats

    stats.avg_T0 = round(sum(r.T0 for r in included) / len(included), 3)
    stats.avg_T1 = round(sum(r.T1 for r in included) / len(included), 3)
    stats.avg_T2 = round(sum(r.T2 for r in included) / len(included), 3)
    stats.avg_T3 = round(sum(r.T3 for r in included) / len(included), 3)
    stats.avg_E2E = round(sum(r.E2E for r in included) / len(included), 3)
    stats.min_E2E = round(min(r.E2E for r in included), 3)
    stats.max_E2E = round(max(r.E2E for r in included), 3)

    return stats
