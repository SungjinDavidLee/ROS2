#!/usr/bin/env python3
"""현재 관절 각도를 읽어, 지정한 관절 하나만 상대적으로 이동시킨다.

목표 값 6개를 손으로 적는 방식은 현재 자세를 잘못 적으면 그 관절이 갑자기 튄다.
이 스크립트는 joint_states를 먼저 읽어 나머지 관절을 그대로 유지하고,
URDF limit을 넘는 목표는 경계값으로 잘라낸다.

사용법:
    python3 move-joint.py <관절이름> <변화량_라디안> [소요초]

예시:
    python3 move-joint.py wrist_roll 2.0 5      # 114도 회전, 5초에 걸쳐
    python3 move-joint.py gripper -0.5 2
"""

import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

# 컨트롤러가 기대하는 순서. allow_partial_joints_goal 이 false 이므로 항상 6개를 보낸다
ORDER = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# URDF 에서 읽은 값 (scripts/urdf-limits.py 로 확인)
LIMITS = {
    "shoulder_pan": (-1.9199, 1.9199),
    "shoulder_lift": (-1.7453, 1.7453),
    "elbow_flex": (-1.6900, 1.6900),
    "wrist_flex": (-1.6581, 1.6581),
    "wrist_roll": (-2.7439, 2.8412),
    "gripper": (-0.1745, 1.7453),
}

STATE_TOPIC = "/follower/joint_states"
CMD_TOPIC = "/follower/trajectory_controller/joint_trajectory"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    joint = sys.argv[1]
    delta = float(sys.argv[2])
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    if joint not in LIMITS:
        sys.exit(f"모르는 관절: {joint}\n가능한 값: {', '.join(ORDER)}")

    rclpy.init()
    node = Node("move_joint")
    state = {}

    def on_state(msg):
        for name, pos in zip(msg.name, msg.position):
            state[name] = pos

    node.create_subscription(JointState, STATE_TOPIC, on_state, 10)
    pub = node.create_publisher(JointTrajectory, CMD_TOPIC, 10)

    # 현재 자세를 받을 때까지 대기 (최대 10초)
    for _ in range(200):
        rclpy.spin_once(node, timeout_sec=0.05)
        if len(state) >= len(ORDER):
            break
    if len(state) < len(ORDER):
        sys.exit("joint_states를 받지 못했다. 브링업이 떠 있는지 확인")

    target = [state[n] for n in ORDER]
    idx = ORDER.index(joint)
    low, high = LIMITS[joint]

    want = target[idx] + delta
    clamped = max(low, min(high, want))
    if abs(clamped - want) > 1e-9:
        print(f"!! limit에 걸려 {want:.4f} -> {clamped:.4f} 로 잘림")
    target[idx] = clamped

    print("현재: " + " ".join(f"{state[n]:.3f}" for n in ORDER))
    print("목표: " + " ".join(f"{v:.3f}" for v in target))
    print(
        f"{joint} : {state[joint]:.3f} -> {clamped:.3f}  "
        f"({math.degrees(clamped - state[joint]):.1f} deg, {secs:.1f}초)"
    )

    msg = JointTrajectory()
    msg.joint_names = ORDER
    point = JointTrajectoryPoint()
    point.positions = target
    point.time_from_start.sec = int(secs)
    point.time_from_start.nanosec = int((secs % 1) * 1e9)
    msg.points = [point]

    # 발행 직후 종료하면 전달되지 않을 수 있어 여러 번 보낸다
    for _ in range(5):
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.1)

    print("전송 완료")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
