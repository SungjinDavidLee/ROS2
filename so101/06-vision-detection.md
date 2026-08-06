# 06. 카메라와 물체 검출

카메라 영상을 ROS 토픽으로 올리고, 학습된 YOLO 모델로 물체 위치를 픽셀 좌표로 뽑아낸다.

**전제 조건**

- [01-env-setup](01-env-setup.md) 완료
- USB 웹캠 1대 연결
- 학습된 모델 파일 (`.pt`). 학습 과정은 이 문서 뒷부분 참고

**ROS 터미널 세 줄**

```bash
micromamba activate rosenv
cd ~/so101_ws
source install/setup.bash
```

---

## 01. 카메라를 ROS 토픽으로

### 왜 토픽으로 올리는가

OpenCV로 직접 열면(`cv2.VideoCapture(0)`) 그 프로그램만 카메라를 쓴다.
**비디오 장치는 한 번에 하나의 프로세스만 열 수 있어서**,
추론 노드와 녹화 프로그램을 동시에 돌릴 수 없다.

토픽으로 올리면 카메라 노드 하나가 장치를 잡고, 나머지는 전부 구독만 한다.

| | 직접 열기 | ROS 토픽 |
|---|---|---|
| 동시 사용 | 불가 | 여럿 가능 |
| RViz / rqt 확인 | 불가 | 가능 |
| rosbag 녹화 | 불가 | 가능 |
| 실패 지점 | 적다 | 노드가 하나 늘어난다 |

### 장치 확인

```bash
ls -l /dev/video*
```

```
crw-rw----+ 1 root video 81, 0 /dev/video0
crw-rw----+ 1 root video 81, 1 /dev/video1
```

**웹캠 1대인데 장치가 두 개로 잡힌다.** 최근 커널에서는 하나가 영상 스트림,
다른 하나가 메타데이터용으로 잡히는 경우가 많다. 보통 `/dev/video0`이 영상이다.

`v4l2-ctl` 같은 시스템 유틸리티는 이 환경에 없지만 필요 없다.
**`v4l2_camera` 노드가 직접 장치를 열고 지원 포맷과 컨트롤 목록을 로그로 찍어준다.**

### 실행

```bash
ros2 run v4l2_camera v4l2_camera_node \
  --ros-args -p video_device:=/dev/video0 -p image_size:="[640,480]"
```

### 확인

```bash
ros2 topic list | grep -E "image|camera"
ros2 topic hz /image_raw
ros2 topic echo /image_raw --once --field width
ros2 topic echo /image_raw --once --field encoding
```

```
/camera_info
/image_raw

average rate: 29.728
	min: 0.027s max: 0.066s std dev: 0.00382s

640
rgb8
```

눈으로 보려면:

```bash
ros2 run rqt_image_view rqt_image_view
```

<img width="459" height="527" alt="Screenshot from 2026-08-06 13-39-35" src="https://github.com/user-attachments/assets/44830b60-937a-4c30-a9fc-7fcf7770ec11" />


창 상단 드롭다운에서 `/image_raw`를 선택한다.

### 체크포인트

| 항목 | 기대 |
|---|---|
| 토픽 | `/image_raw`, `/camera_info` |
| 발행 주기 | 25~30 Hz |
| rqt_image_view | 실시간 영상 표시 |

---

### 정상인데 ERROR로 찍히는 로그

```
[ERROR] [camera_calibration_parsers]: Unable to open camera calibration file
        [~/.ros/camera_info/usb2.0_pc_camera:_usb2.0_pc_cam.yaml]
[WARN]  [v4l2_camera]: Camera calibration file ... not found
```

**에러가 아니라 알림이다.** 노드는 계속 돌고 `/image_raw`도 정상 발행된다.
`/camera_info`만 빈 값으로 나간다.

| | 캘리브레이션 없음 | 있음 |
|---|---|---|
| `/image_raw` | 정상 | 정상 |
| `/camera_info` | 빈 행렬 | 렌즈 왜곡 계수, 초점거리 |
| 물체를 **보는** 것 | 가능 | 가능 |
| 픽셀 → **실제 거리** 환산 | 불가 | 가능 |

이 단계에서는 필요 없다. 물체 위치를 로봇 좌표로 바꿀 때 필요해진다.

### 포맷 변환이 일어나고 있다

```
[WARN] Image encoding not the same as requested output,
       performing possibly slow conversion: yuv422_yuy2 => rgb8
```

카메라는 YUYV로 주는데 RGB를 요청해서 매 프레임 CPU가 변환한다.
640×480에서는 30fps가 유지되지만, 해상도를 올리면 여기가 병목이 된다.
`pixel_format` 파라미터로 조정할 수 있다.

