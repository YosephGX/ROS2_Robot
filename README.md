# Robot ROS2 para Raspberry Pi
El primer robot que he creado con la plataforma ROS2 sobre una Raspberry PI 5

## Rama `pi4b`: variante para Raspberry Pi 4B

Esta rama adapta el proyecto a un Raspberry Pi 4B con cámara y luces LED, sin brazo
robótico ni pan de cabeza — solo el servo de **tilt** (arriba/abajo) que sostiene la
cámara, limitado por software a **0°-95°** (más allá de eso el cable de la cámara se
masca contra el chasis).

Diferencias respecto a `main` (Pi5):

- **Cámara**: nodo nuevo `camera_node` (Picamera2/libcamera) que captura video y lo
  expone como MJPEG en `127.0.0.1:8090` (solo localhost). `server_node.py` hace de
  proxy en `/stream.mjpg` sobre el mismo puerto 5000 que el resto de la interfaz web
  — así todo pasa por un único host/puerto, lo cual importa si expones el robot por
  un túnel (Cloudflare Tunnel, etc.): solo hay que mapear un hostname al puerto 5000.
- **LEDs**: `led_node` se conmuta desde la web (tópico `/led_cmds`, `Bool`) y arranca
  apagado. A diferencia de `main`, aquí la tira **no** va por SPI sino por GPIO12 —
  ver la sección *LEDs WS2812* más abajo.
- **Brazo/garra/pan**: eliminados de `servo_node`, `server_node` y la interfaz web.
  Solo queda el canal PCA9685 11 (tilt) de la cabeza.

> **Nota**: el Pi4B de referencia para esta rama corre **Ubuntu Server 24.04 (Noble)**,
> no Raspberry Pi OS. Los pasos de abajo están probados en ese entorno y son bastante
> más largos que en Raspberry Pi OS porque casi nada del stack de cámara viene
> empaquetado para Ubuntu genérico en una Raspberry Pi.

### 1. Instalar ROS2 Jazzy

Ubuntu 24.04 no trae ROS2 preinstalado. Seguir la guía oficial: habilitar el
repositorio *Universe*, agregar el repo apt de ROS2, e instalar
`ros-jazzy-ros-base` + `ros-dev-tools` (incluye `colcon`).

### 2. Ajustes en `/boot/firmware/config.txt`

```
dtparam=i2c_arm=on
dtparam=audio=off
dtoverlay=spi0-0cs
```

`dtparam=audio=off` es **obligatorio** para los LEDs: la tira va por GPIO12, que es
PWM0, y el audio integrado (`snd_bcm2835`) reclama ese mismo periférico. Desactiva
únicamente el jack de 3.5 mm; el audio por HDMI sigue funcionando.

`dtoverlay=spi0-0cs` en vez de `dtparam=spi=on`: el overlay normal reserva también
GPIO7/GPIO8 como chip-select (CE0/CE1), y GPIO8 es justo el pin ECHO del sensor
ultrasónico (`ultrasonic_node.py`) — con `dtparam=spi=on` puro, `gpiozero` falla con
`lgpio.error: 'GPIO busy'`. El overlay `spi0-0cs` deja libres CE0/CE1 y solo reserva
SCLK/MOSI/MISO. (Desde que los LEDs dejaron de ir por SPI ya no hace falta ningún
bus SPI; se deja el overlay porque es inofensivo y mantiene CE0/CE1 libres.)

La línea `camera_auto_detect=1` (más abajo en el mismo archivo) ya habilita la cámara
CSI vía libcamera sin cambios adicionales.

### 3. Dependencias del sistema (apt)

```
sudo apt install -y python3-pip python3-rpi.gpio python3-gpiozero \
  python3-fastapi python3-uvicorn python3-pydantic python3-httpx python3-smbus
```

(`python3-httpx` lo usa `server_node.py` para el proxy de `/stream.mjpg`.)

### 4. Dependencias Python adicionales (pip, con `--break-system-packages`)

```
pip3 install --break-system-packages \
  adafruit-blinka adafruit-circuitpython-pca9685 adafruit-circuitpython-motor \
  picamera2
sudo pip3 install --break-system-packages rpi_ws281x
```

