# 색까지 살리는 화면 복원기: python3 -I vtc.py <받아 둔 원본> <줄 수> <칸 수> <왼쪽 몇 칸> [text|html]
# vt.py와 같은 일을 하되 글자색·배경색·굵게를 함께 기억한다. html로 내보내면 시안 페이지에 그대로 붙일 수 있다.
# 기본 글자색·배경색(색 지정 없음 = 39·49)은 Ghostty 기본값에 맞춤.
import html
import re
import sys
import unicodedata

DEF_FG, DEF_BG = "#eceff4", "#282c34"


def width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def render(raw, rows, cols):
    """화면을 [글자, 글자색, 배경색, 굵게] 칸의 2차원 목록으로. 넓은 글자(한글) 뒤 칸은 글자 ""."""
    def cell():
        return [" ", DEF_FG, DEF_BG, False]

    scr = [[cell() for _ in range(cols)] for _ in range(rows)]
    fg, bg, bold = DEF_FG, DEF_BG, False
    r = c = 0
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\x1b":
            m = re.match(r"\x1b\[([0-9;?<>=:]*)([ -/]*)([@-~])", raw[i:])
            if m:
                p, final = m.group(1), m.group(3)
                priv = p[:1] in ("?", "<", ">", "=")
                nums = [int(x) if x.isdigit() else 0 for x in p.split(";")] if p and not priv else []
                first = nums[0] if nums and nums[0] else 1
                if final in "Hf":
                    r, c = first - 1, (nums[1] if len(nums) > 1 and nums[1] else 1) - 1
                elif final == "A":
                    r -= first
                elif final == "B":
                    r += first
                elif final == "C":
                    c += first
                elif final == "D":
                    c -= first
                elif final == "G":
                    c = first - 1
                elif final == "d":
                    r = first - 1
                elif final == "J" and nums and nums[0] == 2:
                    scr = [[cell() for _ in range(cols)] for _ in range(rows)]
                elif final == "K" and 0 <= r < rows:
                    for x in range(max(c, 0), cols):
                        scr[r][x] = [" ", fg, bg, False]
                elif final == "X" and 0 <= r < rows:
                    for x in range(max(c, 0), min(cols, c + first)):
                        scr[r][x] = [" ", fg, bg, False]
                elif final == "m" and not priv:
                    nums = nums or [0]
                    k = 0
                    while k < len(nums):
                        v = nums[k]
                        if v == 0:
                            fg, bg, bold = DEF_FG, DEF_BG, False
                        elif v == 1:
                            bold = True
                        elif v == 22:
                            bold = False
                        elif v == 39:
                            fg = DEF_FG
                        elif v == 49:
                            bg = DEF_BG
                        elif v in (38, 48) and k + 4 < len(nums) and nums[k + 1] == 2:
                            col = "#%02x%02x%02x" % tuple(nums[k + 2:k + 5])
                            if v == 38:
                                fg = col
                            else:
                                bg = col
                            k += 4
                        elif v in (38, 48) and k + 2 < len(nums) and nums[k + 1] == 5:
                            k += 2  # 256색은 쓰지 않으므로 건너뜀
                        k += 1
                i += m.end()
                continue
            m = re.match(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1b[P_^][^\x1b]*\x1b\\|\x1b.", raw[i:])
            i += m.end() if m else 1
            continue
        if ch == "\r":
            c = 0
        elif ch == "\n":
            r += 1
        elif ch == "\b":
            c = max(0, c - 1)
        elif ch >= " ":
            w = width(ch)
            if 0 <= r < rows and 0 <= c < cols:
                scr[r][c] = [ch, fg, bg, bold]
                if w == 2 and c + 1 < cols:
                    scr[r][c + 1] = ["", fg, bg, bold]
            c += w
        i += 1
    return scr


def to_html(scr, left):
    """같은 모양끼리 묶은 <span>들. 한글 줄 맞춤이 필요하면 칸마다 2ch 상자로 감싸 쓴다."""
    out = []
    for row in scr:
        parts, cur, buf = [], None, ""
        for ch, fg, bg, bold in row[:left]:
            key = (fg, bg, bold)
            if key != cur:
                if buf:
                    parts.append((cur, buf))
                cur, buf = key, ""
            buf += ch
        if buf:
            parts.append((cur, buf))
        out.append("".join(
            f'<span style="color:{f};background:{b};{"font-weight:700;" if bo else ""}">{html.escape(t)}</span>'
            for (f, b, bo), t in parts))
    return "\n".join(out)


if __name__ == "__main__":
    raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    rows, cols, left = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    screen = render(raw, rows, cols)
    if (sys.argv[5] if len(sys.argv) > 5 else "text") == "html":
        print(to_html(screen, left))
    else:
        for row in screen:
            print("".join(x[0] for x in row[:left]).rstrip())
