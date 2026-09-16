#!/usr/bin/env python3
# File name   : server_node.py
# Description : Nodo ROS2 + Servidor Web FastAPI con Interfaz Gráfica (Puerto único)
# Author      : TheYoseph
# Date        : 2026/08/01

import os
import threading
import uvicorn
import psutil
import httpx
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Int32

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any

CAMERA_STREAM_URL = "http://127.0.0.1:8090/stream.mjpg"

robot_state = {
    "tilt_angle": 90,
}

# -- MODELO DE COMANDOS --
class RobotCommand(BaseModel):
    action: str          # e.g., "move", "head", "set_speed"
    value: Optional[Any] = None
    
# -- NODO ROS2 --
class WebBridgeNode(Node):
    def __init__(self):
        super().__init__('server_node')
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.head_pub = self.create_publisher(Int32, '/head_cmds', 10)

        # Estado actual del servo de tilt
        self.tilt_angle = 90
        self.get_logger().info('WebBridgeNode ROS2 iniciado correctamente.')

    def publish_twist(self, linear_x: float, angular_z: float):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_vel_pub.publish(msg)

    def publish_head(self, tilt: int):
        self.tilt_angle = tilt
        msg = Int32()
        msg.data = tilt
        self.head_pub.publish(msg)

# -- INTERFAZ GRÁFICA (HTML + CSS + JS) --
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Robot Control Center - ROS2</title>
    <style>
        :root { --bg: #1a1a1a; --card: #2d2d2d; --accent: #3b82f6; --text: #f3f4f6; }
        body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 800px; width: 100%; display: grid; gap: 20px; grid-template-columns: 1fr; }
        @media (min-width: 600px) { .container { grid-template-columns: 1fr 1fr; } }
        .card { background: var(--card); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h2 { margin-top: 0; font-size: 1.2rem; border-bottom: 2px solid var(--accent); padding-bottom: 8px; }
        .status { padding: 8px 12px; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 15px; }
        .connected { background: #059669; }
        .disconnected { background: #dc2626; }
        .dpad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; max-width: 220px; margin: 20px auto; }
        .btn { background: #4b5563; color: white; border: none; padding: 15px; border-radius: 8px; font-size: 1.1rem; cursor: pointer; user-select: none; transition: background 0.1s; }
        .btn:active, .btn.active { background: var(--accent); }
        .btn-stop { background: #ef4444; font-weight: bold; }
        .btn-stop:active { background: #b91c1c; }
        .slider-group { margin-bottom: 15px; }
        .slider-group label { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.9rem; }
        input[type=range] { width: 100%; accent-color: var(--accent); }
    </style>
</head>
<body>
    <h1>🤖 Control Center ROS2</h1>
    <div id="status" class="status disconnected">Desconectado</div>

    <div class="container">
        <!-- Tarjeta de Telemetria -->
        <div class="card" style="border: 1px solid #ccc; padding: 10px; grid-column: 1 / -1;">
            <div id="telemetry" style="display: flex; flex-direction: column; align-items: center;">
                <p>🌡️ Temp: <span id="temp-val">--</span> °C - 🧠 CPU: <span id="cpu-val">--</span> % - 💾 RAM: <span id="ram-val">--</span> %</p>
            </div>
        </div>

        <!-- Tarjeta de Cámara -->
        <div class="card" style="grid-column: 1 / -1;">
            <h2>Cámara</h2>
            <img id="camera-feed" src="" alt="Video de la cámara" style="width: 100%; border-radius: 8px; background: #000;">
        </div>

        <!-- Tarjeta de Locomoción -->
        <div class="card">
            <h2>Locomoción (W, A, S, D)</h2>
            <div class="dpad">
                <div></div>
                <button class="btn" id="btn-forward" onmousedown="setMove(1, null)" onmouseup="setMove(0, null)" ontouchstart="setMove(1, null)" ontouchend="setMove(0, null)">W / ▲</button>
                <div></div>
                <button class="btn" id="btn-left" onmousedown="setMove(null, 1)" onmouseup="setMove(null, 0)" ontouchstart="setMove(null, 1)" ontouchend="setMove(null, 0)">A / ◀</button>
                <button class="btn btn-stop" onclick="stopMove()">STOP</button>
                <button class="btn" id="btn-right" onmousedown="setMove(null, -1)" onmouseup="setMove(null, 0)" ontouchstart="setMove(null, -1)" ontouchend="setMove(null, 0)">D / ▶</button>
                <div></div>
                <button class="btn" id="btn-backward" onmousedown="setMove(-1, null)" onmouseup="setMove(0, null)" ontouchstart="setMove(-1, null)" ontouchend="setMove(0, null)">S / ▼</button>
                <div></div>
            </div>
        </div>

        <!-- Tarjeta de Servos -->
        <div class="card">
            <h2>Cabeza (Cámara)</h2>
            <div class="slider-group">
                <label><span>Cabeza - Tilt (Arr/Aba)</span><span id="val-tilt">90°</span></label>
                <input type="range" id="tilt" min="0" max="95" value="90" oninput="updateServos()">
            </div>
        </div>
    </div>

    <script>
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/control`;
        let moveState = { x: 0, z: 0 };
        let ws;
        
        function connect() {
            ws = new WebSocket(wsUrl);
            const statusEl = document.getElementById('status');

            ws.onopen = () => {
                statusEl.textContent = 'Conectado al Robot';
                statusEl.className = 'status connected';
            };
            ws.onclose = () => {
                statusEl.textContent = 'Desconectado - Reconectando...';
                statusEl.className = 'status disconnected';
                setTimeout(connect, 2000);
            };
        }

        // Cámara por WebSocket (frames binarios): a diferencia de un <img> con stream
        // HTTP multipart, esto no se bufferea al pasar por un túnel/proxy como Cloudflare.
        let camWs;
        let lastFrameUrl = null;

        function connectCamera() {
            const camWsUrl = `${wsProtocol}//${window.location.host}/ws/camera`;
            camWs = new WebSocket(camWsUrl);
            camWs.binaryType = 'blob';
            camWs.onmessage = (event) => {
                const url = URL.createObjectURL(event.data);
                document.getElementById('camera-feed').src = url;
                if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
                lastFrameUrl = url;
            };
            camWs.onclose = () => {
                setTimeout(connectCamera, 2000);
            };
        }
        
        function setMove(x, z) {
            if (x !== null) moveState.x = x;
            if (z !== null) moveState.z = z;
            sendCmd('move', moveState);
        }
        
        function stopMove() {
            moveState = { x: 0, z: 0 };
            sendCmd('move', moveState);
        }

        function sendCmd(action, value = null) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action, value }));
            }
        }
        
        function updateServos() {
            const tilt = parseInt(document.getElementById('tilt').value);
            document.getElementById('val-tilt').textContent = tilt + '°';
            sendCmd('head', tilt);
        }
        
        function fetchTelemetry() {
            fetch('/api/telemetry')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('temp-val').innerText = data.temp;
                    document.getElementById('cpu-val').innerText = data.cpu;
                    document.getElementById('ram-val').innerText = data.memory;
                    
                    if (data.temp > 70) document.getElementById('temp-val').style.color = "red";
                    if (data.cpu > 80) document.getElementById('cpu-val').style.color = "red";
                    if (data.memory > 80) document.getElementById('ram-val').style.color = "red";
                }).catch(err => console.error('Error fetching telemetry:', err));
        }

        // Control por teclado
        document.addEventListener('keydown', (e) => {
            if (e.repeat) return;
            let changed = false;
            if (e.key === 'w' || e.key === 'ArrowUp') { moveState.x = 1.0; changed = true; }
            if (e.key === 's' || e.key === 'ArrowDown') { moveState.x = -1.0; changed = true; }
            if (e.key === 'a' || e.key === 'ArrowLeft') { moveState.z = 1.0; changed = true; }
            if (e.key === 'd' || e.key === 'ArrowRight') { moveState.z = -1.0; changed = true; }
            if (e.key === ' ' || e.key === 'Spacebar') { moveState.x = 0; moveState.z = 0; changed = true; }
            if (changed) sendCmd('move', moveState);
        });

        document.addEventListener('keyup', (e) => {
            let changed = false;
            if ((e.key === 'w' || e.key === 'ArrowUp') && moveState.x === 1.0) { moveState.x = 0; changed = true; }
            if ((e.key === 's' || e.key === 'ArrowDown') && moveState.x === -1.0) { moveState.x = 0; changed = true; }
            if ((e.key === 'a' || e.key === 'ArrowLeft') && moveState.z === 1.0) { moveState.z = 0; changed = true; }
            if ((e.key === 'd' || e.key === 'ArrowRight') && moveState.z === -1.0) { moveState.z = 0; changed = true; }
            if (changed) sendCmd('move', moveState);
        });
        
        window.addEventListener('DOMContentLoaded', (event) => {
            fetchTelemetry();
            fetch('/api/state')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('tilt').value = data.tilt_angle;
                    document.getElementById('val-tilt').textContent = data.tilt_angle + '°';
                    console.log('Robot state loaded:', data);
                }).catch(err => console.error('Error fetching robot state:', err));
            setInterval(fetchTelemetry, 3000);
        });
        connect();
        connectCamera();
    </script>
