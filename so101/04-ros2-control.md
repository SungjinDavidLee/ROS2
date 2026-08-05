# 04. ros2_control

컨트롤러가 무엇을 하는지, 그리고 컨트롤러를 바꾸면 무엇이 달라지는지 mock 하드웨어에서 확인한다.

---

## 01. 구조

### 개념

`ros2_control`은 **"명령을 어떻게 만들 것인가"** 와
**"그 명령을 하드웨어에 어떻게 전달할 것인가"** 를 분리하는 계층이다.

```
[MoveIt / 사용자 노드]
      │  목표
      ▼
[controller]              어떻게 갈 것인가
      │  command interface
      ▼
[hardware_interface]      mock 또는 실물 서보
      │  state interface
      ▲
   실제 관절 상태
```

이 분리 덕분에 `hardware_type:=mock`을 `real`로 바꾸는 것만으로
같은 컨트롤러가 실물에서 돈다. 제어 로직과 통신 코드가 한 덩어리였다면
실물 없이 검증하는 것 자체가 불가능하다.

> 서보 SDK로 직접 제어할 때는 "목표 위치 계산"과 "패킷 전송"이 보통 한 파일에 섞인다.
> `ros2_control`은 아래쪽(패킷 전송)을 `hardware_interface`로,
> 위쪽(목표 계산)을 `controller`로 떼어낸다.

### launch 인자는 두 축이다

```bash
ros2 launch so101_bringup follower.launch.py \
  hardware_type:=mock \
  arm_controller:=trajectory_controller
```

| 인자 | 선택지 | 바뀌는 것 |
|---|---|---|
| `hardware_type` | `mock` / `real` | 진짜 서보로 패킷이 나가는지 |
| `arm_controller` | `forward_controller` / `trajectory_controller` | 목표까지 **어떻게** 갈지 |

서로 독립이다. 이 문서의 실험은 전부 `hardware_type:=mock` 상태에서 컨트롤러만 바꿔가며 했다.

**둘 다 기본값이 위험한 쪽이다.** 인자를 생략하면 `real` + `forward_controller`가 걸린다.
실물에 보간 없는 즉시 이동 명령이 나가는 조합이다.

### 실행

```bash
ros2 control list_hardware_interfaces -c /follower/controller_manager
ros2 control list_controllers -c /follower/controller_manager
```

### 결과

```
Hardware Component 1
	name: SO101_follower_SYSTEM
	type: system
	plugin name: mock_components/GenericSystem
	state: id=3 label=active

command interfaces
	shoulder_pan/position   [available] [claimed]
	shoulder_lift/position  [available] [claimed]
	elbow_flex/position     [available] [claimed]
	wrist_flex/position     [available] [claimed]
	wrist_roll/position     [available] [claimed]
	gripper/position        [available] [claimed]

state interfaces
	(각 관절의 position, velocity — 총 12개)
```

| | 개수 | 방향 |
|---|---|---|
| command interface | 6 (position) | 컨트롤러가 **쓴다** |
| state interface | 12 (position + velocity) | 컨트롤러가 **읽는다** |

**`[claimed]`가 핵심이다.** command interface 6개를 컨트롤러 하나가 전부 점유하고 있다.
하나의 command interface는 한 컨트롤러만 잡을 수 있다.
두 컨트롤러가 같은 관절에 서로 다른 명령을 쓰면 결과가 정의되지 않기 때문이다.

그래서 컨트롤러 교체는 "추가"가 아니라 **"놓게 하고 잡게 하기"** 다.

state interface에는 `[claimed]`이 없다. 읽기는 여러 노드가 동시에 해도 상관없다.
`joint_state_broadcaster`가 이것을 읽어 `/joint_states` 토픽으로 발행한다.

---

## 02. 컨트롤러 비교 — trajectory vs forward

같은 목표를 두 컨트롤러로 보내 도달 방식의 차이를 확인한다.
`shoulder_pan`을 0 → 0.5 rad(약 29°)로 움직인다.

### trajectory_controller

```bash
ros2 launch so101_bringup follower.launch.py \
  hardware_type:=mock arm_controller:=trajectory_controller use_rviz:=true
```

