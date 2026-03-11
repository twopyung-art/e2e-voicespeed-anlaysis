"""
SocketIO 이벤트 발송 모듈
"""


class EventEmitter:
    def __init__(self, socketio):
        self.sio = socketio

    def analysis_start(self, total_folders: int, total_files: int):
        self.sio.emit("analysis_start", {
            "total_folders": total_folders,
            "total_files": total_files,
        })

    def folder_start(self, folder_name: str, file_count: int, index: int):
        self.sio.emit("folder_start", {
            "folder_name": folder_name,
            "file_count": file_count,
            "index": index,
        })

    def file_complete(self, result, image_path: str = None):
        rel_image = None
        if image_path:
            import os, config
            try:
                rel_image = os.path.relpath(image_path, config.BASE_DIR).replace("\\", "/")
            except Exception:
                rel_image = image_path.replace("\\", "/")

        self.sio.emit("file_complete", {
            "folder_name": result.command,
            "file_name": result.file_name,
            "T0": result.T0,
            "T1": result.T1,
            "T2": result.T2,
            "T3": result.T3,
            "E2E": result.E2E,
            "error": result.error,
            "image_path": rel_image,
            "segment_labels": result.segment_labels,
            "detection_mode": result.detection_mode,
        })

    def folder_complete(self, stats):
        self.sio.emit("folder_complete", {
            "folder_name": stats.command,
            "total_files": stats.total_files,
            "valid_count": stats.valid_count,
            "avg_T0": stats.avg_T0,
            "avg_T1": stats.avg_T1,
            "avg_T2": stats.avg_T2,
            "avg_T3": stats.avg_T3,
            "avg_E2E": stats.avg_E2E,
            "min_E2E": stats.min_E2E,
            "max_E2E": stats.max_E2E,
            "error_files": stats.error_files,
        })

    def analysis_complete(self, excel_path: str, json_path: str, summary: dict):
        import os, config
        def rel(p):
            try:
                return os.path.relpath(p, config.BASE_DIR).replace("\\", "/")
            except Exception:
                return p

        self.sio.emit("analysis_complete", {
            "excel_path": rel(excel_path),
            "json_path": rel(json_path),
            "summary": summary,
        })

    def error(self, folder_name: str, file_name: str, message: str):
        self.sio.emit("analysis_error", {
            "folder_name": folder_name,
            "file_name": file_name,
            "message": message,
        })
