##ROS 2 실습 — 통신 방식

## 01. talker / listener

### 목표
talker와 listener를 이용해 topic 통신(발행–구독) 구조 이해

### 환경
ROS 2 (Humble), Ubuntu (Linux)

### 코드
ROS 2 기본 제공 예제 사용:
- `demo_nodes_py` 패키지의 `talker`, `listener`

### 실행

터미널 1:
```
ros2 run demo_nodes_py talker
```

터미널 2:
```
ros2 run demo_nodes_py listener
```

### 결과

<img width="1253" height="432" alt="Screenshot from 2026-08-04 15-54-37" src="https://github.com/user-attachments/assets/10e392ea-0681-45b5-8a3a-6409667cc3bc" />

talker와 listener가 서로를 직접 호출하지 않았는데도 /chatter라는 같은 토픽 이름을 통해 자동으로 연결됨. talker가 보낸 숫자와 listener가 받은 숫자가 순서대로 일치하는 것을 확인함.

###listener 끄고 실행해보기
'Ctrl + C' 를 눌러 listener을 끄고 다시 켜보았음 (반대의 경우에는 talker가 없으니 listener에는 출력을 멈춤)

<img width="650" height="429" alt="Screenshot from 2026-08-04 15-59-17" src="https://github.com/user-attachments/assets/6db0ed62-e724-40bb-8add-9c41f3d321f6" />


listener를 껐다 켰을 때, talker는 listener가 꺼진 동안에도 계속 publish함. listener가 다시 켜진 뒤에는 그 이전에 발행된 메시지는 못 받고, 켜진 시점 이후의 메시지만 수신됨.

service였다면 요청-응답 구조라 상대가 없으면 애초에 호출 자체가 성립하지 않았을 것



## 02. service (add_two_ints)

### 목표
service의 요청-응답 구조를 이해하고, topic과의 차이(상대가 없을 때의 동작)를 확인

### 환경
ROS 2 (Humble), Ubuntu (Linux)

### 코드
ROS 2 기본 제공 예제 사용:
- `demo_nodes_py` 패키지의 `add_two_ints_server`, `add_two_ints_client_async`

### 실행

터미널 1:
```
ros2 run demo_nodes_py add_two_ints_server
```

터미널 2:
```
ros2 run demo_nodes_py add_two_ints_client_async
```

### 결과

터미널 1:
<img width="719" height="76" alt="Screenshot from 2026-08-04 16-21-25" src="https://github.com/user-attachments/assets/2f7159ed-ea25-47bf-ac05-d103a0b726bf" />

터미널 2:
<img width="719" height="76" alt="Screenshot from 2026-08-04 16-21-37" src="https://github.com/user-attachments/assets/e63e4298-88ce-498b-a0fa-6e646e4a18df" />

server에 요청이 들어오면 `Incoming request`, `a: 2 b: 3`이 출력되고, client에는 `Result of add_two_ints: 5`가 출력됨. client는 결과를 받자마자 별도로 끄지 않아도 프로세스가 자동으로 종료됨 — listener는 Ctrl+C로 꺼야 했던 것과 다름. 요청 하나에 응답 하나를 받으면 할 일이 끝나는 service의 구조를 보여줌.

### server 없이 client만 실행해보기

server를 끈 상태에서 client를 실행하면 어떻게 되는지 확인

<img width="739" height="130" alt="Screenshot from 2026-08-04 16-25-05" src="https://github.com/user-attachments/assets/24b73ad5-719d-44c7-8656-5a5b40193af2" />

`service not available, waiting again...`이 반복 출력되며 client가 멈춰 있음. talker/listener 때는 상대가 없어도 각자 동작을 계속했던 것과 달리, service는 상대(server)가 없으면 요청을 보낼 곳이 없어 응답을 기다리며 대기함. 01에서 남겼던 추론이 실제로 확인됨.


### 마무리
talker/listener로 topic의 발행-구독 구조를, add_two_ints로 service의 요청-응답 구조를 실습했다.

topic은 이름(토픽)만 같으면 발행자와 구독자가 서로를 몰라도 연결되고, 상대가 없어도 각자 동작을 멈추지 않는다. service는 요청을 보낼 상대(server)가 반드시 있어야 하고, 없으면 응답을 기다리며 대기한다. 응답을 받으면 client는 할 일이 끝나 종료된다.

같은 통신처럼 보여도 상대가 없을 때의 동작이 반대라는 게 이번 실습에서 가장 분명하게 드러난 차이였다.
