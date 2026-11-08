# 아주 작은 터미널 흉내: herdr가 보낸 화면 신호(커서 이동·글자)만 따라 그려서 최종 화면 글자를 복원한다.
import re, sys, unicodedata


def width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def render(raw, rows, cols):
    scr = [[" "] * cols for _ in range(rows)]
    r = c = 0
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\x1b":
            m = re.match(r"\x1b\[([0-9;?<>=]*)([ -/]*)([@-~])", raw[i:])
            if m:
                params, final = m.group(1), m.group(3)
                nums = [int(x) if x.isdigit() else 0 for x in params.split(";")] if params and params[0] not in "?<>=" else []
                if final in "Hf":
                    r = (nums[0] if nums and nums[0] else 1) - 1
                    c = (nums[1] if len(nums) > 1 and nums[1] else 1) - 1
                elif final == "C":
                    c += nums[0] if nums and nums[0] else 1
                elif final == "D":
                    c -= nums[0] if nums and nums[0] else 1
                elif final == "G":
                    c = (nums[0] if nums and nums[0] else 1) - 1
                elif final == "J" and nums and nums[0] == 2:
                    scr = [[" "] * cols for _ in range(rows)]
                elif final == "K" and 0 <= r < rows:
                    for x in range(max(c, 0), cols):
                        scr[r][x] = " "
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
                scr[r][c] = ch
                if w == 2 and c + 1 < cols:
                    scr[r][c + 1] = ""
            c += w
        i += 1
    return ["".join(row).rstrip() for row in scr]


if __name__ == "__main__":
    raw = open(sys.argv[1], encoding="utf-8").read()
    rows, cols = int(sys.argv[2]), int(sys.argv[3])
    left = int(sys.argv[4]) if len(sys.argv) > 4 else cols
    for line in render(raw, rows, cols):
        print(line[:left])
