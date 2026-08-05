#!/usr/bin/env python3
"""실행 중인 robot_state_publisher에서 URDF를 받아 조인트 limit을 표로 출력한다.

파일을 찾지 않고 노드에 직접 물어보므로 워크스페이스 sourcing이 필요 없다.

사용법:
    ros2 param get 이 동작하는 터미널에서
    python3 urdf-limits.py [노드이름]
"""

import math
import re
import subprocess
import sys

NODE = sys.argv[1] if len(sys.argv) > 1 else "/follower/robot_state_publisher"

out = subprocess.run(
    ["ros2", "param", "get", NODE, "robot_description"],
    capture_output=True,
    text=True,
).stdout

# 출력 앞에 "String value is: " 같은 머리말이 붙으므로 XML 시작점부터 자른다
i = out.find("<?xml")
xml = out[i:] if i >= 0 else out

if not xml.strip():
    sys.exit(f"robot_description을 가져오지 못했다. 노드 이름 확인: {NODE}")

pattern = re.compile(r'<joint name="([^"]+)" type="([^"]+)"(.*?)</joint>', re.S)

header = f'{"joint":22} {"type":10} {"lower":>9} {"upper":>9} {"lower deg":>10} {"upper deg":>10}'
print(header)
print("-" * len(header))

for name, jtype, body in pattern.findall(xml):
    m = re.search(r'<limit[^>]*lower="([^"]+)"[^>]*upper="([^"]+)"', body)
    if m:
        lo, up = float(m.group(1)), float(m.group(2))
        print(
            f"{name:22} {jtype:10} {lo:9.4f} {up:9.4f} "
            f"{math.degrees(lo):10.1f} {math.degrees(up):10.1f}"
        )
    else:
        # fixed 조인트는 limit이 없다
        print(f"{name:22} {jtype:10} {'-':>9} {'-':>9} {'-':>10} {'-':>10}")
