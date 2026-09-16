#!/usr/bin/env python3
# File name   : led_daemon.py
# Description : Demonio con privilegios que maneja la tira WS2812 del robot.
# Author      : TheYoseph
#
# La tira va cableada a GPIO12 (PWM0), no al MOSI del SPI, así que hay que generar la
# señal con PWM + DMA (rpi_ws281x). Eso obliga a mapear /dev/mem, cosa que el kernel
# solo permite a root (CAP_SYS_RAWIO).
#
# Para no tener que correr ROS2 entero como root, los privilegios se quedan aquí:
# este proceso es lo único que toca el hardware, y led_node.py (usuario normal) le manda
# los colores por un socket UNIX. Así `ros2 launch` sigue sin privilegios, sin líos de
# memoria compartida de DDS entre usuarios ni procesos root que el launch no pueda parar.
#
# Se instala como servicio systemd: ver scripts/robot-led.service

import os
import shutil
import socket

from rpi_ws281x import Adafruit_NeoPixel, Color

SOCKET_PATH = '/run/robot-led.sock'
SOCKET_GROUP = 'dialout'  # El usuario que corre los nodos ROS2 pertenece a este grupo

# Configuración de la tira (igual que el repo de referencia del hardware)
LED_COUNT = 16
LED_PIN = 12          # GPIO12 = PWM0 canal 0
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 255
LED_INVERT = False
LED_CHANNEL = 0       # 0 para GPIO 12/18; 1 para GPIO 13/19


def clear(strip):
    for i in range(LED_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def main():
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                              LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    strip.begin()
    clear(strip)

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(SOCKET_PATH)
    # Sin esto solo root podría mandar colores, y led_node corre como usuario normal.
    shutil.chown(SOCKET_PATH, group=SOCKET_GROUP)
    os.chmod(SOCKET_PATH, 0o660)
    print(f'Demonio de LEDs escuchando en {SOCKET_PATH} (GPIO{LED_PIN}).', flush=True)

    try:
        while True:
            # Cada datagrama es un frame completo: 3 bytes (R, G, B) por pixel.
            data = sock.recv(4096)
            for i in range(min(LED_COUNT, len(data) // 3)):
                strip.setPixelColor(i, Color(data[3 * i], data[3 * i + 1], data[3 * i + 2]))
            strip.show()
    except KeyboardInterrupt:
        pass
    finally:
        clear(strip)
        sock.close()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


if __name__ == '__main__':
    main()
