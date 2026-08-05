# 02. 하드웨어 브링업

`legalaspro/so101-ros-physical-ai` 스택을 ROS 2 Humble에서 동작시킨 기록.
mock 하드웨어로 먼저 검증하고, 그다음 실물로 넘어간다.

**전제 조건**

- [01-env-setup](01-env-setup.md) 완료 — `rosenv` 활성화 시 `ros2`가 동작
- 워크스페이스가 `colcon build`로 빌드되어 있음
- 실물 장(02)은 SO-101 팔로워암과 전원, USB 케이블 필요

**ROS 터미널을 열 때마다 필요한 세 줄**

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash
```

---

## 리포 수정 목록

이 스택은 상위 배포판(Jazzy) 기준으로 작성되어 있어 Humble에서 쓰려면 여러 곳을 고쳐야 한다.

| # | 파일 | 원인 | 확인 단계 |
|---|---|---|---|
| ① | `so101_description/launch/display.launch.py` | URDF 경로 버그 | [03-urdf-and-tf](03-urdf-and-tf.md) |
| ② | `so101_bringup/launch/follower.launch.py` | `robot_description` 미전달 | 01 (이 문서) |
| ③ | `feetech_driver/.../serial_port.hpp` | 시리얼 타임아웃 | 02 (이 문서) |
| ④ | `so101_bringup/launch/follower_split.launch.py` | ②와 동일 | [05-moveit](05-moveit.md) |
| ⑤ | `.../follower_split_controllers.yaml` | 그리퍼 컨트롤러 타입 | [05-moveit](05-moveit.md) |
| ⑥ | `so101_moveit_config/config/kinematics.yaml` | IK 플러그인 부재 | [05-moveit](05-moveit.md) |
| ⑦ | `.../ompl_planning.yaml`, `.../pilz_*.yaml` | MoveIt 파이프라인 형식 | [05-moveit](05-moveit.md) |
| ⑧ | `.../moveit_controllers.yaml` | 그리퍼 액션 타입 | [05-moveit](05-moveit.md) |

> 이 수정들은 `git pull` 하면 사라진다. 원본 옆에 `.bak`을 남겨두고,
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
이 프로젝트에서 겪은 문제 대부분이 mock에서도 재현되는 설정 문제였다.

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
원본은 이것을 토픽으로 받도록 되어 있는데, 발행 쪽과 구독 쪽 경로가 어긋나 있었다.

| 노드 | 경로 |
|---|---|
| `robot_state_publisher` (발행) | `/follower/robot_description` |
| `controller_manager` (구독) | `~/robot_description` = `/follower/controller_manager/robot_description` |

`~`는 노드 프라이빗 네임스페이스라서 노드 이름이 경로에 한 칸 더 들어간다.
토픽 대기를 우회하고 **파라미터로 직접 넘기는** 방식을 택했다.

### 실행

```bash
ros2 launch so101_bringup follower.launch.py \
  hardware_type:=mock \
  arm_controller:=trajectory_controller \
  use_rviz:=true
```

**launch 인자를 반드시 명시한다.**
`hardware_type` 기본값이 `real`, `arm_controller` 기본값이 `forward_controller`다.
아무 인자 없이 실행하면 실물에 보간 없는 즉시 이동 명령이 걸린다.
남의 리포를 쓸 때 `DeclareLaunchArgument`의 기본값을 먼저 읽어야 하는 이유다.

새 터미널에서 확인한다.

```bash
ros2 node list
ros2 control list_controllers -c /follower/controller_manager
ros2 topic echo /follower/joint_states --once
```

### 결과

```
=== 컨트롤러 ===
joint_state_broadcaster  joint_state_broadcaster/JointStateBroadcaster          active
trajectory_controller    joint_trajectory_controller/JointTrajectoryController  active

