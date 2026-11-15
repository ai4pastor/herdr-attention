# herdr-attention

herdr 왼쪽 사이드바에 두 가지를 색으로 표시해 주는 플러그인입니다.

- **상태** — 에이전트마다 지금 무엇을 해야 하는지 (줄 맨 앞 기호)
- **공간 색** — 공간(작업공간)마다 정한 색을 공간 목록과 에이전트 줄의 `● 공간 이름`에 (0.2.0부터)

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

## 공간 색

공간마다 색을 하나씩 정해, 공간 목록과 에이전트 줄의 공간 이름에 `●` 점과 함께 입힙니다. 예를 들어 「교회」 공간을 파랑으로 두면, 교회 공간의 모든 에이전트 줄에 파란 `● 교회`가 붙습니다.

- **색 7가지**: 주황 · 보라 · 파랑 · 분홍 · 남보라 · 황토 · 회색. herdr 사이드바 한 줄에 표시 조각(토큰)을 16개까지만 넣을 수 있어서(넘으면 herdr가 설정 전체를 버림) 7가지로 정했습니다.
- **상태 색과 구분**: 줄 맨 앞의 `█ ✓ ◐` 기호는 상태, `● 공간 이름`은 공간입니다. 모양과 자리로 구분됩니다.
- **정하는 곳**: `~/.config/herdr/plugins/config/herdr-attention/space-colors.toml`

  ```toml
  "교회" = "파랑"
  "플러그인" = "보라"
  "맥미니" = "없음"   # 색 없이 이름만
  ```

  「파란색」「남색」「갈색」처럼 써도 알아듣습니다. 모르는 색 이름이면 색 없이 이름만 보이고 기록에 남깁니다.
- **새 공간**은 가장 덜 쓰인 색을 자동으로 받아 파일 맨 아래에 한 줄이 붙습니다. **공간 이름을 바꾸면** 파일의 이름도 따라 바뀌어 색이 그대로 유지됩니다. 닫은 공간의 줄은 남아 있어서, 같은 이름으로 다시 만들면 같은 색이 됩니다.
- **색 바꾸기**: 파일을 고친 뒤 `herdr plugin action invoke sync --plugin herdr-attention`. Claude Code에는 "herdr 공간 색에서 교회를 보라로 바꿔 줘"처럼 말하면 됩니다.
- **공간별로 묶어 보기**: 사이드바 아래 **agents** 머리말 오른쪽의 `priority` 글자를 누르면 `grouped`(공간별 묶음)로, 다시 누르면 급한 순으로 바뀝니다. herdr가 기억하며, 설정 파일의 `agent_panel_sort`보다 이 선택이 우선합니다.

## 설치

필요한 것: macOS, herdr 0.9 이상, Xcode 명령줄 도구의 `/usr/bin/python3` (Homebrew를 깔았다면 이미 있습니다).

1. 플러그인 설치

   ```sh
   herdr plugin install ai4pastor/herdr-attention
   ```

   이 폴더를 직접 받았다면 `herdr plugin link <이 폴더 경로>` 로 연결해도 됩니다.

2. 사이드바 줄 구성 넣기: [`sidebar-rows.toml`](sidebar-rows.toml)의 내용을 `~/.config/herdr/config.toml`에 붙여 넣습니다.
   이미 `[ui.sidebar.agents]`·`[ui.sidebar.agents.rows_by_agent]`·`[ui.sidebar.spaces]`가 있으면 그 부분을 바꿉니다.

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
- **세션 번호 연결**: 연동 훅은 세션이 *시작될 때만* 보고해서, 훅을 깔기 전에 떠 있던 Claude 세션은 herdr가 세션 번호를 모릅니다(에이전트 상황판 카드에 모델이 `?@?`로 나옴). "다시 맞추기"를 하면 실행 중인 Claude가 남긴 `<계정 폴더>/sessions/<프로세스번호>.json`에서 세션 번호를 찾아 herdr에 알려 줍니다. 대화를 한 번도 안 한 새 세션은 기록이 없어서 첫 대화 뒤에 채워집니다.
- 하는 일은 `herdr pane report-metadata`·`herdr workspace report-metadata`로 칸·공간마다 표시 글자를 쓰는 것(과 공간 색 파일 관리)뿐입니다. 외부 통신은 없습니다.
- **플러그인을 끄거나 지우면 공간 이름이 사이드바에서 사라집니다**(이름 글자를 플러그인이 쓰기 때문). 끌 때는 `config.toml`의 줄 구성도 함께 되돌리세요.
- herdr는 플러그인 명령을 동시에 32개까지만 돌립니다. 칸을 한꺼번에 많이 만들 때 다른 플러그인이 밀려나지 않도록, 공간 색 요청은 묶어서 한 번에 처리합니다.
- 표시가 어긋나 보이면: `herdr plugin action invoke sync --plugin herdr-attention`
- 기록: `~/.local/state/herdr/plugins/herdr-attention/attention.log` (기억은 같은 폴더의 `state.json`)

## 지우기

```sh
herdr plugin uninstall herdr-attention
```

그다음 `config.toml`에서 위 줄 구성을 빼고 `herdr server reload-config`를 실행합니다.
