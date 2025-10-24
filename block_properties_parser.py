# Zastępuje oryginalny block_properties_parser.py
# (ta wersja przechowuje oryginalne surowe linie wartości i tylko przy
# modyfikacji generuje "nową" reprezentację)

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set


# --- Data Model Classes ---


class AbstractFileElement(ABC):
    """Abstract base class for any element (like a line) in the properties file."""

    @abstractmethod
    def to_string(self) -> str:
        """Converts the element back to its string representation for saving."""
        pass


class Comment(AbstractFileElement):
    """Represents a comment line (e.g., # This is a comment)."""

    def __init__(self, content: str):
        self.content = content  # The full line, including '#'

    def to_string(self) -> str:
        return self.content


class EmptyLine(AbstractFileElement):
    """Represents a blank line used for spacing in the file."""

    def to_string(self) -> str:
        return ""


class Directive(AbstractFileElement):
    """Represents a preprocessor directive (e.g., #ifdef, #define)."""

    def __init__(self, content: str):
        self.content = content  # The full directive line

    def to_string(self) -> str:
        return self.content


class Property(AbstractFileElement):
    """
    Represents a single property (key-value pair), which can span multiple lines.
    This is the core data structure for block definitions.
    """

    def __init__(self, key: str, raw_value: str, original_raw: Optional[str] = None):
        self.key: str = key
        # Groups items by their source (mod id or 'minecraft' for vanilla).
        # The list of strings preserves the original order of items.
        self.item_groups: Dict[str, List[str]] = {}
        # A set for quick duplicate checks.
        self.all_items: Set[str] = set()

        # Store original raw text (exactly as read from file, right side of '=')
        # This is used to faithfully display the "Before" view and to avoid
        # changing the file unless a modification truly happens.
        self._original_raw: Optional[str] = original_raw if original_raw else None
        # If we have an original raw representation, by default preserve it
        # until a real modification occurs.
        self._preserve_original: bool = bool(self._original_raw)

        # Parse the processed raw_value (which should have trailing continuation
        # backslashes removed) to populate item_groups.
        self._parse_value(raw_value)

    def _parse_value(self, raw_value: str):
        """Parses the raw string value into structured item groups."""
        lines = raw_value.splitlines()
        for i, line in enumerate(lines):
            items = line.strip().split()
            if not items:
                continue

            # The first line is always the 'minecraft' group.
            # Subsequent lines are grouped by the mod_id of their first item.
            if i == 0:
                mod_id = 'minecraft'
            else:
                mod_id = items[0].split(':')[0] if ':' in items[0] else 'minecraft'

            if mod_id not in self.item_groups:
                self.item_groups[mod_id] = []

            for item in items:
                if item not in self.all_items:
                    self.item_groups[mod_id].append(item)
                    self.all_items.add(item)

    def add_item(self, item: str, mod_id: str):
        """Adds a new item to the specified mod group and mark as modified."""
        if mod_id not in self.item_groups:
            self.item_groups[mod_id] = []

        if item not in self.all_items:
            self.item_groups[mod_id].append(item)
            self.all_items.add(item)
            # Once we add an item, we must stop preserving the exact original raw text:
            self._preserve_original = False

    def sort_items_alphabetically(self):
        """Sorts all items within each mod group alphabetically and mark as modified."""
        for mod_id in self.item_groups:
            self.item_groups[mod_id].sort()
        # Sorting is a modification of the representation:
        self._preserve_original = False

    def to_string(self) -> str:
        """
        Converts the property back to its string representation,
        handling multi-line formatting with '\' and indentation.

        If this property still preserves the original raw text (no modifications),
        return the original text exactly as it appeared after the '=' sign.
        """
        # If we haven't modified this property and we have the original raw lines,
        # return them exactly as read from the file.
        if self._preserve_original and self._original_raw is not None:
            return f"{self.key}={self._original_raw}"

        # Otherwise construct a canonical representation from item_groups
        if not self.item_groups:
            return f"{self.key}="

        mod_ids_in_order = list(self.item_groups.keys())

        value_lines = []
        for mod_id in mod_ids_in_order:
            if self.item_groups[mod_id]:
                value_lines.append(" ".join(self.item_groups[mod_id]))

        return f"{self.key}=" + " \\\n ".join(value_lines)

    def _get_all_current_items(self) -> List[str]:
        """
        Internal method to gather all current items from item_groups,
        ensuring they are sorted alphabetically. This is the source of truth
        for the updated raw value.
        """
        all_items = []
        if hasattr(self, 'item_groups'):
            for items_list in self.item_groups.values():
                all_items.extend(items_list)
        # Posortowanie itemów, aby odzwierciedlać operację sortowania i zachować spójność
        all_items.sort()
        return all_items

    def regenerate_raw_value(self):
        """
        Kluczowa metoda: Rekonstruuje self.original_raw (surowy tekst bloku)
        na podstawie aktualnej, posortowanej listy itemów.
        Zapewnia to, że to_string() zwróci zaktualizowaną treść po sortowaniu lub dodaniu.
        """
        all_items = self._get_all_current_items()

        # 1. Łączenie wszystkich itemów w jeden duży ciąg (oddzielony przecinkiem i spacją)
        full_text = ", ".join(all_items)

        new_lines = []
        current_line = ""
        # Limit długości linii, aby naśladować format pliku z łamaniem linii za pomocą '\'
        max_line_length = 120

        tokens = full_text.split(", ")

        for token in tokens:
            # Sprawdzenie warunku łamania linii: przekroczenie limitu i linia nie jest pusta
            if len(current_line) + len(token) + (2 if current_line else 0) > max_line_length and current_line:
                # Zakończ linię backslashem i spacją
                new_lines.append(current_line.strip() + ' \\')
                current_line = token
            elif current_line:
                # Dodaj separator ", "
                current_line += ", " + token
            else:
                # Pierwszy token na linii
                current_line = token

        # Dodaj ostatnią linię (BEZ backslasha, co kończy blok)
        if current_line:
            new_lines.append(current_line.strip())

        # Zaktualizuj surowy tekst (self.original_raw) używany przez metodę to_string()
        self.original_raw = "\n".join(new_lines)

        # Zaktualizuj processed_value (tekst bez łamania linii) dla spójności
        self.processed_value = self.original_raw.replace(' \\', '')

