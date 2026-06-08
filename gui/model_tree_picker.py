"""
model_tree_picker.py  –  v1.5 (inline tree)
--------------------------------------------
Accessible inline model selector for Music Separator GUI.

Layout (vertical, full-width):
  ┌─────────────────────────────────────┐
  │ Cerca: [______________________]     │  ← search TextCtrl  (Tab stop 1)
  │ ┌───────────────────────────────┐   │
  │ │ Favorites          (expanded) │   │
  │ │   BS-Roformer-SW   ← leaf     │   │  ← TreeCtrl         (Tab stop 2)
  │ │   UVR-MDX-NET-…               │   │
  │ │ De-Reverb / De-Echo (collapsed│   │
  │ │ Karaoke / Backing Vocals      │   │
  │ └───────────────────────────────┘   │
  └─────────────────────────────────────┘

Screen-reader behaviour (NVDA / JAWS)
--------------------------------------
- Tab to search field → type to filter → Tab to tree → navigate with arrows.
- Right arrow : expand category or enter its first child.
- Left arrow  : collapse category or move to its parent.
- Up / Down   : move between sibling items.
- Selecting a MODEL LEAF immediately sets it as the current model
  (same as a standard listbox – no extra confirmation needed).
- Categories (bold, no data) are skipped as model selection; only
  leaf items (model names) update the selection value.
"""

import wx
from gui.i18n_manager import i18n

# ---------------------------------------------------------------------------
# Custom event: fired when the user navigates to a model leaf
# ---------------------------------------------------------------------------
_myEVT_MODEL_SELECTED = wx.NewEventType()
EVT_MODEL_SELECTED = wx.PyEventBinder(_myEVT_MODEL_SELECTED, 1)


class ModelSelectedEvent(wx.PyCommandEvent):
    def __init__(self, eventType, eid, value=""):
        super().__init__(eventType, eid)
        self._value = value

    def GetValue(self) -> str:
        return self._value