`rpi_ws281x` va instalado con `sudo` a propósito: el demonio de LEDs corre como root
y necesita verlo en `/usr/local/lib/python3.12/dist-packages`, no en `~/.local`.

### 4.1 LEDs WS2812 (GPIO12) y `robot-led.service`

El HAT cablea la línea de datos de la tira a **GPIO12**, no al MOSI del SPI (así está
en el repo de hardware de referencia, `BLONWINER_2in1_Robot_V2/web/LED.py`:
`LED_PIN = 12`, con la alternativa `LED_PIN = 10` comentada). Por eso `neopixel_spi`
no sirve aquí: transmite correctamente por GPIO10 pero ahí no hay nada conectado, y
no da ningún error — los LEDs simplemente nunca encienden.

Generar la señal en GPIO12 exige PWM + DMA (`rpi_ws281x`), que mapea `/dev/mem` y por
tanto necesita root (`CAP_SYS_RAWIO`). Para no correr ROS2 entero como root — lo que
rompería la memoria compartida de DDS entre usuarios y dejaría procesos huérfanos,
porque `ros2 launch` corre sin privilegios y no puede matar un proceso root — el
privilegio se aísla en `scripts/led_daemon.py`:

- `scripts/led_daemon.py` (root, servicio systemd) es lo único que toca el hardware.
  Escucha en el socket UNIX `/run/robot-led.sock`, grupo `dialout`, y cada datagrama
  es un frame completo de 3 bytes (R, G, B) por pixel.
- `led_node.py` (usuario normal, dentro del launch) decide la animación y manda los
  frames por ese socket.

Instalación (una sola vez):

```
sudo install -m 644 scripts/robot-led.service /etc/systemd/system/robot-led.service
sudo systemctl daemon-reload
sudo systemctl enable --now robot-led.service
```

Comprobar: `systemctl status robot-led` y `journalctl -u robot-led -n 20`.

### 5. Compilar `libcamera` desde código fuente

El `libcamera` que trae Ubuntu 24.04 por apt (v0.2.0) tiene un bug real en el
manejador de pipeline RPi/ISP: cualquier captura de cámara (incluso con la
herramienta nativa `cam`, sin Python de por medio) revienta con
`FATAL default ipa_base.cpp:396 assertion "it != buffers_.end()" failed in
prepareIsp()`. No es arreglable por parámetros ni con el repo apt oficial de
Raspberry Pi (ese repo es para Debian Bookworm/Python 3.11 y choca con el Python
3.12 de Ubuntu Noble). La solución fue compilar el fork que mantiene la propia
Raspberry Pi Foundation, nativo contra este sistema:

```
sudo apt install -y meson ninja-build libudev-dev python3-ply libjpeg-dev \
  libtiff-dev libdrm-dev

git clone --depth 1 https://github.com/raspberrypi/libcamera.git ~/libcamera-src
cd ~/libcamera-src
meson setup build --prefix=/usr/local \
  -Dpipelines=rpi/vc4 -Dipas=rpi/vc4 \
  -Dgstreamer=disabled -Dqcam=disabled -Ddocumentation=disabled \
  -Dlc-compliance=disabled -Dcam=disabled -Dpycamera=enabled
ninja -C build -j2      # -j2 para no quedarse sin RAM en un Pi4B; toma 20-45+ min
sudo ninja -C build install
sudo ldconfig
```

Se instala en `/usr/local` y coexiste sin conflicto con la versión vieja de Ubuntu
en `/usr` (sonames distintos: `libcamera.so.0.7` vs `libcamera.so.0.2`).

### 6. Arranque automático al encender (`robot.service`)

Con esto el robot queda listo sin entrar por SSH: al encender espera a tener internet
y lanza `robot_launch.py`. Tres servicios systemd arrancan solos:

| Servicio | Qué hace | Usuario |
|---|---|---|
| `cloudflared.service` | Túnel de Cloudflare (lo instala `cloudflared service install`) | root |
| `robot-led.service` | Demonio de LEDs, ver sección 4.1 | root |
| `robot.service` | `scripts/start_robot.sh`: espera internet y hace `ros2 launch` | `luna` |

`start_robot.sh` comprueba internet con `curl` contra Cloudflare (DNS + HTTPS, lo que
necesita el túnel; el ping sin root está desactivado en Ubuntu). Si en 120 s no hay
internet, **arranca igual**: el robot sigue siendo controlable por red local en
`http://<IP>:5000`, solo falta el acceso por el túnel. Como systemd no lee
`~/.bashrc`, el script carga a mano el entorno de ROS2 y del workspace.

