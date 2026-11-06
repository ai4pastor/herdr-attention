# herdr-attention

herdr 왼쪽 사이드바의 에이전트 목록에 **지금 무엇을 해야 하는지** 색으로 표시해 주는 플러그인입니다.

| 표시 | 뜻 | 할 일 |
| --- | --- | --- |
| **█ 입력 필요** (빨강) | 에이전트가 질문이나 승인을 기다리며 멈춰 있음 | 지금 답하기 |
| **█ 확인 안 함** (노랑) | 일이 끝났는데 아직 그 칸에 들어가 보지 않음 | 들어가서 결과 보기 |
| **✓ 확인함** (초록) | 일이 끝났고 이미 들어가 봄 | 없음 |
| **◐ 작업 중** (파랑) | 일하는 중 | 기다리기 |

작은 동그라미 대신 줄 맨 앞에 굵은 색 글자가 붙습니다.

## 색이 바뀌는 규칙

- 일이 끝났을 때 그 칸을 보고 있지 않았으면 **노랑**입니다. 그 칸에 한 번 들어가면(칸 이동, 클릭, 탭·작업공간 이동) **초록**이 됩니다.
- 일이 끝나는 순간 이미 그 칸을 보고 있었다면 바로 초록입니다.
- 빨강은 답을 해서 에이전트가 다시 일하기 시작하면 풀립니다.
- 처음 설치할 때 이미 끝나 있던 칸은 초록에서 시작합니다. herdr를 다시 켜면 시작할 때 한 번 다시 맞춥니다.

## 설치

필요한 것: macOS, herdr 0.9 이상, Xcode 명령줄 도구의 `/usr/bin/python3` (Homebrew를 깔았다면 이미 있습니다).

1. 플러그인 설치

   ```sh
   herdr plugin install ai4pastor/herdr-attention
   ```

   이 폴더를 직접 받았다면 `herdr plugin link <이 폴더 경로>` 로 연결해도 됩니다.

2. 사이드바 줄 구성 넣기: [`sidebar-rows.toml`](sidebar-rows.toml)의 내용을 `~/.config/herdr/config.toml`에 붙여 넣습니다.
   이미 `[ui.sidebar.agents]`나 `[ui.sidebar.agents.rows_by_agent]`가 있으면 그 부분을 바꿉니다.

3. 적용

   ```sh
   herdr config check
   herdr server reload-config
   herdr plugin action invoke sync --plugin herdr-attention
   ```

Claude Code에 맡기려면 이렇게 말하면 됩니다.

> herdr-attention 플러그인을 설치해 줘. `herdr plugin install ai4pastor/herdr-attention`로 설치하고, 플러그인 폴더의 sidebar-rows.toml 내용을 내 `~/.config/herdr/config.toml`에 넣어 줘. 바꾸기 전에 config.toml을 백업하고, 같은 표가 이미 있으면 그 부분을 바꿔 줘. 끝나면 `herdr config check`, `herdr server reload-config`, `herdr plugin action invoke sync --plugin herdr-attention`을 실행하고 결과를 알려 줘.

## 알아 둘 점

- herdr 사이드바는 줄 배경을 칠하는 기능이 없어서 줄 맨 앞의 굵은 색 글자로 표시합니다.
- 사이드바 순서는 herdr가 정합니다. 빨강은 맨 위로 올라오지만 노랑의 위치는 보장되지 않습니다.
- 상태 판정(작업 중·입력 필요·끝남)은 herdr가 합니다. 정확도를 높이려면 herdr 연동 훅을 설치하세요: `herdr integration install claude` (Claude Code 계정을 여러 개 쓰면 계정마다 `CLAUDE_CONFIG_DIR=<계정 폴더>`를 앞에 붙여 실행).
- 하는 일은 `herdr pane report-metadata`로 칸마다 표시 글자를 쓰는 것뿐입니다. 외부 통신은 없습니다.
- 표시가 어긋나 보이면: `herdr plugin action invoke sync --plugin herdr-attention`
- 기록: `~/.config/herdr/plugins/` 아래 이 플러그인의 상태 폴더에 `attention.log`가 남습니다.

## 지우기

```sh
herdr plugin uninstall herdr-attention
```

그다음 `config.toml`에서 위 줄 구성을 빼고 `herdr server reload-config`를 실행합니다.
