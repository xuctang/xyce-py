# Measurement extraction interface

`xyce-py` parses Xyce measurement output files such as `circuit.cir.mt0` through a dedicated measurement result module. The parser accepts Xyce's `NAME = value` output shape, preserves the raw value text, and exposes a float only when Python can parse the value exactly as numeric text. It does not infer failed-measurement semantics or parse measurement expressions; Xyce remains responsible for `.MEASURE` evaluation.
