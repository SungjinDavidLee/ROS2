# 02. 하드웨어 브링업

`legalaspro/so101-ros-physical-ai` 스택을 ROS 2 Humble에서 동작시킨 기록.
mock 하드웨어로 먼저 검증하고, 그다음 실물로 넘어간다.

이 스택은 상위 배포판(Jazzy) 기준으로 작성되어 있어 Humble에서 쓰려면 여러 곳을 고쳐야 한다.
수정 전체 목록과 각각을 어느 단계에서 확인했는지는 아래 표에 정리했다.

| # | 파일 | 원인 | 확인 단계 |
|---|---|---|---|
| ① | `so101_description/launch/display.launch.py` | URDF 경로 버그 | [03-urdf-and-tf](03-urdf-and-tf.md) |
| ② | `so101_bringup/launch/follower.launch.py` | `robot_description` 미전달 | 01 (이 문서) |
| ③ | `feetech_driver/.../serial_port.hpp` | 시리얼 타임아웃 | 02 (실물) |
| ④ | `so101_bringup/launch/follower_split.launch.py` | ②와 동일 | [05-moveit](05-moveit.md) |
| ⑤ | `.../follower_split_controllers.yaml` | 그리퍼 컨트롤러 타입 | [05-moveit](05-moveit.md) |
| ⑥ | `so101_moveit_config/config/kinematics.yaml` | IK 플러그인 부재 | [05-moveit](05-moveit.md) |
| ⑦ | `.../ompl_planning.yaml`, `.../pilz_*.yaml` | MoveIt 파이프라인 형식 | [05-moveit](05-moveit.md) |
| ⑧ | `so101_moveit_config/config/moveit_controllers.yaml` | 그리퍼 액션 타입 | [05-moveit](05-moveit.md) |

> 이 수정들은 `git pull` 하면 전부 사라진다. 원본 옆에 `.bak`을 남겨두고,
> 변경 내역은 `git diff`로 언제든 다시 뽑을 수 있게 했다.

---

## 01. mock 하드웨어로 스택 검증

### 목표

실물 팔을 연결하지 않은 상태에서 ROS 스택이 끝까지 올라오는지 확인한다.

### mock 하드웨어란

`mock_components/GenericSystem`은 **보낸 명령을 "도달했다"고 그대로 되돌려주는 껍데기**다.
물리 엔진이 아니다. 중력도 관성도 지연도 없다.

시뮬레이션과 혼동하기 쉬운데 역할이 다르다.

| | mock 하드웨어 | 시뮬레이션 |
|---|---|---|
| 잡아내는 것 | 토픽 이름, 컨트롤러 타입, 조인트 개수와 순서, launch 인자 | 동역학, 접촉, 제어 게인 |
| 못 잡는 것 | 지연, 토크 부족, 서보 응답 특성 | 실물과의 도메인 갭 |

설정 오류와 하드웨어 문제를 미리 갈라놓는 것이 목적이다.
실제로 이 프로젝트에서 겪은 문제 대부분이 mock에서도 재현되는 설정 문제였다.

### 코드 — 수정 ②

`ros2_control_node`에 로봇 모델이 전달되지 않는다.

```diff
--- a/so101_bringup/launch/follower.launch.py
+++ b/so101_bringup/launch/follower.launch.py
@@ -77,5 +77,5 @@ def generate_launch_description():
         executable="ros2_control_node",
         namespace=namespace,
-        parameters=[controller_config_file],
+        parameters=[{"robot_description": robot_description}, controller_config_file],
         output="screen",
```

**왜 필요한가**

`ros2_control`은 로봇의 관절 구조를 알아야 컨트롤러를 붙일 수 있다. 그 정보가 URDF(`robot_description`)다.
원본은 이걸 토픽으로 받도록 되어 있는데, 발행 쪽과 구독 쪽의 경로가 어긋나 있었다.

| 노드 | 경로 |
|---|---|
| `robot_state_publisher` (발행) | `/follower/robot_description` |
| `controller_manager` (구독) | `~/robot_description` = `/follower/controller_manager/robot_description` |

`~`는 노드 프라이빗 네임스페이스라서 노드 이름이 경로에 한 칸 더 들어간다.
토픽 대기를 우회하고 **파라미터로 직접 넘기는** 방식을 택했다.

### 실행

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash

ros2 launch so101_bringup follower.launch.py \
  hardware_type:=mock \
  arm_controller:=trajectory_controller \
  use_rviz:=true
```

**launch 인자를 반드시 명시한다.**
`hardware_type` 기본값이 `real`, `arm_controller` 기본값이 `forward_controller`다.
아무 인자 없이 실행하면 실물에 보간 없는 즉시 이동 명령이 걸린다.
남의 리포를 쓸 때 `DeclareLaunchArgument`의 기본값을 먼저 읽어야 하는 이유다.

확인은 새 터미널에서.

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash

ros2 node list
ros2 control list_controllers -c /follower/controller_manager
ros2 topic echo /follower/joint_states --once
```

### 결과

```
=== 노드 ===
/follower/controller_manager
/follower/joint_state_broadcaster
/follower/robot_state_publisher
/follower/trajectory_controller
/rviz

=== 컨트롤러 ===
joint_state_broadcaster  joint_state_broadcaster/JointStateBroadcaster          active
trajectory_controller    joint_trajectory_controller/JointTrajectoryController  active

=== joint_states ===
name:     [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
velocity: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
effort:   [nan, nan, nan, nan, nan, nan]
```