```bash
ros2 topic pub --once \
  /follower/trajectory_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{ joint_names: [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper],
     points: [{ positions: [0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
                time_from_start: {sec: 3, nanosec: 0} }] }'
```
[Screencast from 2026년 08월 05일 10시 22분 28초.webm](https://github.com/user-attachments/assets/cc423c1b-a453-4b56-bc53-62af031e7ae9)

[Screencast from 2026년 08월 05일 10시 22분 44초.webm](https://github.com/user-attachments/assets/64b9402d-77d6-4cd2-b8a1-b770afda1f36)

RViz 모델이 **3초에 걸쳐 부드럽게** 회전한다.
컨트롤러가 시작점과 목표점 사이를 보간해 중간 지점을 계속 만들어낸다
(로그에 `Using 'splines' interpolation method`).

**관절 값 6개를 전부 넣어야 한다.** 이 컨트롤러는 `allow_partial_joints_goal: false`이므로
일부만 보내면 거부된다. 움직이지 않을 관절은 현재값을 그대로 넣는다.

### forward_controller

```bash
ros2 launch so101_bringup follower.launch.py \
  hardware_type:=mock arm_controller:=forward_controller use_rviz:=true
```

토픽 이름과 타입이 다르다. 먼저 확인한다.

```bash
ros2 topic list | grep follower
ros2 topic info /follower/forward_controller/commands
```

```
/follower/forward_controller/commands   std_msgs/msg/Float64MultiArray
```

```bash
ros2 topic pub --once \
  /follower/forward_controller/commands \
  std_msgs/msg/Float64MultiArray \
  '{data: [0.5, 0.0, 0.0, 0.0, 0.0, 0.0]}'
```
[Screencast from 2026년 08월 05일 10시 33분 57초.webm](https://github.com/user-attachments/assets/21e5dca4-131d-4fcf-9ce8-e2fbc0012c11)

RViz 모델이 **한 프레임에 순간이동**한다.

[Screencast from 2026년 08월 05일 10시 34분 13초.webm](https://github.com/user-attachments/assets/375bfaaa-bff0-4838-8668-44ac1176fc0a)


### 차이

| | trajectory | forward |
|---|---|---|
| 메시지 타입 | `JointTrajectory` | `Float64MultiArray` |
| 관절 이름 | 있음 | **없음** — 순서로만 구분 |
| 소요 시간 | `time_from_start` | **없음** |
| 중간 지점 | 컨트롤러가 보간 | 없음 |
| mock에서 | 3초에 걸쳐 이동 | 순간이동 |
| 실물에서 | 안전 | 서보가 최대 속도로 튄다 |

메시지 형식 자체가 차이를 말해준다.
forward에는 관절 이름이 없다. **순서를 틀리면 엉뚱한 관절이 움직인다**는 뜻이다.
시간도 없으니 "언제까지 도달할지"를 컨트롤러가 알 방법이 없고,
받은 값을 그대로 command interface에 쓰는 것이 전부다.

mock 하드웨어는 명령받은 위치에 즉시 도달했다고 응답하는 껍데기이므로,
forward에서는 목표값이 그대로 상태가 된다.
실물에서는 그 순간이동을 서보가 물리적으로 따라가려 하면서 급격히 튄다.

> forward가 쓸모없다는 뜻은 아니다. 상위에서 이미 궤적을 만들어 고주기로 흘려보내는 경우
> (예: 매 프레임 목표를 갱신하는 시각 기반 제어)에는 보간이 오히려 방해가 된다.
> 다만 **사람이 손으로 목표를 던지는 상황에서는 위험하다.**

---

### 막힌 것 — 패키지를 찾지 못함

**증상**

```
Package 'so101_bringup' not found:
"package 'so101_bringup' not found, searching: ['~/micromamba/envs/rosenv']"
```

**원인**

새 터미널에서 워크스페이스를 source하지 않았다.
에러 메시지의 `searching:` 부분이 답을 그대로 말해준다 — 환경 폴더만 뒤지고 있다.

**수정**

ROS 터미널을 열 때마다 세 줄이 세트다.

```bash
micromamba activate rosenv      # ROS 2 본체
cd ~/so101_ws
source install/setup.bash       # 내가 빌드한 패키지 (오버레이)
```

순서를 바꾸면 안 된다. 오버레이는 아래층 위에 덮는 구조다.

**일반화**

`ros2 node`, `ros2 topic`, `ros2 param`은 3번 없이도 동작한다.
그건 파일이 아니라 실행 중인 노드에 묻는 명령이다.
[03-urdf-and-tf](03-urdf-and-tf.md)에서 같은 구분을 이미 만났다.

---

### 막힌 것 — 서비스 호출이 무한 대기

**증상**

```
[INFO] waiting for service /controller_manager/list_controller_types to become available...
[WARN] Could not contact service /controller_manager/list_controller_types
```

10초 간격으로 무한 반복. 에러로 종료되지 않는다.

**원인**

`-c /follower/controller_manager` 옵션을 빠뜨렸다.
이 스택은 모든 노드가 `/follower/` 네임스페이스 아래 있어서
기본 경로인 `/controller_manager`에는 아무도 없다.

```bash
ros2 control list_controller_types -c /follower/controller_manager
```

**일반화**

**ROS에서 없는 주소에 말을 걸면 에러가 아니라 무한 대기다.**
서비스는 상대가 나타날 때까지 기다리도록 설계되어 있다.

이 패턴은 [02-hardware-bringup](02-hardware-bringup.md)의 spawner 문제와 정확히 같다.
에러 없이 멈춰 있을 때는 **로그의 마지막 줄이 "무엇을 기다리는 중인가"** 를 알려준다.
그 이름이 실제로 존재하는지 `ros2 service list`, `ros2 node list`로 대조하는 것이 다음 단계다.

또 하나. 처음 실행할 때 `2>/dev/null`로 에러를 가려서 빈 출력만 보고 원인을 놓쳤다.
**진단 단계에서 에러 출력을 버리면 안 된다.**

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| command / state interface | 컨트롤러가 쓰는 곳 / 읽는 곳 |
| `[claimed]` | 인터페이스 점유. command는 배타적, state는 공유 가능 |
| 컨트롤러 교체 | 추가가 아니라 인터페이스를 놓고 다시 잡는 것 |
| `joint_state_broadcaster` | state interface를 읽어 `/joint_states`로 발행하는 전용 컨트롤러 |
| 보간(splines) | 시작점과 목표점 사이 중간 지점을 만들어내는 것 |
| `allow_partial_joints_goal` | false면 모든 관절 값을 매번 보내야 한다 |
| 무한 대기 | ROS 서비스는 상대가 없으면 에러가 아니라 기다린다 |

## 확인하지 않고 넘어간 것

- `hardware_interface`의 `read()` / `write()` 구현 코드 — 실물 세션에서 본다
- 컨트롤러 실행 중 전환(`ros2 control switch_controllers`)
- 그리퍼 전용 컨트롤러 — [05-moveit](05-moveit.md)

## 다음

[05-moveit.md](05-moveit.md)
