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

class PoliceLightNode(Node):
    def __init__(self):
        super().__init__('led_node')
        self.enabled = False  # Arranca apagado: se enciende desde el panel web
        self.is_red = True
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
        # Animacion a una frecuencia de 5Hz (0.2s)
        self.timer = self.create_timer(0.2, self.police_animation)
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
        if not self.enabled:
            self.clear()
        self.get_logger().info(f'Luces {"encendidas" if self.enabled else "apagadas"}.')

    def police_animation(self):
        if not self.enabled:
            return
        half = NUM_PIXELS // 2
        if self.is_red:
            # Mitad de los LEDs en rojo y la otra mitad apagada
            pixels = [(255, 0, 0)] * half + [(0, 0, 0)] * (NUM_PIXELS - half)
        else:
            # Mitad de los LEDs apagados y la otra mitad en azul
            pixels = [(0, 0, 0)] * half + [(0, 0, 255)] * (NUM_PIXELS - half)
        self.send_pixels(pixels)
        self.is_red = not self.is_red

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
