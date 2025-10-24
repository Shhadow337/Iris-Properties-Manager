
# auto_mapper.py
import re
from typing import List, Tuple, Dict, Callable, Optional

Rule = Tuple[str, str, str]  # (matcher_type, matcher_value, template_name)

def parse_rule_line(line: str) -> Optional[Rule]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "->" not in line:
        return None
    left, right = line.split("->", 1)
    left = left.strip()
    right = right.strip()
    if ":" not in left:
        return None
    matcher_type, matcher_value = left.split(":", 1)
    matcher_type = matcher_type.strip()
    matcher_value = matcher_value.strip()
    # right should contain template:<name>
    tmpl_name = None
    for chunk in right.split(","):
        if ":" in chunk:
            k, v = chunk.split(":", 1)
            if k.strip() == "template":
                tmpl_name = v.strip()
    if tmpl_name is None:
        return None
    return (matcher_type, matcher_value, tmpl_name)

def load_rules(path: str) -> List[Rule]:
    rules = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                r = parse_rule_line(ln)
                if r:
                    rules.append(r)
    except FileNotFoundError:
        # brak pliku -> brak reguł
        return []
    return rules

def matches(item: str, rule: Rule) -> bool:
    t, val, _ = rule
    if t == "contains":
        return val in item
    if t == "prefix":
        return item.startswith(val)
    if t == "suffix":
        return item.endswith(val)
    if t == "exact":
        return item == val
    if t == "regex":
        try:
            return re.search(val, item) is not None
        except re.error:
            return False
    return False

def automap_items(
    new_items: List[str],
    rules: List[Rule],
    template_resolver: Callable[[str], Optional[str]],
    dry_run: bool = True
) -> Tuple[List[Tuple[str,str,str]], List[Tuple[str,str]]]:
    """
    new_items: list of item strings, e.g. ['wide_mod:plate', ...]
    rules: list of parsed rules (matcher_type, matcher_value, template_name)
    template_resolver: function(template_name) -> target_property_key or None
      - should return the actual property key / place where adding should occur,
        or None if template unknown.
    Returns:
      mapped: list of tuples (item, template_name, target_property_key)
      unmapped: list of tuples (item, reason)
    """
    mapped = []
    unmapped = []

    for item in new_items:
        chosen = None
        for rule in rules:
            if matches(item, rule):
                chosen = rule
                break  # first matching rule is used (order matters)
        if not chosen:
            unmapped.append((item, "no rule matched"))
            continue
        _, _, template_name = chosen
        target_key = template_resolver(template_name)
        if not target_key:
            unmapped.append((item, f"template '{template_name}' not found"))
            continue
        mapped.append((item, template_name, target_key))

    return mapped, unmapped
