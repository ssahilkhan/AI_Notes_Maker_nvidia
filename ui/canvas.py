"""Interactive Knowledge Canvas (Phase 4) — a partial Mini-Miro.

The canvas is drawn inside an iframe via ``st.components.v1.html``. All
interactions (drag, zoom, pan, double-click collapse, delete) happen there.
Edits are delivered to the backend through a tiny hidden ``kn_draft`` text
input that the same-origin srcdoc iframe writes to (native-setter + input
event). Python parses the draft, persists to ``knowledge_nodes`` and clears it.
"""

import html as htm
import json

import streamlit as st
import streamlit.components.v1 as components

import core.db as db

DRAFT_KEY = "kn_draft"
CANVAS_H = 560
CARD_W = 232
CARD_H = 88


def _parse_draft(draft):
    try:
        return json.loads((draft or "").strip() or "null")
    except json.JSONDecodeError:
        return None


def _apply_draft(conv_id, data):
    """Persist canvas-originated edits. ``data`` is the parsed draft JSON."""
    if not data or not isinstance(data, dict):
        return
    for nid, pos in (data.get("moves") or {}).items():
        try:
            db.update_knowledge_node_position(int(nid), float(pos[0]), float(pos[1]))
        except (ValueError, TypeError, IndexError):
            pass
    for nid, collapsed in (data.get("collapse") or {}).items():
        try:
            db.update_knowledge_node(int(nid), collapsed=1 if collapsed else 0)
        except ValueError:
            pass
    for nid in data.get("del") or []:
        try:
            db.delete_knowledge_node(int(nid))
        except ValueError:
            pass


def _process_draft(conv_id):
    """Read + clear the hidden bridge widget, then persist canvas edits."""
    if conv_id is None:
        st.session_state.pop(DRAFT_KEY, None)
        return
    draft = (st.session_state.pop(DRAFT_KEY, "") or "").strip()
    if not draft:
        return
    data = _parse_draft(draft)
    _apply_draft(conv_id, data)
    ask = (data or {}).get("ask") or {}
    if ask:
        nid = next(iter(ask), None)
        node = db.get_knowledge_node(nid) if nid else None
        if node:
            st.session_state["chat_input_main"] = (
                f"Explain “{node['title']}” in the context of this session "
                f"(following my knowledge card)."
            )
            st.session_state.pop("canvas_mode", None)
            st.session_state["jump_to"] = None
            st.rerun()


def _esc(text):
    return htm.escape(text or "", quote=True)


def _card_html(n, nodes_by_id):
    title = _esc(n["title"])
    summary = _esc((n["summary"] or "")[:160])
    lines = ("Overview",) if n["parent_id"] in nodes_by_id else ()
    extra = ''.join(f'<span class="kn-line">.{ln}</span>' for ln in lines)
    return (
        f'<div class="kn-card{" flat" if n["collapsed"] else ""}" data-id="{n["id"]}" '
        f'data-x="{n["x"]:.0f}" data-y="{n["y"]:.0f}">'
        f'<div class="kn-title">{title}</div>'
        f'<div class="kn-sum">{summary}</div>'
        f'<div class="kn-meta">{extra}<span class="kn-count">#{n["id"]}</span></div>'
        f'<div class="kn-actions">'
        f'<button class="kn-act" data-a="ask">💬 Ask</button>'
        f'<button class="kn-act" data-a="collapse">{"🗎 Collapse" if not n["collapsed"] else "🗀 Expand"}</button>'
        f'<button class="kn-act danger" data-a="del">Delete</button>'
        f'</div></div>'
    )


def _canvas_html(nodes):
    if not nodes:
        return ""
    parents = [(n["parent_id"], n["id"]) for n in nodes if n["parent_id"]]
    card_html = "".join(_card_html(n, {k["id"] for k in nodes}) for n in nodes)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ width:100%; height:100%; overflow:hidden; background:#f1f4fb; font-family:"Segoe UI",Roboto,Arial,sans-serif; }}
