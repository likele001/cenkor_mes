# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展迁移 SQL 拆分：只在字符串/标识符/注释之外的分号处切。"""

from app.extension_host.migrations import split_sql


def test_semicolon_in_single_quoted_string():
    sql = "INSERT INTO t (a) VALUES ('x;y');\nSELECT 1;"
    assert split_sql(sql) == ["INSERT INTO t (a) VALUES ('x;y')", "SELECT 1"]


def test_doubled_quote_escape():
    sql = "INSERT INTO t (a) VALUES ('it''s;fine'); SELECT 2;"
    assert split_sql(sql) == ["INSERT INTO t (a) VALUES ('it''s;fine')", "SELECT 2"]


def test_backslash_escape():
    sql = "INSERT INTO t (a) VALUES ('a\\';b'); SELECT 3;"
    assert split_sql(sql) == ["INSERT INTO t (a) VALUES ('a\\';b')", "SELECT 3"]


def test_double_quoted_identifier_with_quote():
    sql = 'CREATE TABLE "we;ird" (id INT);\nSELECT "a"";b" FROM t;'
    assert split_sql(sql) == ['CREATE TABLE "we;ird" (id INT)', 'SELECT "a"";b" FROM t']


def test_backtick_identifier():
    sql = "CREATE TABLE `x;y` (id INT); SELECT 4;"
    assert split_sql(sql) == ["CREATE TABLE `x;y` (id INT)", "SELECT 4"]


def test_line_comment_removed():
    sql = "-- header note; not a break\nDROP TABLE t;\nSELECT 1; -- trailing"
    assert split_sql(sql) == ["DROP TABLE t", "SELECT 1"]


def test_block_comment_removed():
    sql = "/* CREATE TABLE a (id INT); */\nCREATE TABLE b (id INT);"
    assert split_sql(sql) == ["CREATE TABLE b (id INT)"]


def test_comment_markers_inside_string_kept():
    sql = "INSERT INTO t (a) VALUES ('-- not a comment; /* nor this */');"
    assert split_sql(sql) == ["INSERT INTO t (a) VALUES ('-- not a comment; /* nor this */')"]


def test_trailing_statement_without_semicolon():
    sql = "SELECT 1;\nSELECT 2"
    assert split_sql(sql) == ["SELECT 1", "SELECT 2"]


def test_empty_and_comment_only_input():
    assert split_sql("") == []
    assert split_sql("  \n\n  ") == []
    assert split_sql("-- only a comment;\n/* block */") == []


def test_empty_statements_skipped():
    sql = ";;\nSELECT 1;;\n\n;"
    assert split_sql(sql) == ["SELECT 1"]


def test_unterminated_quote_keeps_remainder():
    sql = "SELECT 'oops;\nSELECT 2;"
    # 引号未闭合时无法判断语句边界，整段原样交给数据库报错，不误切。
    assert split_sql(sql) == ["SELECT 'oops;\nSELECT 2;"]


def test_unterminated_block_comment_drops_remainder():
    assert split_sql("SELECT 1;\n/* never closed; SELECT 2;") == ["SELECT 1"]
