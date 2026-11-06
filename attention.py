#!/usr/bin/python3 -I
"""herdr-attention: 에이전트 상태를 herdr 사이드바 색 표시로 바꾼다.

빨강 █ 입력 필요  = 질문·승인을 기다리며 멈춤 (herdr blocked)
노랑 █ 확인 안 함 = 일이 끝났는데 아직 그 칸에 들어가 보지 않음
초록 ✓ 확인함     = 일이 끝났고 그 칸에 들어가 봄
파랑 ◐ 작업 중    = 일하는 중 (herdr working)

herdr 자체의 done(안 봄)은 몇 초 만에 idle로 바뀌므로, 끝남·들어가 봄은 여기서 따로 기억한다.
하는 일은 `herdr pane report-metadata`로 칸마다 표시 글자(토큰)를 쓰는 것뿐이다. 외부 통신 없음.

  attention.py sync    전체 다시 맞추기 (서버 시작, 수동 동작)
  attention.py event   herdr 이벤트 훅 (HERDR_PLUGIN_EVENT_JSON)
"""
import fcntl
import json
import os
import subprocess
import sys
import time

SOURCE = "user:herdr-attention"
CATS = ("red", "yellow", "green", "blue")
LABEL = {
    "red": "█ 입력 필요",
    "yellow": "█ 확인 안 함",
    "green": "✓ 확인함",
    "blue": "◐ 작업 중",
}
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser("~/.local/state/herdr-attention")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
LOCK_FILE = os.path.join(STATE_DIR, "state.lock")
LOG_FILE = os.path.join(STATE_DIR, "attention.log")
# 칸 번호(w1:p1)는 herdr 세션마다 겹치므로 세션(소켓 경로)별로 나눠 기억한다
SESSION = os.environ.get("HERDR_SOCKET_PATH") or "default"


def log(msg):
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 200_000:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def herdr(*args):
    try:
        r = subprocess.run([HERDR, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"herdr {' '.join(args[:2])} 실패: {e}")
        return None
    if r.returncode != 0:
        log(f"herdr {' '.join(args[:3])} → {r.returncode}: {r.stderr.strip()[:200]}")
        return None
    out = r.stdout.strip()
    if not out.startswith("{"):
        return {}
    try:
        return json.loads(out)
    except ValueError:
        return {}


def agent_panes():
    """에이전트가 있는 칸: {pane_id: (herdr 상태, 지금 보고 있는 칸인지)}"""
    d = herdr("pane", "list")
    panes = ((d or {}).get("result") or {}).get("panes") or []
    return {
        p["pane_id"]: (p.get("agent_status") or "unknown", bool(p.get("focused")))
        for p in panes
        if p.get("agent")
    }


def category(prev, status, focused):
    if status == "working":
        return "blue"
    if status == "blocked":
        return "red"
    if status in ("idle", "done"):
        if focused:
            return "green"
        if prev in ("blue", "red", "yellow"):
            return "yellow"
        if prev == "green":
            return "green"
        # 처음 보는 칸(서버 시작 직후 등): herdr가 done(안 봄)이라고 할 때만 노랑
        return "yellow" if status == "done" else "green"
    return prev  # unknown: 이전 표시를 그대로 둔다


def apply(pane_id, cat):
    args = ["pane", "report-metadata", pane_id, "--source", SOURCE]
    for c in CATS:
        if c == cat:
            args += ["--token", f"att_{c}={LABEL[c]}"]
        else:
            args += ["--clear-token", f"att_{c}"]
    if cat:
        args += ["--token", f"att_state={cat}"]
    else:
        args += ["--clear-token", "att_state"]
    herdr(*args)


def load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def find(obj, key):
    """이벤트 JSON 어디에 있든 첫 번째 key 값을 찾는다 (감싸는 형식이 달라도 되게)."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            r = find(v, key)
            if r is not None:
                return r
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sync"
    os.makedirs(STATE_DIR, exist_ok=True)
    event = {}
    if mode == "event":
        try:
            event = json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON") or "{}")
        except ValueError:
            event = {}
    etype = str(find(event, "type") or "")

    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load()
        sessions = data.setdefault("sessions", {})
        for s in list(sessions):  # 없어진 세션(시험 세션 등)의 기억은 지운다
            if s != SESSION and s.startswith("/") and not os.path.exists(s):
                del sessions[s]
        mem = sessions.setdefault(SESSION, {})

        if etype == "pane_closed":
            mem.pop(str(find(event, "pane_id")), None)
            save(data)
            return

        panes = agent_panes()
        if etype == "pane_agent_status_changed":
            targets = [str(find(event, "pane_id"))]
        elif mode == "event":  # 포커스가 바뀌는 이벤트: 지금 보고 있는 칸만
            targets = [p for p, (_, focused) in panes.items() if focused]
        else:
            targets = list(panes)
            for p in list(mem):  # 닫힌 칸 정리
                if p not in panes:
                    del mem[p]

        for p in targets:
            if p not in panes:
                continue
            status, focused = panes[p]
            prev = mem.get(p)
            cat = category(prev, status, focused)
            if cat != prev or mode == "sync":
                apply(p, cat)
                log(f"{p} {status}{' (보는 중)' if focused else ''}: {prev} → {cat}")
            if cat:
                mem[p] = cat
            else:
                mem.pop(p, None)
        save(data)


if __name__ == "__main__":
    main()
