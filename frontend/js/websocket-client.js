/**
 * WebSocket 클라이언트 - SocketIO 이벤트 수신
 */

class WSClient {
  constructor(onEvent) {
    this.onEvent = onEvent;
    this.socket = null;
  }

  connect() {
    this.socket = io({ transports: ["websocket", "polling"] });

    this.socket.on("connect", () => {
      this.onEvent("connected", {});
    });

    this.socket.on("disconnect", () => {
      this.onEvent("disconnected", {});
    });

    this.socket.on("analysis_start", (data) => {
      this.onEvent("analysis_start", data);
    });

    this.socket.on("folder_start", (data) => {
      this.onEvent("folder_start", data);
    });

    this.socket.on("file_complete", (data) => {
      this.onEvent("file_complete", data);
    });

    this.socket.on("folder_complete", (data) => {
      this.onEvent("folder_complete", data);
    });

    this.socket.on("analysis_complete", (data) => {
      this.onEvent("analysis_complete", data);
    });

    this.socket.on("analysis_error", (data) => {
      this.onEvent("analysis_error", data);
    });
  }
}
