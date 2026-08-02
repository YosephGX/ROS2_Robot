#!/usr/bin/env python3
# File name   : server_node.py
# Description : Nodo ROS2 + Servidor Web FastAPI con Interfaz Gráfica (Puerto único)
# Author      : TheYoseph
# Date        : 2026/08/01

import threading
import uvicorn
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Int32MultiArray

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Any

# -- MODELO DE COMANDOS --
class RobotCommand(BaseModel):
    action: str          # e.g., "forward", "armup", "set_speed"
    value: Optional[Any] = None
    
# -- NODO ROS2 --
class WebBridgeNode(Node):
    def __init__(self):
        super().__init__('server_node')
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.arm_pub = self.create_publisher(Int32MultiArray, '/arm_cmds', 10)
        self.head_pub = self.create_publisher(Int32MultiArray, '/head_cmds', 10)
        
        # Estado actual de servos para enviar en bloque
        self.head_angles = [90, 90]        # [Pan, Tilt]
        self.arm_angles = [90, 90, 90]     # [Hombro, Mano, Garra]
        self.get_logger().info('WebBridgeNode ROS2 iniciado correctamente.')

    def publish_twist(self, linear_x: float, angular_z: float):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_vel_pub.publish(msg)
        
    def publish_head(self, pan: int, tilt: int):
        self.head_angles = [pan, tilt]
        msg = Int32MultiArray()
        msg.data = self.head_angles
        self.head_pub.publish(msg)
        
    def publish_arm(self, hombro: int, mano: int, garra: int):
        self.arm_angles = [hombro, mano, garra]
        msg = Int32MultiArray()
        msg.data = self.arm_angles
        self.arm_pub.publish(msg)

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
        <!-- Tarjeta de Locomoción -->
        <div class="card">
            <h2>Locomoción (W, A, S, D)</h2>
            <div class="dpad">
                <div></div>
                <button class="btn" id="btn-forward" onmousedown="sendCmd('move', {dir: 'forward'})" onmouseup="sendCmd('move', {dir: 'stop'})">W / ▲</button>
                <div></div>
                <button class="btn" id="btn-left" onmousedown="sendCmd('move', {dir: 'left'})" onmouseup="sendCmd('move', {dir: 'stop'})">A / ◀</button>
                <button class="btn btn-stop" onclick="sendCmd('move', {dir: 'stop'})">STOP</button>
                <button class="btn" id="btn-right" onmousedown="sendCmd('move', {dir: 'right'})" onmouseup="sendCmd('move', {dir: 'stop'})">D / ▶</button>
                <div></div>
                <button class="btn" id="btn-backward" onmousedown="sendCmd('move', {dir: 'backward'})" onmouseup="sendCmd('move', {dir: 'stop'})">S / ▼</button>
                <div></div>
            </div>
        </div>

        <!-- Tarjeta de Servos -->
        <div class="card">
            <h2>Cabeza y Brazo</h2>
            <div class="slider-group">
                <label><span>Cabeza - Pan (Izq/Der)</span><span id="val-pan">90°</span></label>
                <input type="range" id="pan" min="0" max="180" value="90" oninput="updateServos()">
            </div>
            <div class="slider-group">
                <label><span>Cabeza - Tilt (Arr/Aba)</span><span id="val-tilt">90°</span></label>
                <input type="range" id="tilt" min="0" max="180" value="90" oninput="updateServos()">
            </div>
            <hr style="border-color: #4b5563; margin: 15px 0;">
            <div class="slider-group">
                <label><span>Brazo - Hombro</span><span id="val-hombro">90°</span></label>
                <input type="range" id="hombro" min="0" max="180" value="90" oninput="updateServos()">
            </div>
            <div class="slider-group">
                <label><span>Brazo - Mano</span><span id="val-mano">90°</span></label>
                <input type="range" id="mano" min="0" max="180" value="90" oninput="updateServos()">
            </div>
            <div class="slider-group">
                <label><span>Brazo - Garra</span><span id="val-garra">90°</span></label>
                <input type="range" id="garra" min="0" max="180" value="90" oninput="updateServos()">
            </div>
        </div>
    </div>

    <script>
        const wsUrl = `ws://${window.location.host}/ws/control`;
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

        function sendCmd(action, value = null) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action, value }));
            }
        }

        function updateServos() {
            const pan = parseInt(document.getElementById('pan').value);
            const tilt = parseInt(document.getElementById('tilt').value);
            const hombro = parseInt(document.getElementById('hombro').value);
            const mano = parseInt(document.getElementById('mano').value);
            const garra = parseInt(document.getElementById('garra').value);

            document.getElementById('val-pan').textContent = pan + '°';
            document.getElementById('val-tilt').textContent = tilt + '°';
            document.getElementById('val-hombro').textContent = hombro + '°';
            document.getElementById('val-mano').textContent = mano + '°';
            document.getElementById('val-garra').textContent = garra + '°';

            sendCmd('head', [pan, tilt]);
            sendCmd('arm', [hombro, mano, garra]);
        }

        // Control por teclado
        document.addEventListener('keydown', (e) => {
            if (e.repeat) return;
            if (e.key === 'w' || e.key === 'ArrowUp') sendCmd('move', {dir: 'forward'});
            if (e.key === 's' || e.key === 'ArrowDown') sendCmd('move', {dir: 'backward'});
            if (e.key === 'a' || e.key === 'ArrowLeft') sendCmd('move', {dir: 'left'});
            if (e.key === 'd' || e.key === 'ArrowRight') sendCmd('move', {dir: 'right'});
            if (e.key === ' ' || e.key === 'Spacebar') sendCmd('move', {dir: 'stop'});
        });

        document.addEventListener('keyup', (e) => {
            if (['w','s','a','d','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key)) {
                sendCmd('move', {dir: 'stop'});
            }
        });

        connect();
    </script>
</body>
</html>
"""

# -- SERVIDOR FASTAPI --
app = FastAPI(title="Robot Controller Server")
ros_node: Optional[WebBridgeNode] = None

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """ Sirve el panel de control web desde la raíz del servidor """
    return HTML_CONTENT

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
                direction = cmd.value.get("dir", "stop")
                if direction == "forward":
                    ros_node.publish_twist(1.0, 0.0)
                elif direction == "backward":
                    ros_node.publish_twist(-1.0, 0.0)
                elif direction == "left":
                    ros_node.publish_twist(0.0, 1.0)
                elif direction == "right":
                    ros_node.publish_twist(0.0, -1.0)
                else:
                    ros_node.publish_twist(0.0, 0.0)
            elif cmd.action == "head" and isinstance(cmd.value, list) and len(cmd.value) == 2:
                ros_node.publish_head(int(cmd.value[0]), int(cmd.value[1]))
            elif cmd.action == "arm" and isinstance(cmd.value, list) and len(cmd.value) == 3:
                ros_node.publish_arm(int(cmd.value[0]), int(cmd.value[1]), int(cmd.value[2]))            
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
        # Escucha en 0.0.0.0 puerto 8000 para acceso desde red local
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        pass
    finally:
        ros_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()