#!/usr/bin/python3 -I
"""herdr-attention: 에이전트 상태와 공간(작업공간)을 herdr 사이드바 색 표시로 바꾼다.

상태 (줄 맨 앞 기호)
  빨강 █ 입력 필요  = 질문·승인을 기다리며 멈춤 (herdr blocked)
  노랑 █ 확인 안 함 = 일이 끝났는데 아직 그 칸에 들어가 보지 않음
  초록 ✓ 확인함     = 일이 끝났고 그 칸에 들어가 봄
  파랑 ◐ 작업 중    = 일하는 중 (herdr working)

공간 색 (공간 이름 글자와 ● 점)
  공간마다 색 하나. 공간 목록과 에이전트 줄의 공간 이름에 ● 점과 함께 그 색이 입혀진다.
  색은 플러그인 설정 폴더의 space-colors.toml 에 "공간 이름" = "색" 으로 적는다.
  새 공간은 안 쓰인 색을 자동으로 받고, 공간 이름을 바꾸면 색도 따라간다.

herdr 자체의 done(안 봄)은 몇 초 만에 idle로 바뀌므로, 끝남·들어가 봄은 여기서 따로 기억한다.
하는 일은 `herdr pane/workspace report-metadata`로 칸·공간마다 표시 글자(토큰)를 쓰는 것뿐이다. 외부 통신 없음.

  attention.py sync    전체 다시 맞추기 (서버 시작, 수동 동작)
  attention.py event   herdr 이벤트 훅 (HERDR_PLUGIN_EVENT_JSON)
"""
import fcntl
import glob
import json
import os
import re
import subprocess
import sys
import time
import zlib

SOURCE = "user:herdr-attention"
SPACE_SOURCE = "user:herdr-attention-space"
CATS = ("red", "yellow", "green", "blue")
LABEL = {
    "red": "█ 입력 필요",
    "yellow": "█ 확인 안 함",
    "green": "✓ 확인함",
    "blue": "◐ 작업 중",
}
# 공간 색: (토큰 이름, 한국어 이름, 다른 이름들). 실제 색 값은 config.toml 줄 구성(sidebar-rows.toml)이 입힌다.
# 사이드바 한 줄에 토큰은 16개까지라(넘으면 herdr가 설정 전체를 버림) 색은 이 7가지로 고정한다.
PALETTE = (
    ("orange", "주황", ("주황색", "오렌지")),
    ("purple", "보라", ("보라색", "자주")),
    ("blue", "파랑", ("파란색", "파란", "파랑색")),
    ("pink", "분홍", ("분홍색", "핑크")),
    ("indigo", "남보라", ("남색", "남보라색", "인디고")),
    ("tan", "황토", ("황토색", "갈색", "베이지", "brown")),
    ("gray", "회색", ("그레이", "grey")),
)
NONE_WORDS = ("없음", "끔", "none", "off")
DOT = "●"
SPACE_EVENTS = {"pane_created", "pane_moved", "pane_agent_detected", "tab_created", "tab_moved",
                "workspace_created", "workspace_renamed", "workspace_closed"}

HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser("~/.local/state/herdr-attention")
CONFIG_DIR = os.environ.get("HERDR_PLUGIN_CONFIG_DIR") or os.path.expanduser("~/.config/herdr/plugins/config/herdr-attention")
COLORS_FILE = os.environ.get("HERDR_ATTENTION_SPACE_COLORS") or os.path.join(CONFIG_DIR, "space-colors.toml")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
LOCK_FILE = os.path.join(STATE_DIR, "state.lock")
LOG_FILE = os.path.join(STATE_DIR, "attention.log")
# 칸 번호(w1:p1)는 herdr 세션마다 겹치므로 세션(소켓 경로)별로 나눠 기억한다
SESSION = os.environ.get("HERDR_SOCKET_PATH") or "default"

