# 01. ROS 2 환경 구성

ROS 2 Humble을 apt가 아니라 conda 계열 격리 환경(RoboStack)으로 설치했다.
시스템 패키지를 바꾸지 않고, 홈 디렉토리 안에서만 끝난다.

---

## 01. 설치

### micromamba

```bash
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)
```

### ROS 2 Humble

```bash
micromamba create -y -n rosenv -c conda-forge -c robostack-humble ros-humble-desktop
```

```bash
micromamba activate rosenv
micromamba config append channels robostack-humble --env
```

환경 크기는 약 4.3GB.

### 사용법

```bash
micromamba activate rosenv     # ROS 작업 시작할 때마다
```

```bash
micromamba deactivate
```

`activate`는 PATH 검색 순서를 바꿔서 이 터미널이 `ros2`, `python`, `libstdc++`를
전부 환경 폴더 안에서 먼저 찾게 한다.

`.bashrc`에 자동 활성화를 넣지 않는다. 모든 터미널의 PATH가 ROS 쪽으로 바뀌면
다른 파이썬 프로젝트가 엉뚱한 인터프리터를 잡는다.

### 패키지 추가

`rosdep`은 내부적으로 `apt install`을 호출하므로 이 환경에서는 쓸 수 없다.

```bash
micromamba install -y -c robostack-humble ros-humble-<패키지명>
```

C++ 노드를 빌드하려면 컴파일러도 환경 안에 넣는다.

```bash
micromamba install -y -c conda-forge compilers cmake ninja colcon-common-extensions
```

---

## 02. 설치 확인

```bash
micromamba activate rosenv

echo $CONDA_PREFIX
which ros2
which python
python --version
printenv ROS_DISTRO
```

```
~/micromamba/envs/rosenv
~/micromamba/envs/rosenv/bin/ros2
~/micromamba/envs/rosenv/bin/python
Python 3.12.13
humble
```

`ros2 --version`이라는 옵션은 없다. 배포판은 `printenv ROS_DISTRO`로 본다.

### 격리 확인

`rviz2`가 어느 C++ 런타임을 로드하는지 본다.

```bash
ldd $(which rviz2) | grep -E "libstdc|libgcc"
```

```
libstdc++.so.6 => ~/micromamba/envs/rosenv/bin/../lib/libstdc++.so.6
libgcc_s.so.1  => ~/micromamba/envs/rosenv/bin/../lib/libgcc_s.so.1
```

경로가 환경 폴더 안이면 성공이다. `/usr/lib/`가 나오면 격리가 새는 중이다.

> 버전 번호로 판단하면 안 된다. 시스템과 환경이 같은 소네임(`libstdc++.so.6.0.35`)을
> 가질 수 있다. 소네임은 ABI 식별자일 뿐 파일 내용의 동일성을 뜻하지 않는다.
> 판단 기준은 **`ldd`가 출력하는 경로**다.

> 격리 환경을 켠 채로 시스템 상태를 확인하면 안 된다. `which gcc`는 환경 안의 gcc를
> 가리킨다. 시스템 쪽을 보려면 `ls -l /usr/bin/gcc` 처럼 절대 경로로 확인한다.

---

## 03. 통신 검증 — talker / listener

렌더링뿐 아니라 노드 간 통신(DDS)도 정상인지 확인한다.

### ROS_DOMAIN_ID

ROS 2는 중앙 서버 없이 같은 네트워크의 노드끼리 서로를 자동으로 찾는다.
`ROS_DOMAIN_ID`는 그 탐색 범위를 나누는 번호이며, 같은 번호끼리만 보인다.
`.bashrc`에 전역으로 넣지 않고 ROS 터미널에서만 설정한다.

### 실행

터미널 3개. 각각 `micromamba activate rosenv` 먼저.

```bash
# 터미널 1
export ROS_DOMAIN_ID=42
ros2 run demo_nodes_cpp talker
```

```bash
# 터미널 2
export ROS_DOMAIN_ID=42
ros2 run demo_nodes_cpp listener
```

```bash
# 터미널 3
export ROS_DOMAIN_ID=42
ros2 node list
ros2 topic info /chatter
ros2 topic echo /chatter --once
timeout 5 ros2 topic hz /chatter
```

### 결과

```
=== node list ===
/listener
/talker

=== topic info /chatter ===
Type: std_msgs/msg/String
Publisher count: 1
Subscription count: 1

=== echo 1회 ===
data: 'Hello World: 32'

=== 주기 측정 ===
average rate: 1.000   min: 1.000s  max: 1.000s  std dev: 0.00003s
```

Publisher 1 / Subscription 1로 양방향 연결 확정. 발행 주기 1Hz.

listener가 `1`이 아니라 중간 숫자부터 받기 시작했다. talker는 듣는 노드가 없는 동안에도
계속 발행하고 있었고, listener는 합류한 시점부터 받는다.
`practice/basics/pubsub-vs-service.md`의 "topic은 상대가 없어도 각자 동작한다"가 그대로 재현됐다.

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| 격리 환경 | 컴파일러·런타임·ROS를 통째로 가진 폴더. 시스템 라이브러리를 참조하지 않는다 |
| PATH 검색 순서 | 활성화가 하는 일의 전부. 파일을 옮기지 않고 "먼저 찾는 곳"만 바꾼다 |
| 소네임 | ABI 호환 식별자. 같은 번호라도 파일 내용은 다를 수 있다 |
| `ROS_DOMAIN_ID` | DDS 디스커버리 범위를 나누는 칸막이 |

## 확인하지 않고 넘어간 것

- 이 환경에서 `colcon build`(C++ 컴파일)가 실제로 되는지 — 다음 문서에서 확인

## 다음

[02-hardware-bringup.md](02-hardware-bringup.md)
