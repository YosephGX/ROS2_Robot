#!/usr/bin/env python3
# File name   : move_node.py
# Description : Nodo de ROS2 para control de Motores (Direccion, Giro y Velocidad) ROS2
# Author      : TheYoseph
# Date        : 2026/08/01

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

import RPi.GPIO as GPIO
import time

Motor_MF_Pin1 = 26
Motor_MF_Pin2 = 21

Motor_MB_Pin1 = 18
Motor_MB_Pin2 = 27

Motor_MR_Pin1 = 4
Motor_MR_Pin2 = 17

Dir_forward   = 0
Dir_backward  = 1

left_forward  = 0
left_backward = 0

right_forward = 1
right_backward= 1

left_f=0
right_f=1

motorRun=1
motorStop=0

pwm_MR_Pin1 = 0 
pwm_MR_Pin2 = 0
pwm_MF_Pin1 = 0
pwn_MF_Pin2 = 0
pwm_MB_Pin1 = 0
pwm_MB_Pin2 = 0

class MoveNode(Node):
    def __init__(self):
        super().__init__('move_node')
        
        # Nos suscribimos al tópico /cmd_vel que usa mensajes de tipo Twist
        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )
        self.collision_danger = False
        self.safety_sub = self.create_subscription(
            Bool,
            '/safety/collision_danger',
            self.safety_callback,
            10
        )
        
        self.setup_hardware()
        self.get_logger().info('Nodo de locomoción (move_node) iniciado y esperando comandos...')

    def setup_hardware(self):
        """ Configuración inicial de los pines del controlador de motores """
        self.get_logger().info('Configurando hardware de motores...')
        # Aquí va la configuración de pines que tenías al principio de tu move.py original
        global pwm_MR_Pin1, pwm_MR_Pin2, pwm_MF_Pin1, pwm_MF_Pin2, pwm_MB_Pin1, pwm_MB_Pin2
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Motor_MR_Pin1, GPIO.OUT)
        GPIO.setup(Motor_MR_Pin2, GPIO.OUT)
        GPIO.setup(Motor_MF_Pin1, GPIO.OUT)
        GPIO.setup(Motor_MF_Pin2, GPIO.OUT)
        GPIO.setup(Motor_MB_Pin1, GPIO.OUT)
        GPIO.setup(Motor_MB_Pin2, GPIO.OUT)
        self.stopSet()
        try:
            #pwm_MR_Pin1 = GPIO.PWM(Motor_MR_Pin1, 1000)
            #pwm_MR_Pin2 = GPIO.PWM(Motor_MR_Pin2, 1000)
            pwm_MF_Pin1 = GPIO.PWM(Motor_MF_Pin1, 1000)
            pwm_MF_Pin2 = GPIO.PWM(Motor_MF_Pin2, 1000)
            pwm_MB_Pin1 = GPIO.PWM(Motor_MB_Pin1, 1000)
            pwm_MB_Pin2 = GPIO.PWM(Motor_MB_Pin2, 1000)
        except:
            pass

    def safety_callback(self, msg):
        self.collision_danger = msg.data
        if self.collision_danger:
            self.get_logger().warn('¡Freno de emergencia activado por sensor ultrasónico!')
            self.stop()

    def cmd_vel_callback(self, msg):
        """ Esta función se ejecuta cada vez que llega un mensaje de movimiento """
        """ Evalúa la tracción y el giro al mismo tiempo """
        linear_x = msg.linear.x   # Velocidad hacia adelante/atrás
        angular_z = msg.angular.z # Velocidad de giro
        # Lógica básica para traducir velocidades a direcciones
        # 1. Determinar dirección de tracción
        if linear_x > 0:
            direction = 'forward'
        elif linear_x < 0:
            direction = 'backward'
        else:
            direction = 'no'
        # 2. Determinar dirección de giro (En ROS, Z positivo es izquierda)
        if angular_z > 0:
            turn = 'left'
        elif angular_z < 0:
            turn = 'right'
        else:
            turn = 'no'
        # Asignar una velocidad base
        speed = 75
        # Ejecutar el movimiento
        self.move(speed, direction, turn)

    # --- MÉTODOS BASE ---
    # En estas funciones integrarás las rutinas generales
    def motor_MF(self, status, direction, speed): # Motor MF positive and negative rotation
        GPIO.setup(Motor_MF_Pin1, GPIO.OUT)
        GPIO.setup(Motor_MF_Pin2, GPIO.OUT)
        if status == 0: # stop
            pwm_MF_Pin1.start(100)
            pwm_MF_Pin1.ChangeDutyCycle(100)
            pwm_MF_Pin2.start(100)
            pwm_MF_Pin2.ChangeDutyCycle(100)
        else:
            if direction == Dir_forward:
                pwm_MF_Pin1.start(100)
                pwm_MF_Pin1.ChangeDutyCycle(speed)
                pwm_MF_Pin2.start(0)
                pwm_MF_Pin2.ChangeDutyCycle(0)
            elif direction == Dir_backward:
                pwm_MF_Pin1.start(0)
                pwm_MF_Pin1.ChangeDutyCycle(0)
                pwm_MF_Pin2.start(100)
                pwm_MF_Pin2.ChangeDutyCycle(speed)

    def motor_MB(self,status, direction, speed): # Motor MB positive and negative rotation
        if status == 0: # stop
            pwm_MB_Pin1.start(100)
            pwm_MB_Pin1.ChangeDutyCycle(100)
            pwm_MB_Pin2.start(100)
            pwm_MB_Pin2.ChangeDutyCycle(100)
        else:
            if direction == Dir_forward:
                pwm_MB_Pin1.start(100)
                pwm_MB_Pin1.ChangeDutyCycle(speed)
                pwm_MB_Pin2.start(0)
                pwm_MB_Pin2.ChangeDutyCycle(0)
            elif direction == Dir_backward:
                pwm_MB_Pin1.start(0)
                pwm_MB_Pin1.ChangeDutyCycle(0)
                pwm_MB_Pin2.start(100)
                pwm_MB_Pin2.ChangeDutyCycle(speed)

    def motor_MR(self, status, direction, speed): # Motor MR positive and negative rotation
        GPIO.setup(Motor_MR_Pin1, GPIO.OUT)
        GPIO.setup(Motor_MR_Pin2, GPIO.OUT)
        if status == 0: # stop
            GPIO.output(Motor_MR_Pin1, GPIO.HIGH)
            GPIO.output(Motor_MR_Pin2, GPIO.HIGH)
        else:
            if direction == 0:
                GPIO.output(Motor_MR_Pin1, GPIO.HIGH)
                GPIO.output(Motor_MR_Pin2, GPIO.LOW)
            elif direction == 1:
                GPIO.output(Motor_MR_Pin1, GPIO.LOW)
                GPIO.output(Motor_MR_Pin2, GPIO.HIGH)

    def stop(self):
        self.get_logger().info('Deteniendo motores')
        pwm_MB_Pin1.start(100)
        pwm_MB_Pin1.ChangeDutyCycle(100)
        pwm_MB_Pin2.start(100)
        pwm_MB_Pin2.ChangeDutyCycle(100)
        pwm_MF_Pin1.start(100)
        pwm_MF_Pin1.ChangeDutyCycle(100)
        pwm_MF_Pin2.start(100)
        pwm_MF_Pin2.ChangeDutyCycle(100)
        GPIO.output(Motor_MR_Pin1, GPIO.HIGH)
        GPIO.output(Motor_MR_Pin2, GPIO.HIGH)

    def stopSet(self):
        GPIO.output(Motor_MF_Pin1, GPIO.HIGH)
        GPIO.output(Motor_MF_Pin2, GPIO.HIGH)
        GPIO.output(Motor_MB_Pin1, GPIO.HIGH)
        GPIO.output(Motor_MB_Pin2, GPIO.HIGH)
        GPIO.output(Motor_MR_Pin1, GPIO.HIGH)
        GPIO.output(Motor_MR_Pin2, GPIO.HIGH)

    def move(self, speed, direction, turn):
        """ Funcion que decide cómo mover el robot según la dirección y el giro """
        if direction == 'forward' and self.collision_danger:
            self.get_logger().warn('Movimiento frontal bloqueado por obstáculo cercano.')
            self.stop()
            return
        elif direction == 'forward':
            if turn == 'right':
                self.motor_MR(1, 1, speed)
                self.motor_MF(1, 0, speed)
                self.motor_MB(1, 0, speed)
            elif turn == 'left':
                self.motor_MR(1, 0, speed)
                self.motor_MF(1, 0, speed)
                self.motor_MB(1, 0, speed)
            else:
                self.motor_MR(0, 2, speed)
                self.motor_MF(1, 0, speed)
                self.motor_MB(1, 0, speed)
        elif direction == 'backward':
            if turn == 'right':
                self.motor_MR(1, 1, speed)
                self.motor_MF(1, 1, speed)
                self.motor_MB(1, 1, speed)
            elif turn == 'left':
                self.motor_MR(1, 0, speed)
                self.motor_MF(1, 1, speed) 
                self.motor_MB(1, 1, speed) 
            else:
                self.motor_MR(0, 2, speed)             
                self.motor_MF(1, 1, speed)
                self.motor_MB(1, 1, speed)
        elif direction == 'no':
            if turn == 'right':
                self.motor_MR(1, 1, speed)
                self.motor_MB(0, 2, speed)
                self.motor_MF(0, 2, speed)
            elif turn == 'left':
                self.motor_MR(1, 0, speed)
                self.motor_MB(0, 2, speed)
                self.motor_MF(0, 2, speed)
            elif turn == 'no':
                self.stop()
            else:
                self.stop()
        else:
            pass

def main(args=None):
    rclpy.init(args=args)
    move_node = MoveNode()
    
    try:
        # spin() mantiene el nodo ejecutándose y escuchando el tópico
        move_node.setup_hardware()
        rclpy.spin(move_node)
    except KeyboardInterrupt:
        pass
    finally:
        # Seguridad: asegurarnos de detener el robot si cerramos el programa
        move_node.stop()
        GPIO.cleanup()
        move_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()