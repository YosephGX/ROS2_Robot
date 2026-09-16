#!/usr/bin/env python3
# File name   : servo_node.py
# Description : Nodo ROS2 de Control de Servos (Cabeza: tilt)
# Author      : TheYoseph
# Date        : 2026/08/01

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32

from adafruit_pca9685 import PCA9685
from adafruit_motor import servo
from board import SCL, SDA
import busio

TILT_CHANNEL = 11
# Más allá de 95° el cable de la cámara se masca contra el chasis.
TILT_MAX_ANGLE = 95

class ServoNode(Node):
    def __init__(self):
        super().__init__('servo_node')
        # 1. Configuración de Hardware I2C / PCA9685
        self.i2c = busio.I2C(SCL, SDA)
        self.pwm_servo = PCA9685(self.i2c, address=0x40)
        self.pwm_servo.frequency = 50

        # Cabeza: Canal 11 (Tilt) — único servo en esta variante (sin pan, sin brazo)
        self.tilt_servo = servo.Servo(
            self.pwm_servo.channels[TILT_CHANNEL],
            min_pulse=500,
            max_pulse=2400,
            actuation_range=180
        )

        # Suscriptor ROS2: Para el comando de tilt de la Cabeza (Cámara)
        self.head_sub = self.create_subscription(
            Int32,
            '/head_cmds',
            self.head_callback,
            10
        )
        # 3. Posición Inicial (Home)
        self.move_to_home()
        self.get_logger().info('Nodo ServoNode ROS2 iniciado correctamente.')

    def set_tilt_angle(self, angle):
        """Aplica límites de seguridad 0°-95° y mueve el servo de tilt."""
        angle = max(0, min(TILT_MAX_ANGLE, angle))
        self.tilt_servo.angle = angle

    def head_callback(self, msg):
        """Espera el ángulo de tilt (0-95) como entero."""
        self.set_tilt_angle(msg.data)
        self.get_logger().debug(f'Cabeza (tilt) movida a: {msg.data}')

    def move_to_home(self):
        """Posición inicial neutra de la cabeza."""
        self.set_tilt_angle(90)
            
    def destroy_node(self):
        # Limpieza física de motores al apagar el nodo
        self.pwm_servo.deinit()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = ServoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()