import re
from enum import Enum
from typing import List, Set


class MatcherType(Enum):
    """Enumeration for different types of text matching."""
    CONTAINS = "contains"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    EXACT = "exact"
    REGEX = "regex"


class AutoRule:
    """Represents a single rule from the auto_rules.txt file."""

    def __init__(self, matcher_type: MatcherType, value: str, template: str):
        self.matcher_type = matcher_type
        self.value = value
        self.template = template
        if self.matcher_type == MatcherType.REGEX:
            # Pre-compile the regular expression for better performance
            try:
                self.regex = re.compile(value)
            except re.error as e:
                print(f"Warning: Invalid regex '{value}' in rule. Error: {e}")
                self.regex = None
        else:
            self.regex = None

    def matches(self, text: str) -> bool:
        """Checks if the given text matches this rule."""
        if self.matcher_type == MatcherType.EXACT:
            return text == self.value
        if self.matcher_type == MatcherType.CONTAINS:
            return self.value in text
        if self.matcher_type == MatcherType.PREFIX:
            return text.startswith(self.value)
        if self.matcher_type == MatcherType.SUFFIX:
            return text.endswith(self.value)
        if self.matcher_type == MatcherType.REGEX:
            return self.regex is not None and self.regex.search(text) is not None
        return False

    def __repr__(self) -> str:
        return f"AutoRule({self.matcher_type.value}:{self.value} -> {self.template})"


def parse_rules_from_file(filepath: str) -> List[AutoRule]:
    """Parses a rules file and returns a list of AutoRule objects."""
    rules: List[AutoRule] = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split(' -> ')
                if len(parts) != 2:
                    print(f"Warning: Skipping malformed line {line_num} in '{filepath}': {line}")
                    continue

                matcher_part, template_part = parts

                matcher_parts = matcher_part.split(':', 1)
                if len(matcher_parts) != 2:
                    print(f"Warning: Skipping malformed matcher on line {line_num} in '{filepath}': {matcher_part}")
                    continue

                try:
                    matcher_type = MatcherType(matcher_parts[0])
                    value = matcher_parts[1]
                except ValueError:
                    print(
                        f"Warning: Skipping unknown matcher type on line {line_num} in '{filepath}': {matcher_parts[0]}")
                    continue

                if not template_part.startswith('template:'):
                    print(f"Warning: Skipping malformed template on line {line_num} in '{filepath}': {template_part}")
                    continue

                template = template_part.replace('template:', '', 1)
                rules.append(AutoRule(matcher_type, value, template))
    except FileNotFoundError:
        print(f"Warning: Rules file '{filepath}' not found. No auto-rules will be applied.")

    return rules


def get_standard_suggestions(item_name: str) -> List[str]:
    """
    Placeholder for your existing logic to generate standard suggestions.
    """
    print(f"   (Generating standard suggestions for '{item_name}')...")
    suggestions = []
    if "wall" in item_name:
        suggestions.append("stone_wall")
    if "door" in item_name:
        suggestions.append("iron_door")
    return suggestions


def get_all_suggestions_for_item(item_name: str, rules: List[AutoRule]) -> List[str]:
    """
    Generates suggestions for a single item, prioritizing auto_rules
    and then adding standard suggestions. Duplicates are removed.
    """
    final_suggestions: Set[str] = set()
    ordered_suggestions: List[str] = []

    # 1. Apply auto-rules first
    for rule in rules:
        if rule.matches(item_name):
            if rule.template not in final_suggestions:
                final_suggestions.add(rule.template)
                ordered_suggestions.append(rule.template)

    # 2. Add standard suggestions
    for suggestion in get_standard_suggestions(item_name):
        if suggestion not in final_suggestions:
            final_suggestions.add(suggestion)
            ordered_suggestions.append(suggestion)

    return ordered_suggestions


if __name__ == "__main__":
    auto_rules = parse_rules_from_file('auto_rules.txt')
    print(f"Loaded {len(auto_rules)} rules: {auto_rules}\n")

    items_to_check = ["stone wall and door", "iron_door", "wallpaper", "oak_stairs"]
    for item in items_to_check:
        print(f"--- Suggestions for: '{item}' ---")
        all_suggestions = get_all_suggestions_for_item(item, auto_rules)
        print(f"Result: {all_suggestions}\n")