### frame_id가 TF 트리에 없다

```bash
ros2 topic echo /image_raw --once --field header
```

```
frame_id: camera
```

[03-urdf-and-tf](03-urdf-and-tf.md)에서 확인한 TF 트리에 `camera`라는 프레임은 없다.

**즉 지금은 "카메라가 로봇 어디에 붙어 있는지" ROS가 모른다.**
화면에서 물체를 찾아도 그것이 로봇 기준으로 어디인지 계산할 수 없다.
이것을 잇는 것이 static transform이고, 개념은 03에서 `gripper_frame_link`로 이미 봤다.

지금 단계에서는 픽셀 좌표만 쓰므로 문제되지 않는다.

---

## 02. 설정 파일 수정 — launch로 카메라 띄우기

`so101_bringup/config/cameras/so101_cameras.yaml` 원본은 이렇게 되어 있다.

```yaml
cameras:
  - name: cam_wrist
    camera_type: gscam
    ...
  - name: cam_overhead
    camera_type: gscam
```

두 가지가 맞지 않는다.

| 문제 | 수정 |
|---|---|
| 카메라 2대 전제 (손목 + 천장) | 실제로는 1대 |
| `camera_type: gscam` | `gscam`은 빌드된 적이 없음 → `v4l2_camera` |

```yaml
cameras:
  - name: cam_overhead
    camera_type: v4l2_camera
    param_path: so101_v4l2_cam.yaml
    namespace: static_camera
    camera_info_url: ""
```

파라미터 파일(`so101_v4l2_cam.yaml`)에도 존재하지 않는 장치가 적혀 있다.

```diff
 /static_camera/cam_overhead:
   ros__parameters:
-    video_device: "/dev/cam_overhead"
+    video_device: "/dev/video0"
```

`/dev/cam_overhead`는 udev 별칭인데, 이 프로젝트에서는 팔에만 별칭을 만들었고
카메라에는 만들지 않았다.

| 방법 | 장단 |
|---|---|
| yaml을 `/dev/video0`으로 고정 | 지금 바로 동작. USB 순서가 바뀌면 어긋난다 |
| 카메라용 udev 규칙 추가 | 안정적. `sudo` 필요 |

카메라가 1대인 동안은 전자로 충분하다.
2대 이상이 되면 [02-hardware-bringup](02-hardware-bringup.md)의 udev 방식을 그대로 적용한다.

---

## 03. YOLO 추론 노드

### 환경 분리 문제

학습과 추론의 환경이 다르다.

| 환경 | 용도 | torch |
|---|---|---|
| `rosenv` | ROS 2 | CPU |
| 학습 환경 | 모델 학습 | GPU |

**두 환경을 한 터미널에서 섞으면 안 된다.** PATH와 `PYTHONPATH`가 겹치면
잘못된 라이브러리를 잡아 ABI 에러가 난다.

선택지는 셋이다.

| 방식 | 장점 | 단점 |
|---|---|---|
| ① `rosenv`에 ultralytics 설치 | 노드 하나로 끝 | CPU 추론 |
| ② 이미지를 파일로 주고받기 | 환경 완전 분리 | 실시간 불가 |
| ③ 학습 환경에 rclpy 설치 | GPU 추론 + ROS | 의존성 충돌 위험 |

**①을 택했다.** 640×480에서 CPU 추론도 서보 제어에는 충분하고,
환경을 하나 더 만들지 않아도 된다. 학습은 계속 GPU 환경에서 한다.

```bash
python -c "import ultralytics; print(ultralytics.__version__)"
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

```
8.4.113
2.13.0+cpu False
```

### 코드

[scripts/detect-node.py](scripts/detect-node.py)

핵심 부분만 본다.

```python
self.sub = self.create_subscription(Image, "/image_raw", self.on_image, 1)
self.pub = self.create_publisher(Point, "/fbox/center", 10)
```

**구독 큐 깊이가 1이다.** 이유는 뒤의 처리 속도 측정에서 드러난다.

```python
frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
res = self.model.predict(frame, conf=CONF, verbose=False)[0]
```

`CvBridge`가 ROS 이미지 메시지를 OpenCV 배열로 바꾼다.
`/image_raw`는 `rgb8`인데 `bgr8`로 요청한다 — OpenCV의 채널 순서가 BGR이기 때문이다.

```python
best = None
for b in res.boxes:
    x1, y1, x2, y2 = b.xyxy[0].tolist()
    area = (x2 - x1) * (y2 - y1)
    if best is None or area > best[4]:
        best = (x1, y1, x2, y2, area, float(b.conf[0]))
