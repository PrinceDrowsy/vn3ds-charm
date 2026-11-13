# ADR-006 — Rebrand to VN3DS-CHARM

**Status:** Accepted
**Date:** 2026-11-13
**Deciders:** PrinceDrowsy

## Context

"VN3DS-LOVE" described a VNDS-LOVE fork running on LÖVE Potion. ADR-004
dropped VNDS and ADR-005 replaced LÖVE Potion with a native engine, so the
name described neither part anymore. The engine, the converter and the bundle
files had no names of their own.

## Decision

A love-magic theme:

| Part | Name | Meaning |
|---|---|---|
| Project | **VN3DS-CHARM** | Visual novels on the 3DS, each one a charm |
| Converter (PC) | **Witch** | Casts the spell that turns a PC visual novel into a charm |
| Engine (3DS) | **Enchantment** | Brings the charm to life on the 3DS |
| Bundle file | **`.charm`** | One converted game, e.g. `mice-tea.charm` |

The "VN3DS" prefix stays because it says what the project is, and the suffix
keeps it distinct from the abandoned 2015 "VN3DS" project.

## Consequences

- Docs, build targets, the 3DS title metadata and the SD save folder move to
  the new names. New code (REWORK-PLAN R0 onward) uses them from the start.
  The old MoonScript engine and converter keep their names until they're
  retired in R9.
- `.charm` is also used by Canonical's Juju charm packages (zip archives),
  and a 2018 ransomware family appended `.charm` to files it encrypted.
  Neither is likely to matter for a 3DS homebrew bundle, since `.charm` files
  mostly live inside per-game CIAs or on the SD card. It's recorded here in
  case it ever does.
- Renaming the GitHub repository needs the repository owner. The local folder
  move needs the project memory migrated with it.
