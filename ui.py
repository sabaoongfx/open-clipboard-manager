"""Main window for Open Clipboard Manager, styled after Open Task Manager (Windows 11 Task Manager look).

A left navigation rail, a rounded-look content card with a title/toolbar header, a flat table
with a muted header row, and light/dark colours that follow the operating system.
"""
import math
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from platform_base import APP_NAME, APP_VERSION

# Colours mirror the CSS variables in Open Task Manager's App.css.
LIGHT = {
    "bg": "#f3f3f3", "elevated": "#ffffff", "header": "#f9f9f9", "border": "#e1e1e1",
    "text": "#1b1b1b", "muted": "#6b6b6b", "accent": "#0078d4", "on_accent": "#ffffff",
    "danger": "#c42b1c", "danger_bg": "#fdf3f2", "hover": "#f6f6f6", "selected": "#e5f1fb",
    "nav_active": "#e6e6e6", "nav_hover": "#ebebeb", "disabled": "#a8a8a8", "input": "#ffffff",
    "scroll": "#8a8a8a",
}
DARK = {
    "bg": "#202020", "elevated": "#2b2b2b", "header": "#262626", "border": "#3a3a3a",
    "text": "#f2f2f2", "muted": "#a0a0a0", "accent": "#4cc2ff", "on_accent": "#000000",
    "danger": "#ff99a4", "danger_bg": "#3b1f1f", "hover": "#313131", "selected": "#24384a",
    "nav_active": "#3a3a3a", "nav_hover": "#2d2d2d", "disabled": "#6d6d6d", "input": "#323232",
    "scroll": "#6a6a6a",
}

_icons = {}

ICON_SIZE = 96  # icons are drawn at this size, then scaled down for smooth edges
STROKE = 8


def _menu(d, c):
    for y in (26, 48, 70):
        d.line((14, y, 82, y), fill=c, width=STROKE)


def _history(d, c):
    d.ellipse((12, 12, 84, 84), outline=c, width=STROKE)
    d.line([(48, 28), (48, 50), (64, 58)], fill=c, width=STROKE, joint="curve")


def _image(d, c):
    d.rounded_rectangle((12, 18, 84, 78), 8, outline=c, width=STROKE)
    d.ellipse((58, 28, 72, 42), fill=c)
    d.line([(18, 70), (40, 46), (54, 62), (64, 54), (80, 70)], fill=c, width=STROKE - 2, joint="curve")


def _text(d, c):
    d.line((16, 24, 80, 24), fill=c, width=STROKE)
    d.line((16, 48, 80, 48), fill=c, width=STROKE)
    d.line((16, 72, 56, 72), fill=c, width=STROKE)


def _actions(d, c):
    d.polygon([(54, 6), (20, 54), (44, 54), (38, 90), (76, 40), (52, 40)], fill=c)


def _settings(d, c):
    d.ellipse((28, 28, 68, 68), outline=c, width=STROKE)
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        d.line((48 + 32 * math.cos(a), 48 + 32 * math.sin(a), 48 + 44 * math.cos(a), 48 + 44 * math.sin(a)),
               fill=c, width=11)
    d.ellipse((20, 20, 76, 76), outline=c, width=STROKE - 2)


def _search(d, c):
    d.ellipse((12, 12, 62, 62), outline=c, width=STROKE)
    d.line((56, 56, 84, 84), fill=c, width=STROKE + 2)


def _pause(d, c):
    d.rectangle((24, 16, 40, 80), fill=c)
    d.rectangle((56, 16, 72, 80), fill=c)


def _play(d, c):
    d.polygon([(26, 14), (26, 82), (80, 48)], fill=c)


def _trash(d, c):
    d.line((14, 28, 82, 28), fill=c, width=STROKE)
    d.line([(24, 32), (30, 84), (66, 84), (72, 32)], fill=c, width=STROKE, joint="curve")
    d.line([(38, 28), (38, 14), (58, 14), (58, 28)], fill=c, width=STROKE - 2, joint="curve")


def _clear(d, c):
    d.ellipse((12, 12, 84, 84), outline=c, width=STROKE)
    d.line((26, 70, 70, 26), fill=c, width=STROKE)


def _edit(d, c):
    d.line((26, 70, 70, 26), fill=c, width=14)
    d.polygon([(12, 86), (18, 64), (34, 80)], fill=c)


def _copy(d, c):
    d.rounded_rectangle((32, 32, 86, 88), 9, outline=c, width=STROKE)
    d.line([(24, 64), (18, 64), (10, 56), (10, 18), (18, 10), (54, 10), (62, 18), (62, 24)],
           fill=c, width=STROKE, joint="curve")


def _reload(d, c):
    d.arc((14, 14, 82, 82), 40, 320, fill=c, width=STROKE)
    d.polygon([(66, 4), (90, 30), (56, 36)], fill=c)


