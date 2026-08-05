# 05. MoveIt2

관절 각도를 직접 지정하는 대신, **팔 끝을 어디로 보낼지**를 지정하는 단계.

**전제 조건**

- [02-hardware-bringup](02-hardware-bringup.md) 완료 — 실물 브링업으로 팔이 움직임
- [04-ros2-control](04-ros2-control.md) 완료 — 컨트롤러 개념

**ROS 터미널 세 줄**

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash
```

---

## 01. MoveIt은 무엇을 하는가

### 관절 공간과 작업 공간

지금까지는 관절 각도를 직접 지정했다.

```bash
python3 scripts/move-joint.py wrist_roll 2.0 5    # 5번 관절을 114도 회전
```

MoveIt은 팔 끝의 위치를 지정한다.

```
"팔 끝을 (x=0.30, y=0.10, z=0.20)으로"    # 관절 각도는 MoveIt이 계산
```

| | 관절 공간 (joint space) | 작업 공간 (task space) |
|---|---|---|
| 지정하는 것 | 관절 각도 6개 | 팔 끝의 위치와 방향 |
| 쓰는 곳 | 정해진 자세로 이동 | **물체가 있는 곳으로 이동** |

카메라가 물체를 찾으면 나오는 값은 좌표(x, y, z)지 관절 각도가 아니다.
그래서 물체를 집으려면 작업 공간이 필요하다.

### 세 개의 층

| 층 | 하는 일 | 설정 파일 |
|---|---|---|
| **IK 솔버** | 좌표 → 관절 각도 6개 | `kinematics.yaml` |
| **플래너 (OMPL)** | 시작에서 목표까지 충돌 없는 경로 | `ompl_planning.yaml` |
| **컨트롤러 연결** | 만든 궤적을 실제 컨트롤러로 전달 | `moveit_controllers.yaml` |

세 층 중 어디서 실패했는지 로그로 구분하는 것이 이 문서의 핵심이다.

---

## 02. launch 구조

`follower_moveit_demo.launch.py`는 네 덩어리를 띄운다.

```
follower_moveit_demo.launch.py
├── follower_split.launch.py     브링업 (컨트롤러가 여기서 나뉜다)
├── cameras.launch.py            use_cameras:=true 일 때만
├── move_group.launch.py         MoveIt 본체
└── moveit_rviz.launch.py        MotionPlanning 플러그인이 붙은 RViz
```

### 컨트롤러 구성이 지금까지와 다르다

| | `follower.launch.py` | `follower_split.launch.py` (MoveIt) |
|---|---|---|
| 컨트롤러 | `trajectory_controller` 1개 | `arm_trajectory_controller` + `gripper_controller` |
| 담당 관절 | 6축 (그리퍼 포함) | **5축** + 그리퍼 1축 |
| 명령 토픽 | `/follower/trajectory_controller/...` | `/follower/arm_trajectory_controller/...` |

**왜 나누는가.** MoveIt에서 팔과 그리퍼는 다루는 방식이 다르다.
팔은 "경로를 따라 이동", 그리퍼는 "열어라 / 닫아라"다.
후자는 궤적이 아니라 단일 명령이라 전용 액션 타입을 쓴다.

이 때문에 `move-joint.py`는 MoveIt 구성에서 동작하지 않는다. 토픽 이름이 다르다.

### 코드 — 수정 ⑤ 그리퍼 컨트롤러 타입

```diff
--- a/so101_bringup/config/ros2_control/follower_split_controllers.yaml
+++ b/so101_bringup/config/ros2_control/follower_split_controllers.yaml
       gripper_controller:
-        type: parallel_gripper_action_controller/GripperActionController
+        type: position_controllers/GripperActionController
```

### 코드 — 수정 ⑧ MoveIt 쪽 그리퍼 액션 타입

```diff
--- a/so101_moveit_config/config/moveit_controllers.yaml
+++ b/so101_moveit_config/config/moveit_controllers.yaml
   follower/gripper_controller:
