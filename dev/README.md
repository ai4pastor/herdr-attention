# 개발용 도구

- `vt.py` — 아주 작은 터미널 흉내. herdr 화면을 pty로 받아 둔 원본(화면 신호)을 넣으면 최종 화면 글자를 복원한다.
  `python3 -I vt.py <받아 둔 원본.txt> <줄 수> <칸 수> [왼쪽에서 자를 칸]`
  색은 복원하지 않으므로, 색 확인은 원본에서 `\x1b[...38;2;R;G;Bm`(글자색)·`48;2;R;G;B`(배경색)을 센다.

## herdr 화면을 안전하게 시험하는 법 (실제 세션을 건드리지 않게)

1. 시험 세션 서버를 시험 소켓을 박은 채로 띄운다 — 플러그인이 부르는 herdr 명령이 실제 세션으로 새지 않는다.
   `env -u HERDR_PANE_ID -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID -u HERDR_ENV HERDR_SOCKET_PATH=~/.config/herdr/sessions/<이름>/herdr.sock herdr --session <이름> server`
2. 가짜 에이전트: `herdr pane report-agent <칸> --source user:test --agent claude --state blocked|idle|working` (성공하면 출력 없음)
3. 화면 받기: python `pty.fork()`로 `herdr --session <이름>`을 붙이고 출력을 계속 읽어 파일에 저장 → `vt.py`로 복원.
   접두키 입력기 전환을 막으려면 시험 설정 사본에서 `switch_ascii_input_source_in_prefix = false`.
4. 끝나면 `herdr session stop <이름>` 후 `~/.config/herdr/sessions`를 휴지통으로 (`herdr session delete`는 영구 삭제라 쓰지 않는다).
