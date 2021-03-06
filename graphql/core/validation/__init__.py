from ..error import GraphQLError
from ..language.ast import FragmentDefinition, FragmentSpread
from ..language.visitor import Visitor, visit
from ..utils import TypeInfo
from ..type import GraphQLSchema
from . import rules as Rules

specified_rules = [
    Rules.UniqueOperationNames,
    Rules.LoneAnonymousOperation,
    Rules.KnownTypeNames,
    Rules.FragmentsOnCompositeTypes,
    Rules.VariablesAreInputTypes,
    Rules.ScalarLeafs,
    Rules.FieldsOnCorrectType,
    Rules.UniqueFragmentNames,
    Rules.KnownFragmentNames,
    Rules.NoUnusedFragments,
    Rules.PossibleFragmentSpreads,
    Rules.NoFragmentCycles,
    Rules.NoUndefinedVariables,
    Rules.NoUnusedVariables,
    Rules.KnownDirectives,
    Rules.KnownArgumentNames,
    Rules.UniqueArgumentNames,
    Rules.ArgumentsOfCorrectType,
    Rules.ProvidedNonNullArguments,
    Rules.DefaultValuesOfCorrectType,
    Rules.VariablesInAllowedPosition,
    Rules.OverlappingFieldsCanBeMerged,
]


def validate(schema, ast, rules=None):
    assert schema, 'Must provide schema'
    assert ast, 'Must provide document'
    assert isinstance(schema, GraphQLSchema)
    if rules is None:
        rules = specified_rules
    return visit_using_rules(schema, ast, rules)


def visit_using_rules(schema, ast, rules):
    type_info = TypeInfo(schema)
    context = ValidationContext(schema, ast, type_info)
    errors = []
    for rule in rules:
        instance = rule(context)
        visit(ast, ValidationVisitor(instance, type_info, errors))
    return errors


class ValidationVisitor(Visitor):
    __slots__ = ['instance', 'type_info', 'errors', 'visit_spread_fragments']

    def __init__(self, instance, type_info, errors):
        self.instance = instance
        self.type_info = type_info
        self.errors = errors
        self.visit_spread_fragments = getattr(self.instance, 'visit_spread_fragments', False)

    def enter(self, node, key, parent, path, ancestors):
        self.type_info.enter(node)

        if isinstance(node, FragmentDefinition) and key and self.visit_spread_fragments:
            return False

        result = self.instance.enter(node, key, parent, path, ancestors)
        if result and is_error(result):
            append(self.errors, result)
            result = False

        if result is None and self.visit_spread_fragments and isinstance(node, FragmentSpread):
            fragment = self.instance.context.get_fragment(node.name.value)
            if fragment:
                visit(fragment, self)

        if result is False:
            self.type_info.leave(node)

        return result

    def leave(self, node, key, parent, path, ancestors):
        result = self.instance.leave(node, key, parent, path, ancestors)

        if result and is_error(result):
            append(self.errors, result)
            result = False

        self.type_info.leave(node)
        return result


def is_error(value):
    if isinstance(value, list):
        return all(isinstance(item, GraphQLError) for item in value)
    return isinstance(value, GraphQLError)


def append(arr, items):
    if isinstance(items, list):
        arr.extend(items)
    else:
        arr.append(items)


class ValidationContext(object):
    __slots__ = ['_schema', '_ast', '_type_info', '_fragments']

    def __init__(self, schema, ast, type_info):
        self._schema = schema
        self._ast = ast
        self._type_info = type_info
        self._fragments = None

    def get_schema(self):
        return self._schema

    def get_ast(self):
        return self._ast

    def get_fragment(self, name):
        fragments = self._fragments
        if fragments is None:
            self._fragments = fragments = {}
            for statement in self.get_ast().definitions:
                if isinstance(statement, FragmentDefinition):
                    fragments[statement.name.value] = statement
        return fragments.get(name)

    def get_type(self):
        return self._type_info.get_type()

    def get_parent_type(self):
        return self._type_info.get_parent_type()

    def get_input_type(self):
        return self._type_info.get_input_type()

    def get_field_def(self):
        return self._type_info.get_field_def()

    def get_directive(self):
        return self._type_info.get_directive()

    def get_argument(self):
        return self._type_info.get_argument()