-    type: ParallelGripperCommand
+    type: GripperCommand
```

두 이름 모두 상위 배포판(Jazzy)에서 도입된 것이라 Humble에는 존재하지 않는다.
컨트롤러 쪽과 MoveIt 쪽 **양쪽을 다 고쳐야** 한다. 한쪽만 고치면 서로 못 찾는다.

### 코드 — 수정 ⑥ IK 솔버

```diff
--- a/so101_moveit_config/config/kinematics.yaml
+++ b/so101_moveit_config/config/kinematics.yaml
 manipulator:
-  kinematics_solver: pick_ik/PickIkPlugin
-  kinematics_solver_timeout: 0.2
-  approximate: true
-  mode: global
+  kinematics_solver: kdl_kinematics_plugin/KDLKinematicsPlugin
+  kinematics_solver_search_resolution: 0.005
+  kinematics_solver_timeout: 0.05
+  kinematics_solver_attempts: 3
```

`pick_ik`는 별도 설치가 필요한 플러그인이다. MoveIt에 기본 포함된 KDL로 교체했다.

### 코드 — 수정 ⑦ 플래닝 파이프라인 형식

```diff
--- a/so101_moveit_config/config/ompl_planning.yaml
+++ b/so101_moveit_config/config/ompl_planning.yaml
-planning_plugins:
-  - ompl_interface/OMPLPlanner
-request_adapters:
-  - default_planning_request_adapters/ResolveConstraintFrames
-  ...
-response_adapters:
-  - default_planning_response_adapters/AddTimeOptimalParameterization
-  ...
+planning_plugin: ompl_interface/OMPLPlanner
+request_adapters: >-
+    default_planner_request_adapters/AddTimeOptimalParameterization
+    default_planner_request_adapters/ResolveConstraintFrames
+    default_planner_request_adapters/FixWorkspaceBounds
+    default_planner_request_adapters/FixStartStateBounds
+    default_planner_request_adapters/FixStartStateCollision
+    default_planner_request_adapters/FixStartStatePathConstraints
+start_state_max_bounds_error: 0.1
```

세 가지가 동시에 바뀌었다.

| 항목 | 상위 배포판 | Humble |
|---|---|---|
| 키 이름 | `planning_plugins` (복수, 리스트) | `planning_plugin` (단수, 문자열) |
| 어댑터 이름 | `default_planning_request_adapters/...` | `default_planner_request_adapters/...` |
| 어댑터 구분 | YAML 리스트 | 공백으로 구분된 한 문자열 |

`response_adapters`는 Humble에 없어서 `request_adapters`로 합쳤다.
`pilz_industrial_motion_planner_planning.yaml`도 같은 방식으로 고쳤다.

`start_state_max_bounds_error: 0.1`은 뒤에서 다시 나온다.

---

## 03. 실행 — mock 먼저

**`hardware_type` 기본값이 `real`이다.** mock을 쓰려면 반드시 명시한다.

```bash
ros2 launch so101_bringup follower_moveit_demo.launch.py \
  hardware_type:=mock \
  joint_config_file:=~/so101_ws/myconfig/my_follower_joints.yaml
```

새 터미널에서 확인한다.

```bash
ros2 control list_controllers -c /follower/controller_manager
ros2 node list | grep -i move
```

### 결과

```
gripper_controller         position_controllers/GripperActionController           active
arm_trajectory_controller  joint_trajectory_controller/JointTrajectoryController  active
joint_state_broadcaster    joint_state_broadcaster/JointStateBroadcaster          active

/move_group
/moveit_simple_controller_manager
```

### 체크포인트

**컨트롤러가 3개 전부 active여야 한다.**
`gripper_controller`가 빠져 있으면 수정 ⑤가 반영되지 않은 것이다.

`move_group` 노드의 이름에 주의한다. 컨트롤러는 `/follower/` 아래인데
**MoveIt은 전역 네임스페이스(`/move_group`)에 뜬다.**
파라미터를 조회할 때 `/follower/move_group`으로 찾으면 아무것도 나오지 않는다.

```bash
ros2 param get /move_group robot_description_kinematics.manipulator.kinematics_solver
ros2 param get /move_group robot_description_semantic > /tmp/srdf.txt
```

```
String value is: kdl_kinematics_plugin/KDLKinematicsPlugin