# ---------------------------------------------------------------------------
# Public widget: ModelTreePicker (inline version)
# ---------------------------------------------------------------------------
class ModelTreePicker(wx.Panel):
    """
    Inline, accessible model selector.

    Renders a search TextCtrl on top and a TreeCtrl below, both embedded
    directly in the parent panel (no popup / no dialog).

    Public API (drop-in compatible with the former ComboBox usage)
    --------------------------------------------------------------
    Populate(categories)  – {category: [display_name, ...]} dict
    GetValue()            – display name of the current model selection
    SetValue(name)        – programmatically set selection (scrolls to item)
    Enable() / Disable()
    Show() / Hide()       – inherited from wx.Panel
    SetToolTip(str or wx.ToolTip)
    EVT_MODEL_SELECTED    – fired when the user navigates to a model leaf
    """

    _TREE_HEIGHT = 160   # minimum / initial height of the tree control

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._value = ""
        self._categories: dict = {}
        self._enabled = True
        # Prevents EVT_MODEL_SELECTED from firing during Populate / SetValue
        self._programmatic_update = False

        outer = wx.BoxSizer(wx.VERTICAL)

        # ── Search row ────────────────────────────────────────────────────────
        search_row = wx.BoxSizer(wx.HORIZONTAL)
        self._lbl_search = wx.StaticText(self, label=i18n.tr("model_search"))
        search_row.Add(
            self._lbl_search,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5,
        )
        self.search = wx.TextCtrl(self)
        search_row.Add(self.search, proportion=1, flag=wx.EXPAND)
        outer.Add(search_row, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # ── Tree control ──────────────────────────────────────────────────────
        self.tree = wx.TreeCtrl(
            self,
            size=(-1, self._TREE_HEIGHT),
            style=(wx.TR_DEFAULT_STYLE
                   | wx.TR_HIDE_ROOT
                   | wx.TR_SINGLE
                   | wx.TR_LINES_AT_ROOT),
        )
        outer.Add(self.tree, flag=wx.EXPAND)

        self.SetSizer(outer)

        # ── Bindings ──────────────────────────────────────────────────────────
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_sel_changed)
        self.search.Bind(wx.EVT_TEXT, self._on_search)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def Populate(self, categories: dict):
        """Feed category-grouped display names and rebuild the tree."""
        self._categories = categories
        self._programmatic_update = True
        self._rebuild_tree(self._value)
        self._programmatic_update = False

    def GetValue(self) -> str:
        """Return the display name of the currently selected model."""
        return self._value

    def SetValue(self, value: str):
        """Select a model by display name and scroll to it in the tree."""
        self._value = value
        self._programmatic_update = True
        self._rebuild_tree(value, self.search.GetValue())
        self._programmatic_update = False

    def Enable(self, enable: bool = True):
        self._enabled = enable
        self._lbl_search.Enable(enable)
        self.search.Enable(enable)
        self.tree.Enable(enable)
        super().Enable(enable)

    def Disable(self):
        self.Enable(False)

    def IsEnabled(self) -> bool:
        return self._enabled

    def SetToolTip(self, tip):
        """Accept both a plain string and a wx.ToolTip object."""
        if isinstance(tip, str):
            tip = wx.ToolTip(tip)
        self.tree.SetToolTip(tip)

    def UpdateSearchLabel(self):
        """Refresh the search label text after a language change."""
        self._lbl_search.SetLabel(i18n.tr("model_search"))
        self.Layout()

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------
    def _rebuild_tree(self, current_value: str, filter_text: str = ""):
        """Rebuild the TreeCtrl applying an optional filter."""
        self.tree.DeleteAllItems()
        root = self.tree.AddRoot("Models")

        filter_lower = filter_text.strip().lower()
        item_to_select = None
        first_leaf = None

        bold_font = self.tree.GetFont()
        bold_font.SetWeight(wx.FONTWEIGHT_BOLD)

        for category, models in self._categories.items():
            visible = models
            if filter_lower:
                visible = [m for m in models if filter_lower in m.lower()]
            if not visible:
                continue

            # Category node: bold, data=None (not a selectable model)
            cat_item = self.tree.AppendItem(root, category)
            self.tree.SetItemFont(cat_item, bold_font)
            cat_has_current = False

            for display_name in visible:
                leaf = self.tree.AppendItem(cat_item, display_name)
                self.tree.SetItemData(leaf, display_name)
                if first_leaf is None:
                    first_leaf = leaf
                if display_name == current_value:
                    item_to_select = leaf
                    cat_has_current = True

            # Expand: Favorites always; the category containing the current
            # model; and every visible category when a filter is active.
            if category == "Favorites" or cat_has_current or filter_lower:
                self.tree.Expand(cat_item)

        if item_to_select:
            self.tree.SelectItem(item_to_select)
            self.tree.EnsureVisible(item_to_select)
        elif first_leaf and filter_lower:
            self.tree.EnsureVisible(first_leaf)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_sel_changed(self, event):
        """Update _value when the user navigates to a model leaf.

        The EVT_MODEL_SELECTED event is NOT fired during programmatic
        updates (Populate / SetValue) to avoid spurious callbacks.
        """
        if self._programmatic_update:
            event.Skip()
            return
        try:
            item = event.GetItem()
            if item.IsOk():
                data = self.tree.GetItemData(item)
                if data:                       # None for category nodes
                    self._value = data
                    evt = ModelSelectedEvent(
                        _myEVT_MODEL_SELECTED, self.GetId(), data
                    )
                    evt.SetEventObject(self)
                    self.GetEventHandler().ProcessEvent(evt)
        except RuntimeError:
            pass                               # widget already destroyed
        event.Skip()

    def _on_search(self, event):
        """Filter the tree in real time; return focus to the search field.

        TreeCtrl.SelectItem() steals focus on Windows, so we restore it
        to the search TextCtrl after every rebuild.
        """
        self._programmatic_update = True
        self._rebuild_tree(self._value, self.search.GetValue())
        self._programmatic_update = False
        wx.CallAfter(self.search.SetFocus)
        wx.CallAfter(self.search.SetInsertionPointEnd)
        event.Skip()
