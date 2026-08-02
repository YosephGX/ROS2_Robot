#!/usr/bin/env python3
# File name   : ultrasonic_node.py
# Description : Nodo ROS2 de seguridad para sensor ultrasónico (HC-SR04)
# Author      : TheYoseph
# Date        : 2026/08/01

import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool
import RPi.GPIO as GPIO

class UltrasonicNode(Node):
    def __init__(self):
        super().__init__('ultrasonic_node')
        
        # 1. Parámetros configurables en ROS2 para pines GPIO y frecuencia
        self.declare_parameter('trig_pin', 11)
        self.declare_parameter('echo_pin', 8)
        self.declare_parameter('read_frequency_hz', 10.0)
        self.declare_parameter('safety_distance_cm', 20.0)  # Distancia de frenado del monitor pasivo
        self.trig_pin = self.get_parameter('trig_pin').value
        self.echo_pin = self.get_parameter('echo_pin').value
        freq = self.get_parameter('read_frequency_hz').value
        self.safety_distance = self.get_parameter('safety_distance_cm').value
        
        # 2. Configuración de Hardware GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trig_pin, GPIO.LOW)
        
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
        timer_period = 1.0 / freq
        self.timer = self.create_timer(timer_period, self.timer_callback)
        
        self.get_logger().info(
            f'Nodo de Seguridad Ultrasónico iniciado (TRIG={self.trig_pin}, ECHO={self.echo_pin} @ {freq}Hz).'
        )
    
    def read_distance_cm(self):
        """Genera el pulso ultrasónico y calcula la distancia en centímetros."""
        # Pulso de 10 microsegundos
        GPIO.output(self.trig_pin, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.trig_pin, GPIO.LOW)
        
        start_time = time.time()
        stop_time = time.time()
        timeout = start_time + 0.04  # Timeout de seguridad (~6 metros max)
        
        # Esperar inicio del eco
        while GPIO.input(self.echo_pin) == 0:
            start_time = time.time()
            if start_time > timeout:
                return -1.0
                
        # Esperar fin del eco
        while GPIO.input(self.echo_pin) == 1:
            stop_time = time.time()
            if stop_time > timeout:
                return -1.0
                
        elapsed_time = stop_time - start_time
        # Velocidad del sonido = 34300 cm/s (dividir por 2 por ida y vuelta)
        distance = (elapsed_time * 34300.0) / 2.0
        return round(distance, 2)
    
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
        GPIO.cleanup([self.trig_pin, self.echo_pin])
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
        rclpy.shutdown()

if __name__ == '__main__':
    main()