group name="manipulator"
group name="gripper"
chain base_link="base_link" tip_link="gripper_frame_link"
```

IK 체인의 끝점이 `gripper_frame_link`다.
[03-urdf-and-tf](03-urdf-and-tf.md)에서 static transform으로 확인한 그 TCP다.

---

## 04. RViz에서 조작하기

1. Displays → MotionPlanning → Planning Request → **Query Goal State** 체크
2. 팔 끝에 인터랙티브 마커가 나타난다
3. 마커를 드래그해 목표를 정한다
4. Planning 탭 → **Plan**
5. 궤적이 애니메이션으로 재생된다
6. **Execute**

**Plan과 Execute를 따로 누른다.** `Plan and Execute` 버튼은 둘을 묶어서
실패했을 때 어느 쪽이 문제인지 구분이 늦어진다.

### 마커 색이 1차 판정 기준이다

| 색 | 의미 |
|---|---|
| 주황 / 초록 | IK 해가 있다. Plan 시도 가능 |
| **빨강** | IK 해가 없다. Plan해도 실패한다 |

빨간 상태에서 Plan을 누르면 반드시 실패한다. 누르기 전에 색을 본다.

---

## 05. 실패 유형 세 가지 — 로그로 구분하는 법

따라 하다 보면 반드시 만나게 된다. 세 가지가 전부 다른 층의 문제다.

### ① IK 실패 — 목표에 해가 없다

```
RRTConnect.cpp:225 - manipulator/manipulator: Insufficient states in sampleable goal region
ParallelPlan::solve(): Unable to find solution by any of the threads in 0.000141 seconds
Unable to solve the planning problem
```

**판정 근거는 소요 시간이다.** `0.000141초`.
탐색을 시작조차 못 했다는 뜻이다. 목표 자세를 관절 각도로 바꿀 수가 없으니
플래너 입장에서는 향할 곳 자체가 없다.

원인은 셋 중 하나다.

| 원인 | 확인 |
|---|---|
| 목표가 도달 범위 밖 | 마커가 빨강 |
| 그 위치는 되는데 그 **방향**으로는 불가능 | 마커 회전을 되돌리면 풀린다 |
| 시작 자세가 이미 범위 밖 | 별도 경고 메시지 |

### 5축 팔의 구조적 한계

`manipulator` 그룹은 그리퍼를 뺀 **5축**이다.
공간에서 자세를 완전히 지정하려면 위치 3 + 방향 3 = **6 자유도**가 필요한데 관절이 5개다.

**즉 이 팔은 임의의 위치와 방향 조합에 도달할 수 없다.**
위치가 닿는 범위 안이어도 "이 방향으로 향하라"는 조건이 붙으면 해가 없는 경우가 많다.
마커를 조금만 회전시켜도 실패하는 이유가 이것이다.

물체를 집을 때 "위에서 수직으로 내려찍는" 방식을 쓰게 되는 것도 같은 이유다.
방향 조건을 하나 고정하면 자유도가 맞아떨어진다.

### ② 충돌 — 계획은 됐는데 경로가 몸에 부딪힌다

```
Collision checking is considered complete (collision was found and 0 contacts are stored)
Completed listing of explanations for invalid states.
Motion plan was found but it seems to be invalid (possibly due to postprocessing). Not executing.
```

**경로는 찾았다.** IK도 풀렸고 플래너도 성공했는데, 최종 충돌 검사에서 걸렸다.

이 실패는 mock에서는 잘 안 나오고 **실물에서 자주 난다.**
mock은 전 관절 0도, 즉 팔이 펴진 자세에서 시작한다.
실물은 팔이 놓여 있던 자세 그대로이고, 그게 접힌 상태면 여유가 없다.

실제로 겪은 자세:

```
shoulder_lift  -1.641   (한계 근처, 뒤로 젖혀짐)
elbow_flex      1.540   (88도, 접힘)
wrist_flex      1.348   (77도, 접힘)
```

팔이 완전히 접혀 그리퍼가 몸통 쪽에 와 있었다. 이 상태에서는 어디로 계획해도 실패한다.

**어떤 충돌이 검사되는지는 SRDF에 있다.**

```bash
ros2 param get /move_group robot_description_semantic > /tmp/srdf.txt
grep -o 'disable_collisions link1="[^"]*" link2="[^"]*"' /tmp/srdf.txt
```

```
base_link — shoulder_link
base_link — upper_arm_link
gripper_link — lower_arm_link
gripper_link — wrist_link
lower_arm_link — upper_arm_link
...
```

무시 목록은 전부 **서로 붙어 있는 이웃 링크**다. 구조상 항상 닿아 있으니 검사할 이유가 없다.

**여기 없는 조합이 중요하다** — `base_link — gripper_link`, `shoulder_link — gripper_link`.
팔 끝이 몸통을 찍는 것은 진짜 충돌이므로 검사한다.

RViz에서 눈으로 확인할 수 있다.
Displays → MotionPlanning → Scene Robot → **Show Robot Collision** 체크.
충돌하는 링크가 빨갛게 표시된다.

**해결:** 시작 자세를 펴진 상태로 만든다.
MoveIt 구성에서는 `move-joint.py`가 동작하지 않으므로,
6축 브링업으로 잠시 바꿔서 자세를 정리한 뒤 MoveIt으로 돌아온다.

```bash
# follower.launch.py (6축) 으로 실행한 상태에서
python3 scripts/move-joint.py elbow_flex -0.9 4
python3 scripts/move-joint.py wrist_flex -0.9 4
python3 scripts/move-joint.py shoulder_lift 0.9 4
```

**시작 자세가 이미 충돌이면 어떤 목표를 줘도 실패한다.**
플래너는 시작점부터 유효해야 경로를 만들 수 있다.
실물에서 MoveIt을 쓸 때는 먼저 팔을 중립 자세로 보내는 것이 사실상 필수 절차다.

### ③ 목표 자세 자체가 충돌

```
RRTConnect.cpp:265 - manipulator/manipulator: Unable to sample any valid states for goal tree
ParallelPlan::solve(): Unable to find solution by any of the threads in 0.070869 seconds
```




https://github.com/user-attachments/assets/372cba09-64d3-437b-aed0-4367dd77d804




②와 메시지가 다르다. 목표 지점의 IK 해는 있는데 **그 자세가 충돌 상태**라
플래너가 향할 수 있는 유효한 목표를 하나도 못 만든 경우다.

### 소요 시간으로 층을 가른다

| 시간 | 판정 |
|---|---|
| 0.0001 ~ 0.001초 | **IK 해 없음.** 탐색을 시작조차 못 함 |
| 0.01 ~ 0.1초 | **IK는 됐는데 충돌** |
| 타임아웃(5초)까지 | **진짜 경로 탐색 실패.** 좁은 통로 등 |

로그 한 줄로 원인이 갈린다. 이것이 이 세션에서 얻은 가장 실용적인 지식이다.

---

## 06. 성공 로그 읽기



https://github.com/user-attachments/assets/2f091cc1-3367-47b3-854f-2acd63529998



```
Planner configuration 'manipulator' will use planner 'geometric::RRTConnect'.
Returned 2 controllers in list
Validating trajectory with allowed_start_tolerance 0.05
Starting trajectory execution ...
sending trajectory to follower/arm_trajectory_controller
[arm_trajectory_controller]: Received new action goal
[arm_trajectory_controller]: Accepted new action goal
[arm_trajectory_controller]: Goal reached, success!
Completed trajectory execution with status SUCCEEDED ...
Solution was found and executed.
```

세 줄이 특히 유용하다.

**`Returned 2 controllers in list`**
팔과 그리퍼 두 컨트롤러를 인식하고 있다. 궤적은 `arm_trajectory_controller`로만 갔다.
컨트롤러를 나눈 이유가 여기서 보인다.

**`Validating trajectory with allowed_start_tolerance 0.05`**
MoveIt은 실행 직전에 **"지금 팔 위치가 계획의 시작점과 0.05 rad 이내인가"** 를 검사한다.
Plan을 눌러놓고 한참 뒤 Execute하면, 그 사이 팔이 움직였을 경우 여기서 거부된다.

**`sending trajectory to follower/arm_trajectory_controller`**
MoveIt이 만든 궤적이 [04-ros2-control](04-ros2-control.md)에서 본 그 컨트롤러로 간다.
계층이 여기서 이어진다.

---

## 07. 실물 실행 절차

**⚠️ 지금까지와 다르다.** 관절 하나가 아니라 **팔 전체가 계획된 경로를 따라 동시에 움직인다.**

**실행 전**

| # | 확인 |
|---|---|
| 1 | 팔 반경 50cm 안에 물건과 손이 없을 것 |
| 2 | mock 종료 (컨트롤러·포트 중복 방지) |
| 3 | 비상시 터미널 `Ctrl+C` = 토크 해제 |

```bash
ros2 launch so101_bringup follower_moveit_demo.launch.py \
  hardware_type:=real \
  joint_config_file:=~/so101_ws/myconfig/my_follower_joints.yaml
