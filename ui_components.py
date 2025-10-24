import tkinter as tk

class TextLineNumbers(tk.Canvas):
    """A canvas widget to display line numbers for a Text widget."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        """Redraw the line numbers."""
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, fill="#606366")
            i = self.textwidget.index(f"{i}+1line")

class CustomText(tk.Text):
    """A Text widget with a linked line number canvas."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        cmd = (self._orig,) + args
        result = self.tk.call(cmd)

        if (args[0] in ("insert", "delete") or
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] in (("xview", "moveto"), ("xview", "scroll"),
                         ("yview", "moveto"), ("yview", "scroll"))):
            self.event_generate("<<Change>>", when="tail")

        return result

class TextWithLineNumbers(tk.Frame):
    """A frame containing a Text widget and a line number canvas."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        # Extract yscrollcommand for the text widget, but not for the frame
        yscrollcommand = kwargs.pop('yscrollcommand', None)
        self.text = CustomText(self, yscrollcommand=yscrollcommand, **kwargs)
        self.linenumbers = TextLineNumbers(self, width=40, bg='#f0f0f0')
        self.linenumbers.attach(self.text)

        self.linenumbers.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

    def _on_change(self, event):
        self.linenumbers.redraw()