`robot.service` corre como `luna` y no como root, porque la cámara depende de
`picamera2`/`libcamera` en `~/.local` y los permisos de hardware ya salen de los grupos
`dialout` y `video`. Se detiene con `SIGINT`, igual que un Ctrl+C, para que
`ros2 launch` pare los motores y apague los LEDs limpiamente.

Instalación (una sola vez; antes, detener cualquier `ros2 launch` manual):

```
sudo install -m 644 scripts/robot.service /etc/systemd/system/robot.service
sudo systemctl daemon-reload
sudo systemctl enable --now robot.service
```

Uso diario:

| Para... | Comando |
|---|---|
| Ver los logs en vivo | `journalctl -u robot -f` |
| Aplicar cambios tras `colcon build` | `sudo systemctl restart robot` |
| Lanzar a mano (depurar) | `sudo systemctl stop robot` y luego `ros2 launch robot_core robot_launch.py` |
| Desactivar el arranque automático | `sudo systemctl disable --now robot` |

Lanzar a mano con el servicio activo falla con puertos/GPIO ocupados (5000, 8090,
`GPIO busy`): hay que detenerlo antes.

### Workarounds necesarios en Ubuntu (no aplican en Raspberry Pi OS)

1. **Los bindings de Python de `libcamera` no quedan en `sys.path`**: el build de
   meson los instala en `/usr/local/lib/python3/dist-packages/libcamera` (ruta
   genérica), pero Python 3.12 busca en `/usr/local/lib/python3.12/dist-packages`
   (con versión). Enlazar al *user site-packages* (persiste sin depender de
   variables de entorno, por lo que también funciona dentro de los procesos que
   lanza `ros2 launch`):

   ```
   mkdir -p ~/.local/lib/python3.12/site-packages
   ln -sf /usr/local/lib/python3/dist-packages/libcamera \
       ~/.local/lib/python3.12/site-packages/libcamera
   ```

2. **`picamera2` falla al importar por `pykms`/`PyQt5`**: esos paquetes
   (`kmsxx`, Qt) no existen en Ubuntu genérico y solo los usan los modos de
   *preview* con pantalla de picamera2, que este proyecto no usa (solo
   streaming MJPEG headless). Se parcheó
   `~/.local/lib/python3.12/site-packages/picamera2/previews/__init__.py`
   para envolver esos imports en `try/except` en vez de fallar duro.

3. **`move_node` falla con "No access to /dev/mem"**: `RPi.GPIO` necesita
   `/dev/gpiomem` con grupo `dialout`, pero la regla udev empaquetada
   (`60-gpio.rules`) exige `SUBSYSTEM=="bcm2835-gpiomem"` y en este kernel el
   subsistema real se llama solo `gpiomem` — la regla nunca hace match. Hace
   falta una regla propia:

   ```
   sudo usermod -aG dialout $USER
   echo 'SUBSYSTEM=="gpiomem", KERNEL=="gpiomem", GROUP="dialout", MODE="0660"' \
     | sudo tee /etc/udev/rules.d/99-gpiomem-fix.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=gpiomem
   ```

4. **`camera_node` falla con "Could not open any dma-buf provider"**: los
   dispositivos `/dev/dma_heap/*` pertenecen al grupo `video`, hace falta:

   ```
   sudo usermod -aG video $USER
   ```

   (Los cambios de grupo requieren cerrar sesión y volver a entrar, o `sudo reboot`.)

   Cerrar sesión y volver a entrar (o reiniciar) para que el nuevo grupo
   tome efecto.

