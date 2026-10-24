"""Write the current-state and future-state processes as BPMN 2.0 XML (with
diagram layout, so they open in Camunda Modeler or bpmn.io) and as SVG images
for the docs. One model, two outputs, so the picture always matches the file."""
from pathlib import Path
from xml.sax.saxutils import escape

COL, ROW, X0, Y0 = 175, 115, 40, 70
SIZE = {"start": (36, 36), "end": (36, 36), "catch": (36, 36), "gateway": (50, 50),
        "userTask": (130, 72), "serviceTask": (130, 72), "businessRuleTask": (130, 72), "task": (130, 72)}
XML_TAG = {"start": "startEvent", "end": "endEvent", "catch": "intermediateCatchEvent", "gateway": "exclusiveGateway"}

CURRENT = {
    "nodes": [("start", "start", "Support email arrives", 0, 1),
              ("triage", "userTask", "Read and triage email (RMA desk)", 1, 1),
              ("g_rma", "gateway", "RMA request?", 2, 1),
              ("forward", "userTask", "Forward to sales or billing (RMA desk)", 3, 2),
              ("end_fwd", "end", "Forwarded", 4, 2),
              ("g_info", "gateway", "Serial and details?", 3, 1),
              ("ask", "userTask", "Email customer for serial (RMA desk)", 4, 0),
              ("wait", "catch", "Customer replies", 5, 0),
              ("lookup", "userTask", "Look up serial and owner in ERP", 4, 1),
              ("warranty", "userTask", "Check warranty in spreadsheet", 5, 1),
              ("g_war", "gateway", "In warranty?", 6, 1),
              ("quote", "userTask", "Send repair quote", 7, 2),
              ("end_quote", "end", "Quote sent", 8, 2),
              ("enter", "userTask", "Re-key RMA into ERP", 7, 1),
              ("email", "userTask", "Email RMA number", 8, 1),
              ("end", "end", "RMA issued", 9, 1)],
    "flows": [("start", "triage", ""), ("triage", "g_rma", ""), ("g_rma", "forward", "no"), ("forward", "end_fwd", ""),
              ("g_rma", "g_info", "yes"), ("g_info", "ask", "no"), ("ask", "wait", ""), ("wait", "triage", "back to the queue"),
              ("g_info", "lookup", "yes"), ("lookup", "warranty", ""), ("warranty", "g_war", ""),
              ("g_war", "quote", "no"), ("quote", "end_quote", ""), ("g_war", "enter", "yes"),
              ("enter", "email", ""), ("email", "end", "")],
}

FUTURE = {
    "nodes": [("start", "start", "Support email arrives", 0, 1),
              ("agent", "serviceTask", "AI agent reads the email (EN or FR)", 1, 1),
              ("check", "businessRuleTask", "Check serial, owner and warranty in ERP (read-only)", 2, 1),
              ("g_route", "gateway", "Route", 3, 1),
              ("safety", "userTask", "Engineering on-call responds (human)", 4, 0),
              ("end_safety", "end", "Escalated", 5, 0),
              ("draft", "serviceTask", "Draft RMA in ERP", 4, 1),
              ("approve", "userTask", "Approve RMA, one click (RMA desk)", 5, 1),
              ("email", "serviceTask", "Email RMA number", 6, 1),
              ("end", "end", "RMA issued", 7, 1),
              ("ask", "serviceTask", "Send serial request in the customer's language", 4, 2),
              ("end_ask", "end", "Reply re-enters as a new email", 5, 2),
              ("review", "userTask", "RMA desk reviews exception (human)", 4, 3),
              ("end_review", "end", "Handled by desk", 5, 3),
              ("forward", "serviceTask", "Forward to sales or billing", 4, 4),
              ("end_fwd", "end", "Forwarded", 5, 4)],
    "flows": [("start", "agent", ""), ("agent", "check", ""), ("check", "g_route", ""),
              ("g_route", "safety", "safety language"), ("safety", "end_safety", ""),
              ("g_route", "draft", "clean"), ("draft", "approve", ""),
              ("approve", "email", ""), ("email", "end", ""),
              ("g_route", "ask", "no serial"), ("ask", "end_ask", ""),
              ("g_route", "review", "exception or low confidence"), ("review", "end_review", ""),
              ("g_route", "forward", "not an RMA"), ("forward", "end_fwd", "")],
}


