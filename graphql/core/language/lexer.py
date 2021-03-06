import json
from ..compat import unichr
from .error import LanguageError

__all__ = ['Token', 'Lexer', 'TokenKind',
           'get_token_desc', 'get_token_kind_desc']


class Token(object):
    __slots__ = ['kind', 'start', 'end', 'value']

    def __init__(self, kind, start, end, value=None):
        self.kind = kind
        self.start = start
        self.end = end
        self.value = value

    def __repr__(self):
        return '<Token kind={} at {}..{} value={}>'.format(
            get_token_kind_desc(self.kind),
            self.start,
            self.end,
            self.value if self.value is not None else 'None'
        )

    def __eq__(self, other):
        return (self.kind == other.kind and
                self.start == other.start and
                self.end == other.end and
                self.value == other.value)


class Lexer(object):
    __slots__ = ['source', 'prev_position']

    def __init__(self, source):
        self.source = source
        self.prev_position = 0

    def next_token(self, reset_position=None):
        if reset_position is None:
            reset_position = self.prev_position
        token = read_token(self.source, reset_position)
        self.prev_position = token.end
        return token


class TokenKind(object):
    EOF = 1
    BANG = 2
    DOLLAR = 3
    PAREN_L = 4
    PAREN_R = 5
    SPREAD = 6
    COLON = 7
    EQUALS = 8
    AT = 9
    BRACKET_L = 10
    BRACKET_R = 11
    BRACE_L = 12
    PIPE = 13
    BRACE_R = 14
    NAME = 15
    VARIABLE = 16
    INT = 17
    FLOAT = 18
    STRING = 19


def get_token_desc(token):
    if token.value:
        return '{} "{}"'.format(
            get_token_kind_desc(token.kind),
            token.value
        )
    else:
        return get_token_kind_desc(token.kind)


TOKEN_DESCRIPTION = {
    TokenKind.EOF: 'EOF',
    TokenKind.BANG: '!',
    TokenKind.DOLLAR: '$',
    TokenKind.PAREN_L: '(',
    TokenKind.PAREN_R: ')',
    TokenKind.SPREAD: '...',
    TokenKind.COLON: ':',
    TokenKind.EQUALS: '=',
    TokenKind.AT: '@',
    TokenKind.BRACKET_L: '[',
    TokenKind.BRACKET_R: ']',
    TokenKind.BRACE_L: '{',
    TokenKind.PIPE: '|',
    TokenKind.BRACE_R: '}',
    TokenKind.NAME: 'Name',
    TokenKind.VARIABLE: 'Variable',
    TokenKind.INT: 'Int',
    TokenKind.FLOAT: 'Float',
    TokenKind.STRING: 'String',
}

get_token_kind_desc = TOKEN_DESCRIPTION.get


def char_code_at(s, pos):
    if 0 <= pos < len(s):
        return ord(s[pos])
    return 0


PUNCT_CODE_TO_KIND = {
    ord('!'): TokenKind.BANG,
    ord('$'): TokenKind.DOLLAR,
    ord('('): TokenKind.PAREN_L,
    ord(')'): TokenKind.PAREN_R,
    ord(':'): TokenKind.COLON,
    ord('='): TokenKind.EQUALS,
    ord('@'): TokenKind.AT,
    ord('['): TokenKind.BRACKET_L,
    ord(']'): TokenKind.BRACKET_R,
    ord('{'): TokenKind.BRACE_L,
    ord('|'): TokenKind.PIPE,
    ord('}'): TokenKind.BRACE_R,
}


def read_token(source, from_position):
    """Gets the next token from the source starting at the given position.

    This skips over whitespace and comments until it finds the next lexable
    token, then lexes punctuators immediately or calls the appropriate
    helper fucntion for more complicated tokens."""
    body = source.body
    body_length = len(body)

    position = position_after_whitespace(body, from_position)
    code = char_code_at(body, position)

    if position >= body_length:
        return Token(TokenKind.EOF, position, position)

    kind = PUNCT_CODE_TO_KIND.get(code)
    if kind is not None:
        return Token(kind, position, position + 1)

    if code == 46:  # .
        if char_code_at(body, position + 1) == 46 and \
                char_code_at(body, position + 2) == 46:
            return Token(TokenKind.SPREAD, position, position + 3)
    elif 65 <= code <= 90 or code == 95 or 97 <= code <= 122:
        # A-Z, _, a-z
        return read_name(source, position)
    elif code == 45 or 48 <= code <= 57:  # -, 0-9
        return read_number(source, position, code)
    elif code == 34:  # "
        return read_string(source, position)

    raise LanguageError(
        source, position,
        u'Unexpected character {}'.format(json.dumps(body[position])))


def position_after_whitespace(body, start_position):
    """Reads from body starting at start_position until it finds a
    non-whitespace or commented character, then returns the position of
    that character for lexing."""
    body_length = len(body)
    position = start_position
    while position < body_length:
        code = char_code_at(body, position)
        if code in (
            32,  # space
            44,  # comma
            160,  # '\xa0'
            0x2028,  # line separator
            0x2029,  # paragraph separator
        ) or (code > 8 and code < 14):  # whitespace
            position += 1
        elif code == 35:  # #, skip comments
            position += 1
            while position < body_length:
                code = char_code_at(body, position)
                if not code or code in (10, 13, 0x2028, 0x2029):
                    break
                position += 1
        else:
            break
    return position


