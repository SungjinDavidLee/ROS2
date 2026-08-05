# 03. URDF와 TF

로봇의 구조가 어떻게 기술되고, 그 구조가 실행 중에 어떻게 좌표 관계로 바뀌는지 확인한다.
mock 하드웨어를 띄운 상태에서 진행했다.

---

## 01. 개념

| | 정체 | 성격 |
|---|---|---|
| **URDF** | 링크(뼈대)와 조인트(관절)를 XML로 적은 설계도 | 정적 |
| **xacro** | 매크로·변수를 쓸 수 있는 URDF 템플릿. 실행 시 URDF로 펼쳐진다 | 정적 |
| **TF** | URDF + 현재 관절각 → 지금 이 순간의 좌표계 관계를 계산해 방송 | 동적 |

카메라가 본 물체 위치는 카메라 기준 좌표다. 팔을 움직이려면 팔 기준 좌표가 필요하다.
이 둘을 잇지 못하면 "저기 있는 걸 집어라"가 성립하지 않는다.

URDF는 연결 관계만 알려준다. 관절이 움직이면 실제 좌표는 매 순간 바뀌므로,
그 계산을 계속 돌려 토픽으로 뿌리는 것이 TF다.

> 물리 시뮬레이터의 body 중첩 구조와 같은 역할이다.
> 다만 시뮬레이터는 좌표 전파를 엔진 내부에서 계산하고,
> ROS는 그것을 **토픽으로 방송해서 아무 노드나 구독할 수 있게** 한다.
> xacro는 C 매크로 전처리기와 같은 위치다.

---

## 02. TF 트리 확인

### 실행

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash

ros2 run tf2_tools view_frames
```

5초간 TF를 수집해 `frames.pdf`를 만든다.

### 결과

```
base_link
└── shoulder_link
    └── upper_arm_link
        └── lower_arm_link
            └── wrist_link
                └── gripper_link
                    ├── moving_jaw_so101_v1_link
                    └── gripper_frame_link      (static)
