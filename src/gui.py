import math
import random
import tkinter as tk
from tkinter import font as tkfont

# theme
BG = "#0d0f14"
SIDEBAR = "#13161e"
PANEL = "#1a1e29"
PANEL_HI = "#232a3a"
BORDER = "#2a3142"
GRID = "#1f2430"
SHADOW = "#07080b"
TEXT = "#e6e9ef"
MUTED = "#8a93a6"
ACCENT = "#7c6cff"
ACCENT_HI = "#9387ff"

STATUS_COLORS = {
    "idle": "#64748b",
    "working": "#f59e0b",
    "done": "#22c55e",
    "error": "#ef4444",
}

ROLES = ["Researcher", "Planner", "Coder", "Reviewer", "Tester",
         "Writer", "Critic", "Summarizer", "Analyst"]


def pick_family(root):
    available = set(tkfont.families(root))
    for family in ("Inter", "SF Pro Text", "Segoe UI", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans"):
        if family in available:
            return family
    return "Helvetica"


# blend two hex colors, t=0 gives c1 and t=1 gives c2
def mix(c1, c2, t):
    t = min(1.0, max(0.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def rounded_rect(canvas, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, **kw)


class AgentNode:
    def __init__(self, node_id, name, role, parent=None, model="llama3.2"):
        self.id = node_id
        self.name = name
        self.role = role
        self.parent = parent
        self.model = model
        self.children = []
        self.status = "idle"
        self.depth = parent.depth + 1 if parent else 0
        # new nodes start on top of their parent and fly out to their slot
        self.x, self.y = (parent.x, parent.y) if parent else (0.0, 0.0)
        self.tx, self.ty = self.x, self.y
        self.scale, self.vscale = 0.0, 0.0


# canvas that lays out a root agent with its sub-agent swarm radiating around it
class SwarmCanvas(tk.Canvas):
    CARD_W, CARD_H = 172, 60
    ROOT_R = 50

    def __init__(self, master, family, on_select=None, on_change=None):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0)
        self.family = family
        self.on_select = on_select
        self.on_change = on_change
        self.nodes = {}
        self.root_node = None
        self.selected = None
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self.phase = 0.0
        self._next_id = 1
        self._press = None
        self._view_target = None
        self._dirty = True
        self._grid_dirty = True

        self.bind("<Configure>", lambda e: self._mark_view())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double)
        self.bind("<MouseWheel>", lambda e: self._zoom_at(e.x, e.y, 1.1 if e.delta > 0 else 1 / 1.1))
        self.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.1))
        self.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.1))
        self._tick()

    # ---- public api ----

    def create_root(self, name="orchestrator", model="llama3.2"):
        self.clear()
        node = self._add(name, "Root agent", None, model)
        self.root_node = node
        self.select(node)
        self._changed()
        return node

    def spawn(self, parent=None, name=None, role=None, model="llama3.2"):
        parent = parent or self.selected or self.root_node
        if parent is None:
            parent = self.create_root(model=model)
        role = role or random.choice(ROLES)
        name = name or f"{role.lower()}-{self._next_id:02d}"
        node = self._add(name, role, parent, model)
        self.layout()
        self._changed()
        return node

    def remove(self, node):
        if node is None:
            return
        if node.parent is None:
            self.clear()
            self._changed()
            return

        def drop(n):
            for child in n.children:
                drop(child)
            self.nodes.pop(n.id, None)

        drop(node)
        node.parent.children.remove(node)
        if self.selected and self.selected.id not in self.nodes:
            self.select(None)
        self.layout()
        self._changed()

    def set_status(self, node, status):
        node.status = status
        self._changed()

    def clear(self):
        self.nodes = {}
        self.root_node = None
        self.select(None)

    def select(self, node):
        self.selected = node
        self._dirty = True
        if self.on_select:
            self.on_select(node)

    # glide the view so every agent fits on screen
    def fit(self):
        w, h = self.winfo_width(), self.winfo_height()
        if not self.nodes or w < 50:
            return
        xs = [n.tx for n in self.nodes.values()]
        ys = [n.ty for n in self.nodes.values()]
        pad_x, pad_y = self.CARD_W / 2 + 60, self.ROOT_R + 60
        x0, x1 = min(xs) - pad_x, max(xs) + pad_x
        y0, y1 = min(ys) - pad_y, max(ys) + pad_y
        z = max(0.35, min(1.0, w / (x1 - x0), h / (y1 - y0)))
        self._view_target = (z, -(x0 + x1) / 2 * z, -(y0 + y1) / 2 * z)

    def _offscreen(self):
        w, h = self.winfo_width(), self.winfo_height()
        for n in self.nodes.values():
            sx, sy = self._to_screen(n.tx, n.ty)
            if not (self.CARD_W / 2 * self.zoom < sx < w - self.CARD_W / 2 * self.zoom
                    and self.CARD_H * self.zoom < sy < h - self.CARD_H * self.zoom):
                return True
        return False

    # ---- layout ----

    def _add(self, name, role, parent, model):
        node = AgentNode(self._next_id, name, role, parent, model)
        self._next_id += 1
        self.nodes[node.id] = node
        if parent:
            parent.children.append(node)
        return node

    def layout(self):
        if not self.root_node:
            return
        self.root_node.tx = self.root_node.ty = 0.0
        kids = self.root_node.children
        n = len(kids)
        if not n:
            return
        radius = max(240, n * (self.CARD_W + 30) / (2 * math.pi))
        for i, kid in enumerate(kids):
            self._place(kid, -math.pi / 2 + 2 * math.pi * i / n, 2 * math.pi / n, radius)
        if self._offscreen():
            self.fit()

    # place a node on its ring, then fan its children out inside its wedge
    def _place(self, node, angle, wedge, radius):
        node.tx = math.cos(angle) * radius
        node.ty = math.sin(angle) * radius
        n = len(node.children)
        if not n:
            return
        gap = self.CARD_W + 28
        r2 = max(radius + 200, n * gap / wedge)
        span = min(wedge, n * gap / r2)
        for i, kid in enumerate(node.children):
            self._place(kid, angle - span / 2 + span * (i + 0.5) / n, span / n, r2)

    # ---- animation ----

    def _changed(self):
        self._dirty = True
        if self.on_change:
            self.on_change()

    def _mark_view(self):
        self._grid_dirty = True
        self._dirty = True

    def _tick(self):
        self.phase += 0.016
        moving = False
        for n in self.nodes.values():
            dx, dy = n.tx - n.x, n.ty - n.y
            if abs(dx) > 0.3 or abs(dy) > 0.3:
                n.x += dx * 0.16
                n.y += dy * 0.16
                moving = True
            else:
                n.x, n.y = n.tx, n.ty
            # springy pop-in
            if abs(1 - n.scale) > 0.002 or abs(n.vscale) > 0.002:
                n.vscale = (n.vscale + (1 - n.scale) * 0.22) * 0.72
                n.scale += n.vscale
                moving = True
            else:
                n.scale, n.vscale = 1.0, 0.0
        working = any(n.status == "working" for n in self.nodes.values())

        if self._view_target:
            z, px, py = self._view_target
            if abs(z - self.zoom) < 0.002 and abs(px - self.pan_x) < 0.5 and abs(py - self.pan_y) < 0.5:
                self.zoom, self.pan_x, self.pan_y = z, px, py
                self._view_target = None
            else:
                self.zoom += (z - self.zoom) * 0.12
                self.pan_x += (px - self.pan_x) * 0.12
                self.pan_y += (py - self.pan_y) * 0.12
            self._mark_view()

        if self._grid_dirty:
            self._draw_grid()
        if moving or working or self._dirty:
            self._draw_scene()
            self._dirty = False
        self.after(16, self._tick)

    # ---- drawing ----

    def _to_screen(self, x, y):
        return (self.winfo_width() / 2 + self.pan_x + x * self.zoom,
                self.winfo_height() / 2 + self.pan_y + y * self.zoom)

    def _font(self, px, weight="normal"):
        return (self.family, -max(1, int(round(px))), weight)

    def _draw_grid(self):
        self.delete("grid")
        w, h = self.winfo_width(), self.winfo_height()
        step = 32 * self.zoom
        while step < 16:
            step *= 2
        ox = (w / 2 + self.pan_x) % step
        y = (h / 2 + self.pan_y) % step
        while y < h:
            x = ox
            while x < w:
                self.create_rectangle(x, y, x + 2, y + 2, fill=GRID, outline="", tags="grid")
                x += step
            y += step
        self.tag_lower("grid")
        self._grid_dirty = False

    def _draw_scene(self):
        self.delete("scene")
        if not self.root_node:
            self._draw_empty()
            return
        for n in self.nodes.values():
            if n.parent:
                self._draw_edge(n)
        for n in sorted(self.nodes.values(), key=lambda n: -n.depth):
            self._draw_node(n)

    def _draw_empty(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.create_text(w / 2, h / 2 - 14, text="No agents on the canvas",
                         fill=TEXT, font=self._font(20, "bold"), tags="scene")
        self.create_text(w / 2, h / 2 + 16, text="Create a root agent from the sidebar to begin",
                         fill=MUTED, font=self._font(13), tags="scene")

    def _draw_edge(self, n):
        if n.scale < 0.05:
            return
        x0, y0 = self._to_screen(n.parent.x, n.parent.y)
        x1, y1 = self._to_screen(n.x, n.y)
        # bend the line slightly so the swarm reads as organic rather than spokes
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        cx, cy = mx - (y1 - y0) * 0.12, my + (x1 - x0) * 0.12
        kw = dict(width=max(1, 2 * self.zoom), smooth=True, capstyle="round", tags="scene")
        if n.status == "working":
            kw.update(fill=ACCENT, dash=(6, 6), dashoffset=int(-self.phase * 60) % 12)
        elif n.status == "idle":
            kw.update(fill=BORDER)
        else:
            kw.update(fill=mix(BORDER, STATUS_COLORS[n.status], 0.4))
        self.create_line(x0, y0, cx, cy, x1, y1, **kw)

    def _draw_node(self, n):
        s = max(n.scale, 0) * self.zoom
        if s < 0.02:
            return
        sx, sy = self._to_screen(n.x, n.y)
        if n.parent is None:
            self._draw_root(n, sx, sy, s)
        else:
            self._draw_card(n, sx, sy, s)

    def _draw_root(self, n, sx, sy, s):
        color = ACCENT if n.status == "idle" else STATUS_COLORS[n.status]
        r = self.ROOT_R * s
        # soft glow halo
        for i, t in ((3, 0.93), (2, 0.88), (1, 0.8)):
            rr = r + i * 9 * s
            self.create_oval(sx - rr, sy - rr, sx + rr, sy + rr,
                             fill=mix(color, BG, t), outline="", tags="scene")
        if n.status == "working":
            p = (self.phase * 0.9) % 1
            rr = r + 8 * s + p * 40 * s
            self.create_oval(sx - rr, sy - rr, sx + rr, sy + rr,
                             outline=mix(color, BG, p), width=2, tags="scene")
        if n is self.selected:
            rr = r + 5 * s
            self.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, outline=TEXT, width=2, tags="scene")
        self.create_oval(sx - r, sy - r, sx + r, sy + r,
                         fill=mix(color, BG, 0.62), outline=color, width=2, tags="scene")
        if s < 0.45:
            return
        self.create_text(sx, sy - 10 * s, text="ROOT", fill=mix(color, TEXT, 0.5),
                         font=self._font(10 * s, "bold"), tags="scene")
        self.create_text(sx, sy + 8 * s, text=n.name[:14], fill=TEXT,
                         font=self._font(13 * s, "bold"), tags="scene")

    def _draw_card(self, n, sx, sy, s):
        sc = STATUS_COLORS[n.status]
        w, h = self.CARD_W * s, self.CARD_H * s
        x0, y0, x1, y1 = sx - w / 2, sy - h / 2, sx + w / 2, sy + h / 2
        rad = 14 * s
        if n.status == "working":
            p = (self.phase * 1.2) % 1
            pad = p * 14 * s
            rounded_rect(self, x0 - pad, y0 - pad, x1 + pad, y1 + pad, rad + pad,
                         fill="", outline=mix(sc, BG, p), width=2, tags="scene")
        rounded_rect(self, x0, y0 + 6 * s, x1, y1 + 6 * s, rad, fill=SHADOW, outline="", tags="scene")
        selected = n is self.selected
        rounded_rect(self, x0, y0, x1, y1, rad,
                     fill=PANEL_HI if selected else PANEL,
                     outline=ACCENT if selected else BORDER,
                     width=2 if selected else 1, tags="scene")
        # avatar
        ax, ar = x0 + 24 * s, 13 * s
        self.create_oval(ax - ar, sy - ar, ax + ar, sy + ar,
                         fill=mix(sc, BG, 0.75), outline=sc, width=max(1, 1.5 * s), tags="scene")
        if s < 0.45:
            return
        self.create_text(ax, sy, text=n.role[0], fill=TEXT, font=self._font(12 * s, "bold"), tags="scene")
        self.create_text(x0 + 46 * s, sy - 9 * s, text=n.name[:16], anchor="w", fill=TEXT,
                         font=self._font(13 * s, "bold"), tags="scene")
        self.create_text(x0 + 46 * s, sy + 10 * s, text=f"{n.role}  ·  {n.status}", anchor="w",
                         fill=sc if n.status != "idle" else MUTED, font=self._font(11 * s), tags="scene")

    # ---- interaction ----

    def node_at(self, x, y):
        for n in sorted(self.nodes.values(), key=lambda n: n.depth):
            sx, sy = self._to_screen(n.x, n.y)
            if n.parent is None:
                if math.hypot(x - sx, y - sy) <= self.ROOT_R * self.zoom:
                    return n
            elif abs(x - sx) <= self.CARD_W * self.zoom / 2 and abs(y - sy) <= self.CARD_H * self.zoom / 2:
                return n
        return None

    def _on_press(self, e):
        self.focus_set()
        node = self.node_at(e.x, e.y)
        if node:
            self.select(node)
            self._press = None
        else:
            self._view_target = None
            self._press = (e.x, e.y, self.pan_x, self.pan_y, False)
            self.config(cursor="fleur")

    def _on_drag(self, e):
        if not self._press:
            return
        x, y, px, py, _ = self._press
        if abs(e.x - x) + abs(e.y - y) > 3:
            self._press = (x, y, px, py, True)
        self.pan_x = px + e.x - x
        self.pan_y = py + e.y - y
        self._mark_view()

    def _on_release(self, e):
        if self._press and not self._press[4]:
            self.select(None)
        self._press = None
        self.config(cursor="")

    def _on_double(self, e):
        node = self.node_at(e.x, e.y)
        if node:
            self.spawn(parent=node, model=node.model)
        else:
            self.fit()

    def _zoom_at(self, x, y, factor):
        self._view_target = None
        new = min(2.5, max(0.35, self.zoom * factor))
        f = new / self.zoom
        # keep the world point under the cursor fixed
        cx = self.winfo_width() / 2 + self.pan_x
        cy = self.winfo_height() / 2 + self.pan_y
        self.pan_x += (x - cx) * (1 - f)
        self.pan_y += (y - cy) * (1 - f)
        self.zoom = new
        self._mark_view()


