# -*- coding: utf-8 -*-
"""json_parser.py: `//` и `/* */`, load_json_file, parse_json (этап 2).

Кейсы — PLAN-MERGE §6.2: комментарии внутри и вне строк, строки с `,`/`:`/`//`,
пустой JSON, отсутствующий файл, битый JSON, `parse_json(None) -> None`.
Первые два метода — порт `v1/tests/test_json_parser.py:61-82` (2 метода,
6 assert'ов), адаптированный под Python 3 (модуль больше не требует `System`).
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import json_parser


class JsonParserTestCase(unittest.TestCase):
    """Поведение парсера JSON с комментариями."""

    def test_remove_comments_preserves_string_content(self):
        # Порт v1: // и /* */ внутри строк не должны удаляться.
        raw = '{\n  "text": "a b, c: d // not comment",\n  // remove\n  "block": "x/*keep*/y",\n  /* remove */\n  "n": 1\n}'
        cleaned = json_parser._remove_json_comments(raw)
        parsed = json_parser.parse_json(cleaned)

        self.assertEqual(parsed['text'], 'a b, c: d // not comment')
        self.assertEqual(parsed['block'], 'x/*keep*/y')
        self.assertEqual(parsed['n'], 1)

    def test_load_json_file_with_comments_and_complex_string(self):
        # Порт v1: файл с комментариями и строкой со спецсимволами.
        content = '{\n  "msg": "value with spaces, comma, and colon: ok",\n  "arr": [1, 2, 3], // trailing comment\n  /* block comment */\n  "obj": {"k": "v"}\n}'
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                             encoding='utf-8')
        try:
            handle.write(content)
            handle.close()
            parsed = json_parser.load_json_file(handle.name)
            self.assertEqual(parsed['msg'], 'value with spaces, comma, and colon: ok')
            self.assertEqual(parsed['arr'], [1, 2, 3])
            self.assertEqual(parsed['obj']['k'], 'v')
        finally:
            if not handle.closed:
                handle.close()
            os.remove(handle.name)

    def test_line_comment_is_removed(self):
        cleaned = json_parser._remove_json_comments('{"a": 1} // tail\n')
        self.assertEqual(json_parser.parse_json(cleaned), {"a": 1})

    def test_block_comment_between_tokens(self):
        cleaned = json_parser._remove_json_comments('{"a": /* mid */ 2}')
        self.assertEqual(json_parser.parse_json(cleaned), {"a": 2})

    def test_multiline_block_comment(self):
        raw = '{\n/* line 1\n   line 2 */\n"a": [1, 2]\n}'
        self.assertEqual(json_parser.parse_json(json_parser._remove_json_comments(raw)),
                         {"a": [1, 2]})

    def test_escaped_quote_does_not_open_comment(self):
        # Строка содержит экранированную кавычку и // — комментарий не начинается.
        raw = r'{"p": "a\"//b"}'
        self.assertEqual(json_parser.parse_json(json_parser._remove_json_comments(raw)),
                         {"p": 'a"//b'})

    def test_parse_json_none_returns_none(self):
        self.assertIsNone(json_parser.parse_json(None))

    def test_parse_json_empty_object(self):
        self.assertEqual(json_parser.parse_json('{}'), {})

    def test_parse_json_empty_string_raises(self):
        self.assertRaises(ValueError, json_parser.parse_json, '')

    def test_missing_file_raises_ioerror(self):
        missing = os.path.join(tempfile.gettempdir(), 'no_such_config_12345.json')
        self.assertRaises(IOError, json_parser.load_json_file, missing)

    def test_broken_json_raises_value_error(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                             encoding='utf-8')
        try:
            handle.write('{"a": }')
            handle.close()
            self.assertRaises(ValueError, json_parser.load_json_file, handle.name)
        finally:
            if not handle.closed:
                handle.close()
            os.remove(handle.name)

    def test_utf8_bom_is_stripped(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                             encoding='utf-8')
        try:
            handle.write(u'\ufeff{"a": 3}')
            handle.close()
            self.assertEqual(json_parser.load_json_file(handle.name), {"a": 3})
        finally:
            if not handle.closed:
                handle.close()
            os.remove(handle.name)


if __name__ == '__main__':
    unittest.main()