```

링크 8개. 그리퍼에서 가지가 둘로 갈린다.
하나는 실제로 움직이는 집게턱, 하나는 작업 기준점이다.

### static transform과 dynamic transform

`view_frames` 출력에서 `gripper_frame_link`만 수치가 달랐다.

| 프레임 | rate | most_recent_transform | Average Delay |
|---|---|---|---|
| 나머지 6개 | 17.96 Hz | 현재 시각 | 0.0002초 |
| `gripper_frame_link` | 10000.0 | **0.000000** | **1301.65** |

고장이 아니라 **static transform**이다.

| | dynamic | static |
|---|---|---|
| 대상 | 관절이 움직여 변하는 관계 | `fixed` 조인트, 카메라 장착 위치 |
| 발행 | 관절각이 바뀔 때마다 계속 | 한 번 |
| 타임스탬프 | 현재 시각 | 0 |

절대 변하지 않는 관계를 매번 다시 보낼 이유가 없으므로 한 번만 발행하고 타임스탬프를 `0`으로 둔다.
`tf2_monitor`는 `현재시각 − 0`을 지연으로 계산하므로 1301초라는 값이 나온다.
`rate: 10000`은 "무한대" 자리표시자다.

나중에 카메라를 팔 좌표계에 붙일 때 쓰는 것이 이 static transform이다.

---

## 03. 실제 좌표값 읽기

### 실행

```bash
ros2 run tf2_ros tf2_echo base_link gripper_frame_link
ros2 run tf2_ros tf2_echo gripper_link gripper_frame_link
```

### 결과

**`base_link → gripper_frame_link`** (전 관절 0도)

```
- Translation: [0.391, -0.000, 0.226]
- Rotation: in RPY (degree) [89.989, 87.211, 89.990]
```

베이스에서 앞으로 39.1cm, 위로 22.6cm. 이 로봇의 도달 범위 감각이 여기서 나온다.

**`gripper_link → gripper_frame_link`** (static)

```
At time 0.0
- Translation: [-0.008, -0.000, -0.098]
- Rotation: in RPY (degree) [180.000, 0.000, 180.000]
```

그리퍼 링크에서 9.8cm 떨어진 지점에 좌표계가 붙어 있고, 180° 뒤집혀 있다.
이것이 TCP(작업점)이며, MoveIt에 "여기로 가라"고 지시할 때의 기준 프레임이다.
뒤집힌 이유는 물체를 내려다보는 방향이 축의 양방향이 되도록 맞춘 것으로 보인다.

`At time 0.0`이 출력되는 것으로 static임이 다시 확인된다.

---

## 04. URDF 구조

### 실행

노드에 직접 물어보는 방식. 파일을 찾지 않아도 된다.

```bash
ros2 param get /follower/robot_state_publisher robot_description > /tmp/rd.txt
```

이후 `/tmp/rd.txt`를 파싱했다. 파싱 스크립트는 [scripts/urdf-limits.py](scripts/urdf-limits.py).

### 조인트

| 조인트 | 타입 | lower | upper | 도 |
|---|---|---|---|---|
| `shoulder_pan` | revolute | −1.9199 | 1.9199 | ±110.0 |
| `shoulder_lift` | revolute | −1.7453 | 1.7453 | ±100.0 |
| `elbow_flex` | revolute | −1.6900 | 1.6900 | ±96.8 |
| `wrist_flex` | revolute | −1.6581 | 1.6581 | ±95.0 |
| `wrist_roll` | revolute | −2.7439 | 2.8412 | −157.2 ~ 162.8 |
| `gripper` | revolute | −0.1745 | 1.7453 | −10.0 ~ 100.0 |
| `gripper_frame_joint` | **fixed** | — | — | — |

링크 8개, 조인트 7개. 뼈 n개를 잇는 관절이 n−1개라는 관계가 성립한다.
`gripper_frame_joint`가 `fixed`이기 때문에 앞서 static TF로 나온 것이고,
트리 그림과 URDF 텍스트가 서로 일치한다.

| 타입 | 의미 |
|---|---|
| `revolute` | 범위가 정해진 회전 |
| `continuous` | 무한 회전 (이 로봇에는 없음) |
| `fixed` | 고정. 관절이 아니라 좌표계 부착점 |

`limit` 값이 110°, 100°, 95° 같은 반올림 숫자인 것으로 보아
실측이 아니라 설계값으로 기입된 것으로 보인다.

---

### 발견한 것 — 시작 자세가 URDF 범위를 벗어난다

`wrist_flex`의 하한은 **−1.6581**인데, 실물 rest pose는 **−1.661**이다.
**0.0029 rad(0.17°) 만큼 범위 밖**이다. 나머지 관절은 전부 범위 안이다.

| 관절 | rest pose | 범위 | |
|---|---|---|---|
| shoulder_pan | −0.106 | ±1.9199 | 안 |
| shoulder_lift | −1.631 | ±1.7453 | 안 |
| elbow_flex | 1.522 | ±1.6900 | 안 |
| **wrist_flex** | **−1.661** | **±1.6581** | **밖** |
| wrist_roll | −0.126 | −2.74 ~ 2.84 | 안 |
| gripper | 0.233 | −0.17 ~ 1.75 | 안 |

시작 자세가 범위를 벗어나면 모션 플래너는 원칙적으로 계획을 거부한다.
그래서 플래닝 파이프라인 설정에 `FixStartStateBounds` 어댑터가 들어 있다 —
살짝 넘은 시작 자세를 경계값으로 밀어넣어 계획을 진행시키는 보정기이며,
허용 폭은 `start_state_max_bounds_error: 0.1`이다. 0.0029는 여기에 들어간다.

원인은 두 가지 중 하나다.

1. URDF limit이 실제 기구 가동범위보다 좁게 적혀 있다
2. 캘리브레이션 원점이 살짝 밀려 있다

**지금은 판정하지 않는다.** [05-moveit](05-moveit.md)에서 실제 경고 메시지로 확인한다.
limit이 반올림된 설계값으로 보이므로 1번 쪽이 유력하다는 것이 현재의 추정이다.

---

### 막힌 것 — 프레임 이름을 추측해서 넣었다

**증상**

```
Invalid frame ID "gripper_frame" ... frame does not exist
```

**원인**

실제 이름은 `gripper_frame_link`다. `_link` 접미사를 빼고 짐작했다.

**일반화**

프레임 이름은 추측하지 않는다. `view_frames` 출력이나 `ros2 run tf2_ros tf2_monitor`로
**실제 방송되고 있는 이름을 먼저 읽는다.** URDF의 링크 이름이 곧 프레임 이름이 된다.

---

### 막힌 것 — "frame does not exist"의 두 가지 의미

**증상**

에러 메시지 두 줄의 불평 대상이 서로 달랐다.

```
1행: Invalid frame ID "base_link" ... frame does not exist
2행: Invalid frame ID "gripper_frame" ... frame does not exist
```

**처음 세운 가설**

`base_link`가 없다. URDF의 루트 링크 이름이 다른 것 같다.

**어떻게 좁혔나**

`base_link`는 트리의 루트로 분명히 존재한다. 두 줄의 타임스탬프 차이는 1.6초.
두 번째 시도에서는 `base_link`에 대한 불평이 사라지고 `gripper_frame`만 남았다.

**원인**

첫 줄은 `tf2_echo`가 막 실행되어 **아직 TF를 하나도 수신하지 못한 순간**의 메시지다.
TF는 방송이므로 구독을 시작한 시점부터 채워진다. 프레임이 없는 것이 아니라 아직 안 온 것이다.

**일반화**

TF의 "frame does not exist"는 두 가지를 뜻한다 — **진짜 없거나, 아직 안 왔거나.**
재시도 메시지에서 불평 대상이 줄어드는지 보면 갈린다.
첫 줄만 보고 판단했다면 없는 문제를 찾아 URDF를 뒤졌을 것이다.

---

### 막힌 것 — 어떤 ros2 명령만 실패했다

**증상**

같은 터미널에서 한 명령은 실패하고 다른 명령은 성공했다.

```
$ ros2 pkg prefix so101_description
Package not found