def read_number(source, start, first_code):
    """Reads a number token from the source file, either a float
    or an int depending on whether a decimal point appears.

    Int:   -?(0|[1-9][0-9]*)
    Float: -?(0|[1-9][0-9]*)\.[0-9]+(e-?[0-9]+)?"""
    code = first_code
    body = source.body
    position = start
    is_float = False

    if code == 45:  # -
        position += 1
        code = char_code_at(body, position)

    if code == 48:  # 0
        position += 1
        code = char_code_at(body, position)
    elif 49 <= code <= 57:  # 1 - 9
        position += 1
        code = char_code_at(body, position)
        while 48 <= code <= 57:  # 0 - 9
            position += 1
            code = char_code_at(body, position)
    else:
        raise LanguageError(source, position, 'Invalid number')

    if code == 46:  # .
        is_float = True

        position += 1
        code = char_code_at(body, position)
        if 48 <= code <= 57:  # 0 - 9
            position += 1
            code = char_code_at(body, position)
            while 48 <= code <= 57:  # 0 - 9
                position += 1
                code = char_code_at(body, position)
        else:
            raise LanguageError(source, position, 'Invalid number')

        if code == 101:  # e
            position += 1
            code = char_code_at(body, position)
            if code == 45:  # -
                position += 1
                code = char_code_at(body, position)
            if 48 <= code <= 57:  # 0 - 9
                position += 1
                code = char_code_at(body, position)
                while 48 <= code <= 57:  # 0 - 9
                    position += 1
                    code = char_code_at(body, position)
            else:
                raise LanguageError(source, position, 'Invalid number')

    return Token(
        TokenKind.FLOAT if is_float else TokenKind.INT,
        start,
        position,
        body[start:position]
    )


ESCAPED_CHAR_CODES = {
    34: '"',
    47: '/',
    92: '\\',
    98: '\b',
    102: '\f',
    110: '\n',
    114: '\r',
    116: '\t',
}


def read_string(source, start):
    """Reads a string token from the source file.

    "([^"\\\u000A\u000D\u2028\u2029]|(\\(u[0-9a-fA-F]{4}|["\\/bfnrt])))*"
    """
    body = source.body
    position = start + 1
    chunk_start = position
    code = None
    value = u''

    while position < len(body):
        code = char_code_at(body, position)
        if not code or code in (34, 10, 13, 0x2028, 0x2029):
            break
        position += 1
        if code == 92:  # \
            value += body[chunk_start:position - 1]
            code = char_code_at(body, position)
            escaped = ESCAPED_CHAR_CODES.get(code)
            if escaped is not None:
                value += escaped
            elif code == 117:
                char_code = uni_char_code(
                    char_code_at(body, position + 1) or 0,
                    char_code_at(body, position + 2) or 0,
                    char_code_at(body, position + 3) or 0,
                    char_code_at(body, position + 4) or 0,
                )
                if char_code < 0:
                    raise LanguageError(
                        source, position,
                        'Bad character escape sequence')
                value += unichr(char_code)
                position += 4
            else:
                raise LanguageError(
                    source, position,
                    'Bad character escape sequence')
            position += 1
            chunk_start = position

    if code != 34:
        raise LanguageError(source, position, 'Unterminated string')

    value += body[chunk_start:position]
    return Token(TokenKind.STRING, start, position + 1, value)


def uni_char_code(a, b, c, d):
    """Converts four hexidecimal chars to the integer that the
    string represents. For example, uniCharCode('0','0','0','f')
    will return 15, and uniCharCode('0','0','f','f') returns 255.

    Returns a negative number on error, if a char was invalid.

    This is implemented by noting that char2hex() returns -1 on error,
    which means the result of ORing the char2hex() will also be negative.
    """
    return (char2hex(a) << 12 | char2hex(b) << 8 |
            char2hex(c) << 4 | char2hex(d))


def char2hex(a):
    """Converts a hex character to its integer value.
    '0' becomes 0, '9' becomes 9
    'A' becomes 10, 'F' becomes 15
    'a' becomes 10, 'f' becomes 15

    Returns -1 on error."""
    if 48 <= a <= 57:  # 0-9
        return a - 48
    elif 65 <= a <= 70:  # A-F
        return a - 55
    elif 97 <= a <= 102:  # a-f
        return a - 87
    return -1


def read_name(source, position):
    """Reads an alphanumeric + underscore name from the source.

    [_A-Za-z][_0-9A-Za-z]*"""
    body = source.body
    body_length = len(body)
    end = position + 1
    code = None
    while end != body_length:
        code = char_code_at(body, end)
        if not code or not (
            code == 95 or  # _
            48 <= code <= 57 or  # 0-9
            65 <= code <= 90 or  # A-Z
            97 <= code <= 122  # a-z
        ):
            break
        end += 1
    return Token(TokenKind.NAME, position, end, body[position:end])
