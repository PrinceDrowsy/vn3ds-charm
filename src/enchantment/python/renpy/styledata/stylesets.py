"""The style property tables of the game's own Ren'Py, as harvested.

all_properties: property name -> the properties it sets (`xalign` sets
xpos and xanchor). prefix_priority: prefix -> priority. prefix_alts:
prefix -> the prefixes it sets. property_priority: property -> priority
within a prefix. rules: property -> [target, source, conversion] for each
property it sets (witch/renpy/styles.py).
"""
all_properties = {}
prefix_priority = {}
prefix_alts = {}
property_priority = {}
prefixed_all_properties = set()
rules = {}
priority_levels = 1


def load(tables):
    """Installs the harvested tables. Runs before anything imports
    renpy.style."""
    global all_properties, prefix_priority, prefix_alts, property_priority, prefixed_all_properties, rules
    global priority_levels
    all_properties = tables["all_properties"]
    rules = tables["rules"]
    prefix_priority = tables["prefix_priority"]
    prefix_alts = tables["prefix_alts"]
    property_priority = tables["property_priority"]
    prefixed_all_properties = set(prefix + name for prefix in prefix_priority for name in all_properties)
    # Each property dict of a style outranks the ones before it, whatever
    # the prefix and property priorities within it.
    priority_levels = max(prefix_priority.values()) + max(property_priority.values() or [0]) + 1
