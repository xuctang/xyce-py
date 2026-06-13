# Typed directive builders

`xyce-py` provides directive builders for common outer directive contracts such as `.PARAM`, `.PRINT`, and `.MEASURE`, but it does not parse Xyce expressions inside those directives. The builders validate Python-side structure that would otherwise generate malformed netlist lines, then emit exact SPICE directive text. Xyce remains the source of truth for expression semantics, supported analysis combinations, and measurement syntax details.