```

**RViz 절차 (순서를 지킨다)**

1. Scene Robot → **Show Robot Collision** → 빨간 링크가 없는지 확인
2. Planning 탭 → `Goal State` = **`<current>`** → **Update**
3. 마커를 **2~3cm만** 이동 (회전은 건드리지 않는다)
4. 마커 색 확인
5. **Plan** → 궤적 재생이 이상하면 여기서 멈춘다
6. **Execute**

**2번을 건너뛰면 안 된다.** 마커가 이전 자세로 남아 있으면
실물 현재 자세와 크게 달라 팔이 급하게 휜다.

---

## 08. 남은 것 — 저장된 자세가 없다

```bash
grep -o 'group_state name="[^"]*"' /tmp/srdf.txt
```

출력이 비어 있다. SRDF에 `home`, `ready` 같은 미리 정의된 자세가 하나도 없다.
그래서 RViz의 Goal State 드롭다운에도 선택지가 거의 없고,
"홈으로 복귀"를 만들려면 직접 추가해야 한다.

이 팔은 시작 자세가 매번 다르므로([02-hardware-bringup](02-hardware-bringup.md) 참고),
안전한 중립 자세를 `group_state`로 등록해두면 매번 손으로 펴는 작업이 사라진다.

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| 관절 공간 / 작업 공간 | 관절 각도를 지정 / 팔 끝 위치를 지정 |
| IK (역기구학) | 좌표 → 관절 각도. 해가 없을 수 있다 |
| 5축의 한계 | 위치+방향 6자유도를 5개 관절로 만족시킬 수 없다 |
| OMPL / RRTConnect | 무작위 표본으로 충돌 없는 경로를 찾는 플래너 |
| SRDF | 플래닝 그룹, IK 체인, 충돌 무시 쌍을 정의 |
| `disable_collisions` | 이웃 링크는 항상 닿으므로 검사에서 제외 |
| `allowed_start_tolerance` | 실행 직전 현재 자세와 계획 시작점의 허용 오차 |
| `FixStartStateBounds` | 범위를 살짝 넘은 시작 자세를 경계값으로 보정 |
| 소요 시간으로 층 가르기 | ms 단위 실패 = IK, 수십 ms = 충돌, 타임아웃 = 경로 |

## 확인하지 않고 넘어간 것

- `group_state`(저장된 자세) 추가
- 그리퍼 액션을 실제로 호출해 물체를 잡는 동작
- 장애물(테이블 등)을 planning scene에 추가하기
- Pilz 플래너 (PTP / LIN) — 설정만 고치고 사용하지 않음
- [03-urdf-and-tf](03-urdf-and-tf.md)에서 발견한 `wrist_flex` 범위 초과.
  이번 세션의 시작 자세에서는 재현되지 않아 확정하지 못했다

## 다음

[06-vision-detection.md](06-vision-detection.md)