RViz에 로봇 모델이 표시되고, 6개 관절 상태가 발행된다.

**성공 판정 기준은 컨트롤러 목록이 아니라 launch 로그의 이 줄이다.**

```
[INFO] [spawner-4]: process has finished cleanly
```

spawner는 컨트롤러를 등록하고 **끝나야 하는** 일회성 프로세스다.
수정 ② 전에는 이게 종료되지 않고 `Could not contact service`를 반복했다.
깨끗하게 종료됐다는 것은 controller_manager가 로봇 모델을 제대로 받았다는 뜻이다.

`position`이 전부 `0.0`인 것도 정상이다. mock은 실물 관절 각도를 알 수 없으므로 원점을 그대로 보고한다.
`effort`가 `nan`인 것은 mock이 토크를 측정하지 않기 때문이다.

---

### 잘못 예상한 것 — 컨트롤러 개수

컨트롤러가 3개(`joint_state_broadcaster`, `trajectory_controller`, `gripper_controller`)
활성화될 것으로 예상했으나 2개였다.

`gripper_controller`는 `follower_split_controllers.yaml`에만 정의되어 있다.
`follower.launch.py`가 쓰는 구성에서는 `trajectory_controller` 하나가 **그리퍼를 포함한 6축 전부**를 담당한다.
`joint_states`에 `gripper`가 들어 있는 것이 그 증거다.

컨트롤러를 팔 5축과 그리퍼로 쪼개는 것은 `follower_split` 계열 구성이고,
MoveIt이 그리퍼를 별도 액션으로 다루기 위해 필요하다. [05-moveit](05-moveit.md)에서 다룬다.

> 컨트롤러 구성이 하나가 아니라는 것, 그리고 **어느 launch 파일을 쓰느냐에 따라
> 토픽 이름과 조인트 개수가 달라진다**는 것이 여기서 확인됐다.
> 나중에 직접 명령을 보낼 때 이 차이가 그대로 문제가 된다.

---

### 막힌 것 — 스크립트 안의 환경 활성화가 동작하지 않음

**증상**

명령을 스크립트 파일로 만들어 `bash run.sh`로 실행했더니 첫 줄에서 경고가 났다.

```
'micromamba' is running as a subprocess and can't modify the parent shell.
critical libmamba Shell not initialized
```

그런데 뒤의 ROS 명령들은 정상 실행됐다.

**처음 세운 가설**

셸 초기화가 안 된 것이니 `micromamba shell init`을 실행하면 된다.

**어떻게 좁혔나**

경고 문구를 그대로 읽으면 답이 있었다 — `is running as a subprocess`.
`bash run.sh`는 **자식 셸**을 만든다. 자식 프로세스는 부모 셸의 환경 변수를 바꿀 수 없다.
`activate`가 하는 일이 PATH 수정이므로, 구조적으로 불가능한 요청이었다.

뒤의 명령이 동작한 이유는 별개다. **터미널에서 이미 환경을 켜둔 상태였고,
그 PATH가 자식 셸에 상속됐기 때문**이다. 활성화 성공이 아니라 상속이다.

**수정**

스크립트에서 `activate` 줄을 뺀다. 터미널에서 먼저 활성화한 뒤 스크립트를 실행한다.

```bash
micromamba activate rosenv
bash run.sh
```

스크립트 안에서 반드시 지정해야 한다면 활성화 대신 `run`을 쓴다.

```bash
micromamba run -n rosenv ros2 node list
```

**일반화**

- **자식 프로세스는 부모의 환경을 바꿀 수 없다.** `activate`, `source`, `export`처럼
  현재 셸을 바꾸는 명령은 스크립트에 넣어도 호출한 셸에 반영되지 않는다.
- 경고가 떴는데 결과가 잘 나오면 더 위험하다. 우연히 동작하는 경우를
  "동작한다"로 기록하면 환경이 조금만 달라져도 재현되지 않는다.

---

### 무시해도 되는 메시지

| 메시지 | 이유 |
|---|---|
| `A message was lost!!!` | `--once`로 즉시 구독을 해제해서 발생 |
| `Could not enable FIFO RT scheduling policy` | 관리자 권한 없이 실행. 제어 주기에는 문제없음 |
| `kdl_parser: root link base_link has an inertia` | KDL이 루트 링크 관성을 무시할 뿐 |
| `CMake Deprecation Warning` | 에러 아님 |

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| mock 하드웨어 | 명령을 즉시 도달했다고 응답하는 껍데기. 설정 오류 전용 검증 도구 |
| `robot_description` | URDF 문자열. `ros2_control`이 관절 구조를 아는 유일한 경로 |
| `~` 네임스페이스 | `~/topic` = `/노드이름/topic`. 노드 프라이빗 |
| spawner | 컨트롤러를 등록하고 종료하는 일회성 프로세스. **살아 있으면 대기 중이라는 신호** |
| launch 인자 기본값 | 리포 작성자의 환경 기준이지 내 환경 기준이 아니다 |

## 확인하지 않고 넘어간 것

- RViz 모델 자세와 실물 자세의 시각적 일치
- `trajectory_controller`에 실제로 명령을 보냈을 때의 동작 — [04-ros2-control](04-ros2-control.md)

## 다음

[03-urdf-and-tf.md](03-urdf-and-tf.md)
