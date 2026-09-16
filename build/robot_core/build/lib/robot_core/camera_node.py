#!/usr/bin/env python3
# File name   : camera_node.py
# Description : Nodo ROS2 de streaming de cámara (MJPEG por HTTP) para el Pi4B
# Author      : TheYoseph

import io
import logging
import socketserver
from http import server
from threading import Condition, Thread

import rclpy
from rclpy.node import Node

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

STREAM_PORT = 8090
# El cliente descarta los frames que no alcanza a pintar, así que codificar a 30 fps solo
# gastaría CPU. 15 fps y ~4 Mbps dan frames de ~30 KB, ligeros para pasar por un túnel.
FRAME_RATE = 15.0
BITRATE = 4_000_000


class StreamingOutput(io.BufferedIOBase):
    """Buffer de un solo frame compartido entre el hilo de captura y los clientes HTTP."""

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/stream.mjpg')
            self.end_headers()
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with self.server.output.condition:
                        self.server.output.condition.wait()
                        frame = self.server.output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Cliente de streaming desconectado: %s', str(e))
        else:
            self.send_error(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Evita saturar los logs con cada frame servido


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler, output):
        self.output = output
        super().__init__(address, handler)


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.picam2 = None
        self.http_server = None
        try:
            self.picam2 = Picamera2()
            video_config = self.picam2.create_video_configuration(
                main={"size": (640, 480)},
                controls={"FrameRate": FRAME_RATE},
            )
            self.picam2.configure(video_config)

            self.output = StreamingOutput()
            self.picam2.start_recording(MJPEGEncoder(bitrate=BITRATE), FileOutput(self.output))

            # Solo localhost: server_node.py hace de proxy hacia el exterior en /stream.mjpg.
            self.http_server = StreamingServer(('127.0.0.1', STREAM_PORT), StreamingHandler, self.output)
            self.server_thread = Thread(target=self.http_server.serve_forever, daemon=True)
            self.server_thread.start()
            self.get_logger().info(
                f'Streaming de cámara disponible en 127.0.0.1:{STREAM_PORT} (/stream.mjpg).'
            )
        except Exception as e:
            self.get_logger().error(f'Error al inicializar la cámara: {e}')

    def destroy_node(self):
        if self.http_server is not None:
            self.http_server.shutdown()
        if self.picam2 is not None:
            self.picam2.stop_recording()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
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
