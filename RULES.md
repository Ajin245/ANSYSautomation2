# Coding Rules and Standards

## Environment
- **ANSYS Workbench Version**: 21r1
- **Python Version**: Python 2.7 (IronPython environment within ANSYS)

## File Standards
- **Encoding**: All Python source files MUST be saved in **UTF-8** encoding.
- **Header**: Every script should start with `# -*- coding: utf-8 -*-`.

## Syntax Restrictions (Python 2 Compatibility)
To ensure compatibility with the IronPython 2.7 environment, the following rules apply:

### 1. No f-strings
- **Prohibited**: `f"Value: {x}"`
- **Use instead**: `"Value: {}".format(x)` or `"Value: %s" % x`.

### 2. Print Statement
- Use `print "message"` instead of `print("message")` unless `from __future__ import print_function` is used.
- Avoid using `print` as a function if it breaks standard IronPython 2.7 behavior in older ANSYS versions.

### 3. Strings and Unicode
- Use `u"текст"` for strings containing non-ASCII characters (e.g., Russian text).
- Be careful with `str` vs `unicode` types.

### 4. Prohibited Python 3 Features
- **No Type Hinting**: Do not use `: int` or `-> None` syntax.
- **No Async/Await**: `async def` and `await` are not supported.
- **No Keyword-only arguments**: `def func(*, arg):` is not supported.
- **No Extended Iterable Unpacking**: `a, *b = [1, 2, 3]` is not supported.
- **No `yield from`**: Use manual loops for delegating to sub-generators.
- **Division**: Be aware that `/` performs integer division on integers (e.g., `5 / 2 = 2`). Use `from __future__ import division` if float division is needed.

### 5. Dictionary Methods
- Use `.iteritems()`, `.iterkeys()`, and `.itervalues()` for performance when iterating over large dictionaries, as `.items()` creates a list in Python 2.

## ANSYS Specifics
- Use `Tree.AllObjects` and other ANSYS-specific API calls carefully, checking for object existence before access.
- Always wrap API-heavy logic in `try...except` blocks to provide meaningful error messages in the ANSYS console.

## SpaceClaim Specifics
- **Python Script, API Version**: V19
- **Python Version**: 2.7.4 (IronPython 2.7.4 (2.7.0.40) on .NET 4.0.30319.42000 (64 bit))
- **ANSYS SpaceClaim Version**: V21R1 (2021.1.0.11221)
