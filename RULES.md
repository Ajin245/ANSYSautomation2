# Coding Rules and Standards

## Environment
- **ANSYS Workbench Version**: 21r1
- **Python Version**: Python 2.7 (IronPython environment within ANSYS)

## File Standards
- **Encoding**: All Python source files MUST be saved in **UTF-8** encoding.
- **Header**: Every script should start with `# -*- coding: utf-8 -*-`.

## Syntax Restrictions (Python 2 Compatibility)
- **No f-strings**: Use `.format()` or `%`.
- **Print Statement**: Use `print "message"` (or `from __future__ import print_function`).
- **Strings and Unicode**: Use `u"текст"` for Russian characters.
- **No Python 3 features**: (No type hinting, async/await, yield from, etc.).
- **Division**: Be aware of integer division (`/`). Use `from __future__ import division`.
- **Dictionary Methods**: Use `.iteritems()`, `.iterkeys()`, `.itervalues()`.

## ANSYS Specifics
- Use `Tree.AllObjects` carefully.
- Wrap API-heavy logic in `try...except` blocks.
- **Do not use traceback**: Do not allow traceback prints; use concise, meaningful error messages via `self.log`.
- **Quantity/Enum Handling**: Avoid manual `clr.AddReference` for `Quantity` or `Enum` types where possible. Pass these types via `ProjectContext` to prevent `TypeError` conflicts (assembly isolation issues).

## SpaceClaim Specifics
- Python Script, API Version: V19.