COLORS_HEADER = """# herdr-attention 공간 색 — "공간 이름" = "색"
# 쓸 수 있는 색: 주황 · 보라 · 파랑 · 분홍 · 남보라 · 황토 · 회색  (색을 빼려면 "없음")
# 새 공간은 안 쓰인 색을 자동으로 받아 맨 아래에 한 줄이 붙고, 공간 이름을 바꾸면 이 파일의 이름도 따라 바뀐다.
# 고친 뒤 바로 보려면: herdr plugin action invoke sync --plugin herdr-attention
"""


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


def pane_list():
    d = herdr("pane", "list")
    return ((d or {}).get("result") or {}).get("panes") or []


def workspace_list():
    d = herdr("workspace", "list")
    if d is None:
        return None
    return [(w["workspace_id"], w.get("label") or "") for w in ((d.get("result") or {}).get("workspaces") or [])]


def agent_panes(panes):
    """에이전트가 있는 칸: {pane_id: (herdr 상태, 지금 보고 있는 칸인지)}"""
    return {
        p["pane_id"]: (p.get("agent_status") or "unknown", bool(p.get("focused")))
        for p in panes
        if p.get("agent")
    }


def link_sessions(panes):
    """세션 번호를 모르는 Claude 칸에, 실행 중인 Claude가 남긴 <계정 폴더>/sessions/<pid>.json의
    세션 번호를 herdr에 알려 준다. herdr 연동 훅은 세션이 시작될 때만 보고해서, 훅을 깔기 전에
    떠 있던 세션은 비어 있다(상황판 카드의 모델이 ?@?로 나오는 원인)."""
    for p in panes:
        if p.get("agent") != "claude" or p.get("agent_session"):
            continue
        pane = p["pane_id"]
        info = (((herdr("pane", "process-info", "--pane", pane) or {}).get("result") or {})
                .get("process_info") or {})
        procs = info.get("foreground_processes") or []
        lead = [x for x in procs if x.get("pid") == info.get("foreground_process_group_id")] or procs[:1]
        pid = lead[0].get("pid") if lead else None
        if not pid:
            continue
        env = subprocess.run(["ps", "eww", "-o", "command=", "-p", str(pid)],
                             capture_output=True, text=True).stdout
        m = re.search(r"CLAUDE_CONFIG_DIR=(\S+)", env)
        cfg = os.path.expanduser(m.group(1)) if m else os.path.expanduser("~/.claude")
        try:
            with open(os.path.join(cfg, "sessions", f"{pid}.json"), encoding="utf-8") as f:
                sid = json.load(f).get("sessionId")
        except (OSError, ValueError):
            continue
        if not sid:
            continue
        args = ["pane", "report-agent-session", pane, "--source", "herdr:claude",
                "--agent", "claude", "--agent-session-id", sid]
        found = glob.glob(os.path.join(cfg, "projects", "*", f"{sid}.jsonl"))
        if found:
            args += ["--agent-session-path", found[0]]
        herdr(*args)
        log(f"{pane} 세션 번호 연결: {sid[:8]} ({os.path.basename(cfg)})")


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


# ---------- 공간 색 ----------

def color_key(word):
    """사람이 쓴 색 이름 → 토큰 이름 (없음 = "", 모르는 이름 = None)"""
    w = (word or "").strip().lower()
    if w in NONE_WORDS:
        return ""
    for key, ko, alias in PALETTE:
        if w in (key, ko, *alias):
            return key
    return None


def color_ko(key):
    for k, ko, _ in PALETTE:
        if k == key:
            return ko
    return "없음"


LINE_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"([^"]*)"\s*(#.*)?$')


def load_colors():
    """space-colors.toml → (줄 목록, {공간 이름: (토큰 이름 또는 "", 줄 번호)})"""
    try:
        with open(COLORS_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = COLORS_HEADER.rstrip("\n").split("\n")
    table = {}
    for i, line in enumerate(lines):
        m = LINE_RE.match(line)
        if not m:
            continue
        name = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
        key = color_key(m.group(2))
        if key is None:
            log(f"공간 색 파일: '{name}'의 색 '{m.group(2)}'을 모름 → 색 없이 표시")
            key = ""
        table[name] = (key, i)
    return lines, table


def save_colors(lines):
    os.makedirs(os.path.dirname(COLORS_FILE), exist_ok=True)
    tmp = COLORS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, COLORS_FILE)


