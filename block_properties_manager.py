import copy
import re
import pickle
from typing import List, Dict, Set, Optional, Tuple

from block_properties_parser import (
    AbstractFileElement,
    BlockPropertiesParser,
    Property,
    EmptyLine,
)


class BlockPropertiesManager:
    """
    The main orchestrator. It uses the parser to load the file data and provides
    an API for the GUI to interact with, modify, and save the properties.
    """

    def __init__(self):
        self.original_elements: Optional[List[AbstractFileElement]] = None
        self.modified_elements: Optional[List[AbstractFileElement]] = None
        self.parser = BlockPropertiesParser()
        # Stack to store previous states for the Undo functionality
        self.history_stack: List[List[AbstractFileElement]] = []
        # Stack to store undone states for the Redo functionality
        self.redo_stack: List[List[AbstractFileElement]] = []
        # List to store human-readable descriptions of actions for the history panel
        self.history_descriptions: List[str] = []
        # Optimized search index for suggestions
        self._suggestion_index: Dict[str, Set[str]] = {}
        # Index for item "family" (e.g. 'sapling') to category mapping with counts
        self._family_index: Dict[str, Dict[str, int]] = {}
        # Sets for fast item existence checking
        self._all_item_values: Set[str] = set()
        self._all_base_item_names: Set[str] = set()

    def _save_state_for_undo(self, action_description: str):
        """
        Saves a deep copy of the current state to the history stack.
        This should be called BEFORE any modification.
        """
        if self.modified_elements:
            # A new action clears the redo stack.
            self.redo_stack.clear()
            # Add the description of the action being performed
            self.history_descriptions.append(action_description)
            # A deep copy is crucial! Otherwise, we'd just save a reference.
            self.history_stack.append(copy.deepcopy(self.modified_elements))

    def load_file(self, file_path: str) -> bool:
        """Loads and parses the properties file, storing its initial state."""
        elements = self.parser.parse(file_path)
        if not elements:
            return False
        self.original_elements = elements
        # The initial state is a deep copy of the original
        self.modified_elements = copy.deepcopy(self.original_elements)
        # Clear history for the new file
        self.history_stack.clear()
        self.redo_stack.clear()
        self.history_descriptions.clear()
        self._build_suggestion_index()
        self._build_lookup_sets()
        return True

    def _build_suggestion_index(self):
        """Builds an inverted index for fast keyword-based suggestion searching."""
        self._suggestion_index.clear()
        self._family_index.clear()
        if not self.modified_elements:
            return

        for element in self.modified_elements:
            if isinstance(element, Property):
                # Build keyword index
                all_item_names_in_prop = " ".join(element.all_items).replace("_", " ")
                words_in_prop = set(re.findall(r'\b\w+\b', all_item_names_in_prop.lower()))
                for word in words_in_prop:
                    self._suggestion_index.setdefault(word, set()).add(element.key)

                # Build family index
                for item in element.all_items:
                    # e.g., 'minecraft:oak_sapling' -> 'oak_sapling'
                    base_name = item.split(":")[-1].split("[")[0]
                    # e.g., 'oak_sapling' -> 'sapling'
                    family_key = base_name.split("_")[-1]
                    # Filter out generic terms or numbers that aren't good family keys
                    if family_key and not family_key.isnumeric() and len(family_key) > 2:
                        if family_key not in self._family_index:
                            self._family_index[family_key] = {}
                        self._family_index[family_key][element.key] = self._family_index[family_key].get(element.key,
                                                                                                         0) + 1

    def _build_lookup_sets(self):
        """Builds sets for fast item lookup. Called after loading a file."""
        if not self.modified_elements: return
        self._all_item_values = {item for prop in self.modified_elements if isinstance(prop, Property) for item in
                                 prop.all_items}
        self._all_base_item_names = {val.split(':')[0].split('[')[0] for val in self._all_item_values}

    def _find_property(self, category_id: str) -> Optional[Property]:
        """Private helper to find a Property object by its key."""
        if not self.modified_elements:
            return None
        for element in self.modified_elements:
            if isinstance(element, Property) and element.key == category_id:
                return element
        return None

    def add_items_to_category(
            self,
            items_to_add: List[str],
            category_id: str,
            template_item: Optional[str] = None,
    ) -> bool:
        """
        Adds a list of new items to a specified category ID.
        If a template_item is provided, it replicates its blockstate variations
        across all relevant categories.
        Returns False if no items were added (e.g., all duplicates), True otherwise.
        """

        if template_item:
            # --- Template Mode Implementation ---
            # 1. Find all variations of the template_item and the categories they belong to.
            template_variations_by_category: Dict[str, List[str]] = {}
            # Correctly identify the base name by splitting at the first '[' or ':' that indicates properties.
            # e.g., 'minecraft:andesite_wall[north=tall]' -> 'minecraft:andesite_wall'
            # e.g., 'andesite_wall:north=tall' -> 'andesite_wall'
            template_base_name = ":".join(template_item.split(":")[:2])

            if not self.modified_elements:
                return False

            for element in self.modified_elements:
                if isinstance(element, Property):
                    for item_in_prop in element.all_items:
                        if item_in_prop.startswith(template_base_name):
                            if element.key not in template_variations_by_category:
                                template_variations_by_category[element.key] = []
                            template_variations_by_category[element.key].append(item_in_prop)

            description = f"Template: Applied '{template_item}' to {len(items_to_add)} items"
            self._save_state_for_undo(description)
            # 2. For each new item, generate its variations and add them to the correct categories.
            items_were_added = False
            # ZM: Set do śledzenia Property, które zostały zmodyfikowane
            modified_properties: Dict[str, Property] = {}

            for category_id, template_variations in template_variations_by_category.items():
                target_property = self._find_property(category_id)
                if not target_property:
                    continue

                for template_variation in template_variations:
                    suffix = template_variation.replace(template_base_name, "", 1)
                    for new_item_base in items_to_add:
                        new_full_item = new_item_base + suffix
                        mod_id = new_item_base.split(":")[0] if ":" in new_item_base else "minecraft"
                        # Add item only if it doesn't already exist in this specific category
                        if new_full_item not in target_property.all_items:
                            target_property.add_item(new_full_item, mod_id)
                            items_were_added = True
                            modified_properties[category_id] = target_property  # ZM: Zapisz Property do odświeżenia

            # ZM: Wymuś rekonstrukcję dla WSZYSTKICH zmodyfikowanych Property
            for prop in modified_properties.values():
                if hasattr(prop, 'regenerate_raw_value'):
                    prop.regenerate_raw_value()

            if not items_were_added:
                return False  # No new items were actually added across all categories
        else:
            # --- Simple Mode ---
            target_property = self._find_property(category_id)
            if not target_property:
                print(f"Warning: Category '{category_id}' not found. Cannot add items.")
                return False

            # --- Pre-validation for Simple Mode ---
            if all(item in target_property.all_items for item in items_to_add):
                return False  # All items already exist in this category, skip action.

            description = f"Added {len(items_to_add)} items to '{category_id}'"
            self._save_state_for_undo(description)
            for item in items_to_add:
                mod_id = item.split(":")[0] if ":" in item else "minecraft"
                target_property.add_item(item, mod_id)

            # ZM: Wymuś rekonstrukcję po dodaniu itemów.
            if hasattr(target_property, 'regenerate_raw_value'):
                target_property.regenerate_raw_value()

        # After modification, the indices need to be rebuilt
        self._build_suggestion_index()
        self._build_lookup_sets()
        return True

    def suggest_categories_for_items_list(self, item_names: List[str]) -> List[Tuple[str, float]]:
        """
        Suggests category IDs for a list of new items using the pre-built search index.
        Returns a list of tuples: (category_id, score).
        """
        if not item_names or not self._suggestion_index:
            return []

        category_scores: Dict[str, float] = {}  # Using float for weighted scores
        FAMILY_MATCH_BONUS_PER_ITEM = 5.0  # Bonus for each existing item of the same family

        for item_name in item_names:
            base_name = item_name.split(":")[-1].split("[")[0]

            # 1. Keyword-based scoring (as before, but simplified)
            keywords = set(base_name.replace("_", " ").split())
            keywords.add(base_name)  # Add the full name as a keyword
            for keyword in keywords:
                weight = 5 if keyword == base_name else 1  # Higher weight for full name match
                if keyword in self._suggestion_index:
                    for category_id in self._suggestion_index[keyword]:
                        category_scores[category_id] = category_scores.get(category_id, 0) + weight

            # 2. Family-based scoring (Your suggestion!)
            family_key = base_name.split("_")[-1]
            if family_key and family_key in self._family_index:
                for category_id, count in self._family_index[family_key].items():
                    # Bonus is proportional to how many items of that family are already in the category
                    category_scores[category_id] = category_scores.get(category_id, 0) + (
                                count * FAMILY_MATCH_BONUS_PER_ITEM)

        # Normalize scores and sort
        # Find the max score to normalize against. This makes scores more like a percentage.
        max_score = max(category_scores.values()) if category_scores else 1.0

        normalized_suggestions = []
        for category_id, score in category_scores.items():
            # Normalize the score to be between 0 and 1
            normalized_score = score / max_score if max_score > 0 else 0
            normalized_suggestions.append((category_id, normalized_score))

        # Sort by score (descending), then by category name (ascending)
        return sorted(normalized_suggestions, key=lambda x: (-x[1], x[0]))

    def get_all_category_ids(self) -> List[str]:
        """Returns a list of all unique category IDs (e.g., 'block.8', 'block.54')."""
        if not self.modified_elements:
            return []
        return [
            el.key for el in self.modified_elements if isinstance(el, Property)
        ]

    def get_all_base_item_names(self) -> List[str]:
        """Returns a sorted list of unique base item names (e.g., 'minecraft:oak_stairs')."""
        if not self.modified_elements:
            return []

        base_names = set()
        for element in self.modified_elements:
            if isinstance(element, Property):
                for item in element.all_items:
                    # Simplified and corrected logic for finding the base name.
                    # This robust logic handles all known formats.
                    # 1. Remove modern blockstates like [facing=east].
                    item_without_brackets = item.split('[')[0]
                    # 2. Iterate through ':' parts until a blockstate (containing '=') is found.
                    parts = item_without_brackets.split(':')
                    base_name_parts = []
                    for part in parts:
                        if '=' in part: break
                        base_name_parts.append(part)
                    base_name = ":".join(base_name_parts)

                    if base_name:
                        base_names.add(base_name)
        return sorted(list(base_names))

    def check_item_existence(self, item_name: str) -> str:
        """
        Checks if an item exists and returns its status.
        Returns: "EXISTS", "PARTIAL", or "NEW".
        """
        if not self._all_item_values:
            self._build_lookup_sets()

        if item_name in self._all_item_values:
            return "EXISTS"

        base_name = item_name.split(':')[0].split('[')[0]
        if base_name in self._all_base_item_names:
            return "PARTIAL"

        return "NEW"

    def get_items_in_category(self, category_id: str) -> List[str]:
        """Returns a flattened list of all items within a specific category."""
        prop = self._find_property(category_id)
        if not prop:
            return []
        all_items = []
        for items in prop.item_groups.values():
            all_items.extend(items)
        return all_items

    def sort_category(self, category_id: str):
        """Sorts all items within a specified category alphabetically."""
        self._save_state_for_undo(f"Sorted category '{category_id}'")
        prop = self._find_property(category_id)
        if prop:
            prop.sort_items_alphabetically()
            # ZM: Wymuś rekonstrukcję wewnętrznej wartości (surowego tekstu) po sortowaniu.
            if hasattr(prop, 'regenerate_raw_value'):
                prop.regenerate_raw_value()
        else:
            # No change was made, so remove the saved state
            self.history_stack.pop()
            print(f"Warning: Category '{category_id}' not found for sorting.")

    def create_new_category(self, category_id: str):
        """
        Creates a new, empty property category if it doesn't exist,
        inserting it in the correct numerical order.
        """
        if self._find_property(category_id):
            print(f"Info: Category '{category_id}' already exists.")
            return

        self._save_state_for_undo(f"Created category '{category_id}'")
        new_prop = Property(key=category_id, raw_value="")

        # Find the correct insertion point to maintain numerical order
        insert_pos = len(self.modified_elements)
        try:
            new_id_num = int(category_id.split(".")[-1])
            for i, el in enumerate(self.modified_elements):
                if isinstance(el, Property):
                    try:
                        current_id_num = int(el.key.split(".")[-1])
                        if current_id_num > new_id_num:
                            insert_pos = i
                            break
                    except (ValueError, IndexError):
                        continue  # Not a numeric block ID, skip
        except (ValueError, IndexError):
            pass  # Not a numeric block ID, append at the end

        self.modified_elements.insert(insert_pos, new_prop)
        # Add an empty line after for formatting, if not at the end
        if insert_pos < len(self.modified_elements) - 1:
            self.modified_elements.insert(insert_pos + 1, EmptyLine())
        self._build_suggestion_index()

    def get_diff(self) -> Tuple[str, str]:
        """
        Generates 'before' and 'after' strings to visualize the changes made.
        """
        original_str = (
            "".join(el.to_string() + "\n" for el in self.original_elements)
            if self.original_elements
            else ""
        )
        modified_str = (
            "".join(el.to_string() + "\n" for el in self.modified_elements)
            if self.modified_elements
            else ""
        )
        return original_str, modified_str

    def save_to_file(self, output_path: str):
        """Saves the modified properties to a new file."""
        if not self.modified_elements:
            print("Error: No data to save.")
            return
        _, content_to_save = self.get_diff()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content_to_save)

    def undo(self):
        """Restores the previous state from the history stack."""
        if not self.history_stack:
            print("Undo history is empty.")
            return

        self.redo_stack.append(copy.deepcopy(self.modified_elements))
        self.modified_elements = self.history_stack.pop()
        self.history_descriptions.pop()  # Remove the corresponding description
        self._build_suggestion_index()

    def redo(self):
        """Restores an undone state from the redo stack."""
        if not self.redo_stack:
            print("Redo history is empty.")
            return

        self.history_stack.append(copy.deepcopy(self.modified_elements))
        self.modified_elements = self.redo_stack.pop()
        # For redo, we don't have the description stored, so we might need a more complex system
        # For now, let's assume we can't easily restore the description on redo.
        self._build_suggestion_index()

    def get_target_categories_for_template(self, template_item: str) -> List[str]:
        """
        Finds all category IDs where variations of the given template item exist.
        This is used for providing a preview to the user.
        """
        if not self.modified_elements or not template_item:
            return []

        target_categories = set()
        # Normalize template_item to its base name, e.g., 'minecraft:oak_stairs'
        template_base_name = ":".join(template_item.split(":")[:2])

        for element in self.modified_elements:
            if isinstance(element, Property):
                for item_in_prop in element.all_items:
                    if item_in_prop.startswith(template_base_name):
                        target_categories.add(element.key)
                        # No need to check other items in this property, move to next element
                        break
        return sorted(list(target_categories))


    def resolve_template_name_to_base_item(self, template_name: str) -> Optional[str]:
        """Try to resolve a short template name (e.g. 'andesite_wall') to an existing base item name
        known by the manager (like 'minecraft:andesite_wall' or 'mod:andesite_wall'). Returns the first match.
        """
        if not template_name or not self.modified_elements:
            return None
        # Gather available base names
        try:
            base_names = self.get_all_base_item_names()
        except Exception:
            base_names = []
        # prefer exact matches (with or without mod)
        for b in base_names:
            if b == template_name or b.endswith(':' + template_name):
                return b
        # fallback: contains match
        for b in base_names:
            if template_name in b:
                return b
        return None

    def get_template_target_property(self, template_name: str) -> Optional[str]:
        """Given a template short-name or base item, return a suitable target category key.
        This uses existing manager logic to find categories for a template item and picks the best candidate.
        """
        # If the template_name already looks like a base item (contains ':') try directly
        candidate_item = template_name if ':' in template_name else self.resolve_template_name_to_base_item(template_name)
        if not candidate_item:
            return None
        # Use existing helper to find target categories for a base template_item
        try:
            categories = self.get_target_categories_for_template(candidate_item)
            if categories:
                # choose the first (best) category
                return categories[0]
        except Exception:
            pass
        return None

    def apply_mapped_items(self, mapped_list: list):
        """
        mapped_list: list of tuples (item, template_name, maybe_target)
        This implementation GROUPS mapped items by template_name, resolves the full
        template base item (as shown in the template list) and calls the exact same
        manager API used by the "Use Template" / "Add -> Apply Changes" flow:
            self.add_items_to_category(items_list, category_id="", template_item=full_template_item)
        Items for which no suitable full template could be resolved are left unmapped.
        """
        if not mapped_list:
            return

        # Group items by template_name
        items_by_template = {}
        for entry in mapped_list:
            # allow both (item, template_name, target) and (item, template_name) shapes
            if len(entry) >= 2:
                item = entry[0]
                tmpl_name = entry[1]
            else:
                # malformed entry - skip
                continue
            items_by_template.setdefault(tmpl_name, []).append(item)

        applied_items = set()
        unmapped_info = []  # list of (item, reason)

        # Helper: resolve a short template name (e.g. 'andesite_wall') to a full base item
        def resolve_full_template_item(short_name: str) -> Optional[str]:
            """
            Tries to find the best matching base item from manager's available templates.
            Strategy (in order):
              1. exact full name match (if user gave full name)
              2. candidate endswith ':<short_name>'
              3. candidate's base (after colon) equals short_name
              4. candidate contains short_name in its name part
            Returns full base item like 'minecraft:andesite_wall' or None if not found.
            """
            try:
                candidates = self.get_all_base_item_names()
            except Exception:
                candidates = []
            if not candidates:
                return None

            # 1. exact match
            for c in candidates:
                if c == short_name:
                    return c

            # 2. endswith :short_name
            for c in candidates:
                if c.endswith(":" + short_name):
                    return c

            # 3. base equal (after colon)
            for c in candidates:
                parts = c.split(":", 1)
                if len(parts) == 2 and parts[1] == short_name:
                    return c

            # 4. contains short_name in base part
            for c in candidates:
                parts = c.split(":", 1)
                if len(parts) == 2 and short_name in parts[1]:
                    return c

            return None

        # For each template group, resolve and call add_items_to_category in template mode
        for tmpl_name, items in items_by_template.items():
            full_template = resolve_full_template_item(tmpl_name)
            if not full_template:
                # mark all items in this group as unmapped (leave them in New Items list)
                for it in items:
                    unmapped_info.append((it, f"template '{tmpl_name}' not found"))
                continue

            # Call the exact same manager API used by UI -> Use Template path.
            try:
                # We call with category_id="" and template_item=full_template to ensure
                # the manager uses the template-mode implementation and copies all variants.
                result = self.add_items_to_category(items, category_id="", template_item=full_template)
                if result:
                    for it in items:
                        applied_items.add(it)
                else:
                    for it in items:
                        unmapped_info.append((it, f"add_items_to_category returned False for template '{tmpl_name}'"))
            except Exception as e:
                for it in items:
                    unmapped_info.append((it, f"error applying template '{tmpl_name}': {e}"))

        # Remove applied items from New Items queue (respect existing attribute names)
        try:
            if hasattr(self, "new_items") and isinstance(self.new_items, list):
                self.new_items = [it for it in self.new_items if it not in applied_items]
            elif hasattr(self, "items_to_add") and isinstance(self.items_to_add, list):
                self.items_to_add = [it for it in self.items_to_add if it not in applied_items]
            else:
                # best-effort: if there's a UI widget, try to clear lines - leave for UI layer to refresh
                pass
        except Exception:
            # never crash here
            pass

        # Refresh indices/views if available
        try:
            if hasattr(self, "_build_suggestion_index"):
                self._build_suggestion_index()
        except Exception:
            pass
        try:
            if hasattr(self, "_build_lookup_sets"):
                self._build_lookup_sets()
        except Exception:
            pass
        try:
            if hasattr(self, "refresh_views"):
                self.refresh_views()
        except Exception:
            pass
        try:
            if hasattr(self, "refresh_new_items_list"):
                self.refresh_new_items_list()
        except Exception:
            pass

        # Optionally return summary (not required) - manager callers typically ignore return value.
        return {"applied": list(applied_items), "unmapped": unmapped_info}

    def find_element_index_by_id(self, element_id: str) -> Optional[int]:
        """
        Znajduje indeks elementu (Property) w liście self.modified_elements na podstawie ID (klucza).
        Zwraca indeks w liście modified_elements, a nie numer linii.
        """
        if self.modified_elements is None:
            return None

        # Import Property wewnątrz metody, jeśli nie jest zaimportowany globalnie,
        # aby uniknąć problemów z cyklicznymi zależnościami.
        # Zakładamy, że Property jest już zaimportowane na początku pliku.
        from block_properties_parser import Property

        for i, element in enumerate(self.modified_elements):
            if isinstance(element, Property) and element.key == element_id:
                return i
        return None

    def get_block_start_line(self, element_index: int) -> Optional[int]:
        """
        Oblicza numer linii (1-based, jak w tkinter) w widoku 'After Merged',
        na której zaczyna się dany element z listy modified_elements.
        """
        if self.modified_elements is None or element_index >= len(self.modified_elements):
            return None

        # Zaczynamy liczyć od 1, ponieważ to jest konwencja numeracji linii w Tkinter
        start_line = 1

        for i, element in enumerate(self.modified_elements):
            if i == element_index:
                # Znaleziono element, zwracamy bieżący numer linii
                return start_line

            # Obliczanie długości elementu w widoku tekstowym
            element_string = element.to_string()
            # Liczba linii to: liczba znaków nowej linii + 1
            line_count = element_string.count('\n') + 1

            # Przejście do następnego elementu
            start_line += line_count

        return None  # Nie powinno się zdarzyć, jeśli element_index był poprawny

    def save_session(self, filepath: str):
        """Saves the entire manager state to a file using pickle."""
        try:
            with open(filepath, "wb") as f:
                pickle.dump(self, f)
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    @staticmethod
    def load_session(filepath: str) -> Optional['BlockPropertiesManager']:
        """Loads a manager state from a pickle file."""
        try:
            with open(filepath, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading session: {e}")
            return None