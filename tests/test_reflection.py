"""Tests for engine/reflection.py — callable -> NodeSpec conversion."""

from __future__ import annotations

import inspect
import typing

from astrostudio.engine import reflection
from astrostudio.engine.reflection import (
    _annotation_to_str,
    _guess_output_type,
    _parse_docstring,
    reflect,
)


def documented(alpha: int, beta: str = "x") -> float:
    """Short summary line.

    Longer explanation that is not part of the summary.

    Parameters
    ----------
    alpha : int
        The alpha parameter.
    beta : str
        The beta parameter.

    Returns
    -------
    float
        Something useful.
    """
    return float(alpha)


def variadic(a, *args, b=1, **kwargs):
    return a


class Widget:
    """A widget.

    Parameters
    ----------
    size : int
        The widget size.
    """

    def __init__(self, size: int, name: str = "w"):
        self.size = size
        self.name = name

    def scale(self, factor: float) -> "Widget":
        return Widget(int(self.size * factor), self.name)


def test_annotation_to_str_empty_is_any():
    assert _annotation_to_str(inspect.Parameter.empty) == "Any"


def test_annotation_to_str_passes_through_strings():
    assert _annotation_to_str("SkyCoord") == "SkyCoord"


def test_annotation_to_str_uses_type_name():
    assert _annotation_to_str(int) == "int"


def test_annotation_to_str_uses_generic_alias_name():
    assert _annotation_to_str(typing.Optional[int]) == "Optional"


def test_annotation_to_str_strips_typing_prefix_from_repr():
    class Annotation:
        def __str__(self):
            return "typing.Sequence[typing.Any]"

    assert _annotation_to_str(Annotation()) == "Sequence[Any]"


def test_parse_docstring_empty_returns_blanks():
    assert _parse_docstring(None) == ("", {}, "")
    assert _parse_docstring("   \n  ") == ("", {}, "")


def test_parse_docstring_extracts_summary_and_params():
    summary, param_docs, full = _parse_docstring(inspect.getdoc(documented))
    assert summary == "Short summary line."
    assert param_docs["alpha"] == "The alpha parameter."
    assert param_docs["beta"] == "The beta parameter."
    assert "Longer explanation" in full


def test_parse_docstring_fallback_without_docstring_parser(monkeypatch):
    monkeypatch.setattr(reflection, "_HAS_DOCSTRING_PARSER", False)
    summary, param_docs, full = _parse_docstring("First line.\nSecond line.")
    assert summary == "First line."
    assert param_docs == {}
    assert full == "First line.\nSecond line."


def test_parse_docstring_fallback_when_parser_raises(monkeypatch):
    class Boom:
        @staticmethod
        def parse(_doc):
            raise ValueError("bad docstring")

    monkeypatch.setattr(reflection, "_HAS_DOCSTRING_PARSER", True)
    monkeypatch.setattr(reflection, "docstring_parser", Boom, raising=False)
    summary, param_docs, full = _parse_docstring("Fallback line.\nmore")
    assert (summary, param_docs) == ("Fallback line.", {})
    assert full == "Fallback line.\nmore"


def test_guess_output_type_for_class_is_class_name():
    assert _guess_output_type(Widget, True) == "Widget"


def test_guess_output_type_reads_return_annotation():
    assert _guess_output_type(documented, False) == "float"


def test_guess_output_type_falls_back_to_any_for_unsupported_callable():
    assert _guess_output_type(print, False) in ("Any", "None")


def test_reflect_function_builds_params_and_ports():
    spec = reflect(documented, category="tests")
    assert [p.name for p in spec.params] == ["alpha", "beta"]

    alpha, beta = spec.params
    assert (alpha.annotation, alpha.required, alpha.has_default) == ("int", True, False)
    assert alpha.description == "The alpha parameter."
    assert alpha.kind == str(inspect.Parameter.POSITIONAL_OR_KEYWORD)
    assert (beta.annotation, beta.required, beta.has_default, beta.default) == (
        "str", False, True, "x")

    assert [i.name for i in spec.inputs] == ["alpha", "beta"]
    assert all(i.direction == "in" for i in spec.inputs)
    assert [(o.name, o.annotation, o.direction) for o in spec.outputs] == [
        ("result", "float", "out")]


def test_reflect_function_metadata():
    spec = reflect(documented, category="tests")
    assert spec.id == f"{__name__}.documented"
    assert spec.display_name == "documented"
    assert spec.category == "tests"
    assert spec.description == "Short summary line."
    assert spec.kind == "function"
    assert spec.callable_ref is documented
    assert spec.import_path == f"from {__name__} import documented"


def test_reflect_uses_module_as_default_category():
    assert reflect(documented).category == __name__


def test_reflect_honours_explicit_display_name_and_import_path():
    spec = reflect(documented, display_name="Documented Block",
                   import_path="import documented")
    assert spec.display_name == "Documented Block"
    assert spec.import_path == "import documented"


def test_reflect_skips_var_positional_and_var_keyword():
    spec = reflect(variadic)
    assert [p.name for p in spec.params] == ["a", "b"]


def test_reflect_class_uses_init_signature_without_self():
    spec = reflect(Widget, category="tests")
    assert spec.kind == "class"
    assert [p.name for p in spec.params] == ["size", "name"]
    assert spec.params[0].description == "The widget size."
    assert spec.outputs[0].annotation == "Widget"


def test_reflect_method_skips_self():
    spec = reflect(Widget.scale)
    assert [p.name for p in spec.params] == ["factor"]
    assert spec.id.endswith("Widget.scale")


def test_reflect_callable_without_signature_yields_no_params():
    class NoSignature:
        __name__ = "NoSignature"
        __module__ = "tests"

        def __call__(self):  # pragma: no cover - never invoked
            return None

        @property
        def __signature__(self):
            raise ValueError("no signature available")

    spec = reflect(NoSignature())
    assert spec.params == []
    assert spec.inputs == []


def test_reflect_builtin_without_module_still_produces_spec():
    spec = reflect(len)
    assert spec.display_name == "len"
    assert "len" in spec.import_path
