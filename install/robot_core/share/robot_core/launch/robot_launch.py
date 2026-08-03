#!/usr/bin/env python3
# File name   : robot_launch.py
# Description : Archivo de lanzamiento general para el robot en ROS 2
# Author      : TheYoseph

from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Nodo de Motores (Locomoción)
        Node(
            package='robot_core',
            executable='move_node',
            name='move_node',
            output='screen'
        ),
        # 2. Nodo de Servos (Brazo y Cabeza)
        Node(
            package='robot_core',
            executable='servo_node',
            name='servo_node',
            output='screen'
        ),
        # 3. Nodo de Seguridad Ultrasónica
        Node(
            package='robot_core',
            executable='ultrasonic_node',
            name='ultrasonic_node',
            output='screen',
            parameters=[{
                'trig_pin': 11,
                'echo_pin': 8,
                'read_frequency_hz': 10.0,
                'safety_distance_cm': 20.0
            }]
        ),
        # 4. Servidor Web / Interfaz de Control
        Node(
            package='robot_core',
            executable='server_node',
            name='server_node',
            output='screen'
        ),
        # 5. Nodo de Luces de Policía (LEDs WS2812)
        Node(
            package='robot_core',
            executable='led_node',
            name='led_node',
            output='screen'
        )
    ])