sudo nano /boot/firmware/config.txt
```
[all]
arm_64bit=1
kernel=vmlinuz
cmdline=cmdline.txt
initramfs initrd.img followkernel

# Enable the audio output, I2C and SPI interfaces on the GPIO header. As these
# parameters related to the base device-tree they must appear *before* any
# other dtoverlay= specification
dtparam=audio=on
dtparam=i2c_arm=on
#dtparam=spi=on

# Comment out the following line if the edges of the desktop appear outside
# the edges of your display
disable_overscan=1

# If you have issues with audio, you may try uncommenting the following line
# which forces the HDMI output into HDMI mode instead of DVI (which doesn't
# support audio output)
#hdmi_drive=2

# Enable the KMS ("full" KMS) graphics overlay, leaving GPU memory as the
# default (the kernel is in control of graphics memory with full KMS)
dtoverlay=vc4-kms-v3d
disable_fw_kms_setup=1

# Autoload overlays for any recognized cameras or displays that are attached
# to the CSI/DSI ports. Please note this is for libcamera support, *not* for
# the legacy camera stack
camera_auto_detect=1
display_auto_detect=1

# Config settings specific to arm64
dtoverlay=dwc2

[pi4]
max_framebuffers=2
arm_boost=1

[pi3+]
# Use a smaller contiguous memory area, specifically on the 3A+ to avoid an
# OOM oops on boot. The 3B+ is also affected by this section, but it shouldn't
# cause any issues on that board
dtoverlay=vc4-kms-v3d,cma-128

[pi02]
# The Zero 2W is another 512MB board which is occasionally affected by the same
# OOM oops on boot.
dtoverlay=vc4-kms-v3d,cma-128

[cm4]
# Enable the USB2 outputs on the IO board (assuming your CM4 is plugged into
# such a board)
dtoverlay=dwc2,dr_mode=host

[all]
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=82
```