class BlockPropertiesParser:
    """
    Responsible for reading a .properties file and parsing it into a list
    of AbstractFileElement objects.
    """

    def parse(self, file_path: str) -> List[AbstractFileElement]:
        """
        Parses the given file into a structured in-memory representation.
        It handles multi-line properties and identifies different element types.
        """
        elements: List[AbstractFileElement] = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return []
        except Exception as e:
            print(f"Error reading file: {e}")
            return []

        i = 0
        while i < len(lines):
            line = lines[i].rstrip('\n')
            stripped_line = line.strip()

            if not stripped_line:
                elements.append(EmptyLine())
                i += 1
                continue

            if stripped_line.startswith(('#ifdef', '#ifndef', '#else', '#endif', '#define')):
                elements.append(Directive(line))
                i += 1
                continue

            if stripped_line.startswith('#'):
                elements.append(Comment(line))
                i += 1
                continue

            if '=' in line:
                key, rest = line.split('=', 1)
                key = key.strip()
                # Collect raw value lines exactly as in the file (after '='), preserving spacing and backslashes
                raw_value_lines = [rest.rstrip('\n')]
                # Check if the last non-newline-stripped chars end with a backslash (ignoring trailing spaces)
                while raw_value_lines[-1].rstrip().endswith('\\'):
                    i += 1
                    if i < len(lines):
                        next_line = lines[i].rstrip('\n')
                        raw_value_lines.append(next_line)
                    else:
                        break  # Unexpected EOF during continuation

                # Build original_raw (exact text after '=' including line joins exactly as read)
                original_raw_value = "\n".join(raw_value_lines)

                # Build processed value used for parsing items:
                # remove the line-ending backslashes so that joining lines gives actual tokenizable text
                processed_lines = []
                for ln in raw_value_lines:
                    if ln.rstrip().endswith('\\'):
                        # remove the trailing backslash (but preserve other trailing spaces inside the line)
                        # take everything up to the last backslash in the rstripped content, then restore trailing spaces if any
                        r = ln.rstrip()
                        # length difference of rstrip to original tells us trailing spaces count
                        trailing_spaces = len(ln) - len(ln.rstrip('\n').rstrip())
                        processed_lines.append(r[:-1])
                    else:
                        processed_lines.append(ln)
                processed_value = "\n".join(processed_lines).lstrip()  # keep parsing robust by stripping leading spaces

                elements.append(Property(key, processed_value, original_raw=original_raw_value))
                i += 1
                continue

            # If a line doesn't fit any category, treat it as a comment to preserve it
            elements.append(Comment(f"# [UNPARSED] {line}"))
            i += 1

        return elements
