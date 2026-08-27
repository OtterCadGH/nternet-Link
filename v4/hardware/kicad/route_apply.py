#!/usr/bin/env python3
"""Apply a Freerouting Specctra .ses session back onto a KiCad .kicad_pcb by
parsing the session wires/vias and injecting native (segment)/(via) elements.

Headless-safe: does NOT use pcbnew.ImportSpecctraSES (that targets the GUI
board). SES coords are in the DSN resolution (um 10 -> 10000 units per mm),
Y is math-up so it negates vs KiCad. Net codes come from the board file.

Usage: route_apply.py <board.kicad_pcb> <session.ses>
Re-runnable: strips any previously injected copper first.
"""
import re, sys, uuid

def U(): return str(uuid.uuid4())

def tokenize(s):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', s)

def parse(tokens):
    # recursive s-expr -> nested lists
    it = iter(tokens)
    def rec():
        out = []
        for tok in it:
            if tok == '(':
                out.append(rec())
            elif tok == ')':
                return out
            else:
                out.append(tok.strip('"'))
        return out
    # wrap: first token is '('
    assert tokens[0] == '('
    return rec()

def find_all(node, tag):
    """yield every sub-list whose head == tag, recursively."""
    if isinstance(node, list):
        if node and node[0] == tag:
            yield node
        for x in node:
            yield from find_all(x, tag)

def main(board_path, ses_path):
    ses = parse(tokenize(open(ses_path).read()))

    # resolution: (resolution um 10) -> units per mm
    res = next(find_all(ses, 'resolution'))
    unit, factor = res[1], float(res[2])
    per_mm = {'um': 1000.0, 'mm': 1.0, 'inch': 0.0393700787}[unit] * factor
    def X(v): return round(float(v) / per_mm, 4)
    def Y(v): return round(-float(v) / per_mm, 4)   # SES Y is up

    # net code map from the board file
    board = open(board_path).read()
    netcode = {name: int(code) for code, name in
               re.findall(r'\(net (\d+) "([^"]*)"\)', board)}

    segments, vias = [], []
    # walk each (net NAME ...) block in the routes section
    for net in find_all(ses, 'net'):
        if len(net) < 2 or not isinstance(net[1], str):
            continue
        name = net[1]
        code = netcode.get(name)
        if code is None:
            continue
        for wire in find_all(net, 'wire'):
            path = next(iter(find_all(wire, 'path')), None)
            if not path:
                continue
            layer = path[1]
            width = round(float(path[2]) / per_mm, 4)
            coords = path[3:]
            pts = [(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                segments.append(
                    f'  (segment (start {X(x1)} {Y(y1)}) (end {X(x2)} {Y(y2)})'
                    f' (width {width}) (layer "{layer}") (net {code}) (tstamp {U()}))')
        for via in find_all(net, 'via'):
            # (via "Via[..]_600:300_um" x y)  -> sizes from the name
            m = re.search(r'_(\d+):(\d+)_um', via[1])
            size = round(int(m.group(1)) / 1000, 4) if m else 0.6
            drill = round(int(m.group(2)) / 1000, 4) if m else 0.3
            x, y = via[-2], via[-1]
            vias.append(
                f'  (via (at {X(x)} {Y(y)}) (size {size}) (drill {drill})'
                f' (layers "F.Cu" "B.Cu") (net {code}) (tstamp {U()}))')

    # strip previously injected copper, then append fresh
    board = re.sub(r'\n  \(segment .*?\)\)', '', board)
    board = re.sub(r'\n  \(via \(at .*?\)\)', '', board)
    inject = "\n" + "\n".join(segments + vias) + "\n"
    board = board.rstrip()
    assert board.endswith(')'), "unexpected board tail"
    board = board[:-1] + inject + ")\n"
    open(board_path, 'w').write(board)
    print(f"injected {len(segments)} segments + {len(vias)} vias into {board_path}")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