$ ros2 param get /follower/robot_state_publisher robot_description
(정상 출력)
```

**원인**

터미널을 새로 열고 `source install/setup.bash`를 하지 않았다.
두 명령이 의존하는 대상이 다르다.

| 명령 | 무엇에 의존하는가 | sourcing 필요 |
|---|---|---|
| `ros2 pkg`, `ros2 run`, `ros2 launch` | **파일 시스템** — 패키지 경로를 찾아야 한다 | 필요 |
| `ros2 node`, `ros2 topic`, `ros2 param` | **실행 중인 노드** — DDS로 물어본다 | 불필요 |

**일반화**

ROS 명령 중 일부만 실패할 때는, 그 명령이 **파일을 찾는지 노드에 묻는지**부터 구분한다.
파일을 찾는 쪽만 실패하면 워크스페이스 sourcing 문제다.
반대로 노드에 묻는 쪽만 실패하면 노드가 안 떠 있거나 `ROS_DOMAIN_ID`가 다른 것이다.

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| URDF | 링크와 조인트의 정적 설계도 |
| xacro | 매크로를 쓰는 URDF 템플릿. 전처리기와 같은 위치 |
| TF | URDF + 관절각을 실시간 좌표 관계로 바꿔 방송하는 시스템 |
| static transform | 변하지 않는 관계. 한 번만 발행, 타임스탬프 0 |
| TCP (`gripper_frame_link`) | 작업 기준점. 모션 플래닝의 목표 프레임 |
| `revolute` / `fixed` | 범위 있는 회전 / 좌표계 부착점 |
| 조인트 `limit` | 소프트웨어 가동범위. 실제 기구 범위와 다를 수 있다 |

## 확인하지 않고 넘어간 것

- `so101_description/launch/display.launch.py` (URDF 단독 확인용 launch).
  경로 버그가 있어 수정했으나(`urdf/` → `urdf/legacy/`), 이 세션에서는 실행하지 않았다.
  브링업이 띄우는 `robot_state_publisher`로 대신했다.
- `wrist_flex` 범위 초과의 실제 원인
- RViz 모델 자세와 실물 자세의 시각적 일치

## 다음

[04-ros2-control.md](04-ros2-control.md)
