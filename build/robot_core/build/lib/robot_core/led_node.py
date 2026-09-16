#!/usr/bin/env python3
# File name   : led_node.py
# Description : Nodo ROS2 de animación de luces de policía WS2812, conmutable desde la web
# Date        : 2026/08/02
#
# La tira está cableada a GPIO12, que requiere PWM+DMA y por tanto privilegios de root.
# Ese trozo vive en scripts/led_daemon.py (servicio systemd); aquí solo se decide qué
# color va en cada pixel y se manda por el socket, de modo que este nodo sigue corriendo
# como un usuario normal dentro del launch.

import socket

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

LED_SOCKET = '/run/robot-led.sock'
NUM_PIXELS = 16

BLUE = (0, 0, 255)
RED = (255, 0, 0)
OFF = (0, 0, 0)
# Mismo patrón que el repo original (robotLight.py, policeProcessing): toda la tira
# destella 3 veces en azul, pausa, 3 veces en rojo, pausa. Cada paso dura STEP_S.
# Se pinta la tira entera con un solo color en vez de repartir colores por mitades,
# porque no todos los índices tienen un LED físico visible (el original solo usa 0-11).
STEP_S = 0.05
POLICE_SEQUENCE = [BLUE, OFF] * 3 + [OFF] * 2 + [RED, OFF] * 3 + [OFF] * 2

class PoliceLightNode(Node):
    def __init__(self):
        super().__init__('led_node')
        self.enabled = False  # Arranca apagado: se enciende desde el panel web
        self.step = 0
        self.warned = False

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.clear()

        # Suscriptor ROS2: True enciende la animación, False la apaga
        self.led_sub = self.create_subscription(
            Bool,
            '/led_cmds',
            self.led_callback,
            10
        )
        self.timer = self.create_timer(STEP_S, self.police_animation)
        self.get_logger().info('Nodo de luces de policía iniciado correctamente (apagado).')

    def send_pixels(self, pixels):
        """Manda un frame completo al demonio: 3 bytes (R, G, B) por pixel."""
        payload = bytes(component for rgb in pixels for component in rgb)
        try:
            self.sock.sendto(payload, LED_SOCKET)
            self.warned = False
        except OSError as e:
            # Un aviso por caída, no uno cada 200 ms.
            if not self.warned:
                self.get_logger().error(
                    f'No se pudo contactar el demonio de LEDs en {LED_SOCKET}: {e}. '
                    '¿Está activo robot-led.service?'
                )
                self.warned = True

    def clear(self):
        """Apaga todos los LEDs."""
        self.send_pixels([(0, 0, 0)] * NUM_PIXELS)

    def led_callback(self, msg):
        if msg.data == self.enabled:
            return
        self.enabled = msg.data
        if self.enabled:
            self.step = 0  # Siempre empieza por los destellos azules
        else:
            self.clear()
        self.get_logger().info(f'Luces {"encendidas" if self.enabled else "apagadas"}.')

    def police_animation(self):
        if not self.enabled:
            return
        self.send_pixels([POLICE_SEQUENCE[self.step]] * NUM_PIXELS)
        self.step = (self.step + 1) % len(POLICE_SEQUENCE)

def main(args=None):
    rclpy.init(args=args)
    node = PoliceLightNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.clear()  # Apagar todos los LEDs al salir
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
