#!/usr/bin/env python3
# File name   : servo_node.py
# Description : Nodo ROS2 de Control de Servos (Brazo y cabeza)
# Author      : TheYoseph
# Date        : 2026/08/01

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, Bool

from adafruit_pca9685 import PCA9685
from adafruit_motor import servo
from board import SCL, SDA
import busio

class ServoNode(Node):
    def __init__(self):
        super().__init__('servo_node')
        # 1. Configuración de Hardware I2C / PCA9685
        self.i2c = busio.I2C(SCL, SDA)
        self.pwm_servo = PCA9685(self.i2c, address=0x40)
        self.pwm_servo.frequency = 50
        
        # Mapeo de canales y creación de objetos Servo
        # Cabeza: Canal 11 (Tilt), Canal 14 (Pan)
        # Brazo: Canal 12 (Hombro), Canal 13 (Mano), Canal 15 (Garra)
        self.servos = {}
        for ch in [11, 12, 13, 14, 15]:
            self.servos[ch] = servo.Servo(
                self.pwm_servo.channels[ch],
                min_pulse=500,
                max_pulse=2400,
                actuation_range=180
            )
        
        # Suscriptor ROS2 1: Para los comandos del Brazo Robótico
        self.arm_sub = self.create_subscription(
            Int32MultiArray,
            '/arm_cmds',
            self.arm_callback,
            10
        )
        # Suscriptor ROS2 2: Para los comandos de la Cabeza (Cámara/Sensor Ultrasónico)
        self.head_sub = self.create_subscription(
            Int32MultiArray,
            '/head_cmds',
            self.head_callback,
            10
        )
        # Suscriptor ROS2 3: Para el control de la Garra
        self.claw_sub = self.create_subscription(
            Bool,
            '/claw_cmd',
            self.claw_callback,
            10
        )
        # 3. Posiciones Iniciales (Home)
        self.move_to_home()
        self.get_logger().info('Nodo ServoNode ROS2 iniciado correctamente.')
        
    def set_servo_angle(self, ch, angle):
        """Aplica límites de seguridad 0°-180° y mueve el servo."""
        angle = max(0, min(180, angle))
        if ch in self.servos:
            self.servos[ch].angle = angle
            
    def claw_callback(self, msg):
        """ Controla la garra mediante un mensaje booleano: True = cerrar, False = abrir."""
        if msg.data:
            self.set_servo_angle(15, 8)  # Garra cerrada
            self.get_logger().debug('Garra cerrada.')
        else:
            self.set_servo_angle(15, 90)   # Garra abierta
            self.get_logger().debug('Garra abierta.')
            
    def arm_callback(self, msg):
        """
        Espera un arreglo de 3 valores: [Hombro (12), Mano (13), Garra (15)]
        Ejemplo de mensaje: [90, 45, 120]
        """
        if len(msg.data) >= 2:
            self.set_servo_angle(12, msg.data[0])
            self.set_servo_angle(13, msg.data[1])
            self.get_logger().debug(f'Brazo movido a: {msg.data[:2]}')
            
    def head_callback(self, msg):
        """
        Espera un arreglo de 2 valores: [Pan/Izquierda-Derecha (14), Tilt/Arriba-Abajo (11)]
        Ejemplo de mensaje: [90, 100]
        """
        if len(msg.data) >= 2:
            self.set_servo_angle(14, msg.data[0])
            self.set_servo_angle(11, msg.data[1])
            self.get_logger().debug(f'Cabeza movida a: {msg.data[:2]}')
            
    def move_to_home(self):
        """Posición inicial neutra del robot (90 grados para cabeza, etc.)"""
        home_positions = {11: 90, 12: 90, 13: 90, 14: 90, 15: 90}
        for ch, ang in home_positions.items():
            self.set_servo_angle(ch, ang)
            
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