class SideButton(tk.Label):
    def __init__(self, master, text, command, family, primary=False):
        self.base = ACCENT if primary else PANEL
        self.hover = ACCENT_HI if primary else PANEL_HI
        super().__init__(master, text=text, bg=self.base, fg="#ffffff" if primary else TEXT,
                         font=(family, -13, "bold" if primary else "normal"),
                         anchor="w", padx=14, pady=9, cursor="hand2")
        self.bind("<Enter>", lambda e: self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.base))
        self.bind("<Button-1>", lambda e: command())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("local-swarm")
        self.geometry("1440x900")
        self.minsize(1040, 660)
        self.configure(bg=BG)
        self.family = pick_family(self)
        self._run_token = None
        self._list_nodes = []

        sidebar = tk.Frame(self, bg=SIDEBAR, width=290)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(self, bg=BORDER, width=1).pack(side="left", fill="y")
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        self._build_topbar(main)
        self.canvas = SwarmCanvas(main, self.family, on_select=self._on_select, on_change=self._refresh)
        self.canvas.pack(fill="both", expand=True)
        self._build_sidebar(sidebar)

        self.bind("<Delete>", self._on_delete)
        self.bind("<Escape>", lambda e: self.canvas.select(None))

        self.canvas.create_root(model=self.model_var.get())

    def _font(self, px, weight="normal"):
        return (self.family, -px, weight)

    # ---- layout ----

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=BG, height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        left = tk.Frame(bar, bg=BG)
        left.pack(side="left", padx=24)
        tk.Label(left, text="Swarm canvas", bg=BG, fg=TEXT, font=self._font(16, "bold")).pack(side="left", pady=18)
        self.stats = tk.Label(left, text="", bg=BG, fg=MUTED, font=self._font(12))
        self.stats.pack(side="left", padx=16)
        tk.Label(bar, text="Drag to pan  ·  Scroll to zoom  ·  Double-click an agent to spawn under it",
                 bg=BG, fg=MUTED, font=self._font(12)).pack(side="right", padx=24)
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")

    def _build_sidebar(self, sb):
        header = tk.Frame(sb, bg=SIDEBAR)
        header.pack(fill="x", padx=20, pady=(22, 6))
        logo = tk.Canvas(header, width=38, height=38, bg=SIDEBAR, highlightthickness=0)
        logo.pack(side="left")
        rounded_rect(logo, 1, 1, 37, 37, 10, fill=ACCENT, outline="")
        for cx, cy, r in ((19, 12, 4), (11, 25, 3.5), (27, 25, 3.5)):
            logo.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#ffffff", outline="")
        titles = tk.Frame(header, bg=SIDEBAR)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="local-swarm", bg=SIDEBAR, fg=TEXT, font=self._font(17, "bold")).pack(anchor="w")
        tk.Label(titles, text="agent orchestrator", bg=SIDEBAR, fg=MUTED, font=self._font(12)).pack(anchor="w")

        self._section(sb, "MODEL")
        self.model_var = tk.StringVar(value="llama3.2")
        tk.Entry(sb, textvariable=self.model_var, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=self._font(13), highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(fill="x", padx=20, ipady=8)

        self._section(sb, "ACTIONS")
        actions = tk.Frame(sb, bg=SIDEBAR)
        actions.pack(fill="x", padx=20)
        for text, cmd, primary in (
            ("＋  Spawn sub-agent", self.spawn_one, True),
            ("⚡  Spawn swarm ×5", self.spawn_swarm, False),
            ("▶  Simulate run", self.simulate_run, False),
            ("◎  New root agent", self.new_root, False),
            ("✕  Remove selected", lambda: self._on_delete(None), False),
        ):
            SideButton(actions, text, cmd, self.family, primary).pack(fill="x", pady=3)

        # inspector is packed before the list so it keeps its space at the bottom
        self._build_inspector(sb)

        self.list_title = self._section(sb, "AGENTS")
        self.listbox = tk.Listbox(sb, bg=SIDEBAR, fg=TEXT, selectbackground=PANEL_HI,
                                  selectforeground=TEXT, activestyle="none", relief="flat",
                                  highlightthickness=0, bd=0, font=self._font(13))
        self.listbox.pack(fill="both", expand=True, padx=14)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

    def _section(self, parent, text):
        label = tk.Label(parent, text=text, bg=SIDEBAR, fg=MUTED, font=self._font(11, "bold"), anchor="w")
        label.pack(fill="x", padx=20, pady=(20, 8))
        return label

    def _build_inspector(self, sb):
        card = tk.Frame(sb, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(side="bottom", fill="x", padx=20, pady=20)
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=14, pady=12)
        tk.Label(inner, text="SELECTED", bg=PANEL, fg=MUTED, font=self._font(10, "bold")).pack(anchor="w")
        self.insp_name = tk.Label(inner, bg=PANEL, fg=TEXT, font=self._font(15, "bold"), anchor="w")
        self.insp_name.pack(fill="x", pady=(4, 2))
        row = tk.Frame(inner, bg=PANEL)
        row.pack(fill="x")
        self.insp_dot = tk.Canvas(row, width=10, height=10, bg=PANEL, highlightthickness=0)
        self.insp_dot.pack(side="left", pady=2)
        self.insp_dot_item = self.insp_dot.create_oval(1, 1, 9, 9, outline="")
        self.insp_status = tk.Label(row, bg=PANEL, fg=MUTED, font=self._font(12))
        self.insp_status.pack(side="left", padx=6)
        self.insp_meta = tk.Label(inner, bg=PANEL, fg=MUTED, font=self._font(12), anchor="w", justify="left")
        self.insp_meta.pack(fill="x", pady=(4, 0))

    # ---- state sync ----

    def _refresh(self):
        c = self.canvas
        nodes = list(c.nodes.values())
        subs = [n for n in nodes if n.parent]
        working = sum(n.status == "working" for n in nodes)
        done = sum(n.status == "done" for n in subs)
        self.stats.config(text=f"{1 if c.root_node else 0} root  ·  {len(subs)} sub-agents  ·  "
                               f"{working} working  ·  {done} done")
        self.list_title.config(text=f"AGENTS  ·  {len(nodes)}")

        # depth-first order so the list reads like a tree
        ordered = []

        def walk(n):
            ordered.append(n)
            for child in n.children:
                walk(child)

        if c.root_node:
            walk(c.root_node)
        self._list_nodes = ordered
        self.listbox.delete(0, "end")
        for i, n in enumerate(ordered):
            prefix = "◆ " if n.parent is None else "    " * (n.depth - 1) + "└ "
            self.listbox.insert("end", f" {prefix}{n.name}")
            self.listbox.itemconfig(i, fg=TEXT if n.status == "idle" else STATUS_COLORS[n.status])
        self._on_select(c.selected)

    def _on_select(self, node):
        if not hasattr(self, "insp_name"):
            return
        if node is None:
            self.insp_name.config(text="Nothing selected")
            self.insp_status.config(text="click an agent on the canvas")
            self.insp_dot.itemconfig(self.insp_dot_item, fill=PANEL)
            self.insp_meta.config(text="")
            self.listbox.selection_clear(0, "end")
            return
        self.insp_name.config(text=node.name)
        self.insp_status.config(text=node.status, fg=STATUS_COLORS[node.status])
        self.insp_dot.itemconfig(self.insp_dot_item, fill=STATUS_COLORS[node.status])
        self.insp_meta.config(text=f"{node.role}  ·  {node.model}\n{len(node.children)} sub-agents")
        if node in self._list_nodes:
            i = self._list_nodes.index(node)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(i)
            self.listbox.see(i)

    def _on_list_select(self, e):
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self._list_nodes):
            self.canvas.select(self._list_nodes[sel[0]])

    def _on_delete(self, e):
        if isinstance(self.focus_get(), tk.Entry):
            return
        node = self.canvas.selected
        if node is not None and node.parent is not None:
            self.canvas.remove(node)

    # ---- actions ----

    def spawn_one(self):
        self.canvas.spawn(model=self.model_var.get())

    def spawn_swarm(self, count=5):
        parent = self.canvas.selected or self.canvas.root_node
        if parent is None:
            parent = self.canvas.create_root(model=self.model_var.get())
        for i in range(count):
            self.after(i * 90, lambda: parent.id in self.canvas.nodes
                       and self.canvas.spawn(parent=parent, model=self.model_var.get()))

    def new_root(self):
        self._run_token = None
        self.canvas.create_root(model=self.model_var.get())

    # fake a run so the canvas states can be previewed without a live model
    def simulate_run(self):
        c = self.canvas
        if not c.root_node:
            return
        token = object()
        self._run_token = token
        for n in c.nodes.values():
            n.status = "idle"
        c.set_status(c.root_node, "working")
        subs = [n for n in c.nodes.values() if n.parent]
        if not subs:
            self.after(1500, lambda: self._finish_root(token))
        for n in subs:
            start = random.randint(200, 1600) * n.depth
            duration = random.randint(1500, 4500)
            self.after(start, lambda n=n: self._step(token, n, "working"))
            self.after(start + duration,
                       lambda n=n: self._step(token, n, "error" if random.random() < 0.08 else "done"))

    def _step(self, token, node, status):
        if token is not self._run_token or node.id not in self.canvas.nodes:
            return
        self.canvas.set_status(node, status)
        subs = [n for n in self.canvas.nodes.values() if n.parent]
        if all(n.status in ("done", "error") for n in subs):
            self._finish_root(token)

    def _finish_root(self, token):
        if token is self._run_token and self.canvas.root_node:
            self.canvas.set_status(self.canvas.root_node, "done")


def run():
    App().mainloop()


if __name__ == "__main__":
    run()
