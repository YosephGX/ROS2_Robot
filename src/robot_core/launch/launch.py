from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='mi_paquete',
            executable='ejecutable_uno',
            name='nodo_emisor',
            output='screen'
        ),
        Node(
            package='mi_paquete',
            executable='ejecutable_dos',
            name='nodo_receptor',
            output='screen'
        ),
    ])
