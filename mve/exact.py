"""Bounded algebraic expression parser; never evaluates Python or accepts floats."""

import ast
import re
import sympy as sp


def _number(node, depth=0):
    if depth > 24:
        raise ValueError("exact expression nesting limit")
    if isinstance(node, ast.Constant) and type(node.value) is int:
        if abs(node.value).bit_length() > 80:
            raise ValueError("integer magnitude limit")
        return sp.Integer(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_number(node.operand, depth + 1)
    if isinstance(node, ast.Call):
        if (
            not isinstance(node.func, ast.Name)
            or node.func.id != "sqrt"
            or len(node.args) != 1
            or node.keywords
            or not isinstance(node.args[0], ast.Constant)
            or type(node.args[0].value) is not int
            or node.args[0].value < 0
        ):
            raise ValueError("only sqrt(nonnegative integer) is allowed")
        return sp.sqrt(_number(node.args[0], depth + 1))
    if isinstance(node, ast.BinOp):
        left, right = _number(node.left, depth + 1), _number(node.right, depth + 1)
        operations = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
        }
        if isinstance(node.op, ast.Pow):
            if (
                left.is_Rational
                and (int(left.p).bit_length() + int(left.q).bit_length()) * abs(right)
                > 4096
            ):
                raise ValueError("exact arithmetic growth limit")
            if not right.is_Integer or abs(right) > 8:
                raise ValueError("integer exponent must be between -8 and 8")
            return left**right
        if type(node.op) in operations:
            return operations[type(node.op)]()
    raise ValueError("unsupported exact expression")


def canonical_exact(text):
    if not isinstance(text, str) or not 0 < len(text) <= 120:
        raise ValueError("exact expression length must be 1..120")
    if not re.fullmatch(r"[0-9sqrt()+*/^\- ]+", text) or "**" in text:
        raise ValueError("invalid exact expression alphabet")
    try:
        tree = ast.parse(text.replace("^", "**"), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 80:
            raise ValueError("exact expression complexity limit")
        value = sp.expand(sp.nsimplify(_number(tree.body), rational=True))
        if value.is_real is not True or value.is_finite is not True:
            raise ValueError("exact expression must be finite and real")
        rendered = sp.sstr(value).replace("**", "^").replace(" ", "")
        if len(rendered) > 120:
            raise ValueError("canonical expression length limit")
        return rendered
    except (SyntaxError, TypeError, ZeroDivisionError, RecursionError) as exc:
        raise ValueError("invalid exact expression") from exc
