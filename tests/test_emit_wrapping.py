"""Regression tests for line wrapping of flat assigns (_wrap_line)."""

from plane.emit import _wrap_line


def test_wrapped_lines_respect_max_width():
    # Bug report repro: last continuation line used to overflow to 74 chars
    terms = " | ".join(f"({{32{{sel{i}}}}} & {{val{i}}})" for i in range(10))
    line = f"  assign rdata           = ({terms});"

    wrapped = _wrap_line(line, "  ", 60)
    lines = wrapped.split("\n")

    assert len(lines) > 1
    assert all(len(ln) <= 60 for ln in lines)
    # Every continuation except the last ends with an operator
    assert all(ln.rstrip().endswith("|") for ln in lines[:-1])


def test_wrap_at_continuation_budget_boundary():
    # The lengths of the two `&` operands (16 + 26) place the first `|`
    # exactly at the continuation budget (60 - 13 indent). The old boundary
    # check split there anyway, emitting a 62-char line; the fix must fall
    # back to the in-budget `&` split instead.
    def term(i, n):
        return f"({{32{{s{i}}}}} & {{{'v' * n}}})"

    line = (
        "  assign d = "
        + term(2, 15)
        + " | ("
        + term(0, 1)
        + " & "
        + term(1, 11)
        + ") | "
        + term(3, 5)
        + " | "
        + term(4, 5)
        + ");"
    )

    wrapped = _wrap_line(line, "  ", 60)
    lines = wrapped.split("\n")

    assert len(lines) > 1
    assert all(len(ln) <= 60 for ln in lines)


def test_fitting_line_unchanged():
    line = "  assign rdata           = ({32{sel0}} & {val0});"

    assert _wrap_line(line, "  ", 60) == line
    assert _wrap_line(line, "  ", 47) == line


def test_tight_budget_splits_at_first_reachable_operator():
    # Even one term exceeds the budget; the wrapper now degrades to
    # splitting at the first reachable operator (one minimal-overflow line
    # per term) instead of emitting the whole expression unwrapped.
    terms = " | ".join(f"({{32{{sel{i}}}}} & {{val{i}}})" for i in range(4))
    line = f"  assign rdata           = ({terms});"

    wrapped = _wrap_line(line, "  ", 40)
    lines = wrapped.split("\n")

    assert len(lines) == 4
    assert all(ln.rstrip().endswith("|") for ln in lines[:-1])
    # No line is longer than a single term plus its continuation indent
    assert all(len(ln) <= len(line) for ln in lines)


def test_paren_wall_isolated_to_first_line():
    # Left-folded OR (e.g. CSR readback mux before the balanced-tree fix):
    # N-1 opening parens precede the first operator, so no split fits the
    # budget. The fallback must isolate the wall to one overflowing line
    # and wrap the remaining terms within max_width.
    terms = [f"({{32{{sel{i}}}}} & {{val{i}}})" for i in range(30)]
    expr = terms[0]
    for t in terms[1:]:
        expr = f"({expr} | {t})"
    line = f"  assign bus_rdata        = {expr};"

    wrapped = _wrap_line(line, "  ", 120)
    lines = wrapped.split("\n")

    assert len(lines) > 1
    assert all(len(ln) <= 120 for ln in lines[1:])
    # First line carries the paren wall; its overflow is bounded by the
    # wall plus one term, not the whole expression.
    assert len(lines[0]) < len(line) / 2


def test_no_flanked_operator_stays_unwrapped():
    # Concatenation has no )(-flanked split operator at all; best-effort
    # means the line stays whole.
    parts = ", ".join(f"sig{i}" for i in range(40))
    line = f"  assign cat             = {{{parts}}};"

    assert _wrap_line(line, "  ", 60) == line


def test_none_max_width_disables_wrapping():
    terms = " | ".join(f"({{32{{sel{i}}}}} & {{val{i}}})" for i in range(20))
    line = f"  assign rdata           = ({terms});"

    assert _wrap_line(line, "  ", None) == line
