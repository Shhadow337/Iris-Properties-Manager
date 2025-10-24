import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import difflib
import tempfile
from auto_mapper import load_rules, automap_items
import threading

from typing import Optional
from block_properties_manager import BlockPropertiesManager
from ui_components import TextWithLineNumbers


class ToastNotification(tk.Toplevel):
    """A semi-transparent, self-fading notification window (toast)."""

    def __init__(self, parent, message, duration=3000):
        super().__init__(parent)
        self.duration = duration

        # Window configuration
        self.overrideredirect(True)  # No title bar, borders, etc.
        self.attributes("-alpha", 0.0)  # Start fully transparent
        self.attributes("-topmost", True)  # Always on top

        # Label with message
        label = ttk.Label(self, text=message, padding=(10, 5), background="#45935f", foreground="white",
                          font=("TkDefaultFont", 9), wraplength=350)
        label.pack()

        # Position the toast in the bottom right corner of the parent window
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        self_width = self.winfo_reqwidth()
        self_height = self.winfo_reqheight()
        pos_x = parent_x + parent_width - self_width - 10
        pos_y = parent_y + parent_height - self_height - 10
        self.geometry(f"+{pos_x}+{pos_y}")

        # Start the fade-in and fade-out sequence
        self.fade_in()

    def fade_in(self, alpha=0.0):
        if alpha < 0.9:
            alpha += 0.05
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self.fade_in(alpha))
        else:
            self.after(self.duration, self.fade_out)

    def fade_out(self, alpha=0.9):
        if alpha > 0.0:
            alpha -= 0.05
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self.fade_out(alpha))
        else:
            self.destroy()

