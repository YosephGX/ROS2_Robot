#!/usr/bin/env python3
# File name   : led_node.py
# Description : Nodo ROS2 temporal para animación de luces de policía WS2812 vía SPI
# Date        : 2026/08/02

import rclpy
from rclpy.node import Node
import board
import neopixel_spi

class PoliceLightNode(Node):
    def __init__(self):
        super().__init__('led_node')
        self.NUM_PIXELS = 16
        
        try:
            spi = board.SPI()
            self.pixels = neopixel_spi.NeoPixel_SPI(spi, self.NUM_PIXELS, brightness=0.5, auto_write=False)
            self.get_logger().info('Nodo de luces de policía iniciado correctamente.')
            # Animacion a una frecuencia de 5Hz (0.2s)
            self.timer = self.create_timer(0.2, self.police_animation)
            self.is_red = True
        except Exception as e:
            self.get_logger().error(f'Error al inicializar las luces: {e}')
            self.pixels = None
            
    def police_animation(self):
        if not self.pixels:
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
        if node.pixels:
            node.pixels.fill((0, 0, 0))  # Apagar todos los LEDs al salir
            node.pixels.show()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
            
if __name__ == '__main__':
    main()