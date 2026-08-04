# ROS 2 실습 — Action

## 01. rotate_absolute (turtlesim)

### 목표
turtlesim의 rotate_absolute action을 이용해 목표(goal)-피드백(feedback)-결과(result) 구조 이해

### 환경
ROS 2 (Humble), Ubuntu (Linux)

### 코드
직접 작성한 코드 없음. ROS 2 기본 제공 turtlesim 사용

### 실행
터미널 1:
```
ros2 run turtlesim turtlesim_node
```

터미널 2 (action 확인):
```
ros2 action list
```

<img width="911" height="421" alt="Screenshot from 2026-08-04 16-44-30" src="https://github.com/user-attachments/assets/64ca97ef-9926-4a69-8b39-69cfe648cca4" />

터미널 2 (목표 전달):
```
ros2 action send_goal /turtle1/rotate_absolute turtlesim/action/RotateAbsolute "{theta: 1.57}"
```

### 결과

<img width="530" height="409" alt="Screenshot from Screencast from 2026년 08월 04일 16시 47분 06초 webm" src="https://github.com/user-attachments/assets/aa161c8b-91e0-49a6-a3f8-79897ec271ec" />

실행 후

<img width="530" height="409" alt="Screenshot from Screencast from 2026년 08월 04일 16시 47분 06초 webm - 5" src="https://github.com/user-attachments/assets/0702d77d-b1f5-4024-9d4c-81025e61f2ab" />

<img width="723" height="277" alt="Screenshot from 2026-08-04 16-54-12" src="https://github.com/user-attachments/assets/ffec8d6d-0b09-481a-9f08-07a257ddad24" />


목표(theta: 1.57)를 보내자 거북이가 왼쪽으로 회전함. 터미널에는 목표를 보낸 즉시 결과가 아니라, 회전이 진행되는 동안 피드백이 먼저 출력되고 
회전이 끝난 뒤에 결과가 출력됨. service처럼 응답 하나로 바로 끝나는 게 아니라, 중간 진행 상황을 계속 받는다는 점이 다름.