=== joint_states ===
name:     [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
effort:   [nan, nan, nan, nan, nan, nan]
```

### 체크포인트

**launch 로그에 이 줄이 나와야 다음으로 간다.**

```
[INFO] [spawner-4]: process has finished cleanly
```

spawner는 컨트롤러를 등록하고 **끝나야 하는** 일회성 프로세스다.
수정 ② 전에는 종료되지 않고 `Could not contact service`를 반복했다.
깨끗하게 종료됐다는 것은 controller_manager가 로봇 모델을 제대로 받았다는 뜻이다.

RViz에 로봇 모델이 표시되고, `position`이 전부 `0.0`이면 정상이다.
mock은 실물 관절 각도를 알 수 없으므로 원점을 그대로 보고한다.
`effort`가 `nan`인 것은 mock이 토크를 측정하지 않기 때문이다.

---

### 잘못 예상한 것 — 컨트롤러 개수

컨트롤러가 3개(`joint_state_broadcaster`, `trajectory_controller`, `gripper_controller`)
활성화될 것으로 예상했으나 2개였다.

`gripper_controller`는 `follower_split_controllers.yaml`에만 정의되어 있다.
`follower.launch.py`가 쓰는 구성에서는 `trajectory_controller` 하나가
**그리퍼를 포함한 6축 전부**를 담당한다. `joint_states`에 `gripper`가 있는 것이 그 증거다.

컨트롤러를 팔 5축과 그리퍼로 쪼개는 것은 `follower_split` 계열 구성이고,
MoveIt이 그리퍼를 별도 액션으로 다루기 위해 필요하다.

---

### 막힌 것 — 스크립트 안의 환경 활성화가 동작하지 않음

**증상**

명령을 스크립트로 만들어 `bash run.sh`로 실행했더니 첫 줄에서 경고가 났다.

```
'micromamba' is running as a subprocess and can't modify the parent shell.
critical libmamba Shell not initialized
```

그런데 뒤의 ROS 명령들은 정상 실행됐다.

**처음 세운 가설**

셸 초기화가 안 된 것이니 `micromamba shell init`을 실행하면 된다.

**어떻게 좁혔나**

경고 문구에 답이 있었다 — `is running as a subprocess`.
`bash run.sh`는 **자식 셸**을 만든다. 자식 프로세스는 부모 셸의 환경 변수를 바꿀 수 없다.
`activate`가 하는 일이 PATH 수정이므로 구조적으로 불가능한 요청이었다.

뒤의 명령이 동작한 이유는 별개다. **터미널에서 이미 환경을 켜둔 상태였고,
그 PATH가 자식 셸에 상속됐기 때문**이다. 활성화 성공이 아니라 상속이다.

**수정**

스크립트에서 `activate` 줄을 뺀다. 터미널에서 먼저 활성화한 뒤 스크립트를 실행한다.
스크립트 안에서 반드시 지정해야 한다면 `micromamba run -n rosenv <명령>`을 쓴다.

**일반화**

- **자식 프로세스는 부모의 환경을 바꿀 수 없다.** `activate`, `source`, `export`처럼
  현재 셸을 바꾸는 명령은 스크립트에 넣어도 호출한 셸에 반영되지 않는다.
- 경고가 떴는데 결과가 잘 나오면 더 위험하다. 우연히 동작하는 것을
  "동작한다"로 기록하면 환경이 조금만 달라져도 재현되지 않는다.

---

## 02. 실물 하드웨어

**전제 조건:** 01이 통과했을 것. 서보 전원 인가. USB 연결.

### 사전 점검 — 세 가지를 순서대로

실물에 명령을 보내기 전에 아래층부터 확인한다.

```
[launch] → [xacro] → [controller_manager] → [하드웨어 플러그인] → [시리얼] → [서보]
                                                                            ↑
                                                            여기를 먼저 단독 테스트
```

**① 포트와 권한**

```bash
ls -l /dev/so101_follower
ls -l /dev/ttyACM*
cat /etc/udev/rules.d/99-so101.rules
fuser -v /dev/ttyACM0
```

```
/dev/so101_follower -> ttyACM0
crw-rw-rw- 1 root dialout 166, 0 /dev/ttyACM0
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d3", SYMLINK+="so101_follower", MODE="0666"
```

udev 규칙의 역할은 두 가지다.

| 항목 | 효과 |
|---|---|
| `SYMLINK+="so101_follower"` | `ttyACM0`/`ttyACM1`이 바뀌어도 같은 이름으로 접근 |
| `MODE="0666"` | **권한 부여가 매번 불필요해진다** |

권한이 `crw-rw-rw-`면 `sudo chmod`나 `dialout` 그룹 가입이 필요 없다.
udev 규칙을 만들기 전에는 연결할 때마다 권한을 줘야 했는데, 규칙 적용 후 그 단계가 사라졌다.

`fuser`에 프로세스가 잡히면 이전 실행이 안 죽은 것이다. 그대로 launch하면 포트 열기에 실패한다.

**② 서보 단독 통신 — ROS를 빼고 확인**

[scripts/servo-ping.py](scripts/servo-ping.py)로 서보에 직접 PING 패킷을 보낸다.

```bash
python3 scripts/servo-ping.py
```

```
포트 열림: /dev/so101_follower @ 1000000
ID  응답  에러바이트
  1   O      0x00
  2   O      0x00
  3   O      0x00
  4   O      0x00
  5   O      0x00
  6   O      0x00
응답한 ID: [1, 2, 3, 4, 5, 6]
```

**이 단계가 판정을 절반으로 줄인다.** 여기서 6개가 응답하면
이후 어떤 에러가 나도 "하드웨어 고장"이 아니라 "설정 불일치"로 확정된다.

에러 바이트 `0x00`은 서보 내부 이상 플래그가 없다는 뜻이다 — 과열·과부하·전압 이상 없음.

**③ 실행할 스크립트의 인자 확인**

실물에 명령을 보내기 직전이므로 `cat`으로 내용을 읽고 실행한다.

| 확인할 인자 | 안전한 값 |
|---|---|
| `hardware_type` | `real` (의도한 경우에만) |
| `arm_controller` | **`trajectory_controller`** — 생략하면 `forward_controller`가 걸린다 |
| `joint_config_file` | 캘리브레이션 yaml 경로 |
| `usb_port` | `/dev/so101_follower` |

### 코드 — 수정 ③

시리얼 응답 타임아웃이 이 USB 칩에는 너무 짧았다.

```diff
--- a/feetech_driver/include/feetech_driver/serial_port.hpp
+++ b/feetech_driver/include/feetech_driver/serial_port.hpp
@@ -67,5 +67,5 @@ class SerialPort {
   std::string dev_;
-  std::chrono::milliseconds timeout_ = std::chrono::milliseconds(5);
+  std::chrono::milliseconds timeout_ = std::chrono::milliseconds(50);
   LibSerial::SerialPort port_;
```

`servo-ping.py`가 30ms 타임아웃으로 정상 응답을 받는다는 사실이 이 수정의 근거다.
5ms는 이 칩의 왕복 지연보다 짧다.

### 실행

```bash
ros2 launch so101_bringup follower.launch.py \
  hardware_type:=real \
  usb_port:=/dev/so101_follower \
  joint_config_file:=~/so101_ws/myconfig/my_follower_joints.yaml \
  arm_controller:=trajectory_controller \
  use_rviz:=true
```

**팔에서 손을 뗀 상태로 실행한다.** 토크가 걸리면 팔이 딱딱해진다. 그것이 통신 확립 신호다.

### 결과

```
position:
- 0.5568350260024878     shoulder_pan
- -1.6413594430376361    shoulder_lift
- 1.538582730249298      elbow_flex
- 1.3360972662483934     wrist_flex
- -1.6398254622497503    wrist_roll
- 0.17487380981896308    gripper
```

### 체크포인트

`joint_states`의 `position` 값으로 판정한다.

| 값 | 의미 |
|---|---|
| 전부 `0.0` | mock이 뜬 것. `hardware_type` 인자 확인 |
| **0이 아닌 제각각의 값** | 실물 각도를 읽고 있다 |

0이 아닌 값이 나오면 **캘리브레이션까지 정상**이라는 뜻이다.
서보의 원시 틱 값이 라디안으로 제대로 변환됐다는 증거다.
RViz 모델의 자세가 실물과 눈으로 비슷하면 좌표 변환도 맞다.

---

### 알게 된 것 — rest pose는 상수가 아니다

브링업 직후의 관절 각도를 이전 기록과 비교했더니 상당히 달랐다.

| 관절 | 이전 기록 | 이번 |
|---|---|---|
| shoulder_pan | −0.106 | **0.557** |
| shoulder_lift | −1.631 | −1.641 |
| elbow_flex | 1.522 | 1.539 |
| wrist_flex | −1.661 | **+1.336** |
| wrist_roll | −0.126 | **−1.640** |
| gripper | 0.233 | 0.175 |

고장이 아니다. **rest pose는 로봇의 고유값이 아니라 "마지막에 팔이 놓여 있던 자세"** 다.
토크가 꺼진 동안 팔은 중력과 손에 맡겨져 있다가, 브링업 순간 그 자세 그대로 굳는다.

중력이 크게 작용하는 `shoulder_lift`, `elbow_flex`는 값이 거의 같고,
손으로 돌리기 쉬운 `shoulder_pan`, `wrist_roll`은 크게 달랐다. 설명과 일치한다.

**일반화:** 측정값을 문서에 표로 적을 때는 **그것이 상수인지 그때의 상태인지** 함께 적는다.
표 형태는 상수처럼 보이게 만든다. 이전 문서에서 이 값을 "첫 실측 관절 각도"로 적어둔 것이
재현 시 혼란의 원인이 됐다.

한 가지가 여기서 풀렸다. [03-urdf-and-tf](03-urdf-and-tf.md)에서
`wrist_flex`가 URDF 범위(±1.6581)를 벗어난다고 기록했는데(−1.661),
이번 값 1.336은 범위 안이다. 즉 URDF나 캘리브레이션의 결함이 아니라
**그날 팔이 그 자세로 놓여 있었기 때문**일 가능성이 크다. 확정은 [05-moveit](05-moveit.md)에서 한다.

---

## 03. 실물 관절 움직이기

목표 값 6개를 손으로 적는 방식은 위험하다. 현재 자세를 잘못 적으면 그 관절이 갑자기 튄다.
현재 각도를 읽어 **한 관절만 상대적으로** 움직이는 스크립트를 만들었다.

[scripts/move-joint.py](scripts/move-joint.py)

```bash
python3 scripts/move-joint.py wrist_roll 2.0 5
```



https://github.com/user-attachments/assets/28ab2266-8b5a-47b0-b1b5-1e61290dd6ab




`wrist_roll`을 현재 위치에서 +2.0 rad(114°), 5초에 걸쳐 회전시킨다.




https://github.com/user-attachments/assets/264fe7c9-a8bf-4605-8566-81a01a9d2ba0


```
현재: 0.557 -1.641 1.539 1.336 -1.640 0.175
목표: 0.557 -1.641 1.539 1.336 0.360 0.175
wrist_roll : -1.640 -> 0.360  (114.6 deg, 5.0초)
전송 완료
```

**스크립트가 하는 일**

| 기능 | 이유 |
|---|---|
| 현재 각도를 읽어 나머지 5개를 그대로 유지 | 손으로 적다 틀리면 다른 관절이 튄다 |
| URDF limit으로 목표를 잘라냄 | 범위 밖 명령을 애초에 보내지 않는다 |
| 전송 전 현재/목표를 출력 | 실행 직전 눈으로 확인 |

`allow_partial_joints_goal: false`이므로 6개 값을 항상 전부 보내야 한다.
이 제약이 곧 "현재값을 알아야 한다"는 요구가 되고, 그래서 `joint_states`를 먼저 읽는다.

### 결과

`wrist_roll`, `gripper`, `shoulder_pan` 모두 지정한 시간에 걸쳐 부드럽게 이동했다.
RViz 모델과 실물이 같이 움직인다.

mock에서 보낸 것과 **같은 형식의 명령**이며, `hardware_type`만 다르다.
[04-ros2-control](04-ros2-control.md)에서 확인한 계층 분리가 여기서 실제 효과를 낸다.

---

### 무시해도 되는 메시지

| 메시지 | 이유 |
|---|---|
| `A message was lost!!!` | `--once`로 즉시 구독을 해제해서 발생 |
| `Could not enable FIFO RT scheduling policy` | 관리자 권한 없이 실행. 제어 주기에는 문제없음 |
| `kdl_parser: root link base_link has an inertia` | KDL이 루트 링크 관성을 무시할 뿐 |

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| mock 하드웨어 | 명령을 즉시 도달했다고 응답하는 껍데기. 설정 오류 전용 검증 도구 |
| `robot_description` | URDF 문자열. `ros2_control`이 관절 구조를 아는 유일한 경로 |
| `~` 네임스페이스 | `~/topic` = `/노드이름/topic` |
| spawner | 컨트롤러를 등록하고 종료하는 일회성 프로세스. 살아 있으면 대기 중 |
| udev 규칙 | 장치 이름 고정 + 권한 설정. `MODE="0666"`이면 권한 부여 불필요 |
| 아래층부터 확인 | 시리얼·서보를 ROS 없이 먼저 테스트하면 원인 후보가 절반으로 준다 |
| rest pose | 상수가 아니라 마지막에 팔이 놓여 있던 자세 |

## 확인하지 않고 넘어간 것

- `hardware_interface`의 `read()` / `write()` 구현 코드 읽기
- 통신 실패 시 컨트롤러의 복구 동작
- 장시간 구동 시 서보 온도

## 다음

[03-urdf-and-tf.md](03-urdf-and-tf.md)