class TutorialManager:
    """Manages the step-by-step tutorial for the main application."""

    def __init__(self, parent_app):
        self.app = parent_app
        self.tutorial_window = None
        self.current_step_index = -1
        self.steps = None  # Inicjalizuj na None.
        # --- NEW STATE VARIABLES FOR CLEANUP ---
        self.original_file_path = None
        self.original_items_text = None
        self.original_template_state = False
        self.temp_session_path = None  # To store the path to the temporary session file
        self.original_active_target_category = None # To store the original active target category
        self.automap_dialog_open = False  # Flaga do obsługi messagebox
        # -----------------------------

    def _simulate_app_action(self, action_func):
        """Safely executes an action on the main app, ensuring GUI updates."""
        self.app.lift()
        self.app.update_idletasks()
        action_func()
        self.app.update_idletasks()

    def _get_automap_buttons(self):
        """Finds Apply/Cancel buttons in the Auto-map popup window."""
        apply_btn = None

        if self.app.automap_popup and self.app.automap_popup.winfo_exists():
            # Przycisk "Apply" jest w btn_frame, który jest ostatnim dzieckiem popupu
            for widget in self.app.automap_popup.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button) and btn.cget("text") == "Apply":
                            apply_btn = btn
                            break
            return apply_btn
        return None

    def _handle_automap_apply(self):
        """Simulates clicking 'Apply' and waits for the confirmation dialog."""
        apply_btn = self._get_automap_buttons()
        if apply_btn:
            # Ustawiamy flagę. Tkinter messagebox jest blokujący. Kiedy messagebox się zamknie,
            # kontrola wróci i _next_step zostanie wywołane ponownie, przesuwając nas do kroku 11.
            self.automap_dialog_open = True
            self._simulate_app_action(apply_btn.invoke)
        else:
            self.app.status_var.set("Tutorial Error: Could not find 'Apply' button in Auto-map popup. Skipping...")
            self._next_step()

    def _define_steps(self):
        """Defines the tutorial steps, elements, and descriptions with actions."""
        if self.steps is None:
            import os

            # Musisz mieć plik block.properties w tym samym katalogu
            file_path = os.path.abspath("block.properties")

            self.steps = [
                {
                    "widget": self.app.load_properties_button,
                    "text": "1/15: **Load File**.\n\nThis is where you load the `block.properties` file from shader.\nTo demonstrate how it works, we'll temporarily load the file.\n\nAs You can see, already done.",
                    "side": tk.BOTTOM,
                    "action": lambda: self._simulate_app_action(
                        lambda: self.app.manager.load_file(file_path) and self.app.update_all_views())
                },
                {
                    "widget": self.app.before_widget,
                    "text": "2/15: **Before (Original)**.\n\nIn this panel you see the original contents of the `block.properties` file after loading.",
                    "side": tk.RIGHT,
                },
                {
                    "widget": self.app.after_widget,
                    "text": "3/15: **After (Merged)**.\n\nIn this panel, you can see the current contents of the file, including any changes made.\nOf course, there are no changes at this point, but we'll get to that in a moment.\nThis is also the version that will be saved to the new file.",
                    "side": tk.LEFT,
                },
                {
                    "widget": self.app.history_tree,
                    "text": "4/15: **History**.\n\nThis tracks all file modifications.\nYou can double-click to go back to any point in the history if something goes wrong.",
                    "side": tk.TOP,
                },
                {
                    "widget": self.app.items_text,
                    "text": "5/15: **New Items**.\n\nYou paste new entries here.\nWe'll temporarily enter `my_mod:stone_wall` to see the suggestions (Next step).\nWe recommend pasting items in groups, e.g. all blocks relating to doors, walls, etc.",
                    "side": tk.RIGHT,
                    "action": lambda: self._simulate_app_action(
                        lambda: self.app.items_text.insert(tk.END, "my_mod:stone_wall"))
                },
                {
                    "widget": self.app.suggestions_tree,
                    "text": "6/15: **Suggestions**.\n\nBased on the entered elements, the system suggests which category (block.*) they might fit into.\nThe percentage (and color) indicates the certainty of a match.",
                    "side": tk.RIGHT,
                },
                {
                    "widget": self.app.category_listbox,
                    "text": "7/15: **Category Explorer**.\n\nIf you know which category you want to add items to, you can manually select it here.\nYou just have to click on it.",
                    "side": tk.LEFT,
                },
                {
                    "widget": self.app.auto_map_button,
                    "text": "8/15: **Auto-map**.\n\nThis tool automatically maps new elements to templates defined in the `auto_rules.txt` file, which is created when you first run the program.\nIt will also contain instructions on how to add new templates. However, let's move on.**",
                    "side": tk.TOP,
                    # LOGIKA KROKU 8: ZWALNIA GRAB, OTWIERA POPUP, WYMUSZA FOCUS NA POPUPIE.
                    # Jest OK, ponieważ grab_release() działa na aktualnie istniejącym oknie
                    "action": lambda: (
                        self.tutorial_window.grab_release() if self.tutorial_window else None,
                        # KLUCZOWA POPRAWKA: Upewnij się, że stare okno jest zniszczone przed otwarciem nowego
                        (self.app.automap_popup.destroy() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None),
                        setattr(self.app, 'automap_popup', None), # Zresetuj referencję
                        self._simulate_app_action(lambda: self.app.on_auto_map()),
                        self.app.automap_popup.attributes("-topmost",
                                                          True) if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None,
                        self.app.automap_popup.lift() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None, # Lift po ustawieniu topmost
                        self.app.automap_popup.focus_force() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None,
                        self.app.update_idletasks()
                    )
                },
                {
                    "widget": self.app,
                    "text": "9/15: **Preview of mapping**.\n\nThis is a preview of the mapping.\nHere you can see the categories (blocks) that will be modified by auto-mapping.\nDon't worry, we're not breaking the current mapping in the file.\nFor now, let's see what happens after clicking **Apply**\n\n (THIS CAN TAKE FEW SECONDS, don't worry)",
                    "side": tk.TOP,
                    "custom_widget_getter": lambda: self.app.automap_popup.winfo_children()[
                        2] if self.app.automap_popup and self.app.automap_popup.winfo_exists() else self.app.target_category_label,
                    # --- POPRAWIONA AKCJA DLA KROKU 9 ---
                    # Akcja skupia się TYLKO na popupie, nie na samouczku.
                    "action": lambda: (
                        self.app.automap_popup.attributes("-topmost",
                                                          True) if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None, # Ustaw na wierzchu
                        self.app.automap_popup.lift() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None, # Podnieś
                        self.app.automap_popup.focus_force() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None,
                        self.app.update_idletasks()
                        # USUNIĘTO: self.tutorial_window.grab_set() i self.tutorial_window.focus_force()
                    ),
                    # --- KONIEC POPRAWIONEJ AKCJI ---
                    "delay": 500
                },
                {
                    "widget": self.app,
                    "text": "10/15: **Apply changes**.\n\n\n[LET'S WAIT FOR END, one sec.. popup window will show up.]\n\n\nThe changes have been applied, and you've just uploaded your first mapping.\n\nCongratulations!",
                    "side": tk.TOP,
                    "action": lambda: (
                        self.tutorial_window.grab_release() if self.tutorial_window else None,
                        # ZWALNIA GRAB, ABY WIDŻETY W POPUPIE BYŁY KLIKALNE
                        self.app.automap_popup.attributes("-topmost",
                                                          True) if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None, # Ustaw na wierzchu
                        self.app.automap_popup.lift() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None, # Podnieś
                        self.app.automap_popup.focus_force() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else None,
                        self.app.update_idletasks(),
                        self._handle_automap_apply()
                    ),
                    "custom_widget_getter": lambda: self._get_automap_buttons() if self.app.automap_popup and self.app.automap_popup.winfo_exists() else self.app.target_category_label,
                },
                {
                    "widget": self.app.after_widget,
                    "text": "11/15: **Visible list**.\n\nAfter applying the changes, the Auto-map window closes.\nThe changes are visible in this list (click next to show you where exactly).",
                    "side": tk.BOTTOM,
                    # Akcja to brak akcji, ponieważ _next_step po messagebox jest wystarczające
                },
                {
                    "widget": self.app.after_widget.text,
                    "text": "12/15: **Changes (After)**.\n\nSee, the lines highlighted in green are lines that have been changed in some way (yes, I know, for polishing).\nTypically, the only lines you'll see here are:\n1. Your mod's line, of course (if it's not already there)\n2. The line of the preceding mod or block (because you have to break the line to keep the formatting correct, right?)",
                    "side": tk.LEFT,
                    "action": lambda: self._simulate_app_action(lambda: self.app.scroll_to_first_added())
                },
                {
                    "widget": self.app.template_checkbutton,  # POPRAWKA: Zwraca obiekt widżetu!
                    "text": "13/15: **Use Template**.\n\nInstead of automapping, you can use a template from the `block.properties` file to do some manual work.\n\nIt works on a cool principle: you select an item (we recommend the one from vanilla Minecraft), and the program automatically searches for all instances of it—including instances with different blockstates.\n\nThis is important because many blocks (e.g., stone_wall) don't appear without them.\nHowever, let's enable this mode.",
                    "side": tk.LEFT,
                    "action": lambda: self._simulate_app_action(
                        lambda: self.app.use_template_var.set(True) and self.app.on_template_toggle())
                },
                {
                    "widget": self.app.after_widget, # Zakładam, że self.app.after_widget jest ramką, w której są dodawane nowe itemy.
                    "text": "14/15: **Suggestions**.\n\nRemember that you can also simply select a suggested category and add items manually (**Add/Apply Changes** button) if there's no Template you're happy with.\n\nNOTE: adding via **Suggestions** only adds a single entry.\n\nIt's recommended to use this only for simple items (no blockstates), or simply be prepared to add all blockstates manually...",
                    "side": tk.BOTTOM,
                    # --- KLUCZOWA ZMIANA: Dodaj akcję automatycznego dodania przedmiotu ---
                    "action": lambda: (
                        self.app.items_text.delete("1.0", tk.END),
                        self.app.items_text.insert(tk.END, "my_mod:oak_door"),
                        self.app.update_idletasks(),
                    ),
                    # --- KONIEC KLUCZOWEJ ZMIANY ---
                },
                {
                    "widget": self.app.start_tutorial_button,
                    "text": "15/15: **End of Tutorial**.\n\nOkay, you made it to the end, which means you're interested in the program – great.\n\nRemember, if you see any problems with the program's functionality, please report them on my GitHub profile: **https://github.com/Shhadow337**.\n\n\nAnd one last thing: after finishing the tutorial, I recommend resetting the program – just in case something goes wrong :D",
                    "side": tk.BOTTOM,
                },
            ]
        return self.steps

    def start_tutorial(self):
        """Initializes and starts the tutorial."""
        # W pierwszej kolejności upewniamy się, że kroki są zdefiniowane
        if self.steps is None:
            self._define_steps()

        if not self.steps:
            messagebox.showinfo("Tutorial", "No tutorial steps defined.")
            return

        # --- ZAPISZ STAN POCZĄTKOWY ---
        self.original_file_path = self.app.current_file_path
        self.original_items_text = self.app.items_text.get("1.0", tk.END)
        self.original_template_state = self.app.use_template_var.get()
        self.original_active_target_category = self.app._active_target_category # Save active target
        self.automap_dialog_open = False # KLUCZOWA POPRAWKA: Zresetuj flagę przy starcie

        # --- SAVE CURRENT SESSION (so we can restore it after tutorial) ---
        try:
            saved = False
            try:
                saved = self.app.manager.save_session(self.app.tutorial_start_session_path)
            except Exception:
                saved = False

            if not saved:
                messagebox.showerror("Tutorial Error",
                                     f"Failed to save session to {self.app.tutorial_start_session_path}. Tutorial aborted.")
                return
            else:
                self.app.status_var.set(
                    f"Session saved to {self.app.tutorial_start_session_path} before starting tutorial.")
        except Exception as e:
            messagebox.showerror("Tutorial Error", f"Failed to save session before tutorial: {e}")
            return

        # --- NOW LOAD INITIAL STATE for tutorial to run on clean data ---
        try:
            self.app.clear_app_state()
        except Exception as e:
            messagebox.showerror("Tutorial Error", f"Failed to load initial state for tutorial: {e}")
            # cleanup the saved session because we couldn't load initial state
            try:
                if os.path.exists(self.app.tutorial_start_session_path):
                    os.remove(self.app.tutorial_start_session_path)
            except Exception:
                pass
            return

        # KLUCZOWA POPRAWKA 1: Wymuś, by główne okno było ZAWSZE NA WIERZCHU
        self.app.attributes("-topmost", True)
        self.app.lift()  # Podnieś okno na wierzch stosu okien

        # Wymuś aktualizację geometrii okna głównego, aby uniknąć problemów z pozycjonowaniem pierwszego kroku
        self.app.update_idletasks()

        # Disable main window interaction
        self.app.attributes("-disabled", True)
        self.app.tutorial_mode_active = True
        self.app.status_var.set("Tutorial Mode Active. Click Next to continue.")

        self.current_step_index = -1
        self._next_step()

    def _next_step(self):
        """Moves to the next step or finishes the tutorial."""
        if self.tutorial_window:
            self.tutorial_window.destroy()

        self.current_step_index += 1

        if self.current_step_index >= len(self.steps):
            self._finish_tutorial()
            return

        step = self.steps[self.current_step_index]
        self._show_step(step)

    def _show_step(self, step):
        """Creates and displays the Toplevel window for the current step."""
        widget = step["widget"]
        description = step["text"]

        # --- CUSTOM WIDGET/POPUP HANDLING ---
        # 1. Sprawdź, czy cel jest w oknie popup (np. Auto-map preview)
        popup_getter = step.get("custom_widget_getter")

        # KLUCZOWA POPRAWKA: Upewnij się, że popup istnieje, zanim spróbujesz go użyć
        if not (self.app.automap_popup and self.app.automap_popup.winfo_exists()) and self.current_step_index in [8, 9]:
             self.app.status_var.set(f"Tutorial Error: Auto-map popup not found at step {self.current_step_index + 1}. Skipping.")
             self._next_step()
             return
        if popup_getter:
            target_widget = popup_getter()
            # Jeśli to jest krok 10 (indeks 9) i dialog z Apply jest aktywowany
            if self.current_step_index == 9 and self.automap_dialog_open:
                # Oznacza, że akcja 'Apply' została wywołana i oczekujemy na zamknięcie messagebox.
                # W Tkinterze messagebox jest blokujący, więc jeśli kod tu dotarł,
                # to znaczy, że po kliknięciu 'Next' w kroku 9, wywołano akcję,
                # akcja kliknęła 'Apply', i po zamknięciu messagebox kontrola powróciła do _next_step
                # a teraz jesteśmy w _show_step dla kroku 10 (indeks 9).
                # W tym miejscu chcemy się cofnąć do _next_step, aby przejść do kroku 11.
                self.automap_dialog_open = False
                self._next_step()
                return

            # W przeciwnym razie użyjemy znalezionego widżetu
            if target_widget and target_widget.winfo_exists():
                widget = target_widget
            else:
                # Fallback, jeśli okno popup nie jest jeszcze otwarte (krok 8)
                if self.current_step_index == 8:
                    # Zwalniamy focus, by system operacyjny mógł aktywować okno popup
                    try:
                        self.app.grab_release()
                    except tk.TclError:
                        pass

                    # TA AKCJA JEST ZDUPLIKOWANA! Została już wywołana przez step.get("action")
                    # self._simulate_app_action(lambda: self.app.on_auto_map())  # Otwórz popup


                    # Po otwarciu popupu, upewniamy się, że jest na wierzchu
                    if self.app.automap_popup and self.app.automap_popup.winfo_exists():

                        # Ustawiamy, że popup też ma być zawsze na wierzchu i sfocusowany.
                        # To pomaga, gdy samouczek jest na wierzchu.
                        self.app.automap_popup.attributes("-topmost", True)
                        self.app.automap_popup.lift()
                        self.app.automap_popup.focus_force()

                        # Wracamy do ustawiania widget = target_widget
                        widget = popup_getter()

                        # --- PONOWNE ZŁAPANIE FOKUSU PRZEZ SAMOUCZEK ---
                        # To jest niezbędne. Samouczek musi złapać focus z powrotem,
                        # by użytkownik mógł kliknąć "Next".
                        self.tutorial_window.grab_set()
                        self.tutorial_window.focus_force()
                    else:
                        # Jeśli popup się nie otworzył, kontynuuj
                        self.app.status_var.set("Błąd: Nie udało się otworzyć okna Auto-map Preview.")
                        self._next_step()
                        return

            # Wykonaj akcję przed pokazaniem kroku
        if step.get("action"):
            step["action"]()

        # 1. Create Toplevel Window
        self.tutorial_window = tk.Toplevel(self.app)
        self.tutorial_window.title(f"Tutorial Krok {self.current_step_index + 1}/15")
        self.tutorial_window.overrideredirect(True)  # Remove border/title bar
        self.tutorial_window.attributes("-topmost", True)

        # 2. Add Content
        frame = ttk.Frame(self.tutorial_window, padding="10", relief="raised", borderwidth=2)
        frame.pack(fill=tk.BOTH, expand=True)

        # Highlight the current widget (optional - a visual highlight is nice)
        # widget.focus_set() # <--- USUŃ TĘ LINIĘ! To powoduje błąd!

        # Description Label
        desc_label = ttk.Label(frame, text=description, wraplength=300, justify=tk.LEFT,
                               font=('TkDefaultFont', 10, 'bold'))
        desc_label.pack(pady=5, padx=5, fill=tk.X)

        # --- Frame for buttons ---
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=5)

        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        #  Stop button ---
        stop_button = ttk.Button(button_frame, text="Stop Tutorial", command=self._finish_tutorial)
        stop_button.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        # --- Next Button ---
        next_button = ttk.Button(button_frame, text="Next »", command=self._next_step, style="Accent.TButton")
        next_button.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0))

        # 3. Position the window
        self.tutorial_window.update_idletasks()  # Ensure sizes are correct

        # Upewnij się, że widżet istnieje i jest widoczny, zanim pobierzesz jego koordynaty
        if not widget.winfo_exists():
            widget = self.app.load_properties_button  # Fallback

        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_w = widget.winfo_width()
        widget_h = widget.winfo_height()

        win_w = self.tutorial_window.winfo_width()
        win_h = self.tutorial_window.winfo_height()

        # Prosta logika pozycjonowania
        pos_x = widget_x
        pos_y = widget_y + widget_h + 10  # 10 pixels below

        # Jeśli samouczek wykracza poza prawą krawędź ekranu
        if pos_x + win_w > self.app.winfo_screenwidth():
            pos_x = self.app.winfo_screenwidth() - win_w - 20

        # Jeśli samouczek wykracza poza dolną krawędź, przenieś go nad widżet
        if pos_y + win_h > self.app.winfo_screenheight() and widget_y - win_h - 10 > 0:
            pos_y = widget_y - win_h - 10

        # POPRAWKA: Usunięto zduplikowany, błędny blok kodu z poprzedniej rundy (który zawierał konfigurację Toplevel).

        self.tutorial_window.geometry(f"+{pos_x}+{pos_y}")

        # Make the tutorial modal by grabbing focus
        if self.tutorial_window and self.tutorial_window.winfo_exists():
            self.tutorial_window.grab_set()
            self.tutorial_window.focus_force()  # Utrzymanie fokusu

    def _finish_tutorial(self):
        """Cleans up and restores the main application."""
        if self.tutorial_window:
            self.tutorial_window.destroy()

        # --- PRZYWRÓĆ STAN POCZĄTKOWY ---
        # 1. Przywróć pole items_text
        self.app.items_text.delete("1.0", tk.END)
        self.app.items_text.insert("1.0", self.original_items_text)

        # 2. Wyłącz tryb szablonów, jeśli był wyłączony
        if not self.original_template_state and self.app.use_template_var.get():
            self.app.use_template_var.set(False)
            self.app.on_template_toggle()
        elif self.original_template_state and not self.app.use_template_var.get():
            # Włącz tryb, jeśli był włączony na początku
            self.app.use_template_var.set(True)
            self.app.on_template_toggle()

        # 3. Przywróć stan BlockPropertiesManager z zapisanego session
        tutorial_path = getattr(self.app, "tutorial_start_session_path", None)
        if tutorial_path and os.path.exists(tutorial_path):
            try:
                restored_manager = BlockPropertiesManager.load_session(tutorial_path)
                if restored_manager:
                    self.app.manager = restored_manager
                    self.app.current_file_path = self.original_file_path
                    self.app._active_target_category = self.original_active_target_category
                    if self.app.current_file_path:
                        self.app.title(f"Minecraft Properties Merger - {os.path.basename(self.app.current_file_path)}")
                    else:
                        self.app.title("Minecraft Properties Merger")
                else:
                    messagebox.showerror("Tutorial Cleanup Error", "Failed to load session saved before tutorial.")
            except Exception as e:
                messagebox.showerror("Tutorial Cleanup Error", f"Error restoring session saved before tutorial: {e}")
            finally:
                try:
                    os.remove(tutorial_path)
                except Exception:
                    pass
        else:
            # fallback: clear manager state
            self.app.manager.original_elements = {}
            self.app.manager.modified_elements = {}
            self.app.manager.history_stack.clear()
            self.app.manager.redo_stack.clear()
            self.app.manager.history_descriptions.clear()
            self.app.current_file_path = None
            self.app._active_target_category = None
            self.app.title("Minecraft Properties Merger")

        self.app.update_all_views()  # Upewnij się, że widok jest odświeżony

        # 5. Upewnij się, że okno auto-map jest zamknięte
        if self.app.automap_popup and self.app.automap_popup.winfo_exists():
            self.app.automap_popup.destroy()
            self.app.automap_popup = None

        # Re-enable main window interaction
        self.app.attributes("-disabled", False)
        self.app.tutorial_mode_active = False

        # KLUCZOWA POPRAWKA 2: Przywróć normalne zachowanie okna
        self.app.attributes("-topmost", False)

        self.app.status_var.set("Tutorial finished. Ready.")

        # Release focus grab
        try:
            self.app.grab_release()
        except tk.TclError:
            pass  # Ignore if not grabbed

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Iris Properties Merger")

        # DEFAULT session filename (saved in working directory)
        self.DEFAULT_SESSION_FILENAME = "last_session.session"
        self.default_session_path = os.path.join(os.getcwd(), self.DEFAULT_SESSION_FILENAME)
        # Path for the session saved right before starting the tutorial
        self.tutorial_start_session_filename = "tutorial_start.session"
        self.tutorial_start_session_path = os.path.join(os.getcwd(), self.tutorial_start_session_filename)

        # --- Theme Colors ---
        self.themes = {
            "dark": {
                "bg": "#2b2b2b", "fg": "#dcdcdc",
                "entry_bg": "#3c3f41", "entry_fg": "#dcdcdc",
                "button_bg": "#4a4d4f", "button_fg": "#dcdcdc",
                "accent_bg": "#0078d7", "accent_fg": "white",
                "list_bg": "#3c3f41", "list_fg": "#dcdcdc", "list_select_bg": "#0078d7",
                "diff_add_bg": "#0d3d1a", "diff_add_fg": "#77e594",
                "disabled_bg": "#3c3f41", "disabled_fg": "#6e6e6e",
                "tree_heading_bg": "#4a4d4f", "items_text_bg": "#313335",
                "suggestion_gradient": ["#d32f2f", "#e6a200", "#a5b831", "#41802e", "#45935f"],
                "item_new_fg": "#77e594",  # A slightly brighter green for readability on dark bg
                "item_partial_fg": "#ffc700",  # Orange/Yellow
                "item_exists_fg": "#d32f2f",  # Dark Red
                "highlight_color": "#45935f"
            },
            "light": {
                "bg": "#f0f0f0", "fg": "black",
                "entry_bg": "white", "entry_fg": "black",
                "button_bg": "#e0e0e0", "button_fg": "black",
                "accent_bg": "#0078D7", "accent_fg": "white",
                "list_bg": "white", "list_fg": "black", "list_select_bg": "#0078d7",
                "diff_add_bg": "#d4edda", "diff_add_fg": "#155724",
                "disabled_bg": "#f0f0f0", "disabled_fg": "#a0a0a0",
                "tree_heading_bg": "#e0e0e0", "items_text_bg": "#ffffff",
                "suggestion_gradient": ["#d32f2f", "#e6a200", "#a5b831", "#41802e", "#45935f"],
                "item_new_fg": "#155724",  # Dark Green
                "item_partial_fg": "#e6a200",  # Dark Orange
                "item_exists_fg": "#d32f2f",  # Dark Red
                "highlight_color": "#45935f"
            }
        }
        self.style = ttk.Style(self)
        self.geometry("1200x800")

        self.manager = BlockPropertiesManager()
        self.current_file_path = None
        self._active_target_category = None
        self.automap_popup = None

        # mapping suggestion storage: map tree item id -> mapped tuples list from automap_items
        self._suggestion_auto_mappings = {}
        # currently selected automap suggestion (mapped list) or None
        self._selected_auto_mapping = None
        # cache loaded auto_rules to avoid reloading for every line
        self._cached_auto_rules = None

        # --- KLUCZOWA POPRAWKA A: Inicjalizacja atrybutu szablonów ---
        self._available_templates = []
        # -----------------------------------------------------------

        # --- NEW TUTORIAL/WIDGET STATE ---
        self.tutorial_manager = TutorialManager(self)
        self.tutorial_mode_active = False
        self.load_properties_button = None  # Placeholder for widget reference
        self.start_tutorial_button = None  # NOWY: Referencja do przycisku samouczka
        self.auto_map_button = None  # NOWY: Referencja do przycisku Auto-map

        # --- Initial state for "Clear" button ---
        self.initial_session_path = None
        self._save_initial_app_state() # Save the initial state right after setup

        # If there is a last_session.session in current working dir, ask user whether to load it
        try:
            if os.path.exists(self.default_session_path):
                if messagebox.askyesno("Load session",
                                       "A saved session was found in this folder. Do you want to load it?"):
                    # call helper (implemented below)
                    self.load_default_session()
        except Exception as e:
            # don't stop startup if something goes wrong
            print(f"Session startup check error: {e}")

        # --- Main Layout ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        # Theme switcher button
        self.theme_button = ttk.Button(top_frame, text="Light Mode", command=self.toggle_theme)
        self.theme_button.pack(side=tk.RIGHT, padx=5)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1, minsize=200)  # Set a minsize and smaller weight
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_columnconfigure(2, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # --- Top Frame Widgets ---
        self.load_properties_button = ttk.Button(top_frame, text="Load block.properties",command=self.load_properties_file)
        self.load_properties_button.pack(side=tk.LEFT, padx=5)

        self.work_in_progress_label = tk.Label(
            top_frame,
            text="WORK IN PROGRESS – DO NOT EXIT PROGRAM",
            bg="#0078d7", fg="white", font=("TkDefaultFont", 10, "bold"),
            padx=16, pady=5
        )
        self.work_in_progress_label.pack(side=tk.LEFT, padx=5)
        self.work_in_progress_label.pack_forget()

        self.progressbar = ttk.Progressbar(top_frame, mode='indeterminate', length=200)
        self.progressbar.pack_forget()

        # ttk.Button(top_frame, text="Load block.properties", command=self.load_properties_file).pack(side=tk.LEFT,
        #                                                                                             padx=5)
        # For clarity, session management can be grouped
        # ttk.Button(top_frame, text="Load Session", command=self.load_session).pack(side=tk.LEFT, padx=5)
        # ttk.Button(top_frame, text="Save Session", command=self.save_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Save As...", command=self.save_properties_file, style="Accent.TButton").pack(
            side=tk.RIGHT, padx=5)

        # --- NEW TUTORIAL BUTTON ---
        self.start_tutorial_button = ttk.Button(top_frame, text="Start Tutorial", command=self.tutorial_manager.start_tutorial)
        self.start_tutorial_button.pack(side=tk.RIGHT, padx=5)

        # --- NEW CLEAR BUTTON ---
        self.clear_button = ttk.Button(top_frame, text="Clear", command=self.clear_app_state)
        self.clear_button.pack(side=tk.RIGHT, padx=5) # Placed next to Start Tutorial

        # --- LOAD LAST SESSION BUTTON ---
        self.load_last_session_button = ttk.Button(top_frame, text="Load Last Session",command=self.load_default_session)
        self.load_last_session_button.pack(side=tk.RIGHT, padx=5)

        # --- Center Panel (Diff View with Synchronized Scrolling) ---
        center_container = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        center_container.grid(row=0, column=1, sticky="nswe")

        # New History Panel
        history_frame = ttk.LabelFrame(center_container, text="History", padding="5")
        center_container.add(history_frame, weight=1)  # Smaller weight
        self.history_tree = ttk.Treeview(history_frame, show="tree", columns=("action",))
        self.history_tree.heading("#0", text="Action")
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        self.history_tree.bind("<Double-1>", self.on_history_select)

        # Diff Panel Container (to hold the diff and its scrollbars)
        diff_container = ttk.Frame(center_container)
        center_container.add(diff_container, weight=4)  # Larger weight
        diff_container.grid_rowconfigure(0, weight=1)
        diff_container.grid_columnconfigure(0, weight=1)

        diff_panel = ttk.PanedWindow(diff_container, orient=tk.HORIZONTAL)
        diff_panel.grid(row=0, column=0, sticky="nswe")

        v_scrollbar = ttk.Scrollbar(diff_container, orient=tk.VERTICAL, command=self.on_vertical_scroll)
        v_scrollbar.grid(row=0, column=1, sticky="ns")

        h_scrollbar = ttk.Scrollbar(diff_container, orient=tk.HORIZONTAL, command=self.on_horizontal_scroll)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        before_frame = ttk.LabelFrame(diff_panel, text="Before (Original)", padding="5")
        diff_panel.add(before_frame, weight=1)
        self.before_widget = TextWithLineNumbers(before_frame, wrap=tk.NONE, state=tk.DISABLED,
                                                 yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.before_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        after_frame = ttk.LabelFrame(diff_panel, text="After (Merged)", padding="5")
        diff_panel.add(after_frame, weight=1)
        self.after_widget = TextWithLineNumbers(after_frame, wrap=tk.NONE,
                                                yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.after_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.before_widget.text.bind("<MouseWheel>", self.on_mouse_wheel)
        self.after_widget.text.bind("<MouseWheel>", self.on_mouse_wheel)

        # --- Left Panel (New Items & Suggestions) ---
        left_panel = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        left_panel.grid(row=0, column=0, sticky="nswe", padx=(0, 10))

        items_frame = ttk.LabelFrame(left_panel, text="New Items to Add", padding="5")
        left_panel.add(items_frame, weight=1)

        self.items_text = tk.Text(items_frame, height=10, wrap=tk.WORD, borderwidth=2, relief="sunken")
        self.items_text.pack(fill=tk.BOTH, expand=True)
        self.items_text.bind("<<Modified>>", self.on_items_text_changed)

        suggestions_frame = ttk.LabelFrame(left_panel, text="Suggestions", padding="10")
        left_panel.add(suggestions_frame, weight=2)  # Give suggestions more space

        self.suggestions_tree = ttk.Treeview(suggestions_frame, show="tree", selectmode="extended")
        self.suggestions_tree.pack(fill=tk.BOTH, expand=True)
        self.suggestions_tree.bind("<<TreeviewSelect>>", self.on_suggestion_select)
        self.suggestions_tree["columns"] = ("text",)

        # --- Right Panel (Actions & Category Explorer) ---
        self.right_panel = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.right_panel.grid(row=0, column=2, sticky="nswe", padx=(10, 0))

        self.actions_frame = ttk.LabelFrame(self.right_panel, text="Actions", padding="10")
        self.right_panel.add(self.actions_frame)  # Use .add() for PanedWindow children
        self.actions_frame.bind("<Configure>", self._on_actions_frame_configure)

        self.use_template_var = tk.BooleanVar(value=False)

        # --- KLUCZOWA POPRAWKA A ---
        self.template_checkbutton = ttk.Checkbutton(self.actions_frame, text="Use Template",
                                                    variable=self.use_template_var,
                                                    command=self.on_template_toggle)
        self.template_checkbutton.pack(anchor=tk.W)
        # -----------------------------

        self.template_label = ttk.Label(self.actions_frame, text="Select a template item from the list below:")
        # Initially hidden

        self.template_search_var = tk.StringVar()
        self.template_search_var.trace_add("write", self.filter_templates)
        self.template_search_entry = ttk.Entry(self.actions_frame, textvariable=self.template_search_var)
        # Initially hidden

        self.template_listbox = tk.Listbox(self.actions_frame, height=6)
        self.template_listbox.bind("<<ListboxSelect>>", self.select_template_from_list)
        # Initially hidden

        self.selected_template_label = ttk.Label(self.actions_frame, text="Template: None")
        # Initially hidden

        # --- Target Category Display ---
        ttk.Separator(self.actions_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        # Use a Text widget to allow for partial text styling (highlighting)
        self.target_category_label = tk.Text(
            self.actions_frame,
            height=1,  # Start with a height of 1, it will auto-adjust
            font=("TkDefaultFont", 9, "bold"),
            wrap=tk.WORD,
            borderwidth=0,
            highlightthickness=0,
            relief=tk.FLAT,  # Makes it look like a label
        )
        self.target_category_label.pack(anchor=tk.W, pady=(0, 5), fill=tk.X)

        ttk.Button(self.actions_frame, text="Add/Apply Changes", command=self.apply_changes).pack(fill=tk.X, pady=5)
        # ZMIEŃ: Przypisz przycisk Auto-map do zmiennej instancji
        self.auto_map_button = ttk.Button(self.actions_frame, text="Auto-map", command=self.on_auto_map)
        self.auto_map_button.pack(fill=tk.X, pady=5)

        ttk.Button(self.actions_frame, text="Sort Category", command=self.sort_category).pack(fill=tk.X, pady=5)

        ttk.Button(self.actions_frame, text="New Category", command=self.create_new_category).pack(fill=tk.X, pady=5)

        undo_redo_frame = ttk.Frame(self.actions_frame)
        undo_redo_frame.pack(fill=tk.X, pady=5)
        ttk.Button(undo_redo_frame, text="Undo", command=self.undo_action).pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                                padx=(0, 2))
        ttk.Button(undo_redo_frame, text="Redo", command=self.redo_action).pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                                padx=(2, 0))

        category_frame = ttk.LabelFrame(self.right_panel, text="Category Explorer", padding="5")
        self.right_panel.add(category_frame, weight=1)

        self.category_filter_var = tk.StringVar()
        self.category_filter_var.trace_add("write", self.filter_categories)
        category_search = ttk.Entry(category_frame, textvariable=self.category_filter_var)
        category_search.pack(fill=tk.X, pady=(0, 5))

        self.category_listbox = tk.Listbox(category_frame)
        self.category_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.category_listbox.bind("<<ListboxSelect>>", self.on_category_select)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Gotowy")
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor=tk.W, padding="5 2")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Set the initial theme after all widgets are created
        self.set_theme("dark")

        # Set initial text for the target label after theme is set
        self._set_active_target(None)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _save_initial_app_state(self):
        """Saves the initial, empty state of the application to a temporary session file."""
        try:
            fd, path = tempfile.mkstemp(suffix=".session", prefix="initial_app_state_")
            os.close(fd)
            self.initial_session_path = path
            self.manager.save_session(self.initial_session_path)
            # We don't need to save current_file_path or _active_target_category
            # separately here, as they are None at this point, and clear_app_state
            # will explicitly reset them.
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to save initial application state: {e}")
            # If initial state can't be saved, the clear button might not work,
            # but the app should still be usable.

    def clear_app_state(self):
        """Restores the application to its initial state (as if just launched)."""
        if self.tutorial_mode_active:
            messagebox.showwarning("Cannot Clear", "Please finish the tutorial before clearing the application state.")
            return

        if not self.initial_session_path or not os.path.exists(self.initial_session_path):
            messagebox.showerror("Clear Error", "Initial application state not found. Cannot clear.")
            return

        try:
            restored_manager = BlockPropertiesManager.load_session(self.initial_session_path)
            if restored_manager:
                self.manager = restored_manager
                self.current_file_path = None
                self._active_target_category = None
                self.items_text.delete("1.0", tk.END)
                self.use_template_var.set(False)
                self.on_template_toggle() # Ensure template widgets are hidden
                self.title("Minecraft Properties Merger")
                self.update_all_views()
                self.status_var.set("Application state cleared to initial state.")
            else:
                messagebox.showerror("Clear Error", "Failed to load initial session state.")
        except Exception as e:
            messagebox.showerror("Clear Error", f"Error restoring initial session: {e}")

    def set_theme(self, theme_name):
        """Sets the application theme."""
        if getattr(self, "current_theme", None) == theme_name:
            return

        self.current_theme = theme_name
        colors = self.themes[theme_name]

        self.config(bg=colors["bg"])
        self.style.theme_use('clam')

        # General widget styling
        self.style.configure('.', background=colors["bg"], foreground=colors["fg"], fieldbackground=colors["entry_bg"])
        self.style.map('.', background=[('active', colors["button_bg"])])

        # Specific widget styling
        self.style.configure("TFrame", background=colors["bg"], bordercolor=colors["bg"]) # Added bordercolor
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TLabelframe", background=colors["bg"], bordercolor=colors["fg"])
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TButton", background=colors["button_bg"], foreground=colors["fg"])
        self.style.map("TButton", background=[('active', colors["accent_bg"])])
        self.style.configure("Accent.TButton", background=colors["accent_bg"], foreground=colors["accent_fg"])
        self.style.map("Accent.TButton", background=[('active', colors["bg"])])
        self.style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"])
        self.style.map("TCombobox", fieldbackground=[('readonly', colors["entry_bg"])],
                       foreground=[('readonly', colors["fg"])])
        self.style.configure("TEntry", fieldbackground=colors["entry_bg"], foreground=colors["fg"])
        self.style.configure("Treeview", fieldbackground=colors["list_bg"], foreground=colors["fg"])
        self.style.map("Treeview", background=[('selected', colors["list_select_bg"])])
        self.history_tree.tag_configure('oddrow', background=colors["entry_bg"])
        self.history_tree.tag_configure('evenrow', background=colors["list_bg"])

        # Non-ttk widgets
        list_kwargs = {"background": colors["list_bg"], "foreground": colors["fg"],
                       "selectbackground": colors["list_select_bg"]}
        self.category_listbox.config(**list_kwargs)
        self.items_text.config(background=colors["items_text_bg"], foreground=colors["fg"],
                               insertbackground=colors["fg"])
        self.template_listbox.config(**list_kwargs)

        # Template widgets
        self.selected_template_label.config(background=colors["bg"], foreground=colors["fg"])
        self.target_category_label.config(background=colors["bg"], foreground=colors["fg"],
                                          inactiveselectbackground=colors["bg"])

        # Diff view widgets
        self.before_widget.text.config(bg=colors["disabled_bg"], fg=colors["disabled_fg"])
        self.after_widget.text.config(bg=colors["entry_bg"], fg=colors["fg"], insertbackground=colors["fg"])
        self.before_widget.linenumbers.config(bg=colors["disabled_bg"])
        self.after_widget.linenumbers.config(bg=colors["disabled_bg"])

        # Diff tags
        self.after_widget.text.tag_configure("added", background=colors["diff_add_bg"],
                                             foreground=colors["diff_add_fg"])

        # Force update view if manager is loaded
        if self.manager.original_elements:
            self.update_diff_view()
            # Force a refresh of item validation and suggestion colors
            self.highlight_items_in_text()
            self.generate_suggestions()
            self.update_history_view()

        # Style treeview headings
        self.style.configure("Treeview.Heading", background=colors["tree_heading_bg"], foreground=colors["fg"])
        self.suggestions_tree.tag_configure('parent_item', background=colors["tree_heading_bg"],
                                            font=('TkDefaultFont', 9, 'bold'))

        # Item validation tags
        self.items_text.tag_configure("item_new", foreground=colors["item_new_fg"])
        self.items_text.tag_configure("item_partial", foreground=colors["item_partial_fg"])
        self.items_text.tag_configure("item_exists", foreground=colors["item_exists_fg"])

        # A special tag for highlighting parts of the target label
        self.target_category_label.tag_configure("highlight", foreground="#45935f")
        if self.automap_popup and self.automap_popup.winfo_exists():
            self.automap_popup.update_colors()

    def toggle_theme(self):
        if self.current_theme == "dark":
            self.set_theme("light")
            self.theme_button.config(text="Dark Mode")
        else:
            self.set_theme("dark")
            self.theme_button.config(text="Light Mode")

    def on_vertical_scroll(self, *args):
        self.before_widget.text.yview(*args)
        self.after_widget.text.yview(*args)

    def on_mouse_wheel(self, event):  # For Windows/macOS
        delta = -1 * int(event.delta / 120 if self.tk.call('tk', 'windowingsystem') == 'win32' else event.delta)
        self.before_widget.text.yview_scroll(delta, "units")
        self.after_widget.text.yview_scroll(delta, "units")
        return "break"

    def update_diff_view(self):
        original_str, modified_str = self.manager.get_diff()

        self.before_widget.text.config(state=tk.NORMAL)
        self.before_widget.text.delete("1.0", tk.END)
        self.before_widget.text.insert("1.0", original_str)
        self.before_widget.text.config(state=tk.DISABLED)

        self.after_widget.text.delete("1.0", tk.END)
        self.after_widget.text.insert("1.0", modified_str)

        before_lines = original_str.splitlines()
        after_lines = modified_str.splitlines()
        diff = difflib.ndiff(before_lines, after_lines)

        # Poprawiona logika podświetlania
        line_num = 1  # Indeksy linii w widżecie Text zaczynają się od 1

        for line in diff:
            # Linia została dodana. Podświetlamy ją i przesuwamy się do następnej linii.
            if line.startswith('+ '):
                self.after_widget.text.tag_add("added", f"{line_num}.0", f"{line_num}.end")
                line_num += 1
            # Linia jest wspólna (niezmieniona). Nie podświetlamy, ale przesuwamy się do następnej linii.
            elif line.startswith('  '):
                line_num += 1
            # Linia została usunięta ('- ') lub jest linią informacyjną ('? ').
            # Obie nie istnieją w oknie "After", więc ignorujemy je i NIE zwiększamy licznika.
            elif line.startswith('- ') or line.startswith('? '):
                pass

        self.status_var.set("View updated.")

        # --- NOWO: przewiń do pierwszej nowo-dodanej linii (jeśli istnieje) ---
        try:
            self.scroll_to_first_added()
        except Exception:
            pass

        self.scroll_to_last_added_item()

        if hasattr(self, "_last_added_items") and self._last_added_items:
            for item in self._last_added_items:
                idx = self.after_widget.text.search(item, "1.0", tk.END)
                if idx:
                    self.after_widget.text.see(idx)
                    break

    def scroll_to_first_added(self):
        """
        Znajduje pierwsze wystąpienie taga "added" w after_widget i przewija do niego.
        Jeśli nie ma taga "added", nie zmienia widoku.
        """
        try:
            ranges = self.after_widget.text.tag_ranges("added")
            if ranges:
                # tag_ranges zwraca [start1, end1, start2, end2, ...] - weź pierwszy start
                first_start = ranges[0]
                # Upewnij się, że indeks jest widoczny
                self.after_widget.text.see(first_start)
                # Opcjonalnie: ustaw fokus krótko na after_widget, by użytkownik zobaczył pozycję
                # self.after_widget.text.focus_set()
            else:
                # Brak nowych linii - zachowaj obecny widok (możesz ewentualnie przewinąć do góry)
                pass
        except Exception as e:
            # Nie hamujemy działania programu jeśli coś pójdzie nie tak
            self.status_var.set(f"Scroll error: {e}")

    def scroll_to_last_added_item(self):
        """
        Przewija widok 'After (Merged)' do pierwszego z ostatnio dodanych przedmiotów
        wewnątrz ostatnio modyfikowanej kategorii. Szuka substringów w tekście,
        a nie porównuje całych linii — dzięki temu działa gdy elementy są
        w tej samej linii (np. lista rozdzielona przecinkami) lub po sortowaniu.
        """
        try:
            if not (hasattr(self, "_last_added_items") and self._last_added_items and
                    hasattr(self, "_last_added_category") and self._last_added_category):
                return

            full_text = self.after_widget.text.get("1.0", "end")
            cat_id = self._last_added_category.strip()

            # Znajdź pozycję nagłówka kategorii (pierwsze wystąpienie)
            cat_pos = full_text.find(cat_id)
            if cat_pos == -1:
                # fallback: jeśli nie ma nagłówka, po prostu przewiń do pierwszego znalezionego itemu w całym tekście
                for item in self._last_added_items:
                    pos = full_text.find(item)
                    if pos != -1:
                        idx = self.after_widget.text.index(f"1.0+{pos}c")
                        self.after_widget.text.see(idx)
                        return
                return

            # Znajdź koniec tej kategorii: pierwsza podwójna nowa linia po nagłówku lub koniec tekstu
            next_blank = full_text.find("\n\n", cat_pos)
            cat_end_pos = next_blank if next_blank != -1 else len(full_text)

            # Szukaj itemów tylko w obrębie [cat_pos, cat_end_pos)
            for item in self._last_added_items:
                search_start = cat_pos
                while True:
                    pos = full_text.find(item, search_start, cat_end_pos)
                    if pos == -1:
                        break
                    # Znaleźliśmy dopasowanie w zakresie kategorii
                    idx = self.after_widget.text.index(f"1.0+{pos}c")
                    self.after_widget.text.see(idx)
                    return
                    # (gdybyśmy chcieli, można szukać dalej: search_start = pos + len(item))
            # fallback: jeśli nic w zakresie kategorii nie znaleziono, poszukaj gdziekolwiek
            for item in self._last_added_items:
                pos = full_text.find(item)
                if pos != -1:
                    idx = self.after_widget.text.index(f"1.0+{pos}c")
                    self.after_widget.text.see(idx)
                    return
        except Exception as e:
            # Nie hamujemy działania programu jeśli coś pójdzie nie tak
            self.status_var.set(f"Scroll fallback error: {e}")

    def load_properties_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("Properties Files", "*.properties"), ("All Files", "*.*")])
        if not filepath:
            return

        self.show_work_in_progress()

        def task():
            success = self.manager.load_file(filepath)
            if success:
                self.current_file_path = filepath
                self.after(0, self.update_all_views)
                self.after(0, lambda: self.title(f"Minecraft Properties Merger - {os.path.basename(filepath)}"))
                self.after(0, lambda: self.status_var.set(f"Loaded {filepath}"))
            else:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to load or parse file: {filepath}"))

            self.after(0, self.hide_work_in_progress)

        threading.Thread(target=task, daemon=True).start()

    def update_all_views(self):
        self.update_diff_view()
        self.filter_categories()
        self.highlight_items_in_text()
        self.update_history_view()

    def filter_categories(self, *args):
        all_categories = self.manager.get_all_category_ids()
        filter_text = self.category_filter_var.get().lower()
        self.category_listbox.delete(0, tk.END)
        for category in all_categories:
            if filter_text in category.lower():
                self.category_listbox.insert(tk.END, category)

    def update_history_view(self):
        """Refreshes the history panel with the latest actions."""
        self.history_tree.delete(*self.history_tree.get_children())
        for i, description in enumerate(self.manager.history_descriptions):
            tag = 'oddrow' if i % 2 == 1 else 'evenrow'
            self.history_tree.insert("", "end", text=f" {i + 1}. {description}", tags=(tag,))
        # Scroll to the latest action
        self.history_tree.yview_moveto(1)

    def on_items_text_changed(self, event=None):
        """Generate suggestions when text in 'New Items' box changes."""
        # The edit_modified flag is crucial to prevent infinite loops,
        # but we only check it for actual text modifications.
        # Theme changes will call the highlight/generate functions directly.
        if not self.items_text.edit_modified():
            return
        self.highlight_items_in_text()
        self.generate_suggestions()
        self.items_text.edit_modified(False)  # Reset the flag after processing

    def highlight_items_in_text(self):
        """Color each line in the items_text widget based on its existence."""
        # Clear all tags first
        self.items_text.tag_remove("item_new", "1.0", tk.END)
        self.items_text.tag_remove("item_partial", "1.0", tk.END)
        self.items_text.tag_remove("item_exists", "1.0", tk.END)

        lines = self.items_text.get("1.0", tk.END).strip().splitlines()
        for i, line in enumerate(lines):
            if not line.strip(): continue
            status = self.manager.check_item_existence(line)
            start_index = f"{i + 1}.0"
            end_index = f"{i + 1}.{len(line)}"
            self.items_text.tag_add(f"item_{status.lower()}", start_index, end_index)

    def generate_suggestions(self):
        # Clear previous suggestions and automap mappings
        for i in self.suggestions_tree.get_children():
            self.suggestions_tree.delete(i)
        self._suggestion_auto_mappings.clear()
        self._selected_auto_mapping = None

        items_to_add = self.items_text.get("1.0", tk.END).strip().splitlines()
        gradient = self.themes[self.current_theme]["suggestion_gradient"]

        # Try to load rules once (cache)
        if self._cached_auto_rules is None:
            try:
                self._cached_auto_rules = load_rules("auto_rules.txt")
            except Exception:
                self._cached_auto_rules = None

        for item_name in items_to_add:
            if not item_name.strip():
                continue

            parent_id = self.suggestions_tree.insert("", "end", text=item_name, open=True, tags=('parent_item',))

            # 1) AUTO-RULES SUGGESTIONS FIRST (if rules exist)
            auto_added = False
            if self._cached_auto_rules:
                def resolver(template_name: str):
                    return self.manager.get_template_target_property(template_name)

                try:
                    mapped, unmapped = automap_items([item_name], self._cached_auto_rules, resolver, dry_run=True)
                except Exception:
                    mapped, unmapped = [], []

                if mapped:
                    # Insert each automap suggestion first
                    for m in mapped:
                        # m is expected as tuple e.g. (item, template, target) from automap_items
                        tmpl = m[1] if len(m) > 1 else "auto_template"
                        display_text = f"AUTO • {tmpl} (auto)"
                        child_id = self.suggestions_tree.insert(parent_id, "end", text=display_text,
                                                                tags=('auto_rule',))
                        # store mapping for this child so apply_changes can use it
                        self._suggestion_auto_mappings[child_id] = mapped
                    auto_added = True

            # 2) STANDARD SUGGESTIONS (existing logic; keep behaviour)
            suggestions_with_scores = self.manager.suggest_categories_for_items_list([item_name])
            perfect_matches = [s for s in suggestions_with_scores if s[1] >= 1.0]
            other_matches = [s for s in suggestions_with_scores if s[1] < 1.0]

            final_suggestions = perfect_matches
            needed = 2 - len(final_suggestions)
            if needed > 0:
                final_suggestions.extend(other_matches[:needed])

            # Insert standard suggestions AFTER auto rules (so auto are first)
            for category_id, score in final_suggestions:
                display_text = f"{(score * 100):.0f}% - {category_id}"
                color_index = min(int(score * (len(gradient) - 1) + 0.5), len(gradient) - 1)
                color = gradient[color_index]
                tag_name = f"score_{color_index}"
                self.suggestions_tree.tag_configure(tag_name, background=color)
                self.suggestions_tree.insert(parent_id, "end", text=display_text, tags=(tag_name,))

        # Configure the auto_rule tag color (use a greener, highlighted color)
        try:
            auto_color = self.themes[self.current_theme].get("highlight_color", "#45935f")
        except Exception:
            auto_color = "#32cd32"
        self.suggestions_tree.tag_configure('auto_rule', background=auto_color, foreground="white")

    def on_category_select(self, event):
        selected_indices = self.category_listbox.curselection()
        if not selected_indices: return
        category_id = self.category_listbox.get(selected_indices[0])
        self._set_active_target(category_id)

    def on_suggestion_select(self, event):
        selected_item_id = self.suggestions_tree.focus()
        if not selected_item_id or not self.suggestions_tree.parent(selected_item_id):
            return  # Ensure it's a child

        # If this child id is in automap mappings, mark it as selected auto mapping
        if selected_item_id in self._suggestion_auto_mappings:
            self._selected_auto_mapping = self._suggestion_auto_mappings[selected_item_id]
            # Display friendly target (we don't set a plain category, because automap may touch many categories)
            self._update_target_label(text="Auto-mapping selection (press Add/Apply to apply auto-mapped changes)")
            # Also ensure template mode is off
            self.use_template_var.set(False)
            self._active_target_category = None
            return

        # Otherwise, clear any automap selection and handle standard suggestion as before
        self._selected_auto_mapping = None
        suggestion_text = self.suggestions_tree.item(selected_item_id, "text")
        # handle if suggestion_text is like "100% - block.123"
        if ' - ' in suggestion_text:
            category_id = suggestion_text.split(' - ')[-1]
            self._set_active_target(category_id)
        else:
            self._set_active_target(None)

    def _set_active_target(self, category_id: str):
        self._active_target_category = category_id
        self.target_category_label.config(text=f"Target Category: {category_id}")

    def on_history_select(self, event=None):
        """Handles double-clicking an item in the history panel to undo to that point."""
        selected_item_id = self.history_tree.focus()
        if not selected_item_id: return

        # The index of the item in the treeview is its position
        selected_index = self.history_tree.index(selected_item_id)
        num_actions_to_undo = len(self.manager.history_descriptions) - selected_index

        if messagebox.askyesno("Undo to Point", f"This will undo the last {num_actions_to_undo} actions. Continue?"):
            self.show_work_in_progress()
            for _ in range(num_actions_to_undo):
                self.undo_action(update_status=False)
            self.status_var.set(f"Reverted to state before action #{selected_index + 1}.")
            self.after(0, self.hide_work_in_progress)

    def filter_templates(self, *args):
        """Filters the template listbox based on the search entry."""
        filter_text = self.template_search_var.get().lower()
        self.template_listbox.delete(0, tk.END)
        for template in self._available_templates:
            if filter_text in template.lower():
                self.template_listbox.insert(tk.END, template)

    def select_template_from_list(self, event=None):
        """Sets the selected template from the listbox."""
        selected_indices = self.template_listbox.curselection()
        if not selected_indices:
            return
        selected_template = self.template_listbox.get(selected_indices[0])
        self.selected_template_label.config(text=f"Template: {selected_template}")

        # Find and display all categories that will be affected by this template
        target_categories = self.manager.get_target_categories_for_template(selected_template)
        if target_categories:
            # Use a special internal value for the target, but display a user-friendly list
            self._active_target_category = "TEMPLATE_MODE"
            self._update_target_label(target_categories)
        else:
            self._set_active_target(None)  # No categories found for this template

    def on_template_toggle(self):
        if self.use_template_var.get():
            if not self.manager.original_elements:
                messagebox.showwarning("No File", "Load a properties file first to populate templates.")
                self.use_template_var.set(False)
                return

            # Get only base item names for templates
            templates = self.manager.get_all_base_item_names()

            self._available_templates = templates
            self.filter_templates()  # Populate the listbox

            # Show template widgets
            self.template_label.pack(anchor='w', pady=(5, 2))
            self.template_search_entry.pack(fill=tk.X, pady=(0, 5))
            self.template_listbox.pack(fill=tk.X, expand=True, pady=(0, 2))
            self.selected_template_label.pack(anchor='w', pady=(0, 5))
            self.selected_template_label.config(text="Template: None")
            self._set_active_target(None)  # Clear target when enabling template mode

            # Adjust the sash to make the new widgets visible
            self.update_idletasks()
            new_height = self.actions_frame.winfo_reqheight()
            self.right_panel.sashpos(0, new_height + 10)  # +10 for some padding


        else:
            # Hide template widgets
            self.template_label.pack_forget()
            self.template_search_entry.pack_forget()
            self.template_listbox.pack_forget()
            self.selected_template_label.pack_forget()
            self.template_search_var.set("")
            self._set_active_target(None)  # Clear target when disabling template mode
            self.selected_template_label.config(text="Template: None")

            # Adjust the sash back to its original position
            self.update_idletasks()
            new_height = self.actions_frame.winfo_reqheight()
            self.right_panel.sashpos(0, new_height + 10)

    def _on_actions_frame_configure(self, event):
        """Dynamically set the wraplength of the target label when the frame is resized."""
        # Subtract some padding to prevent text from touching the edge
        # This is handled by the Text widget's wrap=tk.WORD, so this function is now a placeholder
        pass

    def _update_target_label(self, content: Optional[list[str]] = None, text: Optional[str] = None):
        """Updates the target label, highlighting the numeric parts of category IDs."""
        self.target_category_label.config(state=tk.NORMAL)
        self.target_category_label.delete("1.0", tk.END)

        if content:  # Highlighted list mode
            self.target_category_label.insert("1.0", "Targets: ")
            for i, category in enumerate(content):
                parts = category.split('.')
                if len(parts) == 2 and parts[1].isdigit():
                    self.target_category_label.insert(tk.END, f"{parts[0]}.")
                    self.target_category_label.insert(tk.END, parts[1], ("highlight",))
                else:
                    self.target_category_label.insert(tk.END, category)
                if i < len(content) - 1:
                    self.target_category_label.insert(tk.END, ", ")
        elif text:  # Simple text mode
            self.target_category_label.insert("1.0", text)

        # Auto-adjust height
        self.target_category_label.update_idletasks()
        num_lines = self.target_category_label.count("1.0", "end", "displaylines")[0]
        self.target_category_label.config(height=num_lines)
        self.target_category_label.config(state=tk.DISABLED)

    def _set_active_target(self, category_id: Optional[str]):
        self._active_target_category = category_id
        display_text = f"Target: {category_id}" if category_id else "Target: None"
        self._update_target_label(text=display_text)
        if category_id:
            self.use_template_var.set(False)  # Uncheck template mode if a category is selected directly

    def apply_mapped_items_with_wip(self, mapped, info_message=None, post_cleanup=None):
        """
        Applies mapped items with WIP label handling.
        Optionally: shows info_message after success, calls post_cleanup (e.g., closing a popup).
        """
        self.show_work_in_progress()

        def task():
            try:
                if not mapped:
                    self.after(0, lambda: messagebox.showinfo("Auto-map", "Brak dopasowań do zastosowania."))
                    return
                self.manager.apply_mapped_items(mapped)
                self.after(0, self.update_all_views)
                if info_message:
                    self.after(0, lambda: messagebox.showinfo("Auto-map", info_message))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Auto-map", f"Błąd podczas stosowania mapowań: {e}"))
            finally:
                # Always cleanup and hide WIP label
                if post_cleanup:
                    self.after(0, post_cleanup)
                self.after(0, self.hide_work_in_progress)

        # Short delay before starting the thread to ensure the UI updates
        self.after(100, lambda: threading.Thread(target=task, daemon=True).start())

    def apply_changes(self):
        # Template Mode
        if self.use_template_var.get():
            template_text = self.selected_template_label.cget("text")
            if "Template: " in template_text and template_text != "Template: None":
                # Save current "After" text so we can diff later and find insertion
                try:
                    self._after_text_before_add = self.after_widget.text.get("1.0", "end")
                except Exception:
                    self._after_text_before_add = ""
                self.show_work_in_progress()

                def task():
                    selected_template = template_text.replace("Template: ", "")
                    self._apply_template_changes(selected_template)
                    self.after(0, self.hide_work_in_progress)

                # Dodanie krótkiej zwłoki przed uruchomieniem wątku
                self.after(100, lambda: threading.Thread(target=task, daemon=True).start())
            else:
                messagebox.showwarning("No Template", "Please select a template from the list.")
            return

        # Automap logic
        if self._selected_auto_mapping:
            mapped = self._selected_auto_mapping
            applied_items = {m[0] for m in mapped}

            def cleanup():
                remaining = [it for it in self.items_text.get("1.0", tk.END).strip().splitlines() if
                             it and it not in applied_items]
                self.items_text.delete("1.0", tk.END)
                if remaining:
                    self.items_text.insert("1.0", "\n".join(remaining))
                self._selected_auto_mapping = None
                self._suggestion_auto_mappings.clear()

            self.apply_mapped_items_with_wip(
                mapped,
                info_message=f"Number of matches used: {len(mapped)}",
                post_cleanup=cleanup
            )
            return

        # Simple Add Logic
        category_id = self._active_target_category
        if not category_id:
            messagebox.showwarning("Input Missing", "Please select a target category.")
            return

        items_to_add = [item for item in self.items_text.get("1.0", tk.END).strip().splitlines() if item]
        self._last_added_items = items_to_add.copy()
        self._last_added_category = category_id
        if not items_to_add or not category_id:
            messagebox.showwarning("Input Missing",
                                   "Please enter items to add AND select a target category (or use Template Mode).")
            return

        self.show_work_in_progress()

        def task():
            try:
                result = self.manager.add_items_to_category(items_to_add, category_id)
                if result:
                    toast_msg = f"Added {len(items_to_add)} items to {category_id}."
                    self.after(0, lambda: ToastNotification(self, toast_msg))
                    self.after(0, lambda: self.status_var.set(toast_msg))
                    self.after(0, lambda: self.items_text.delete("1.0", tk.END))
                else:
                    self.after(0, lambda: ToastNotification(self,
                                                            f"All items already exist in '{category_id}'. Action skipped."))
                self.after(0, self.update_all_views)
            finally:
                self.after(0, self.hide_work_in_progress)

        # Dodanie krótkiej zwłoki przed uruchomieniem wątku
        self.after(100, lambda: threading.Thread(target=task, daemon=True).start())

    def on_auto_map(self):
        """Auto-map handler - reads rules from auto_rules.txt, does dry-run and shows preview,
        then applies mappings if user confirms."""
        rules = load_rules("auto_rules.txt")
        if not rules:
            messagebox.showinfo("Auto-map", "No auto-mapping rules (auto_rules.txt file - remember to have one where You start .exe).")
            return

        # ... (reszta kodu odpowiedzialna za pobranie itemów i automap_items)
        try:
            items_text_raw = self.items_text.get("1.0", tk.END).strip()
            new_items = [l for l in items_text_raw.splitlines() if l]
        except Exception:
            messagebox.showerror("Auto-map", "Nie można odczytać listy nowych itemów z UI.")
            return

        if not new_items:
            messagebox.showinfo("Auto-map", "Brak nowych itemów do zmapowania.")
            return

        def resolver(template_name: str):
            return self.manager.get_template_target_property(template_name)

        mapped, unmapped = automap_items(new_items, rules, resolver, dry_run=True)

        popup = tk.Toplevel(self)
        self.automap_popup = popup
        popup.title("Auto-map preview")
        popup.geometry("900x550")  # ZWIĘKSZONY ROZMIAR OKNA

        header = ttk.Label(popup, text=f"Mapped: {len(mapped)}    Unmapped: {len(unmapped)}",
                           font=('TkDefaultFont', 10, 'bold'))
        header.pack(pady=10)

        # --- SEKCJA DOCELOWYCH KATEGORII (NOWA) ---
        target_cats_frame = ttk.LabelFrame(popup, text="Target Categories (Will Be Modified)", padding="5")
        target_cats_frame.pack(fill=tk.X, padx=10, pady=5)

        target_cats_text = tk.Text(target_cats_frame, height=5, wrap=tk.WORD, borderwidth=1, relief="sunken")
        target_cats_text.pack(fill=tk.BOTH, expand=True)
        target_cats_text.config(state=tk.DISABLED)

        # ZBIERANIE I PRZETWARZANIE KATEGORII DOCELOWYCH
        # 1. Zidentyfikuj unikalne szablony użyte w mapowaniu
        used_templates = set(m[1] for m in mapped)

        # 2. Dla każdego użytego szablonu, znajdź WSZYSTKIE kategorie, które ten szablon modyfikuje.
        all_potential_target_categories = set()
        for template_name in used_templates:
            # manager.get_target_categories_for_template() zwraca wszystkie kategorie
            # zawierające dany 'base item name' (szablon).
            targets = self.manager.get_target_categories_for_template(template_name)
            all_potential_target_categories.update(targets)

        # 3. Posortuj wynikową listę
        target_categories = sorted(list(all_potential_target_categories))

        def _update_target_text_content(text_widget, categories):
            """Lokalna funkcja do wstawiania i tagowania kategorii w nowym widżecie Text."""
            text_widget.config(state=tk.NORMAL)
            text_widget.delete("1.0", tk.END)

            # POBIERZ KOLOR BEZPOŚREDNIO ZE SŁOWNIKA MOTYWÓW
            highlight_color = self.themes[self.current_theme]["highlight_color"]
            text_widget.tag_configure("highlight_popup", foreground=highlight_color)

            if not categories:
                text_widget.insert("1.0", "Brak docelowych kategorii.")
                return

            text_widget.insert("1.0", "Targets: ")
            for i, category in enumerate(categories):
                parts = category.split('.')
                # Sprawdzenie i podświetlenie numeru kategorii (np. block.999)
                if len(parts) == 2 and parts[1].isdigit():
                    text_widget.insert(tk.END, f"{parts[0]}.")
                    text_widget.insert(tk.END, parts[1], ("highlight_popup",))
                else:
                    text_widget.insert(tk.END, category)
                if i < len(categories) - 1:
                    text_widget.insert(tk.END, ", ")

            text_widget.config(state=tk.DISABLED)

        _update_target_text_content(target_cats_text, target_categories)
        # --- KONIEC NOWEJ SEKCJI ---

        frame = ttk.Frame(popup)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.LabelFrame(frame, text="Mapped Items (item -> template)", padding="5")  # ZMIENIONA NAZWA
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        mapped_listbox = tk.Listbox(left)
        mapped_listbox.pack(fill=tk.BOTH, expand=True)
        for item, tmpl, target in mapped:
            mapped_listbox.insert(tk.END, f"{item} -> {tmpl}")  # USUNIĘCIE -> TARGET

        right = ttk.LabelFrame(frame, text="Unmapped (item -> reason)", padding="5")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        unmapped_listbox = tk.Listbox(right)
        unmapped_listbox.pack(fill=tk.BOTH, expand=True)
        for item, reason in unmapped:
            unmapped_listbox.insert(tk.END, f"{item} -> {reason}")

        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        def _update_popup_colors():
            try:
                colors = self.themes[self.current_theme]
            except (KeyError, AttributeError):
                colors = self.themes["light"]  # Fallback

            listbox_config = {
                "background": colors.get("list_bg", "white"),
                "foreground": colors.get("fg", "black"),
                "selectbackground": colors.get("list_select_bg", "#0078D7"),
                "selectforeground": colors.get("accent_fg", "white"),
                "borderwidth": 0,
                "highlightthickness": 0
            }

            popup.config(bg=colors["bg"])
            mapped_listbox.config(**listbox_config)
            unmapped_listbox.config(**listbox_config)

            # Konfiguracja nowego Text widget
            target_cats_text.config(
                background=colors["items_text_bg"],
                foreground=colors["fg"],
                selectbackground=colors.get("list_select_bg", "#0078D7"),
                inactiveselectbackground=colors["items_text_bg"]  # Aby wyglądało jak etykieta
            )
            # Musimy ręcznie zaktualizować tag koloru dla numerów kategorii
            target_cats_text.tag_configure("highlight_popup", foreground=colors["highlight_color"])

            # Ponowne wywołanie w celu aktualizacji tagów kolorystycznych
            _update_target_text_content(target_cats_text, target_categories)

        popup.update_colors = _update_popup_colors

        def on_auto_map(self):
            ...

        def apply_and_close():
            applied_items = {m[0] for m in mapped}

            def cleanup():
                remaining = [it for it in new_items if it not in applied_items]
                self.items_text.delete("1.0", tk.END)
                if remaining:
                    self.items_text.insert("1.0", "\n".join(remaining))
                self.update_all_views()
                popup.destroy()
                self.automap_popup = None

            self.apply_mapped_items_with_wip(
                mapped,
                info_message=f"Number of matches used: {len(mapped)}",
                post_cleanup=cleanup
            )

        def cancel_and_close():
            popup.destroy()
            self.automap_popup = None

        popup.protocol("WM_DELETE_WINDOW", cancel_and_close)

        btn_apply = ttk.Button(btn_frame, text="Apply", command=apply_and_close, style="Accent.TButton")
        btn_apply.pack(side=tk.RIGHT)
        btn_cancel = ttk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        btn_cancel.pack(side=tk.RIGHT, padx=5)

        _update_popup_colors()  # Wywołaj funkcję raz, aby ustawić początkowy motyw

    def _apply_template_changes(self, template_item: str):
        """Helper function to apply changes using a template."""
        items_to_add = [item for item in self.items_text.get("1.0", tk.END).strip().splitlines() if item]
        if not items_to_add:
            messagebox.showwarning("No Items", "Please enter items to add for the template.")
            return

        # The manager handles finding the base name. We just pass the full template item.
        result = self.manager.add_items_to_category(items_to_add, category_id="", template_item=template_item)
        if result:
            toast_msg = f"Applied template '{template_item}' for {len(items_to_add)} items."
            ToastNotification(self, toast_msg)
            self.status_var.set(toast_msg)
        else:
            ToastNotification(self, f"Template application resulted in no new items. All may already exist.")
        self.update_all_views()

    def sort_category(self):
        selected_indices = self.category_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Category", "Please select a category to sort.")
            return
        self.show_work_in_progress()
        category_id = self.category_listbox.get(selected_indices[0])
        self.manager.sort_category(category_id)
        self._last_added_items = []
        self._last_added_category = None
        self.update_all_views()
        self.status_var.set(f"Sorted category {category_id}.")
        self.after(0, self.hide_work_in_progress)

    def create_new_category(self):
        """Opens a dialog to create a new category."""
        if not self.manager.original_elements:
            messagebox.showwarning("No File", "Load a properties file first.")
            return

        new_category_id = simpledialog.askstring("New Category", "Enter new category ID (e.g., block.999):",
                                                 parent=self)
        self.show_work_in_progress()
        if new_category_id and new_category_id.strip():
            self.manager.create_new_category(new_category_id.strip())
            self.update_all_views()
            self.status_var.set(f"Created new category: {new_category_id.strip()}")
        else:
            self.status_var.set("New category creation cancelled.")
        self.after(0, self.hide_work_in_progress)

    def undo_action(self, update_status=True):
        self.show_work_in_progress()
        self.manager.undo()
        self.update_all_views()
        if update_status:
            self.status_var.set("Undo successful.")
        self.after(0, self.hide_work_in_progress)

    def redo_action(self, update_status=True):
        self.show_work_in_progress()
        self.manager.redo()
        self.update_all_views()
        if update_status:
            self.status_var.set("Redo successful.")
        self.after(0, self.hide_work_in_progress)

    def save_properties_file(self):
        if not self.manager.original_elements:
            messagebox.showerror("Error", "No file loaded to save.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".properties",
                                                filetypes=[("Properties Files", "*.properties"), ("All Files", "*.*")],
                                                title="Save Properties As")
        if not filepath:
            return

        self.show_work_in_progress()

        def task():
            self.manager.save_to_file(filepath)
            self.show_work_in_progress()
            self.after(0, self.hide_work_in_progress)
            self.after(0, lambda: self.status_var.set(f"File saved to {filepath}"))

        threading.Thread(target=task, daemon=True).start()

    def save_session(self):
        if not self.manager.original_elements:
            messagebox.showwarning("No Data", "Nothing to save.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".session",
                                                filetypes=[("Session Files", "*.session"), ("All Files", "*.*")],
                                                title="Save Session")
        if not filepath:
            return

        self.show_work_in_progress()

        def task():
            ok = self.manager.save_session(filepath)
            self.after(0, self.hide_work_in_progress)
            if ok:
                self.after(0, lambda: self.status_var.set(f"Session saved to {filepath}"))
            else:
                self.after(0, lambda: messagebox.showerror("Save Error", f"Failed to save session to {filepath}"))

        threading.Thread(target=task, daemon=True).start()

    def save_session_to_default(self, show_status=True) -> bool:
        """Save session to default path in current working dir (no dialog)."""
        try:
            # Ensure there's data to save
            if not self.manager or not self.manager.original_elements:
                if show_status:
                    messagebox.showwarning("No Data", "Nothing to save to session.")
                return False

            # Build metadata to store in the manager object
            try:
                has_unsaved_changes = False
                # Determine unsaved-file changes: simple heuristic
                if getattr(self.manager, "modified_elements", None) and getattr(self.manager, "original_elements",
                                                                                None):
                    has_unsaved_changes = (self.manager.modified_elements != self.manager.original_elements) or bool(
                        self.manager.history_stack)
            except Exception:
                has_unsaved_changes = bool(self.manager.history_stack)

            metadata = {
                "current_file_path": getattr(self, "current_file_path", None),
                "items_text": self.items_text.get("1.0", tk.END),
                "active_target": getattr(self, "_active_target_category", None),
                "has_unsaved_file_changes": has_unsaved_changes
            }

            # attach to manager (pickle will include it)
            setattr(self.manager, "_saved_app_state", metadata)

            ok = self.manager.save_session(self.default_session_path)
            if ok:
                if show_status:
                    self.status_var.set(f"Session saved to {self.default_session_path}")
                return True
            else:
                if show_status:
                    messagebox.showerror("Save Error", f"Failed to save session to {self.default_session_path}")
                return False
        except Exception as e:
            if show_status:
                messagebox.showerror("Save Error", f"Failed to save session: {e}")
            return False

    def load_session(self):
        filepath = filedialog.askopenfilename(filetypes=[("Session Files", "*.session"), ("All Files", "*.*")],
                                              title="Load Session")
        if not filepath:
            return

        self.show_work_in_progress()

        def task():
            new_manager = BlockPropertiesManager.load_session(filepath)
            self.after(0, self.hide_work_in_progress)
            if new_manager:
                self.manager = new_manager
                self.after(0, self.update_all_views)
                meta = getattr(self.manager, "_saved_app_state", None)
                if meta and meta.get("has_unsaved_file_changes"):
                    self.after(0, lambda: messagebox.showinfo("Session Loaded",
                                                              "Loaded session contains unsaved changes to the properties file."))
                self.after(0, lambda: self.status_var.set(f"Session loaded from {filepath}"))
            else:
                self.after(0, lambda: messagebox.showerror("Load Error", f"Failed to load session from {filepath}"))

        threading.Thread(target=task, daemon=True).start()

    def load_default_session(self):
        """Try to load the default session file in cwd."""
        if not os.path.exists(self.default_session_path):
            messagebox.showinfo("No session", "No last_session.session found in this folder.")
            return False
        try:
            new_manager = BlockPropertiesManager.load_session(self.default_session_path)
            if not new_manager:
                messagebox.showerror("Load Error", f"Failed to load session from {self.default_session_path}")
                return False

            self.show_work_in_progress()

            # Replace current manager
            self.manager = new_manager

            # Restore optional UI metadata if present
            meta = getattr(self.manager, "_saved_app_state", None)
            if meta and isinstance(meta, dict):
                # restore file path
                self.current_file_path = meta.get("current_file_path")
                # restore items_text content
                try:
                    self.items_text.delete("1.0", tk.END)
                    self.items_text.insert("1.0", meta.get("items_text", ""))
                except Exception:
                    pass
                # restore active target
                self._active_target_category = meta.get("active_target")
                # update title
                if self.current_file_path:
                    self.title(f"Minecraft Properties Merger - {os.path.basename(self.current_file_path)}")
                else:
                    self.title("Minecraft Properties Merger")
            else:
                # No metadata: leave UI defaults (but manager state is restored)
                self.current_file_path = None
                self._active_target_category = None

            # Refresh UI
            self.update_all_views()
            self.after(0, self.hide_work_in_progress)
            self.status_var.set(f"Session loaded from {self.default_session_path}")
            return True
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load session: {e}")
            return False

    def on_closing(self):
        # Clean up the initial session temporary file
        if self.initial_session_path and os.path.exists(self.initial_session_path):
            try:
                os.remove(self.initial_session_path)
            except Exception as e:
                print(f"Warning: Could not remove initial session temp file {self.initial_session_path}: {e}")

        if self.manager.original_elements and self.manager.history_stack:
            if messagebox.askyesno("Quit",
                                   "You have unsaved changes. Do you want to save your session before quitting?"):
                # Try autosave to default location
                saved = self.save_session_to_default(show_status=True)
                if not saved:
                    # fallback to manual save dialog if autosave failed
                    if messagebox.askyesno("Save failed",
                                           "Autosave failed. Do you want to pick a location to save the session?"):
                        self.save_session()  # existing dialog-based save
        # finally clean up and exit
        self.destroy()

    def on_horizontal_scroll(self, *args):
        """Handler for the shared horizontal scrollbar."""
        self.before_widget.text.xview(*args)
        self.after_widget.text.xview(*args)

    def show_work_in_progress(self):
        self.work_in_progress_label.config(bg="#0078d7", text="WORK IN PROGRESS – DO NOT EXIT PROGRAM")
        self.work_in_progress_label.pack(side=tk.LEFT, padx=5)
        self.work_in_progress_label.lift()
        # self.progressbar.pack(side=tk.LEFT, padx=5)
        self.progressbar.start(10)  # animacja co 10ms
        self.update_idletasks()

    def hide_work_in_progress(self):
        self.work_in_progress_label.config(bg="#006400", text="OK")
        self.progressbar.stop()
        #self.progressbar.pack_forget()
        self.update_idletasks()
        self.after(1500, lambda: self.work_in_progress_label.pack_forget())

if __name__ == "__main__":
    # To prevent the extra root window, we instantiate the App first
    app = App()
    app.mainloop()
