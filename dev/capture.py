# herdr 화면 받기 (시험용): python3 -I capture.py <출력 파일> <줄 수> <칸 수> [초] [보낼 키]
#
# 붙을 대상은 환경 변수로 정한다.
#   CAP_SESSION=<이름>   herdr --session <이름> 에 붙는다 (없으면 기본 세션 — 완전 분리 시험이면 XDG_CONFIG_HOME으로 가른다)
#   CAP_CONFIG=<설정 파일> 그 설정으로 화면을 그린다. 🚨 사이드바는 서버가 아니라 '붙는 쪽(클라이언트)'의 설정을 읽는다.
#                         빈 값을 넘기면 herdr 기본 화면이 나오므로, 쓸 때만 지정한다.
#   XDG_STATE_HOME=<폴더>  클라이언트 화면 기억(사이드바 너비·정렬)을 실제 파일과 가른다 — 시험 때는 꼭 새 폴더로.
# 보낼 키는 파이썬 이스케이프로: 마우스 클릭 '\x1b[<0;열;줄M\x1b[<0;열;줄m', ⌥A 신호 '\x1b[24~a'
# 받은 원본은 vt.py(글자만)나 vtc.py(색까지)로 복원한다.
import os, pty, sys, time, select, struct, fcntl, termios, signal

out, rows, cols = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
secs = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
keys = sys.argv[5].encode().decode("unicode_escape").encode("latin-1") if len(sys.argv) > 5 else b""

env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}  # herdr 칸 안에서 돌려도 겹치지 않게
if os.environ.get("CAP_CONFIG"):
    env["HERDR_CONFIG_PATH"] = os.environ["CAP_CONFIG"]
env["TERM"] = "xterm-256color"
env["COLORTERM"] = "truecolor"
argv = ["herdr"] + (["--session", os.environ["CAP_SESSION"]] if os.environ.get("CAP_SESSION") else [])
herdr_bin = os.environ.get("HERDR_BIN_PATH") or "/opt/homebrew/bin/herdr"

pid, fd = pty.fork()
if pid == 0:
    os.execve(herdr_bin, argv, env)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
os.kill(pid, signal.SIGWINCH)
buf = b""
t0 = time.time()
sent = False
while time.time() - t0 < secs:
    if keys and not sent and time.time() - t0 > secs / 2:
        os.write(fd, keys)
        sent = True
    r, _, _ = select.select([fd], [], [], 0.1)
    if r:
        try:
            buf += os.read(fd, 65536)
        except OSError:
            break
with open(out, "wb") as f:
    f.write(buf)

# 끝내기: 그냥 waitpid로 기다리면 영원히 멈춘다 → pty를 닫고 HUP → TERM → KILL 차례로, 기다림은 WNOHANG
os.close(fd)
for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        break
    end = time.time() + 1.0
    done = False
    while time.time() < end:
        try:
            if os.waitpid(pid, os.WNOHANG)[0]:
                done = True
                break
        except ChildProcessError:
            done = True
            break
        time.sleep(0.05)
    if done:
        break
print(len(buf), "bytes")