pip freeze
```
action-msgs==2.0.4
action-tutorials-interfaces==0.33.11
action-tutorials-py==0.33.11
actionlib-msgs==5.3.8
Adafruit-Blinka==9.2.0
adafruit-circuitpython-busdevice==5.2.17
adafruit-circuitpython-connectionmanager==3.1.8
adafruit-circuitpython-motor==3.5.0
adafruit-circuitpython-neopixel-spi==1.0.16
adafruit-circuitpython-pca9685==3.4.22
adafruit-circuitpython-pixelbuf==2.0.12
adafruit-circuitpython-register==1.12.1
adafruit-circuitpython-requests==4.1.17
adafruit-circuitpython-typing==1.12.3
Adafruit-PlatformDetect==3.89.1
Adafruit-PureIO==1.1.11
ament-cmake-test==2.5.6
ament-copyright==0.17.5
ament-cppcheck==0.17.5
ament-cpplint==0.17.5
ament-flake8==0.17.5
ament-index-python==1.8.4
ament-lint==0.17.5
ament-lint-cmake==0.17.5
ament-package==0.16.5
ament-pep257==0.17.5
ament-uncrustify==0.17.5
ament-xmllint==0.17.5
angles==1.16.1
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.14.2
appdirs==1.4.4
argcomplete==3.1.4
attrs==23.2.0
Babel==2.10.3
bcrypt==3.2.2
beautifulsoup4==4.12.3
binho-host-adapter==0.1.6
blinker==1.7.0
Brlapi==0.8.5
Brotli==1.1.0
builtin-interfaces==2.0.4
catkin-pkg-modules==1.1.0
cbor2==5.6.2
certifi==2023.11.17
chardet==5.2.0
click==8.1.6
cloud-init==26.1
colcon-argcomplete==0.3.3
colcon-bash==0.5.0
colcon-cd==0.2.1
colcon-cmake==0.2.30
colcon-common-extensions==0.3.0
colcon-core==0.21.0
colcon-defaults==0.2.9
colcon-devtools==0.3.0
colcon-installed-package-information==0.2.1
colcon-library-path==0.2.1
colcon-metadata==0.2.5
colcon-notification==0.3.1
colcon-output==0.2.14
colcon-override-check==0.0.1
colcon-package-information==0.4.1
colcon-package-selection==0.2.10
colcon-parallel-executor==0.3.0
colcon-pkg-config==0.1.0
colcon-powershell==0.5.0
colcon-python-setup-py==0.2.9
colcon-recursive-crawl==0.2.3
colcon-ros==0.5.0
colcon-test-result==0.3.8
colcon-zsh==0.5.0
colorama==0.4.6
colorzero==2.0
command-not-found==0.3
composition-interfaces==2.0.4
configobj==5.0.8
contourpy==1.0.7
coverage==7.4.4
cryptography==41.0.7
cssselect==1.2.0
cupshelpers==1.0
cv-bridge==4.1.0
cycler==0.11.0
dbus-python==1.3.2
decorator==5.1.1
defer==1.0.6
demo-nodes-py==0.33.11
Deprecated==1.2.14
diagnostic-msgs==5.3.8
distlib==0.3.8
distro==1.9.0
distro-info==1.7+build1
docutils==0.20.1
domain-coordinator==0.12.1
duplicity==2.1.4
empy==3.3.4
example-interfaces==0.12.1
examples-rclpy-executors==0.19.7
examples-rclpy-minimal-action-client==0.19.7
examples-rclpy-minimal-action-server==0.19.7
examples-rclpy-minimal-client==0.19.7
examples-rclpy-minimal-publisher==0.19.7
examples-rclpy-minimal-service==0.19.7
examples-rclpy-minimal-subscriber==0.19.7
fastapi==0.141.1
fasteners==0.18
flake8==7.0.0
flake8-builtins==2.1.0
flake8-comprehensions==3.14.0
flake8-docstrings==1.6.0
flake8-import-order==0.18.2
flake8-quotes==3.4.0
fonttools==4.46.0
fs==2.4.16
geometry-msgs==5.3.8
gpiozero==2.0.1.post3
h11==0.16.0
html5lib==1.1
httplib2==0.20.4
httptools==0.8.0
idna==3.6
image-geometry==4.1.0
importlib-metadata==4.12.0
iniconfig==1.1.1
interactive-markers==2.5.5
Jinja2==3.1.2
jsonpatch==1.32
jsonpointer==2.0
jsonschema==4.10.3
kiwisolver==0.0.0
language-selector==0.1
lark==1.1.9
laser-geometry==2.7.2
launch==3.4.11
launch-ros==0.26.12
launch-testing==3.4.11
launch-testing-ros==0.26.12
launch-xml==3.4.11
launch-yaml==3.4.11
launchpadlib==1.11.0
lazr.restfulclient==0.14.6
lazr.uri==1.0.6
lgpio==0.2.2.0
lifecycle-msgs==2.0.4
logging-demo==0.33.11
louis==3.29.0
lxml==5.2.1
lz4==4.0.2+dfsg
Mako==1.3.2.dev0
map-msgs==2.4.1
markdown-it-py==3.0.0
MarkupSafe==2.1.5
matplotlib==3.6.3
mccabe==0.7.0
mdurl==0.1.2
message-filters==4.11.17
monotonic==1.6
more-itertools==10.2.0
mpi4py==3.1.5
mpmath==0.0.0
nav-msgs==5.3.8
notify2==0.3
numpy==1.26.4
oauthlib==3.2.2
olefile==0.46
osrf-pycommon==2.1.7
packaging==24.0
paramiko==2.12.0
pcl-msgs==1.0.0
pemmican==1.0.3
pendulum-msgs==0.33.11
pexpect==4.9.0
pillow==10.2.0
pluggy==1.4.0
psutil==5.9.8
ptyprocess==0.7.0
pycairo==1.25.1
pycodestyle==2.11.1
pycups==2.0.1
pydantic==2.13.4
pydantic_core==2.46.4
pydocstyle==6.3.0
pydot==1.4.2
pyflakes==3.2.0
pyftdi==0.57.2
Pygments==2.17.2
PyGObject==3.48.2
PyJWT==2.7.0
PyNaCl==1.5.0
pyparsing==3.1.1
PyQt5==5.15.10
PyQt5-sip==12.13.0
pyrsistent==0.20.0
pyserial==3.5
pytest==7.4.4
pytest-cov==4.1.0
python-apt==2.7.7+ubuntu5.2
python-dateutil==2.8.2
python-debian==0.1.49+ubuntu2
python-dotenv==1.2.2
python-qt-binding==2.2.2
pytz==2024.1
pyudev==0.24.0
pyusb==1.3.1
pyxdg==0.28
PyYAML==6.0.1
qt-dotgraph==2.7.6
qt-gui==2.7.6
qt-gui-cpp==2.7.6
qt-gui-py-common==2.7.6
quality-of-service-demo-py==0.33.11
rcl-interfaces==2.0.4
rclpy==7.1.11
rcutils==6.7.6
requests==2.31.0
resource-retriever==3.4.4
rich==13.7.1
rmw-dds-common==3.1.1
robot-core==0.0.0
roman==3.3
ros2action==0.32.10
ros2bag==0.26.11
ros2bag-mcap-cli==0.26.11
ros2bag-sqlite3-cli==0.26.11
ros2cli==0.32.10
ros2component==0.32.10
ros2doctor==0.32.10
ros2interface==0.32.10
ros2launch==0.26.12
ros2lifecycle==0.32.10
ros2multicast==0.32.10
ros2node==0.32.10
ros2param==0.32.10
ros2pkg==0.32.10
ros2plugin==5.4.5
ros2run==0.32.10
ros2service==0.32.10
ros2topic==0.32.10
rosapi==2.7.0
rosapi-msgs==2.7.0
rosbag2-interfaces==0.26.11
rosbag2-py==0.26.11
rosbridge-library==2.7.0
rosbridge-msgs==2.7.0
rosbridge-server==2.7.0
rosdep==0.26.0
rosdep-modules==0.26.0
rosdistro-modules==1.0.1
rosgraph-msgs==2.0.4
rosidl-adapter==4.6.9
rosidl-cli==4.6.9
rosidl-cmake==4.6.9
rosidl-generator-c==4.6.9
rosidl-generator-cpp==4.6.9
rosidl-generator-py==0.22.2
rosidl-generator-rs==0.4.12
rosidl-generator-type-description==4.6.9
rosidl-parser==4.6.9
rosidl-pycommon==4.6.9
rosidl-runtime-py==0.13.2
rosidl-typesupport-c==3.2.3
rosidl-typesupport-cpp==3.2.3
rosidl-typesupport-fastrtps-c==3.6.4
rosidl-typesupport-fastrtps-cpp==3.6.4
rosidl-typesupport-introspection-c==4.6.9
rosidl-typesupport-introspection-cpp==4.6.9
rospkg-modules==1.6.1
rpi-lgpio==0.6
RPi.GPIO==0.7.1
rpyutils==0.4.2
rqt-action==2.2.1
rqt-bag==1.5.6
rqt-bag-plugins==1.5.6
rqt-console==2.2.2
rqt-graph==1.5.6
rqt-gui==1.6.4
rqt-gui-py==1.6.4
rqt-msg==1.5.2
rqt-plot==1.4.5
rqt-publisher==1.7.3
rqt-py-common==1.6.4
rqt-py-console==1.2.3
rqt-reconfigure==1.6.4
rqt-service-caller==1.2.2
rqt-shell==1.2.3
rqt-srv==1.2.3
rqt-topic==1.7.5
SciPy==1.11.4
sensor-msgs==5.3.8
sensor-msgs-py==5.3.8
service-msgs==2.0.4
setuptools==68.1.2
shape-msgs==5.3.8
six==1.16.0
snowballstemmer==2.2.0
soupsieve==2.5
sros2==0.13.6
ssh-import-id==5.11
starlette==1.3.1
statistics-msgs==2.0.4
std-msgs==5.3.8
std-srvs==5.3.8
stereo-msgs==5.3.8
sympy==1.12
systemd-python==235
sysv_ipc==1.2.0
teleop-twist-keyboard==2.4.1
tf2-geometry-msgs==0.36.21
tf2-kdl==0.36.21
tf2-msgs==0.36.21
tf2-py==0.36.21
tf2-ros-py==0.36.21
tf2-sensor-msgs==0.36.21
tf2-tools==0.36.21
topic-monitor==0.33.11
tornado==6.4
trajectory-msgs==5.3.8
turtlesim==1.8.4
type-description-interfaces==2.0.4
typing-inspection==0.4.2
typing_extensions==4.16.0
ubuntu-drivers-common==0.0.0
ubuntu-pro-client==8001
ufoLib2==0.16.0
ufw==0.36.2
ujson==5.9.0
unattended-upgrades==0.1
unicodedata2==15.1.0
unique-identifier-msgs==2.5.1
urllib3==2.0.7
uvicorn==0.52.1
uvloop==0.22.1
visualization-msgs==5.3.8
wadllib==1.3.6
watchfiles==1.2.0
webencodings==0.5.1
websockets==17.0.1
wheel==0.42.0
wrapt==1.15.0
xdg==5
xkit==0.0.0
zipp==1.0.0
```