# -*- coding: utf-8 -*-
"""
测试任务1 - 基础功能测试
"""
import unittest


def hello(name: str) -> str:
    """示例函数：返回问候语"""
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if not name.strip():
        raise ValueError("name cannot be empty")
    return f"Hello, {name.strip()}!"


class TestHello(unittest.TestCase):
    """测试 hello 函数"""

    def test_normal_name(self):
        self.assertEqual(hello("World"), "Hello, World!")

    def test_name_with_spaces(self):
        self.assertEqual(hello("  OpenClaw  "), "Hello, OpenClaw!")

    def test_empty_name(self):
        with self.assertRaises(ValueError):
            hello("")

    def test_non_string(self):
        with self.assertRaises(TypeError):
            hello(123)


if __name__ == "__main__":
    unittest.main()