```

**여러 개가 검출되면 면적이 가장 큰 것을 고른다.**


<img width="657" height="586" alt="Screenshot from 2026-08-06 13-27-27" src="https://github.com/user-attachments/assets/ce9ec7d3-1ea2-4fe3-b3db-8ab0ee9a86a9" />

confidence가 아니라 면적을 기준으로 삼은 이유는, 카메라에 가까운 물체가 크게 보이고
가까운 것부터 다루는 것이 자연스럽기 때문이다.

```python
p = Point()
p.x, p.y, p.z = float(cx), float(cy), float(area)
self.pub.publish(p)
```

`Point` 메시지를 재활용했다. `x`, `y`는 픽셀 좌표, `z`에는 면적을 넣었다.
전용 메시지 타입을 만들려면 패키지를 빌드해야 하는데,
이 단계에서는 표준 타입으로 충분하다.

**의미가 다른 값을 표준 메시지에 억지로 넣은 것이므로**,
나중에 3D 좌표를 다루게 되면 전용 타입으로 바꿔야 한다. 지금은 의도적인 타협이다.

### 실행

터미널 1에 카메라 노드가 떠 있는 상태에서:

```bash
python3 scripts/detect-node.py
```

```bash
ros2 topic echo /fbox/center
```

---

## 04. 측정 결과

### 검출률

물체를 놓았을 때와 치웠을 때를 나눠 측정했다.

| 상태 | 프레임 | 검출 | 비율 |
|---|---|---|---|
| 물체 있음 | 442 | 442 | **100%** |
| 물체 없음 | 147 | 0 | **0%** |

물체를 화면 밖으로 치우자 `detections` 카운터가 완전히 멈췄다.
`CONF = 0.40`에서 **오검출이 발생하지 않는다.**


<img width="657" height="586" alt="Screenshot from 2026-08-06 13-32-59" src="https://github.com/user-attachments/assets/ac9a19eb-9c32-48e8-a720-9522ee54f745" />


이 값은 이전에 시행착오로 정한 것이었는데,
동작을 숫자로 확인한 것은 이번이 처음이다.

> 이 결과는 "이 조명, 이 배경, 이 물체" 조건에서만 유효하다.
> 조명이나 배경이 바뀌면 다시 측정해야 한다.

### 처리 속도

```
frames=366  detections=366
...
frames=442  detections=442     (12초 경과)
```

| 항목 | 값 |
|---|---|
| 카메라 발행 | 30 fps |
| **추론 처리** | **약 6.3 fps** (프레임당 약 158ms) |

**5분의 1로 떨어진다.** CPU 추론의 비용이다.

여기서 구독 큐 깊이 1의 의미가 드러난다.
카메라가 30fps로 밀어넣는데 노드는 6fps로 처리하므로, 큐가 크면 처리하지 못한
프레임이 계속 쌓인다. 그러면 노드는 **점점 과거의 영상을 보고** 위치를 계산하게 된다.

큐가 1이면 밀린 프레임은 버려지고 항상 최신 영상만 처리한다.
제어에서는 오래된 정확한 정보보다 최신 정보가 중요하다.

**158ms가 제어 주기의 하한이다.** 이보다 빠른 폐루프는 만들 수 없다.
[07-visual-servoing](07-visual-servoing.md)에서 이 숫자를 그대로 쓴다.

---

## 배운 개념

| 개념 | 한 줄 설명 |
|---|---|
| 비디오 장치 배타성 | 한 번에 한 프로세스만 열 수 있다. 토픽화로 해결 |
| `v4l2_camera` | V4L2 장치를 ROS 토픽으로 올리는 노드 |
| `/camera_info` | 렌즈 왜곡·초점거리. 픽셀을 실제 거리로 바꿀 때 필요 |
| `CvBridge` | ROS 이미지 메시지 ↔ OpenCV 배열 변환 |
| 구독 큐 깊이 | 처리가 느릴 때, 큐가 크면 과거 영상을 보게 된다 |
| 검출률 측정 | 물체를 치웠을 때 0이 나와야 오검출이 없는 것 |
| 처리 속도 하한 | 추론 시간이 제어 주기의 바닥을 정한다 |

## 확인하지 않고 넘어간 것

- 카메라 캘리브레이션 (`/camera_info`가 빈 상태)
- `camera` 프레임과 로봇 TF 트리의 연결
- 다른 조명·배경에서의 오검출률
- `MIN_AREA` 필터 (너무 작은 검출을 무시하는 필터)
- GPU 추론 시 속도 비교
- launch 파일로 카메라 띄우기 (설정만 고치고 노드 직접 실행으로 확인)

## 다음

[07-visual-servoing.md](07-visual-servoing.md)