ICON_DRAWERS = {
    "menu": _menu, "history": _history, "image": _image, "text": _text, "actions": _actions,
    "settings": _settings, "search": _search, "pause": _pause, "play": _play, "trash": _trash,
    "clear": _clear, "edit": _edit, "reload": _reload, "copy": _copy,
}


def render_icon(name, color):
    """Draw a named icon as a transparent ICON_SIZE x ICON_SIZE image."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    ICON_DRAWERS[name](ImageDraw.Draw(img), color)
    return img


def icon(name, color, size=18):
    """A small anti-aliased icon as a Tk image."""
    key = (name, color, size)
    if key not in _icons:
        _icons[key] = ImageTk.PhotoImage(render_icon(name, color).resize((size, size), Image.LANCZOS))
    return _icons[key]


def when(ts):
    if not ts:
        return ""
    delta = max(0, time.time() - ts)
    if delta < 60:
        return "Just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return time.strftime("%b %d", time.localtime(ts))


_shapes = {}


def rounded_bg(w, h, radius, fill, outline=None):
    """A w x h rounded rectangle as an anti-aliased image with transparent corners."""
    key = (w, h, radius, fill, outline)
    if key not in _shapes:
        s = 4
        img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius * s, fill=fill,
                                              outline=outline, width=s if outline else 0)
        _shapes[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
    return _shapes[key]


def corner_images(radius, outside, inside, border):
    """The four corner pieces of a bordered rounded box: (top-left, top-right, bottom-left, bottom-right).

    Pixels outside the arc use `outside` (the window colour) so they can be laid over square content.
    """
    key = ("corners", radius, outside, inside, border)
    if key not in _shapes:
        s, r = 8, radius
        img = Image.new("RGBA", (2 * r * s, 2 * r * s), outside)
        ImageDraw.Draw(img).rounded_rectangle((0, 0, 2 * r * s - 1, 2 * r * s - 1), r * s, fill=inside,
                                              outline=border, width=s)
        img = img.resize((2 * r, 2 * r), Image.LANCZOS)
        boxes = ((0, 0, r, r), (r, 0, 2 * r, r), (0, r, r, 2 * r), (r, r, 2 * r, 2 * r))
        _shapes[key] = tuple(ImageTk.PhotoImage(img.crop(b)) for b in boxes)
    return _shapes[key]


class ToolButton(tk.Canvas):
    """Header toolbar button: rounded hover background, icon + label, grey when disabled, red if destructive."""

    HEIGHT = 34

    def __init__(self, parent, theme, font, text, icon_name, command, kind="normal"):
        super().__init__(parent, bg=theme["header"], bd=0, highlightthickness=0, height=self.HEIGHT)
        self.t, self.command, self.kind = theme, command, kind
        self.font = tkfont.Font(family=font, size=10)
        self.text, self.icon_name, self.enabled, self.hover = text, icon_name, True, False
        self.width = None
        self.bind("<Enter>", lambda _: self._set_hover(True))
        self.bind("<Leave>", lambda _: self._set_hover(False))
        self.bind("<Button-1>", self._click)
        self._paint()

    def _set_hover(self, hover):
        self.hover = hover
        self._paint()

    def _click(self, _event):
        if self.enabled:
            self.command()

    def configure_button(self, text=None, icon_name=None, enabled=None):
        if text is not None:
            self.text = text
        if icon_name is not None:
            self.icon_name = icon_name
        if enabled is not None:
            self.enabled = enabled
        self._paint()

    def _paint(self):
        t, h = self.t, self.HEIGHT
        width = 10 + 18 + 6 + self.font.measure(self.text) + 12
        if width != self.width:  # reconfiguring on every hover would make Tk re-layout the toolbar
            self.width = width
            self.config(width=width)
        self.config(cursor="hand2" if self.enabled else "arrow")
        bg, fg = None, t["text"]
        if self.kind == "accent":
            bg, fg = t["accent"], t["on_accent"]
        elif self.kind == "danger" and self.enabled:
            fg = t["danger"]
        if not self.enabled:
            fg = t["disabled"]
        elif self.hover and self.kind != "accent":
            bg = t["danger_bg"] if self.kind == "danger" else t["hover"]
        self.delete("all")
        if bg:
            self.create_image(0, 0, anchor="nw", image=rounded_bg(width, h, 5, bg))
        self.create_image(10, h // 2, anchor="w", image=icon(self.icon_name, fg))
        self.create_text(34, h // 2, anchor="w", text=self.text, fill=fg, font=self.font)


class NavItem(tk.Canvas):
    """Sidebar entry: rounded highlight, accent bar on the left when active."""

    HEIGHT = 36

    def __init__(self, parent, theme, font, text, icon_name, command):
        super().__init__(parent, bg=theme["bg"], bd=0, highlightthickness=0, height=self.HEIGHT, cursor="hand2")
        self.t, self.text, self.icon_name = theme, text, icon_name
        self.font = tkfont.Font(family=font, size=10)
        self.active, self.hover, self.collapsed = False, False, False
        self.bind("<Configure>", lambda _: self._paint())
        self.bind("<Button-1>", lambda _: command())
        self.bind("<Enter>", lambda _: self._set_hover(True))
        self.bind("<Leave>", lambda _: self._set_hover(False))

    def _set_hover(self, hover):
        self.hover = hover
        self._paint()

    def set_active(self, active):
        self.active = active
        self._paint()

    def set_collapsed(self, collapsed):
        self.collapsed = collapsed
        self._paint()

    def _paint(self):
        t, h, w = self.t, self.HEIGHT, self.winfo_width()
        if w <= 1:
            return
        self.delete("all")
        if self.active or self.hover:
            self.create_image(0, 0, anchor="nw",
                              image=rounded_bg(w, h, 5, t["nav_active"] if self.active else t["nav_hover"]))
        if self.active:
            self.create_image(1, (h - 16) // 2, anchor="nw", image=rounded_bg(3, 16, 1, t["accent"]))
        self.create_image(14, h // 2, anchor="w", image=icon(self.icon_name, t["text"]))
        if not self.collapsed:
            self.create_text(44, h // 2, anchor="w", text=self.text, fill=t["text"], font=self.font)


class RowActions(tk.Frame):
    """Copy and delete icons laid over the last cell of one table row (a ttk table can't hold widgets)."""

    def __init__(self, tree, theme, on_copy, on_delete, on_wheel):
        super().__init__(tree, bg=theme["elevated"], bd=0, highlightthickness=0)
        self.t, self.iid = theme, None
        self.copy = tk.Label(self, bd=0, cursor="hand2", image=icon("copy", theme["muted"], 16))
        self.trash = tk.Label(self, bd=0, cursor="hand2", image=icon("trash", theme["muted"], 16))
        self.copy.place(x=20, rely=0.5, anchor="center")
        self.trash.place(x=50, rely=0.5, anchor="center")
        for label, name, hover, command in ((self.copy, "copy", theme["accent"], on_copy),
                                            (self.trash, "trash", theme["danger"], on_delete)):
            label.bind("<Button-1>", lambda _e, cmd=command: cmd(self.iid))
            label.bind("<Enter>", lambda _e, lb=label, n=name, c=hover: lb.config(image=icon(n, c, 16)))
            label.bind("<Leave>", lambda _e, lb=label, n=name: lb.config(image=icon(n, theme["muted"], 16)))
        for widget in (self, self.copy, self.trash):  # the table would scroll under the mouse; keep that working
            widget.bind("<MouseWheel>", on_wheel)
            widget.bind("<Button-4>", on_wheel)
            widget.bind("<Button-5>", on_wheel)

    def show(self, iid, x, y, w, h, selected):
        self.iid = iid
        bg = self.t["selected"] if selected else self.t["elevated"]
        for widget in (self, self.copy, self.trash):
            widget.config(bg=bg)
        self.place(x=x, y=y, width=w, height=h)

    def hide(self):
        self.iid = None
        self.place_forget()


class RoundedField(tk.Canvas):
    """A rounded, bordered input box around another widget; the border turns accent-coloured on focus."""

    HEIGHT = 34

    def __init__(self, parent, theme, outer, width, make_inner, icon_name=None):
        super().__init__(parent, bg=outer, width=width, height=self.HEIGHT, bd=0, highlightthickness=0)
        self.t, self.w = theme, width
        self.bg_item = self.create_image(0, 0, anchor="nw", image=self._shape(False))
        left = 10
        if icon_name:
            self.create_image(10, self.HEIGHT // 2, anchor="w", image=icon(icon_name, theme["muted"], 16))
            left = 32
        self.inner = make_inner(self)
        self.create_window(left, self.HEIGHT // 2, anchor="w", window=self.inner, width=width - left - 8)
        for event, focused in (("<FocusIn>", True), ("<FocusOut>", False)):
            self.inner.bind(event, lambda _e, f=focused: self.itemconfig(self.bg_item, image=self._shape(f)), add="+")

    def _shape(self, focused):
        t = self.t
        return rounded_bg(self.w, self.HEIGHT, 5, t["input"], t["accent"] if focused else t["border"])


class MainWindow:
    NAV = (("history", "History", "history"), ("images", "Images", "image"), ("actions", "Actions", "actions"))
    TITLES = {"history": "History", "images": "Images", "actions": "Actions", "settings": "Settings"}

    def __init__(self, root, app, platform, app_icon):
        self.root, self.app, self.platform, self.app_icon = root, app, platform, app_icon
        self.font = platform.ui_font
        self.win = None
        self.dark = None
        self.page = "history"
        self.collapsed = False
        self.visible = []
        self._thumbs = {}
        self._photo = None
        self.row_buttons = []         # pool of RowActions, one per visible table row
        self._layout_pending = False
        self._scroll_shown = False
        self._flash_token = None

    # -- public API -------------------------------------------------------------
    def show(self, page=None):
        dark = self.platform.is_dark_mode()
        if self.win is not None and dark != self.dark:
            self.win.destroy()
            self.win = None
        if self.win is None:
            self._build(dark)
        if page:
            self._select_page(page)
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)  # forces it in front; dropped again below
        # Scheduled on the root, not the window: a callback registered on a window is deleted with it, and Tk
        # then reports "invalid command name" if the window was rebuilt before the timer fired.
        self.root.after(250, lambda win=self.win: self._drop_topmost(win))
        self.win.focus_force()
        if self.page in ("history", "images"):
            self.search_var.set("")
            self.refresh()
            self.search_entry.focus_set()

    @staticmethod
    def _drop_topmost(win):
        try:
            win.attributes("-topmost", False)
        except tk.TclError:  # the window was rebuilt (theme change) or closed in the meantime
            pass

    def hide(self):
        if self.win is not None:
            self.win.withdraw()

    def has_focus(self):
        return self.win is not None and self.win.state() != "withdrawn" and self.win.focus_displayof() is not None

    def refresh(self):
        if self.win is None or self.page not in ("history", "images"):
            return
        needle = self.search_var.get().lower()
        only_images = self.page == "images"
        self.visible = []
        for item in self.app.history.items:
            if only_images and item["type"] != "image":
                continue
            haystack = item["text"].lower() if item["type"] == "text" else f"image {item['w']}x{item['h']}"
            if needle in haystack:
                self.visible.append(item)
        self.tree.delete(*self.tree.get_children())
        muted = self.t["muted"]
        for i, item in enumerate(self.visible):
            if item["type"] == "image":
                img, kind, size = self._thumb(item), "Image", f"{item['w']}×{item['h']}"
                label = f"Image {item['w']}×{item['h']}"
            else:
                img, kind, size = icon("text", muted, 18), "Text", f"{len(item['text'])} chars"
                label = " ".join(item["text"].split())[: self.app.config["preview_chars"]]
            self.tree.insert("", "end", iid=str(i), text="  " + label, image=img,
                             values=(kind, size, when(item.get("time")), ""))
        if self.visible:
            self.tree.selection_set("0")
        self._on_select()
        self._schedule_row_buttons()

    def update_pause(self):
        if self.win is not None:
            paused = self.app.paused
            self.pause_btn.configure_button(text="Resume" if paused else "Pause",
                                            icon_name="play" if paused else "pause")

    # -- construction -------------------------------------------------------------
    def _style(self):
        t, f = self.t, self.font
        st = ttk.Style(self.win)
        st.theme_use("clam")
        st.configure("Clip.Treeview", background=t["elevated"], fieldbackground=t["elevated"],
                     foreground=t["text"], borderwidth=0, rowheight=36, font=(f, 10))
        st.layout("Clip.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.map("Clip.Treeview", background=[("selected", t["selected"])], foreground=[("selected", t["text"])])
        st.configure("Clip.Treeview.Heading", background=t["elevated"], foreground=t["muted"], relief="flat",
                     borderwidth=0, padding=(8, 10), font=(f, 9))
        st.map("Clip.Treeview.Heading", background=[("active", t["hover"])])
        st.layout("Clip.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
            "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        st.configure("Clip.Vertical.TScrollbar", background=t["scroll"], troughcolor=t["elevated"],
                     borderwidth=0, width=8)
        st.map("Clip.Vertical.TScrollbar", background=[("active", t["muted"])])
        st.configure("Clip.TSpinbox", fieldbackground=t["input"], foreground=t["text"], background=t["input"],
                     arrowcolor=t["text"], bordercolor=t["input"], lightcolor=t["input"],
                     darkcolor=t["input"], insertcolor=t["text"], borderwidth=0, padding=2)

    def _build(self, dark):
        self.dark = dark
        self.t = t = DARK if dark else LIGHT
        f = self.font
        self._thumbs.clear()
        _icons.clear()  # a rebuild means a new theme or a recreated window; don't keep stale images alive
        _shapes.clear()
        win = self.win = tk.Toplevel(self.root)
        win.title(APP_NAME)
        self._window_icon = ImageTk.PhotoImage(self.app_icon)  # replaces Tk's default feather icon
        win.iconphoto(False, self._window_icon)
        win.configure(bg=t["bg"])
        win.geometry("1000x660")
        win.minsize(900, 500)  # the History toolbar needs this much room
        win.protocol("WM_DELETE_WINDOW", self.hide)
        win.bind("<Escape>", lambda _: self.hide())
        win.columnconfigure(1, weight=1)
        win.rowconfigure(1, weight=1)
        self._style()

        # Top bar: menu button, app icon, title.
        top = tk.Frame(win, bg=t["bg"], height=48)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        menu = tk.Label(top, image=icon("menu", t["text"], 20), bg=t["bg"], cursor="hand2")
        menu.pack(side="left", padx=(16, 12), pady=14)
        menu.bind("<Button-1>", lambda _: self._toggle_sidebar())
        self._app_photo = ImageTk.PhotoImage(self.app_icon.resize((20, 20), Image.LANCZOS))
        tk.Label(top, image=self._app_photo, bg=t["bg"]).pack(side="left")
        tk.Label(top, text=APP_NAME, font=(f, 10), fg=t["muted"], bg=t["bg"]).pack(side="left", padx=8)

        # Sidebar.
        self.sidebar = tk.Frame(win, bg=t["bg"], width=200)
        self.sidebar.grid(row=1, column=0, sticky="ns", padx=(6, 0), pady=(0, 10))
        self.sidebar.pack_propagate(False)
        self.nav = {}
        for key, label, ic in self.NAV:
            item = NavItem(self.sidebar, t, f, label, ic, lambda k=key: self._select_page(k))
            item.pack(fill="x", pady=1)
            self.nav[key] = item
        settings = NavItem(self.sidebar, t, f, "Settings", "settings", lambda: self._select_page("settings"))
        settings.pack(side="bottom", fill="x", pady=1)
        self.nav["settings"] = settings

        # Content card.
        card = tk.Frame(win, bg=t["border"])  # the 1px border is the card's own background showing through
        card.grid(row=1, column=1, sticky="nsew", padx=10, pady=(0, 10))
        inner = tk.Frame(card, bg=t["elevated"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        header = tk.Frame(inner, bg=t["header"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.title = tk.Label(header, font=(f, 11, "bold"), fg=t["text"], bg=t["header"])
        self.title.pack(side="left", padx=20)
        tk.Frame(inner, bg=t["border"], height=1).pack(fill="x")
        self.body = tk.Frame(inner, bg=t["elevated"])
        self.body.pack(fill="both", expand=True)

        self.toolbars = {}
        self.pages = {}
        self._build_history(header)
        self._build_actions(header)
        self._build_settings(header)
        self._select_page(self.page if self.page in self.TITLES else "history")

        # Round the card's corners: small corner pieces laid over the square header and body.
        radius = 8
        top_left, top_right, _, _ = corner_images(radius, t["bg"], t["header"], t["border"])
        _, _, bottom_left, bottom_right = corner_images(radius, t["bg"], t["elevated"], t["border"])
        for image, place in ((top_left, dict(x=0, y=0, anchor="nw")),
                             (top_right, dict(relx=1, x=0, y=0, anchor="ne")),
                             (bottom_left, dict(x=0, rely=1, y=0, anchor="sw")),
                             (bottom_right, dict(relx=1, x=0, rely=1, y=0, anchor="se"))):
            corner = tk.Label(card, image=image, bd=0, highlightthickness=0, bg=t["bg"])
            corner.place(**place)
            corner.lift()

    def _field(self, parent, outer, width, make_inner, icon_name=None):
        """A rounded input box around the widget that make_inner(parent) builds."""
        return RoundedField(parent, self.t, outer, width, make_inner, icon_name)

    def _entry(self, parent, **kw):
        t = self.t
        return tk.Entry(parent, bd=0, relief="flat", bg=t["input"], fg=t["text"], insertbackground=t["text"],
                        highlightthickness=0, font=(self.font, 10), **kw)

    def _build_history(self, header):
        t, f = self.t, self.font
        bar = self.toolbars["history"] = tk.Frame(header, bg=t["header"])
        self.clear_btn = ToolButton(bar, t, f, "Clear all", "trash", self.app.clear_history)
        self.clear_btn.pack(side="right", padx=2)
        self.remove_btn = ToolButton(bar, t, f, "Remove", "clear", self._remove_selected, kind="danger")
        self.remove_btn.pack(side="right", padx=2)
        self.pause_btn = ToolButton(bar, t, f, "Pause", "pause", self.app.toggle_pause)
        self.pause_btn.pack(side="right", padx=2)
        self.copy_btn = ToolButton(bar, t, f, "Copy", "copy", self._copy_selected)
        self.copy_btn.pack(side="right", padx=2)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        box = self._field(bar, t["header"], 165, lambda p: self._entry(p, textvariable=self.search_var),
                          icon_name="search")
        box.pack(side="right", padx=(0, 10))
        self.search_entry = box.inner
        self.search_entry.bind("<Down>", lambda _: self._move(1))
        self.search_entry.bind("<Up>", lambda _: self._move(-1))
        self.search_entry.bind("<Return>", lambda _: self._use_selected())
        self.search_entry.bind("<Delete>", self._delete_key)

        page = self.pages["history"] = tk.Frame(self.body, bg=t["elevated"])
        pane = tk.Frame(page, bg=t["elevated"], height=170)
        pane.pack(side="bottom", fill="x")
        pane.pack_propagate(False)
        tk.Frame(page, bg=t["border"], height=1).pack(side="bottom", fill="x")
        self.preview_caption = tk.Label(pane, anchor="w", font=(f, 9), fg=t["muted"], bg=t["elevated"])
        self.preview_caption.pack(fill="x", padx=20, pady=(10, 4))
        self.preview_label = tk.Label(pane, anchor="nw", justify="left", wraplength=640, font=(f, 10),
                                      fg=t["text"], bg=t["elevated"])
        self.preview_label.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        wrap = tk.Frame(page, bg=t["elevated"])
        wrap.pack(fill="both", expand=True, padx=(12, 4), pady=(4, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.tree_scroll = ttk.Scrollbar(wrap, style="Clip.Vertical.TScrollbar", orient="vertical")
        self.tree = ttk.Treeview(wrap, style="Clip.Treeview", columns=("kind", "size", "when", "actions"),
                                 show="tree headings", selectmode="browse", yscrollcommand=self._on_yscroll)
        self.tree_scroll.config(command=self.tree.yview)
        for col, text, width in (("#0", "Content", 240), ("kind", "Type", 70), ("size", "Size", 90),
                                 ("when", "Copied", 90), ("actions", "", 72)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=width, anchor="w", stretch=(col == "#0"),
                             minwidth=72 if col == "actions" else 60)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
        self.tree_scroll.grid_remove()  # only shown when the list is longer than the view
        self._scroll_shown = False
        self.tree.bind("<Configure>", lambda _: self._schedule_row_buttons())
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._on_select())
        self.tree.bind("<Double-Button-1>", lambda _: self._use_selected())
        self.tree.bind("<Return>", lambda _: self._use_selected())
        self.tree.bind("<Delete>", lambda _: self._remove_selected())
        context = "<Button-2>" if self.platform.name == "macos" else "<Button-3>"
        self.tree.bind(context, self._context_menu)
        if self.platform.name == "macos":
            self.tree.bind("<Control-Button-1>", self._context_menu)
        self.update_pause()

    def _build_actions(self, header):
        t, f = self.t, self.font
        bar = self.toolbars["actions"] = tk.Frame(header, bg=t["header"])
        ToolButton(bar, t, f, "Reload", "reload", self._reload_actions).pack(side="right", padx=2)
        ToolButton(bar, t, f, "Edit actions", "edit", self.app.edit_actions).pack(side="right", padx=2)
        page = self.pages["actions"] = tk.Frame(self.body, bg=t["elevated"])
        tk.Label(page, anchor="w", justify="left", fg=t["muted"], bg=t["elevated"], font=(f, 9),
                 text="Actions run a command when a clipboard entry matches a pattern. "
                      "Right-click a history item to use them.").pack(fill="x", padx=20, pady=(14, 4))
        wrap = tk.Frame(page, bg=t["elevated"])
        wrap.pack(fill="both", expand=True, padx=(12, 4))
        self.actions_tree = ttk.Treeview(wrap, style="Clip.Treeview", columns=("pattern", "commands"),
                                         show="tree headings", selectmode="browse")
        for col, text, width in (("#0", "Name", 180), ("pattern", "Pattern", 300), ("commands", "Commands", 300)):
            self.actions_tree.heading(col, text=text, anchor="w")
            self.actions_tree.column(col, width=width, anchor="w", stretch=True, minwidth=80)
        self.actions_tree.pack(fill="both", expand=True)

    def _build_settings(self, header):
        t, f = self.t, self.font
        bar = self.toolbars["settings"] = tk.Frame(header, bg=t["header"])
        ToolButton(bar, t, f, "Save", "play", self._save_settings, kind="accent").pack(side="right", padx=(2, 10))
        self.status = tk.Label(bar, font=(f, 9), fg=t["muted"], bg=t["header"])
        self.status.pack(side="right", padx=10)
        page = self.pages["settings"] = tk.Frame(self.body, bg=t["elevated"])
        cfg = self.app.config
        self.v_hotkey = tk.StringVar(value=cfg["hotkey"])
        self.v_max = tk.StringVar(value=str(cfg["max_items"]))
        self.v_preview = tk.StringVar(value=str(cfg["preview_chars"]))
        self.v_paste = tk.BooleanVar(value=cfg["paste_on_select"])
        self.v_hist = tk.BooleanVar(value=cfg["save_history"])
        self.v_img = tk.BooleanVar(value=cfg["save_images"])
        self.v_auto = tk.BooleanVar(value=self.platform.autostart_enabled())

        rows = (
            ("Popup hotkey", self.platform.hotkey_examples,
             lambda p: self._field(p, t["elevated"], 220, lambda q: self._entry(q, textvariable=self.v_hotkey))),
            ("History size", "How many entries to keep (1-1000)",
             lambda p: self._field(p, t["elevated"], 110, lambda q: ttk.Spinbox(
                 q, style="Clip.TSpinbox", from_=1, to=1000, textvariable=self.v_max))),
            ("Preview length", "Characters shown per row (20-300)",
             lambda p: self._field(p, t["elevated"], 110, lambda q: ttk.Spinbox(
                 q, style="Clip.TSpinbox", from_=20, to=300, textvariable=self.v_preview))),
            ("Paste after choosing", "Paste into the previous window when you pick an item",
             lambda p: self._check(p, self.v_paste)),
            ("Remember history", "Keep history between sessions", lambda p: self._check(p, self.v_hist)),
            ("Record images", "Also keep copied images", lambda p: self._check(p, self.v_img)),
            ("Start at login", "Launch automatically when you sign in", lambda p: self._check(p, self.v_auto)),
        )
        for label, hint, make in rows:
            row = tk.Frame(page, bg=t["elevated"])
            row.pack(fill="x", padx=20)
            left = tk.Frame(row, bg=t["elevated"])
            left.pack(side="left", pady=8)
            tk.Label(left, text=label, font=(f, 10), fg=t["text"], bg=t["elevated"], anchor="w").pack(anchor="w")
            tk.Label(left, text=hint, font=(f, 9), fg=t["muted"], bg=t["elevated"], anchor="w").pack(anchor="w")
            make(row).pack(side="right", ipady=2)
            tk.Frame(page, bg=t["border"], height=1).pack(fill="x", padx=20)
        tk.Label(page, text=f"{APP_NAME} {APP_VERSION} · MIT license", font=(f, 9), fg=t["muted"],
                 bg=t["elevated"], anchor="w").pack(fill="x", padx=20, pady=(12, 0))

    def _check(self, parent, var):
        t = self.t
        return tk.Checkbutton(parent, variable=var, bg=t["elevated"], activebackground=t["elevated"],
                              selectcolor=t["input"], fg=t["text"], activeforeground=t["text"], bd=0,
                              highlightthickness=0)

    # -- navigation ---------------------------------------------------------------
    def _toggle_sidebar(self):
        self.collapsed = not self.collapsed
        self.sidebar.config(width=52 if self.collapsed else 200)
        for item in self.nav.values():
            item.set_collapsed(self.collapsed)

    def _select_page(self, page):
        self.page = page
        for key, item in self.nav.items():
            item.set_active(key == page)
        self.title.config(text=self.TITLES[page])
        for bar in self.toolbars.values():
            bar.pack_forget()
        for frame in self.pages.values():
            frame.pack_forget()
        if page in ("history", "images"):
            self.toolbars["history"].pack(side="right", fill="y")
            self.pages["history"].pack(fill="both", expand=True)
            self.refresh()
            if self.win.state() != "withdrawn":
                self.search_entry.focus_set()
        elif page == "actions":
            self._reload_actions()
            self.toolbars["actions"].pack(side="right", fill="y")
            self.pages["actions"].pack(fill="both", expand=True)
        else:
            self.status.config(text="")
            self.toolbars["settings"].pack(side="right", fill="y")
            self.pages["settings"].pack(fill="both", expand=True)

    # -- history list -------------------------------------------------------------
    def _thumb(self, item):
        name = item["file"]
        if name not in self._thumbs:
            try:
                with Image.open(self.app.image_file(item)) as img:
                    img = img.convert("RGBA")
                    img.thumbnail((40, 28))
                    self._thumbs[name] = ImageTk.PhotoImage(img)
            except (OSError, ValueError):
                self._thumbs[name] = icon("image", self.t["muted"], 18)
        return self._thumbs[name]

    def selected_item(self):
        sel = self.tree.selection()
        return self.visible[int(sel[0])] if sel else None

    def _on_yscroll(self, first, last):
        """Scrollbar callback: show the bar only when some rows are out of view, and keep the icons in place."""
        self.tree_scroll.set(first, last)
        needed = float(first) > 0.0 or float(last) < 1.0
        if needed != self._scroll_shown:
            self._scroll_shown = needed
            if needed:
                self.tree_scroll.grid()
            else:
                self.tree_scroll.grid_remove()
        self._schedule_row_buttons()

    def _schedule_row_buttons(self):
        if not self._layout_pending:
            self._layout_pending = True
            self.root.after_idle(self._layout_row_buttons)  # on the root: the window may be rebuilt meanwhile

    def _layout_row_buttons(self):
        """Lay a copy/delete icon pair over the last cell of every row that is currently in view."""
        self._layout_pending = False
        try:
            if self.win is None or self.page not in ("history", "images"):
                return
            selected = self.tree.selection()
            used = 0
            for iid in self.tree.get_children():
                box = self.tree.bbox(iid, "actions")
                if not box:  # scrolled out of view
                    continue
                if used == len(self.row_buttons):
                    self.row_buttons.append(RowActions(self.tree, self.t, self._copy_row, self._delete_row,
                                                       self._wheel))
                self.row_buttons[used].show(iid, *box, selected=iid in selected)
                used += 1
            for spare in self.row_buttons[used:]:
                spare.hide()
        except tk.TclError:  # the window was closed or rebuilt while this was queued
            pass

    def _wheel(self, event):
        up = event.num == 4 or getattr(event, "delta", 0) > 0
        self.tree.yview_scroll(-1 if up else 1, "units")

    def _copy_row(self, iid):
        if iid is not None:
            self._copy(self.visible[int(iid)])

    def _delete_row(self, iid):
        if iid is not None:
            self.app.remove_item(self.visible[int(iid)])

    def _copy_selected(self):
        item = self.selected_item()
        if item is not None:
            self._copy(item)

    def _copy(self, item):
        if self.app.copy_item(item):
            self._flash("Copied to clipboard", self.t["accent"])
        else:
            self._flash("Could not copy this item", self.t["danger"])

    def _flash(self, text, colour):
        """Show a short confirmation where the selected entry's caption normally is."""
        self.preview_caption.config(text=text, fg=colour)
        token = self._flash_token = object()
        self.root.after(1600, lambda: self._end_flash(token))

    def _end_flash(self, token):
        try:
            if self.win is not None and token is self._flash_token:
                self._on_select()
        except tk.TclError:
            pass

    def _on_select(self):
        item = self.selected_item()
        self.remove_btn.configure_button(enabled=item is not None)
        self.copy_btn.configure_button(enabled=item is not None)
        self.preview_caption.config(fg=self.t["muted"])
        self._schedule_row_buttons()  # the selected row has a different background
        self.preview_label.config(image="", text="")
        self._photo = None
        if item is None:
            self.preview_caption.config(text="Nothing selected")
            return
        if item["type"] == "text":
            self.preview_caption.config(text=f"Text · {len(item['text'])} characters")
            self.preview_label.config(text=item["text"][:800])
            return
        self.preview_caption.config(text=f"Image · {item['w']}×{item['h']}")
        try:
            with Image.open(self.app.image_file(item)) as img:
                img = img.convert("RGBA")
                img.thumbnail((620, 130))
                self._photo = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self._photo)
        except (OSError, ValueError):
            self.preview_label.config(text="(image file missing)")

    def _move(self, delta):
        kids = self.tree.get_children()
        if not kids:
            return "break"
        sel = self.tree.selection()
        i = max(0, min(len(kids) - 1, (kids.index(sel[0]) if sel else -1) + delta))
        self.tree.selection_set(kids[i])
        self.tree.see(kids[i])
        return "break"

    def _use_selected(self):
        item = self.selected_item()
        if item is not None:
            self.app.use_item(item)

    def _remove_selected(self):
        item = self.selected_item()
        if item is not None:
            self.app.remove_item(item)

    def _delete_key(self, _event):
        if not self.search_var.get():
            self._remove_selected()
            return "break"

    def _context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        item = self.visible[int(row)]
        t = self.t
        menu = tk.Menu(self.win, tearoff=0, bg=t["elevated"], fg=t["text"], activebackground=t["selected"],
                       activeforeground=t["text"], bd=0, font=(self.font, 10))
        menu.add_command(label="Use this item", command=self._use_selected)
        menu.add_command(label="Copy", command=self._copy_selected)
        menu.add_separator()
        if item["type"] == "image":
            menu.add_command(label="Open image", command=lambda: self.platform.open_path(self.app.image_file(item)))
        else:
            matches = self.app.actions.match(item["text"])
            for action, command, template, m in matches:
                menu.add_command(label=f"{action}: {command}",
                                 command=lambda tp=template, mm=m: self.app.run_action(tp, mm))
            if not matches:
                menu.add_command(label="No actions match", state="disabled")
        menu.add_separator()
        menu.add_command(label="Remove from history", command=self._remove_selected)
        menu.tk_popup(event.x_root, event.y_root)

    # -- actions and settings pages -------------------------------------------------
    def _reload_actions(self):
        self.app.reload_actions()
        self.actions_tree.delete(*self.actions_tree.get_children())
        for i, (name, rx, commands) in enumerate(self.app.actions.actions):
            self.actions_tree.insert("", "end", iid=str(i), text="  " + name,
                                     values=(rx.pattern, ", ".join(c["name"] for c in commands)))

    def _save_settings(self):
        saved, message = self.app.save_settings({
            "hotkey": self.v_hotkey.get(), "max_items": self.v_max.get(), "preview_chars": self.v_preview.get(),
            "paste_on_select": self.v_paste.get(), "save_history": self.v_hist.get(),
            "save_images": self.v_img.get(), "autostart": self.v_auto.get(),
        })
        self.status.config(text=message or "Settings saved", fg=self.t["muted"] if saved else self.t["danger"])
        if saved:
            self.v_hotkey.set(self.app.config["hotkey"])