#wrap {{ position:relative; width:100%; height:100%; overflow:hidden; }}
#scene {{ position:absolute; left:0; top:0; transform-origin:0 0; }}
#wires {{ position:absolute; left:0; top:0; pointer-events:none; overflow:visible; }}
#wires line {{ stroke:#b7c4e3; stroke-width:1.5; }}
#wires circle {{ fill:#b7c4e3; }}
.kn-card {{ position:absolute; width:{CARD_W}px; background:#fff; border:1px solid #dbe3f4;
            border-radius:12px; box-shadow:0 1px 3px rgba(30,41,59,.08); cursor:grab;
            padding:10px 12px; user-select:none; }}
.kn-card.flat {{ height:44px; overflow:hidden; border-style:dashed; background:#fbfdff; }}
.kn-card.selected {{ border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.18); }}
.kn-card .kn-title {{ font-size:13px; font-weight:600; color:#1f2430; line-height:1.25; }}
.kn-card .kn-sum {{ margin-top:4px; font-size:11px; color:#64748b; line-height:1.4;
                    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
.kn-card.flat .kn-sum {{ display:none; }}
.kn-card .kn-meta {{ margin-top:5px; font-size:10px; color:#9aa7bd; display:flex; gap:8px; }}
.kn-card .kn-count {{ margin-left:auto; }}
.kn-card .kn-actions {{ display:none; gap:6px; margin-top:8px; }}
.kn-card.selected .kn-actions {{ display:flex; }}
.kn-act {{ border:1px solid #cbd5e1; background:#f8fafc; border-radius:8px; font-size:11px;
            padding:3px 8px; cursor:pointer; color:#334155; }}
.kn-act:hover {{ background:#eef2ff; }}
.kn-act.danger:hover {{ background:#fee2e2; color:#b91c1c; border-color:#fecaca; }}
#toolbar {{ position:absolute; bottom:14px; left:14px; right:14px; display:flex; gap:8px;
             align-items:center; background:#fff; border:1px solid #dbe3f4; border-radius:12px;
             padding:6px 10px; box-shadow:0 2px 8px rgba(30,41,59,.08); font-size:12px; color:#475569; }}
#toolbar button {{ border:1px solid #dbe3f4; background:#fff; border-radius:8px; padding:4px 10px;
                    cursor:pointer; font-size:12px; color:#2563eb; }}
#toolbar button:hover {{ background:#eef2ff; }}
#zoomPct {{ min-width:44px; text-align:center; }}
#hint {{ margin-right:auto; color:#94a3b8; }}
</style></head><body>
<div id="wrap">
  <div id="scene">
    <svg id="wires" width="20000" height="20000"></svg>
    {card_html}
  </div>
  <div id="toolbar">
    <span id="hint">drag cards · ctrl+wheel zoom · double-click collapse</span>
    <button id="zminus">−</button><span id="zoomPct">100%</span><button id="zplus">+</button>
    <button id="zfit">Fit view</button>
  </div>
</div>
<script>
(function(){{
  const PARENTS = {json.dumps(parents)};
  const state = {{ k:1, tx:0, ty:0, drag:null, pan:null, sel:null }};
  const payload = {{ t:0, moves:{{}}, collapse:{{}}, del:[] }};
  const scene = document.getElementById('scene');
  const wires = document.getElementById('wires');
  const zoomPct = document.getElementById('zoomPct');
  let draftInput = null;
  (function findInput(){{
    try {{
      const holder = window.parent.document.querySelector('[class*="st-key-{DRAFT_KEY}"]');
      draftInput = holder && holder.querySelector('input');
    }} catch(e) {{ draftInput = null; }}
    if (!draftInput) setTimeout(findInput, 400);
  }})();

  function notify() {{
    if (!draftInput) return;
    try {{
      payload.t = Date.now();
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(draftInput, JSON.stringify(payload));
      draftInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }} catch(e) {{ console.error('kn notify', e); }}
  }}

  function card(id) {{ return document.querySelector('.kn-card[data-id="'+id+'"]'); }}
  function pos(id) {{ const c = card(id); return {{ x:+c.dataset.x, y:+c.dataset.y }}; }}
  function drawWires() {{
    let d = '', markers = '';
    for (const [p, id] of PARENTS) {{
      if (!card(p) || !card(id)) continue;
      const a = pos(p), b = pos(id);
      const ax = a.x + CARD_W/2, ay = a.y + CARD_H/2, bx = b.x + CARD_W/2, by = b.y + CARD_H/2;
      d += 'M ' + ax + ' ' + ay + ' L ' + bx + ' ' + by + ' ';
      markers += '<circle cx="'+bx+'" cy="'+by+'" r="3">';
    }}
    wires.innerHTML = d ? d + markers : '';
  }}

  function applyTransform() {{
    scene.style.transform = 'translate(' + state.tx + 'px,' + state.ty + 'px) scale(' + state.k + ')';
    zoomPct.textContent = Math.round(state.k * 100) + '%';
  }}

  function zoomAt(cx, cy, nk) {{
    const wk = nk / state.k;
    state.tx = cx - (cx - state.tx) * wk;
    state.ty = cy - (cy - state.ty) * wk;
    state.k = nk;
    applyTransform();
  }}

  document.querySelectorAll('.kn-card').forEach(card => {{
    card.addEventListener('pointerdown', function (e) {{
      if (e.target.closest('.kn-act')) return;
      card.setPointerCapture(e.pointerId);
      state.sel = card.dataset.id;
      state.drag = {{ id:card.dataset.id, sx:e.clientX, sy:e.clientY,
                    ox:+card.dataset.x, oy:+card.dataset.y }};
      e.preventDefault();
    }});
    card.addEventListener('dblclick', function () {{
      const flat = card.classList.toggle('flat');
      payload.collapse[card.dataset.id] = flat;
      notify();
    }});
    card.addEventListener('click', function () {{
      document.querySelectorAll('.kn-card.selected').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
    }});
  }});

  document.addEventListener('pointermove', function (e) {{
    if (state.drag) {{
      const d = state.drag, c = card(d.id);
      const nx = d.ox + (e.clientX - d.sx) / state.k;
      const ny = d.oy + (e.clientY - d.sy) / state.k;
      c.dataset.x = nx; c.dataset.y = ny;
      c.style.left = nx + 'px'; c.style.top = ny + 'px';
      drawWires();
    }} else if (state.pan) {{
      state.tx = state.pan.ox + (e.clientX - state.pan.sx);
      state.ty = state.pan.oy + (e.clientY - state.pan.sy);
      applyTransform();
    }}
  }});

  document.addEventListener('pointerup', function () {{
    if (state.drag) {{
      const c = card(state.drag.id);
      payload.moves[state.drag.id] = [Math.round(+c.dataset.x), Math.round(+c.dataset.y)];
      notify();
    }}
    state.drag = null; state.pan = null;
  }});

  document.addEventListener('click', function (e) {{
    if (e.target.closest('.kn-card')) return;
    document.querySelectorAll('.kn-card.selected').forEach(c => c.classList.remove('selected'));
  }});

  document.addEventListener('click', function (e) {{
    const act = e.target.closest('.kn-act');
    if (!act) return;
    const card = act.closest('.kn-card');
    if (act.dataset.a === 'del') {{
      payload.del.push(card.dataset.id);
      card.remove(); drawWires(); notify();
    }} else if (act.dataset.a === 'ask') {{
      payload.ask = payload.ask || {{}};
      payload.ask[card.dataset.id] = true;
      notify();
    }} else {{
      const flat = card.classList.toggle('flat');
      payload.collapse[card.dataset.id] = flat;
      notify();
    }}
  }});

  document.getElementById('wrap').addEventListener('pointerdown', function (e) {{
    if (e.target.closest('.kn-card') || e.target.closest('#toolbar')) return;
    state.pan = {{ sx:e.clientX, sy:e.clientY, ox:state.tx, oy:state.ty }};
  }});

  document.getElementById('wires').setPointerCapture;

  document.getElementById('zplus').addEventListener('click', () => zoomAt(innerWidth/2, innerHeight/2, Math.min(2.5, state.k * 1.2)));
  document.getElementById('zminus').addEventListener('click', () => zoomAt(innerWidth/2, innerHeight/2, Math.max(0.3, state.k / 1.2)));
  document.getElementById('zfit').addEventListener('click', function () {{
    const cards = document.querySelectorAll('.kn-card');
    if (!cards.length) return;
    let minX=1e9, minY=1e9, maxX=-1e9, maxY=-1e9;
    cards.forEach(c => {{
      const x = +c.dataset.x, y = +c.dataset.y;
      minX=Math.min(minX,x); minY=Math.min(minY,y);
      maxX=Math.max(maxX,x+CARD_W); maxY=Math.max(maxY,y+CARD_H);
    }});
    const k = Math.min(1, Math.max(0.3, (innerWidth-70)/Math.max(100, maxX-minX), (innerHeight-120)/Math.max(100, maxY-minY)));
    state.k = k; state.tx = 35 - minX*k; state.ty = 70 - minY*k;
    applyTransform();
  }});

  document.getElementById('wrap').addEventListener('wheel', function (e) {{
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const rect = document.getElementById('wrap').getBoundingClientRect();
    zoomAt(e.clientX - rect.left, e.clientY - rect.top,
           Math.min(2.5, Math.max(0.3, state.k * (e.deltaY < 0 ? 1.15 : 0.87))));
  }}, {{ passive: false }});

  applyTransform();
  drawWires();
}})();
</script></body></html>"""


def _mode_buttons():
    rows = st.columns(3, gap="small")
    if rows[0].button("", icon=":material/view_column:", help="Split view (chat + map)", key="kn_split"):
        st.session_state["canvas_mode"] = "split"
        st.rerun()
    if rows[1].button("", icon=":material/space_dashboard:", help="Full-screen map", key="kn_full"):
        st.session_state["canvas_mode"] = "full"
        st.rerun()
    if rows[2].button("", icon=":material/close:", help="Close the knowledge map", key="kn_off"):
        st.session_state.pop("canvas_mode", None)
        st.rerun()


def render_canvas(conv_id):
    _process_draft(conv_id)
    if conv_id is None:
        st.info("Open a study session first, then browse its knowledge cards here.")
        return

    nodes = db.get_conversation_nodes(conv_id)

    head = st.container(border=True)
    with head:
        hcols = st.columns([1.6, 4, 3], vertical_alignment="bottom")
        hcols[0].markdown("**🗺 Knowledge map**")
        hcols[0].caption(
            f"{len(nodes)} card{'s' if len(nodes) != 1 else ''} · cards persist per session"
        )
        with hcols[1]:
            new_title = st.text_input(
                "New knowledge card",
                label_visibility="collapsed",
                placeholder="Card title, e.g. Attention Mechanism",
                key="kn_new",
            )
        if hcols[2].button("＋ Add card", type="primary", key="kn_add"):
            title = (new_title or "").strip()
            if title:
                x, y = db.next_node_position(conv_id)
                db.create_knowledge_node(conv_id, title, summary="", x=x, y=y)
                st.rerun()
            else:
                st.toast("Enter a card title first.")
        st.caption("Chips (＋ Concept) under AI answers and each note section's "
                   "📌 button also create cards.")
        _mode_buttons()

    if not nodes:
        st.info("No knowledge cards yet — click a **＋ Concept** chip under an AI answer, "
                "use the 📌 button on a note section, or type a title above.")
        return

    st.text_input("", label_visibility="collapsed", key=DRAFT_KEY, value="", placeholder="")
    components.html(_canvas_html(nodes), height=CANVAS_H, scrolling=False)