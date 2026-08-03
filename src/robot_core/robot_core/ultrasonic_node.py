#!/usr/bin/env python3
# File name   : ultrasonic_node.py
# Description : Nodo ROS2 de seguridad para sensor ultrasónico (HC-SR04)
# Author      : TheYoseph
# Date        : 2026/08/01

import time
import rclpy
import warnings
from rclpy.node import Node
from std_msgs.msg import Float32, Bool
from gpiozero import DistanceSensor
warnings.filterwarnings("ignore", message=".*PWMSoftwareFallback.*")

class UltrasonicNode(Node):
    def __init__(self):
        super().__init__('ultrasonic_node')
        
        # 1. Parámetros configurables en ROS2 para pines GPIO y frecuencia
        self.trig_pin = 11
        self.echo_pin = 8
        self.max_distance = 2 # Distancia máxima en metros para el sensor
        self.freq = 10
        self.safety_distance = 15
        
        # 2. Configuración de Hardware GPIO
        self.sensor = DistanceSensor(echo=self.echo_pin, trigger=self.trig_pin, max_distance=self.max_distance)
        
        # 3. Publicador ROS2
        self.distance_pub = self.create_publisher(
            Float32,
            '/safety/ultrasonic_distance',
            10
        )
        self.danger_pub = self.create_publisher(
            Bool,
            '/safety/collision_danger',
            10
        )
        
        # 4. Timer no bloqueante para lecturas periódicas
        timer_period = 1.0 / self.freq
        self.timer = self.create_timer(timer_period, self.timer_callback)
        
        self.get_logger().info(f'Nodo de Seguridad Ultrasónico iniciado (TRIG={self.trig_pin}, ECHO={self.echo_pin} @ {self.freq}Hz).')
    
    def read_distance_cm(self):
        return self.sensor.distance * 100  # Convertir a cm
    
    def timer_callback(self):
        dist = self.read_distance_cm()
        if dist >= 0:
            # 1. Publicar distancia en cm
            dist_msg = Float32()
            dist_msg.data = float(dist)
            self.distance_pub.publish(dist_msg)
            # 2. Evaluar y publicar estado de peligro de colisión
            danger_msg = Bool()
            if 0 < dist < self.safety_distance:
                danger_msg.data = True
                self.get_logger().warn(f'¡PELIGRO! Objeto detectado a {dist} cm. Frenando...')
            else:
                danger_msg.data = False
            self.danger_pub.publish(danger_msg)
            self.get_logger().debug(f'Distancia medida: {dist} cm | Peligro: {danger_msg.data}')
            
    def destroy_node(self):
        self.sensor.close()
        super().destroy_node()
        
def main(args=None):
    rclpy.init(args=args)
    node = UltrasonicNode()
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