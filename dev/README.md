# 개발용 도구

- `vt.py` — 아주 작은 터미널 흉내. herdr 화면을 pty로 받아 둔 원본(화면 신호)을 넣으면 최종 화면 글자를 복원한다.
  `python3 -I vt.py <받아 둔 원본.txt> <줄 수> <칸 수> [왼쪽에서 자를 칸]`
- `vtc.py` — vt.py에 색을 더한 것. 글자색·배경색·굵게까지 복원하고 `html`로 내보내면 시안 페이지에 그대로 붙일 수 있다(0.2.0 공간 색 시안에 씀).
  `python3 -I vtc.py <원본> <줄 수> <칸 수> <왼쪽 몇 칸> [text|html]`
- `capture.py` — herdr에 pty로 붙어 몇 초간 화면 신호를 받아 저장한다. 중간에 키·마우스 클릭을 보낼 수 있다(사용법은 파일 머리말).

## herdr 화면을 안전하게 시험하는 법 (실제 세션을 건드리지 않게)

1. 시험 세션 서버를 시험 소켓을 박은 채로 띄운다 — 플러그인이 부르는 herdr 명령이 실제 세션으로 새지 않는다.
   `env -u HERDR_PANE_ID -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID -u HERDR_ENV HERDR_SOCKET_PATH=~/.config/herdr/sessions/<이름>/herdr.sock herdr --session <이름> server`
2. 가짜 에이전트: `herdr pane report-agent <칸> --source user:test --agent claude --state blocked|idle|working` (성공하면 출력 없음)
3. 화면 받기: `CAP_SESSION=<이름> CAP_CONFIG=<시험 설정> XDG_STATE_HOME=<새 폴더> python3 -I capture.py 원본.txt 56 150 3` → `vt.py`·`vtc.py`로 복원.
   - 🚨 사이드바는 **붙는 쪽(클라이언트)의 설정**을 읽는다 → 시험 설정은 `CAP_CONFIG`로 클라이언트에 넘긴다.
   - 클라이언트는 사이드바 너비·정렬(agents 머리말 클릭)을 `$XDG_STATE_HOME/herdr/client-shell/`에 기억한다 → 시험 때는 새 폴더로 갈라 실제 기억 파일을 지킨다.
   - 접두키 입력기 전환을 막으려면 시험 설정 사본에서 `switch_ascii_input_source_in_prefix = false`.
4. 끝나면 `herdr session stop <이름>` 후 **내가 만든** `~/.config/herdr/sessions/<이름>` 폴더만 휴지통으로. 다른 Claude 세션도 같은 폴더에 시험 세션을 만든다. `herdr session delete`는 영구 삭제라 쓰지 않는다.

## 플러그인 자체를 실제 등록부와 갈라서 시험하는 법 (0.2.0에서 씀)

위 방법은 실제 등록부의 플러그인이 시험 세션에서도 돈다. 고친 플러그인을 실제에 넣기 전에 **실제 이벤트로** 시험하려면 herdr 전체를 가른다.

1. herdr는 `XDG_CONFIG_HOME`(설정·플러그인 등록부·기본 세션 소켓)과 `XDG_STATE_HOME`(플러그인 기억)을 따른다.
   소켓 경로는 104자를 넘으면 실패하므로 짧은 폴더를 쓴다. 맥의 `/private/tmp/…`는 `/tmp/…`로 줄여 쓸 수 있다.
2. `X=<짧은 폴더>; mkdir -p $X/herdr $X/state` 후 시험 설정을 `$X/herdr/config.toml`에 둔다.
3. 실행기: `env -u HERDR_PANE_ID -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID -u HERDR_ENV -u HERDR_SOCKET_PATH -u HERDR_CONFIG_PATH XDG_CONFIG_HOME=$X XDG_STATE_HOME=$X/state herdr …`
   이걸로 `server`를 띄우고, `plugin link <고친 사본 폴더>` → 그 사본만 등록된 herdr가 된다(실제 `plugins.json`은 그대로).
4. 칸·탭·공간을 만들고 이름을 바꾸면 실제 이벤트가 사본으로 간다. 결과는 `plugin log list`(최근 50건만 보관)와 `$X/state/herdr/plugins/<id>/`의 기록으로 본다.
5. 🚨 herdr는 플러그인 명령을 **동시에 32개까지만** 돌린다(넘으면 `maximum concurrent plugin commands reached (32)`로 거절). 칸을 몰아 만드는 시험(탭 8개 등)으로 꼭 확인한다.
