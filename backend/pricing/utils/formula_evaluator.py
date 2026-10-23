"""Avaluació segura de les fórmules de tarifes i ajustos, sense eval.

La fórmula es parseja amb ast i només s'accepten números, textos, operacions aritmètiques,
comparacions, and/or/not, `x if condició else y`, les variables %nom i una llista tancada de
funcions. Res d'atributs, imports, lambdes, subíndexs ni noms lliures: no es pot arribar a cap
objecte de Python.
"""
import ast
import math
import operator
import re

MAX_FORMULA_LENGTH = 1000
MAX_POWER_EXPONENT = 100
MAX_ABS_NUMBER = 1e15

# %contract.persons, %variable.5021... També entre cometes ('%contract.communication_type'),
# com calia escriure-la amb l'eval per comparar textos: llavors és la mateixa variable.
_VARIABLE_RE = re.compile(r"""(['"]?)%([A-Za-z_][\w.]*\w|[A-Za-z_])\1""")

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_FUNCTIONS = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'int': int,
    'float': float,
    'math.ceil': math.ceil,
    'math.floor': math.floor,
    'math.sqrt': math.sqrt,
}


class FormulaError(ValueError):
    pass


def _function_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f'{node.value.id}.{node.attr}'
    return None


def _check(node, names):
    """Comprova tot l'arbre abans d'avaluar-lo, també les branques que no s'executaran."""
    if isinstance(node, ast.Expression):
        return _check(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
        return
    if isinstance(node, ast.Name) and node.id in names:
        return
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        _check(node.left, names)
        return _check(node.right, names)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _check(node.operand, names)
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            _check(value, names)
        return
    if isinstance(node, ast.Compare) and all(type(op) in _COMPARE_OPS for op in node.ops):
        for child in [node.left, *node.comparators]:
            _check(child, names)
        return
    if isinstance(node, ast.IfExp):
        for child in (node.test, node.body, node.orelse):
            _check(child, names)
        return
    if isinstance(node, ast.Call) and not node.keywords and _function_name(node.func) in _FUNCTIONS:
        for arg in node.args:
            _check(arg, names)
        return
    if isinstance(node, ast.Tuple):
        raise FormulaError('Fórmula no vàlida: els decimals s\'escriuen amb punt (0.5), no amb coma')
    raise FormulaError(f'Element no permès a la fórmula: {ast.unparse(node)[:80]}')


def _check_number(value):
    if isinstance(value, (int, float)) and abs(value) > MAX_ABS_NUMBER:
        raise FormulaError('Resultat massa gran')
    return value


def _eval(node, names):
    if isinstance(node, ast.Expression):
        return _eval(node.body, names)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, names)
        right = _eval(node.right, names)
        # Només números: 'a' * 10**9 ompliria la memòria.
        if not all(isinstance(x, (int, float)) for x in (left, right)):
            raise FormulaError('Operació aritmètica amb un valor que no és un número')
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER_EXPONENT:
            raise FormulaError('Exponent massa gran')
        return _check_number(_BIN_OPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPS[type(node.op)](_eval(node.operand, names))
    if isinstance(node, ast.BoolOp):
        # and/or de Python: torna el primer valor que decideix el resultat.
        stop_when = not isinstance(node.op, ast.And)
        for value in node.values:
            result = _eval(value, names)
            if bool(result) == stop_when:
                return result
        return result
    if isinstance(node, ast.Compare):
        left = _eval(node.left, names)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, names)
            if not _COMPARE_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body if _eval(node.test, names) else node.orelse, names)
    if isinstance(node, ast.Call):
        function = _FUNCTIONS[_function_name(node.func)]
        return _check_number(function(*(_eval(arg, names) for arg in node.args)))
    raise FormulaError(f'Element no permès a la fórmula: {ast.unparse(node)[:80]}')


def _as_value(value):
    """Valor d'una variable tal com l'entenia l'eval: un text numèric és un número."""
    if isinstance(value, str):
        for number_type in (int, float):
            try:
                return number_type(value)
            except ValueError:
                pass
    return value


def _parse(formula, variables):
    """Arbre de la fórmula i els valors de les variables, amb un nom intern per a cada %variable."""
    if len(formula) > MAX_FORMULA_LENGTH:
        raise FormulaError('Fórmula massa llarga')
    names = {}

    def to_name(match):
        key = match.group(2)
        if key not in variables:
            raise FormulaError(f'Variable desconeguda: %{key}')
        name = f'v{len(names)}'
        names[name] = _as_value(variables[key])
        return name

    expression = _VARIABLE_RE.sub(to_name, formula.strip())
    try:
        tree = ast.parse(expression, mode='eval')
        _check(tree, names)
    except SyntaxError as e:
        raise FormulaError(f'Sintaxi incorrecta a la fórmula: {e.msg}') from e
    except RecursionError as e:
        raise FormulaError('Fórmula massa niuada') from e
    return tree, names


def evaluate(formula, variables):
    """Avalua `formula` amb els valors de `variables` ({'contract.persons': 3, ...}).

    Llença FormulaError si la fórmula no és vàlida, fa servir una variable que no existeix o
    no es pot calcular (divisió per zero, tipus incompatibles...).
    """
    tree, names = _parse(formula, variables)
    try:
        return _eval(tree, names)
    except FormulaError:
        raise
    except (ArithmeticError, TypeError, ValueError, RecursionError) as e:
        raise FormulaError(str(e)) from e


class _AnyVariable(dict):
    """Accepta qualsevol %variable: en desar no se sap quines tindrà cada contracte."""

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return 1


def validate(formula):
    """Comprova en desar que la fórmula només fa servir elements permesos (sense avaluar-la)."""
    _parse(formula, _AnyVariable())
