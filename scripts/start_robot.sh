#!/bin/bash
# File name   : start_robot.sh
# Description : Arranque automático del robot. Lo ejecuta robot.service al encender.
# Author      : TheYoseph
#
# systemd no lee ~/.bashrc, así que el entorno de ROS2 se carga aquí a mano.

WORKSPACE=/home/luna/Desktop/robot/ROS2_Robot

# Sin internet el robot se sigue controlando por la red local (http://<IP>:5000), así
# que pasado este tiempo se arranca igual: solo se pierde el acceso por el túnel.
INTERNET_TIMEOUT_S=120
# Comprueba DNS + HTTPS, que es lo que necesita el túnel de Cloudflare (ping sin root
# está desactivado en este sistema).
INTERNET_CHECK_URL=https://www.cloudflare.com/cdn-cgi/trace

echo "Esperando conexión a internet (máx. ${INTERNET_TIMEOUT_S}s)..."
until curl -fs --max-time 5 -o /dev/null "$INTERNET_CHECK_URL"; do
    if (( SECONDS >= INTERNET_TIMEOUT_S )); then
        echo "AVISO: sin internet tras ${SECONDS}s; se arranca igual (solo red local)."
        break
    fi
    sleep 5
done
(( SECONDS < INTERNET_TIMEOUT_S )) && echo "Internet OK (${SECONDS}s)."

source /opt/ros/jazzy/setup.bash
source "$WORKSPACE/install/setup.bash"

echo "Lanzando robot_launch.py..."
exec ros2 launch robot_core robot_launch.py
