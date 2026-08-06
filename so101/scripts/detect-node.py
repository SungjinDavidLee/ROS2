#!/usr/bin/env python3
"""/image_raw 를 구독해 학습된 YOLO 모델로 물체를 찾고,
중심 픽셀 좌표와 면적을 /fbox/center 로 발행한다.

화면 표시가 필요 없으면 SHOW = False 로 둔다.
원격 접속 등으로 cv2.imshow 가 막힌 환경에서는 창이 뜨지 않는다.

사용법:
    # 터미널 1
    ros2 run v4l2_camera v4l2_camera_node \
      --ros-args -p video_device:=/dev/video0 -p image_size:="[640,480]"

    # 터미널 2
    python3 detect-node.py
"""

import os

import cv2
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
from rclpy.node import Node
from sensor_msgs.msg import Image
from ultralytics import YOLO

MODEL = os.path.expanduser("~/so101_ws/models/fbox_v1.pt")
CONF = 0.40
SHOW = True

IMAGE_TOPIC = "/image_raw"
CENTER_TOPIC = "/fbox/center"


class Detector(Node):
    def __init__(self):
        super().__init__("fbox_detector")
        self.bridge = CvBridge()
        self.model = YOLO(MODEL)
        self.get_logger().info(f"model loaded: {MODEL}")

        # 큐 깊이 1: 추론이 카메라보다 느리므로 밀린 프레임은 버리고 최신만 쓴다
        self.sub = self.create_subscription(Image, IMAGE_TOPIC, self.on_image, 1)
        self.pub = self.create_publisher(Point, CENTER_TOPIC, 10)

        self.frames = 0
        self.hits = 0
        self.create_timer(2.0, self.report)

    def report(self):
        self.get_logger().info(f"frames={self.frames}  detections={self.hits}")

    def on_image(self, msg):
        self.frames += 1

        # /image_raw 는 rgb8 이지만 OpenCV 는 BGR 순서를 쓴다
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        result = self.model.predict(frame, conf=CONF, verbose=False)[0]

        # 여러 개가 검출되면 면적이 가장 큰 것을 고른다
        # (카메라에 가까운 물체가 크게 보이고, 가까운 것부터 다루는 것이 자연스럽다)
        best = None
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            area = (x2 - x1) * (y2 - y1)
            if best is None or area > best[4]:
                best = (x1, y1, x2, y2, area, float(box.conf[0]))

        if best:
            x1, y1, x2, y2, area, conf = best
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            # Point 를 재활용: x, y 는 픽셀 좌표, z 에 면적을 넣었다.
            # 표준 메시지에 의미가 다른 값을 넣은 것이므로
            # 3D 좌표를 다루게 되면 전용 타입으로 바꿔야 한다.
            point = Point()
            point.x, point.y, point.z = float(cx), float(cy), float(area)
            self.pub.publish(point)
            self.hits += 1

            if SHOW:
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.circle(frame, (int(cx), int(cy)), 5, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    f"conf {conf:.2f} area {int(area)}",
                    (int(x1), int(y1) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
        elif SHOW:
            cv2.putText(
                frame, "NO DETECTION", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
            )

        if SHOW:
            # 화면 중심선. 검출 중심과의 차이가 곧 제어 오차가 된다
            h, w = frame.shape[:2]
            cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 0, 0), 1)
            cv2.line(frame, (0, h // 2), (w, h // 2), (255, 0, 0), 1)
            cv2.imshow("fbox detector", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                rclpy.shutdown()


def main():
    rclpy.init()
    node = Detector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if SHOW:
            cv2.destroyAllWindows()
        node.destroy_node()


if __name__ == "__main__":
    main()