def layout(model):
    box = {}
    for nid, kind, name, c, r in model["nodes"]:
        w, h = SIZE[kind]
        cx, cy = X0 + c * COL + 65, Y0 + r * ROW + 36
        box[nid] = (kind, name, cx - w / 2, cy - h / 2, w, h)
    return box


def route(box, s, t):
    _, _, sx, sy, sw, sh = box[s]
    _, _, tx, ty, tw, th = box[t]
    scx, scy, tcx, tcy = sx + sw / 2, sy + sh / 2, tx + tw / 2, ty + th / 2
    if abs(scy - tcy) < 1:
        return [(sx + sw, scy), (tx, tcy)] if tcx > scx else [(sx, scy), (tx + tw, tcy)]
    if tcx < scx:                                      # loop back: over the top
        top = min(sy, ty) - 28
        return [(scx, sy), (scx, top), (tcx, top), (tcx, ty)]
    return [(scx, sy + sh if tcy > scy else sy), (scx, tcy), (tx, tcy)]


def to_bpmn(model, pid, name):
    box = layout(model)
    el, shapes, edges = [], [], []
    for nid, (kind, label, x, y, w, h) in box.items():
        tag = XML_TAG.get(kind, kind)
        el.append(f'    <bpmn:{tag} id="{nid}" name="{escape(label)}" />')
        extra = ' isMarkerVisible="true"' if kind == "gateway" else ""
        shapes.append(f'      <bpmndi:BPMNShape id="{nid}_di" bpmnElement="{nid}"{extra}>'
                      f'<dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')
    for i, (s, t, lbl) in enumerate(model["flows"]):
        fid = f"flow_{i}"
        el.append(f'    <bpmn:sequenceFlow id="{fid}" name="{escape(lbl)}" sourceRef="{s}" targetRef="{t}" />')
        pts = "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}" />' for x, y in route(box, s, t))
        edges.append(f'      <bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">{pts}</bpmndi:BPMNEdge>')
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            f'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
            f'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="defs_{pid}" targetNamespace="http://bpmn.io/schema/bpmn">\n'
            f'  <bpmn:process id="{pid}" name="{escape(name)}" isExecutable="false">\n' + "\n".join(el) +
            f'\n  </bpmn:process>\n  <bpmndi:BPMNDiagram id="diagram_{pid}">\n    <bpmndi:BPMNPlane id="plane_{pid}" bpmnElement="{pid}">\n'
            + "\n".join(shapes + edges) + "\n    </bpmndi:BPMNPlane>\n  </bpmndi:BPMNDiagram>\n</bpmn:definitions>\n")


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def to_svg(model, title):
    box = layout(model)
    W = max(x + w for _, _, x, _, w, _ in box.values()) + 60
    H = max(y + h for _, _, _, y, _, h in box.values()) + 70
    human = {"userTask": "#fff4df", "serviceTask": "#e6f0fc", "businessRuleTask": "#e8f6ee", "task": "#f4f4f2"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" font-family="Segoe UI, Arial, sans-serif">',
           f'<rect width="100%" height="100%" fill="#ffffff"/>',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>',
           f'<text x="20" y="28" font-size="17" font-weight="600" fill="#111">{escape(title)}</text>']
    for s, t, lbl in model["flows"]:
        pts = route(box, s, t)
        out.append(f'<polyline points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in pts)}" fill="none" stroke="#444" '
                   f'stroke-width="1.4" marker-end="url(#a)"/>')
        if lbl:
            (x1, y1), (x2, y2) = pts[0], pts[1]
            lx, ly = ((x1 + 6, (y1 + y2) / 2) if abs(x1 - x2) < 1 else ((x1 + x2) / 2 - 30, y1 - 6))
            if len(pts) > 2 and abs(x1 - x2) < 1:
                lx, ly = pts[1][0] + 6, pts[1][1] - 6
            for i, ln in enumerate(wrap(lbl, 22)):
                out.append(f'<text x="{lx:.0f}" y="{ly + i * 12:.0f}" font-size="10.5" fill="#555">{escape(ln)}</text>')
    for nid, (kind, label, x, y, w, h) in box.items():
        cx, cy = x + w / 2, y + h / 2
        if kind in ("start", "end", "catch"):
            sw = {"start": 1.5, "end": 3.5, "catch": 1.5}[kind]
            out.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="18" fill="#fff" stroke="#222" stroke-width="{sw}"/>')
            if kind == "catch":
                out.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="14" fill="none" stroke="#222" stroke-width="1.2"/>'
                           f'<rect x="{cx - 8:.0f}" y="{cy - 5:.0f}" width="16" height="11" fill="none" stroke="#222"/>'
                           f'<path d="M{cx - 8:.0f},{cy - 5:.0f} L{cx:.0f},{cy + 1:.0f} L{cx + 8:.0f},{cy - 5:.0f}" fill="none" stroke="#222"/>')
            for i, ln in enumerate(wrap(label, 18)):
                out.append(f'<text x="{cx:.0f}" y="{y + h + 14 + i * 12:.0f}" font-size="10.5" text-anchor="middle" fill="#333">{escape(ln)}</text>')
        elif kind == "gateway":
            out.append(f'<path d="M{cx:.0f},{y:.0f} L{x + w:.0f},{cy:.0f} L{cx:.0f},{y + h:.0f} L{x:.0f},{cy:.0f} z" fill="#fff" stroke="#222" stroke-width="1.5"/>'
                       f'<path d="M{cx - 9:.0f},{cy - 9:.0f} L{cx + 9:.0f},{cy + 9:.0f} M{cx + 9:.0f},{cy - 9:.0f} L{cx - 9:.0f},{cy + 9:.0f}" stroke="#222" stroke-width="2.5"/>')
            lines = wrap(label, 14)
            for i, ln in enumerate(lines):
                out.append(f'<text x="{x - 4:.0f}" y="{y - 4 - (len(lines) - 1 - i) * 12:.0f}" font-size="11" text-anchor="end" fill="#111" font-weight="600">{escape(ln)}</text>')
        else:
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" rx="9" fill="{human[kind]}" stroke="#222" stroke-width="1.3"/>')
            icon = {"userTask": "person", "serviceTask": "automated", "businessRuleTask": "rule"}.get(kind, "")
            out.append(f'<text x="{x + 7:.0f}" y="{y + 13:.0f}" font-size="9" fill="#666">{icon}</text>')
            lines = wrap(label, 21)
            for i, ln in enumerate(lines):
                out.append(f'<text x="{cx:.0f}" y="{cy + 4 + (i - (len(lines) - 1) / 2) * 13:.0f}" font-size="11" '
                           f'text-anchor="middle" fill="#111">{escape(ln)}</text>')
    lg = H - 22
    out.append(f'<g font-size="10.5" fill="#333"><rect x="20" y="{lg - 10}" width="14" height="10" fill="#fff4df" stroke="#222"/>'
               f'<text x="40" y="{lg}">person</text><rect x="100" y="{lg - 10}" width="14" height="10" fill="#e6f0fc" stroke="#222"/>'
               f'<text x="120" y="{lg}">automated</text><rect x="200" y="{lg - 10}" width="14" height="10" fill="#e8f6ee" stroke="#222"/>'
               f'<text x="220" y="{lg}">business rule</text></g>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    docs = here.parent / "docs"
    for model, pid, name, title in [(CURRENT, "rma_current", "RMA intake, current state", "RMA intake: current state (manual)"),
                                    (FUTURE, "rma_future", "RMA intake, future state", "RMA intake: future state (AI agent, automation and people)")]:
        (here / f"{pid.split('_')[1]}_state.bpmn").write_text(to_bpmn(model, pid, name))
        (docs / f"{pid.split('_')[1]}_state.svg").write_text(to_svg(model, title))
    print("wrote bpmn/current_state.bpmn, bpmn/future_state.bpmn, docs/current_state.svg, docs/future_state.svg")
