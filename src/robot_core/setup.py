import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'robot_core'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='luna',
    maintainer_email='luna@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'move_node = robot_core.move_node:main',
            'servo_node = robot_core.servo_node:main',
            'ultrasonic_node = robot_core.ultrasonic_node:main',
            'server_node = robot_core.server_node:main',
            'led_node = robot_core.led_node:main',
        ],
    },
)
