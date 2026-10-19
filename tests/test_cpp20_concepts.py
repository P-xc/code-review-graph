"""Tests for C++20 concept and variable-template nodes.

Before the fix, `concept_definition` appeared in the parser only as evidence
that a .h is C++ rather than C — never as a node — so a constrained template
could not be traced back to its constraint. Variable templates were dropped
by a different route: they parse as declaration > init_declarator, which
`declaration` being one of cpp's function node types sent to the function
path, where the callable-declaration probe rejected them.

The regression these guard against: capturing them too eagerly cost
tl::optional its entire monadic interface (41 methods), because a defaulted
template parameter arrives here with the whole template header as its text,
and a member function with a trailing ref-qualifier looks like a constant.
"""
from __future__ import annotations

from pathlib import Path

from code_review_graph.parser import CodeParser

FIXTURES = Path(__file__).parent / "fixtures"


class TestCpp20Concepts:
    def setup_method(self) -> None:
        root = FIXTURES / "cpp_cpp20_concepts"
        parser = CodeParser(repo_root=root)
        self.nodes, self.edges = parser.parse_file(root / "sample.cpp")

    def _named(self, name: str) -> list:
        return [n for n in self.nodes if n.name == name]

    def test_concept_produces_a_node(self) -> None:
        """A C++20 concept is addressable, not invisible."""
        hits = self._named("Integral")
        assert hits, f"concept Integral missing; nodes={[n.name for n in self.nodes]}"
        assert hits[0].kind == "Type"
        assert hits[0].extra.get("cpp_kind") == "concept_definition"

    def test_variable_template_produces_a_node(self) -> None:
        """`template <typename T> constexpr bool is_int_v` is recorded."""
        hits = self._named("is_int_v")
        assert hits, f"is_int_v missing; nodes={[n.name for n in self.nodes]}"
        assert hits[0].kind == "Type"
        assert hits[0].extra.get("cpp_kind") == "variable_template"

    def test_constrained_function_is_still_a_function(self) -> None:
        """Adding concepts must not reclassify the function they constrain."""
        hits = [n for n in self.nodes if n.name == "clamp_value"]
        assert hits, "clamp_value missing"
        assert hits[0].kind == "Function"

    def test_ref_qualified_member_is_not_a_variable_template(self) -> None:
        """The exact shape that swallowed tl::optional's map/and_then.

        `constexpr decltype(...) map(F&& f) &` sits inside a
        template_declaration and carries a constexpr qualifier, so an eager
        probe records it as a constant and the method disappears.
        """
        hits = [n for n in self.nodes if n.name == "map"]
        assert hits, "member map() must survive as a function"
        assert all(n.kind == "Function" for n in hits), [
            n.kind for n in hits
        ]

    def test_ordinary_method_unaffected(self) -> None:
        hits = [n for n in self.nodes if n.name == "plain_method"]
        assert hits and hits[0].kind == "Function"

    def test_no_node_has_a_malformed_name(self) -> None:
        """A name must be an identifier, never a whole template header.

        A defaulted template parameter reaches the value-declaration path
        with the header as its text; recording that produced a node that
        could not be merged, which silently dropped sibling methods.
        """
        for node in self.nodes:
            if node.kind == "File":
                continue
            assert "\n" not in node.name and "\r" not in node.name, (
                f"malformed name: {node.name!r}"
            )
            assert "template" not in node.name, f"malformed name: {node.name!r}"
            assert len(node.name) < 200, f"malformed name: {node.name!r}"
