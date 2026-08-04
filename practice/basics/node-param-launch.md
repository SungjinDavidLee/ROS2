# ROS 2 실습 — Node, Parameter, Launch

## 01. node와 parameter 관찰 (turtlesim)

### 목표
실행 중인 node의 정보를 CLI로 확인하고, parameter를 실행 중에 바꿔보며 동작 이해

### 환경
ROS 2 (Humble), Ubuntu (Linux)

### 코드
직접 작성한 코드 없음. ROS 2 기본 제공 turtlesim 사용

### 실행 및 결과
터미널 1:
```
ros2 run turtlesim turtlesim_node
```

<img width="479" height="474" alt="Screenshot from 2026-08-04 17-03-21" src="https://github.com/user-attachments/assets/1aec31b7-7838-41f3-86dd-0213dbddd800" />


터미널 2 (노드 확인):
```
ros2 node list
ros2 node info /turtlesim
```
<img width="721" height="609" alt="Screenshot from 2026-08-04 17-01-46" src="https://github.com/user-attachments/assets/02f4967e-1161-477e-b2b2-32848897d154" />


터미널 2 (파라미터 확인):
```
ros2 param list /turtlesim
```
<img width="593" height="174" alt="Screenshot from 2026-08-04 17-02-22" src="https://github.com/user-attachments/assets/818a3f97-145d-4701-9a97-e029931aeb72" />


터미널 2 (배경색 파라미터 바꿔보기):
```
ros2 param set /turtlesim background_r 255
```

<img width="479" height="474" alt="Screenshot from 2026-08-04 17-03-41" src="https://github.com/user-attachments/assets/1949f638-fe42-4924-83db-93171850a66a" />

(되돌리고 싶다면 255를 69근처의 값으로 변경하여 명령어를 입력하면 됨)



`node info` 결과를 보면 노드 하나(/turtlesim) 안에 
topic(Subscribers/Publishers), service(Service Servers), action(Action Servers)이 전부 같이 들어있음. 
지금까지 따로 실습했던 통신 방식 세 가지가 실제로는 노드 하나 안에서 섞여서 쓰인다는 걸 확인함.

`param list`로 확인한 파라미터 중 `background_r`을 255로 바꾸자 파란색이었던 배경이 핑크색으로 바뀜. 
코드를 다시 실행하거나 노드를 재시작하지 않고도 실행 중인 노드의 설정값을 바로 바꿀 수 있다는 걸 확인함.


## 02. launch file로 한 번에 실행

### 목표
node 실행 + parameter 설정을 launch file 하나로 묶어서 실행

### 환경
ROS 2 (Humble), Ubuntu (Linux)

### 코드
`turtlesim_launch.py`:
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            name='turtlesim',
            parameters=[{'background_r': 255}]
        )
    ])
```

### 실행
```
ros2 launch ./turtlesim_launch.py
```

### 결과
<img width="479" height="474" alt="Screenshot from 2026-08-04 17-10-32" src="https://github.com/user-attachments/assets/93635207-1ce5-449b-a8f3-33c35d85c9de" />

`ros2 launch`로 실행하자 turtlesim 창이 뜨는 순간부터 배경이 핑크색이었음. 
01에서는 노드를 먼저 켜고 `param set`으로 수동으로 바꿔야 했지만, 
launch file은 파라미터 값을 파일 안에 미리 정해두기 때문에 노드가 시작되는 시점부터 그 값으로 실행됨.

### 마무리
`node info`로 하나의 노드 안에 topic·service·action이 함께 들어있는 걸 확인했고, 
`param`으로 실행 중인 노드의 설정값을 즉석에서 바꿔봤다. launch file은 그 노드 실행과 파라미터 설정을 파일 하나로 묶어, 
매번 명령을 따로 치지 않고 한 번에 원하는 상태로 띄우는 역할을 한다는 걸 확인했다.

`ros2 run` + `param set`(01)과 launch file(02)의 차이는 결국 "실행한 뒤에 바꾸는가, 실행하기 전에 정해두는가"였다.