</body>
</html>
"""

# -- SERVIDOR FASTAPI --
app = FastAPI(title="Robot Controller Server")
ros_node: Optional[WebBridgeNode] = None

@app.get("/", response_class=FileResponse)
async def get_interface():
    """ Sirve el panel de control web desde la raíz del servidor """
    ruta_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    return FileResponse(ruta_html, media_type='text/html')

@app.get("/api/state")
def get_robot_state():
    return JSONResponse(content=robot_state)

@app.get("/stream.mjpg")
async def camera_stream():
    """ Reenvía el stream MJPEG de camera_node (solo escucha en localhost) hacia el cliente.
    Sirve para pruebas directas en LAN; a través de un túnel (Cloudflare, etc.) usar /ws/camera,
    ya que los proxies suelen bufferear streams HTTP multipart de larga duración. """
    client = httpx.AsyncClient(timeout=None)
    try:
        upstream = await client.send(
            client.build_request("GET", CAMERA_STREAM_URL), stream=True
        )
    except httpx.ConnectError:
        await client.aclose()
        return JSONResponse(status_code=503, content={"error": "Cámara no disponible"})

    async def relay():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type=upstream.headers.get("content-type", "multipart/x-mixed-replace"),
    )

async def _iter_mjpeg_frames(upstream):
    """ Reensambla el stream multipart de camera_node en frames JPEG individuales. """
    buffer = b""
    async for chunk in upstream.aiter_raw():
        buffer += chunk
        while True:
            header_end = buffer.find(b"\r\n\r\n")
            if header_end == -1:
                break
            length = None
            for line in buffer[:header_end].split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":", 1)[1].strip())
                    break
            if length is None:
                # No era un encabezado de frame (p.ej. el boundary inicial); descartar y seguir
                buffer = buffer[header_end + 4:]
                continue
            frame_start = header_end + 4
            frame_end = frame_start + length
            if len(buffer) < frame_end + 2:  # +2 por el \r\n final de cada parte
                break
            yield buffer[frame_start:frame_end]
            buffer = buffer[frame_end + 2:]

@app.websocket("/ws/camera")
async def camera_ws(websocket: WebSocket):
    """ Envía cada frame JPEG como mensaje binario por WebSocket en vez de un stream HTTP:
    los proxies/túneles (Cloudflare incluido) manejan WebSockets en vivo sin bufferear,
    a diferencia de una respuesta HTTP multipart de larga duración. """
    await websocket.accept()
    client = httpx.AsyncClient(timeout=None)
    try:
        upstream = await client.send(
            client.build_request("GET", CAMERA_STREAM_URL), stream=True
        )
    except httpx.ConnectError:
        await websocket.close(code=1011)
        await client.aclose()
        return

    try:
        async for frame in _iter_mjpeg_frames(upstream):
            await websocket.send_bytes(frame)
    except WebSocketDisconnect:
        pass
    finally:
        await upstream.aclose()
        await client.aclose()

@app.get("/api/telemetry")
def get_telemetry():
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory_info = psutil.virtual_memory().percent
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            cpu_temp = float(f.read().strip()) / 1000.0
    except Exception:
        cpu_temp = 0.0
    return JSONResponse(content={
        "cpu": cpu_usage,
        "memory": memory_info,
        "temp": cpu_temp,
    })

@app.websocket("/ws/control")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Validación automática de datos recibidos
            data = await websocket.receive_json()
            cmd = RobotCommand(**data)
            if not ros_node:
                continue
            
            # Despacho de comandos hacia tópicos ROS2
            if cmd.action == "move" and isinstance(cmd.value, dict):
                # Leemos la X y la Z, si no vienen usamos 0.0
                linear_x = float(cmd.value.get("x", 0.0))
                angular_z = float(cmd.value.get("z", 0.0))
                ros_node.publish_twist(linear_x, angular_z)
            elif cmd.action == "head" and isinstance(cmd.value, (int, float)):
                tilt = int(cmd.value)
                ros_node.publish_head(tilt)
                robot_state["tilt_angle"] = tilt
    except WebSocketDisconnect:
        if ros_node:
            ros_node.publish_twist(0.0, 0.0)  # Freno de seguridad por desconexión
            
def main(args=None):
    global ros_node
    rclpy.init(args=args)
    ros_node = WebBridgeNode()

    # Hilo secundario para que rclpy.spin escuche/publique sin bloquear Uvicorn
    ros_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    ros_thread.start()

    try:
        # Escucha en 0.0.0.0 puerto 5000 para acceso desde red local
        uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info", proxy_headers=True, forwarded_allow_ips="*")
    except KeyboardInterrupt:
        pass
    finally:
        ros_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()