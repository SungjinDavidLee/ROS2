#!/usr/bin/env python3
"""ROS를 거치지 않고 서보에 직접 PING 패킷을 보내 응답을 확인한다.

브링업 전에 실행한다. 여기서 서보가 전부 응답하면 이후 발생하는 에러는
하드웨어 고장이 아니라 설정 불일치로 확정할 수 있다.

사용법:
    python3 servo-ping.py [포트]
"""

import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/so101_follower"
BAUD = 1000000
TIMEOUT = 0.03  # 30ms. 드라이버 원본 기본값 5ms는 이 USB 칩에 짧다
SCAN_RANGE = range(1, 11)


def checksum(body):
    return (~sum(body)) & 0xFF


def ping(ser, sid):
    body = [sid, 0x02, 0x01]  # ID, length, instruction=PING
    packet = bytes([0xFF, 0xFF] + body + [checksum(body)])
    ser.reset_input_buffer()
    ser.write(packet)
    time.sleep(0.01)
    reply = ser.read(6)
    ok = len(reply) >= 6 and reply[0] == 0xFF and reply[1] == 0xFF
    return reply if ok else None


def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    except Exception as exc:
        sys.exit(f"포트 열기 실패: {exc}\n다른 프로세스가 점유 중인지 확인: fuser -v {PORT}")

    print(f"포트 열림: {PORT} @ {BAUD}")
    print("ID  응답  에러바이트")

    found = []
    for sid in SCAN_RANGE:
        reply = ping(ser, sid)
        if reply:
            found.append(sid)
            # 에러 바이트 0x00 = 과열/과부하/전압이상 없음
            print(f" {sid:2d}   O      0x{reply[4]:02X}")
        else:
            print(f" {sid:2d}   -")

    ser.close()
    print()
    print("응답한 ID:", found)
    print("기대값: [1, 2, 3, 4, 5, 6]")

    if len(found) < 6:
        print()
        print("일부만 응답: 해당 서보의 케이블 또는 ID 설정 확인")
        print("전부 무응답: 서보 전원 미인가 또는 보드레이트 불일치")


if __name__ == "__main__":
    main()