def quote(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def least_used(table, present, exclude):
    count = {key: 0 for key, _, _ in PALETTE}
    for name in present:
        if name != exclude and name in table and table[name][0] in count:
            count[table[name][0]] += 1
    return min(count, key=lambda k: (count[k], [p[0] for p in PALETTE].index(k)))


def space_args(key, name):
    args = []
    for k, _, _ in PALETTE:
        if k == key:
            args += ["--token", f"spn_{k}={DOT} {name}"]
        else:
            args += ["--clear-token", f"spn_{k}"]
    if key:
        args += ["--clear-token", "spn_none", "--token", f"space_color={key}"]
    else:
        args += ["--token", f"spn_none={name}", "--clear-token", "space_color"]
    return args


def space_sync(smem, listing, force, renamed=False):
    """공간마다 색을 정하고(파일), 공간 목록과 모든 칸에 색 글자를 쓴다. 바뀐 것만 쓰고, force면 전부."""
    wss = workspace_list()
    if wss is None:
        return
    lines, table = load_colors()
    present = [label for _, label in wss]
    dirty = not os.path.exists(COLORS_FILE)

    # 공간 번호(w3)는 서버가 켜져 있는 동안 바뀌지도, 다시 쓰이지도 않는다(닫은 w8 다음은 w9).
    # 그래서 같은 서버 안에서 같은 번호의 이름이 바뀌었으면 이름 변경이다. 서버를 다시 켜면 번호가
    # 새로 매겨질 수 있으므로, 소켓 파일(서버가 켜질 때 새로 생김)이 달라졌으면 비교하지 않는다.
    # 어느 이벤트가 먼저 처리되든(공간 닫기 묶음 처리 ↔ 이름 변경) 결과가 같도록 매번 확인한다.
    try:
        st = os.stat(SESSION)
        server = f"{st.st_ino}:{st.st_mtime_ns}"
    except OSError:
        server = ""
    same_server = bool(server) and smem.get("server") == server
    names = smem.get("ws_names", {}) if (same_server or renamed) else {}
    smem["server"] = server

    if names:  # 공간 이름을 바꾸면 파일의 이름도 따라 바꾼다
        for wid, label in wss:
            old = names.get(wid)
            if old and old != label and old in table and label not in table:
                key, i = table.pop(old)
                m = LINE_RE.match(lines[i])  # 색 이름·줄 끝 메모는 그대로 두고 공간 이름만 바꾼다
                lines[i] = f'{quote(label)} = "{m.group(2)}"' + (f"  {m.group(3)}" if m.group(3) else "")
                table[label] = (key, i)
                dirty = True
                log(f"공간 이름 변경: {old} → {label} (색 {color_ko(key)} 유지)")

    for label in present:
        if label not in table:
            key = least_used(table, present, label)
            lines.append(f'{quote(label)} = "{color_ko(key)}"  # 자동 배정 {time.strftime("%Y-%m-%d")}')
            table[label] = (key, len(lines) - 1)
            dirty = True
            log(f"공간 색 자동 배정: {label} → {color_ko(key)}")
    if dirty:
        save_colors(lines)

    smem["ws_names"] = {wid: label for wid, label in wss}
    ws_done = smem.setdefault("ws", {})
    for wid in list(ws_done):
        if wid not in smem["ws_names"]:
            del ws_done[wid]
    for wid, label in wss:
        key = table[label][0]
        want = f"{key}|{label}"
        if force or ws_done.get(wid) != want:
            if herdr("workspace", "report-metadata", wid, "--source", SPACE_SOURCE, *space_args(key, label)) is not None:
                ws_done[wid] = want

    label_of = smem["ws_names"]
    pane_done = smem.setdefault("panes", {})
    alive = set()
    for p in listing:
        pid, wid = p.get("pane_id"), p.get("workspace_id")
        if not pid or wid not in label_of:
            continue
        alive.add(pid)
        label = label_of[wid]
        key = table[label][0]
        want = f"{key}|{label}"
        if force or pane_done.get(pid) != want:
            if herdr("pane", "report-metadata", pid, "--source", SPACE_SOURCE, *space_args(key, label)) is not None:
                pane_done[pid] = want
    for pid in list(pane_done):
        if pid not in alive:
            del pane_done[pid]


# ---------- 기억 ----------

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


# ---------- 공간 색 요청 묶어 처리 ----------
# herdr는 플러그인 명령을 동시에 32개까지만 돌린다. 칸을 한꺼번에 많이 만들면 이벤트마다 뜬 실행이
# 잠금을 기다리며 쌓여 한도를 넘고, 그러면 다른 플러그인(상황판·파일 뷰어)까지 거절될 수 있다.
# 그래서 공간 색 요청은 "요청 표시"(파일 값 덮어쓰기)만 남기고, 잠금이 비어 있을 때만 직접 처리한다.
# 잠금을 쥐었던 쪽은 놓은 뒤 표시를 보고 이어서 처리한다(drain). 파일을 지우는 일은 없다.
REQ_FILE = os.path.join(STATE_DIR, "space-request-%08x.txt" % (zlib.crc32(SESSION.encode()) & 0xFFFFFFFF))


def mark_request():
    tmp = REQ_FILE + ".tmp%d" % os.getpid()
    with open(tmp, "w") as f:
        f.write(str(time.time_ns()))
    os.replace(tmp, REQ_FILE)


def read_request():
    try:
        with open(REQ_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def space_mem(data):
    return data.setdefault("space_sessions", {}).setdefault(SESSION, {})


def drain():
    for _ in range(5):  # 끝없이 돌지 않게
        req = read_request()
        if not req or space_mem(load()).get("req_done") == req:
            return
        lock = open(LOCK_FILE, "w")
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # 지금 잠금을 쥔 쪽이 놓은 뒤 이어서 처리한다
            data = load()
            smem = space_mem(data)
            req = read_request()
            if smem.get("req_done") != req:
                space_sync(smem, pane_list(), force=False)
                smem["req_done"] = req
                save(data)
        finally:
            lock.close()


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

    if etype in SPACE_EVENTS and etype != "workspace_renamed":  # 새 칸·칸 이동·공간 생성/닫힘: 묶어 처리
        mark_request()
    else:
        handle(mode, etype, event)
    drain()  # 잠금을 놓은 뒤: 그사이 들어온 공간 색 요청을 처리


def handle(mode, etype, event):
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load()
        sessions = data.setdefault("sessions", {})
        spaces = data.setdefault("space_sessions", {})
        for store in (sessions, spaces):  # 없어진 세션(시험 세션 등)의 기억은 지운다
            for s in list(store):
                if s != SESSION and s.startswith("/") and not os.path.exists(s):
                    del store[s]
        mem = sessions.setdefault(SESSION, {})
        smem = spaces.setdefault(SESSION, {})

        if etype == "pane_closed":
            pid = str(find(event, "pane_id"))
            mem.pop(pid, None)
            smem.get("panes", {}).pop(pid, None)
            save(data)
            return

        listing = pane_list()
        if etype == "workspace_renamed":  # 이름 변경은 드물고, 파일의 이름도 바꿔야 해서 바로 처리
            space_sync(smem, listing, force=False, renamed=True)
            save(data)
            return

        panes = agent_panes(listing)
        if mode == "sync":
            link_sessions(listing)
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

        if mode == "sync":  # 서버 시작·수동: 공간 색도 전부 다시 쓴다 (서버를 다시 켜면 표시 글자가 사라지므로)
            req = read_request()
            smem["ws"], smem["panes"] = {}, {}
            space_sync(smem, listing, force=True)
            smem["req_done"] = req
        elif etype == "pane_agent_status_changed":
            pid = targets[0] if targets else ""
            if pid and pid not in smem.get("panes", {}):  # 색 글자를 놓친 칸: 잠금을 놓은 뒤 채운다
                mark_request()
        save(data)


if __name__ == "__main__":
    main()
