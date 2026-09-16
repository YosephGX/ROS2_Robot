#!/usr/bin/env python3
# File name   : led_node.py
# Description : Nodo ROS2 de animación de luces de policía WS2812 vía SPI, conmutable desde la web
# Date        : 2026/08/02

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
import board
import neopixel_spi

class PoliceLightNode(Node):
    def __init__(self):
        super().__init__('led_node')
        self.NUM_PIXELS = 16
        self.enabled = False  # Arranca apagado: se enciende desde el panel web
        self.is_red = True

        try:
            spi = board.SPI()
            self.pixels = neopixel_spi.NeoPixel_SPI(spi, self.NUM_PIXELS, brightness=0.5, auto_write=False)
            self.clear()
            self.get_logger().info('Nodo de luces de policía iniciado correctamente (apagado).')
        except Exception as e:
            self.get_logger().error(f'Error al inicializar las luces: {e}')
            self.pixels = None

        # Suscriptor ROS2: True enciende la animación, False la apaga
        self.led_sub = self.create_subscription(
            Bool,
            '/led_cmds',
            self.led_callback,
            10
        )
        # Animacion a una frecuencia de 5Hz (0.2s)
        self.timer = self.create_timer(0.2, self.police_animation)

    def clear(self):
        """Apaga todos los LEDs."""
        if not self.pixels:
            return
        self.pixels.fill((0, 0, 0))
        self.pixels.show()

    def led_callback(self, msg):
        if msg.data == self.enabled:
            return
        self.enabled = msg.data
        if not self.enabled:
            self.clear()
        self.get_logger().info(f'Luces {"encendidas" if self.enabled else "apagadas"}.')

    def police_animation(self):
        if not self.pixels or not self.enabled:
            return
        if self.is_red:
            # Mitad de los LEDs en rojo y la otra mitad apagada
            for i in range(self.NUM_PIXELS):
                if i < self.NUM_PIXELS // 2:
                    self.pixels[i] = (255, 0, 0)  # Rojo
                else:
                    self.pixels[i] = (0, 0, 0)    # Apagado
        else:
            # Mitad de los LEDs apagados y la otra mitad en azul
            for i in range(self.NUM_PIXELS):
                if i < self.NUM_PIXELS // 2:
                    self.pixels[i] = (0, 0, 0)    # Apagado
                else:
                    self.pixels[i] = (0, 0, 255)  # Azul
        self.pixels.show()
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
