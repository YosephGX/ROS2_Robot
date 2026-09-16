import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/luna/Desktop/robot/ROS2_Robot/install/robot_core'
