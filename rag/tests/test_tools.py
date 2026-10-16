import unittest

import rag


class ClampKTest(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(rag.clamp_k(5), 5)

    def test_below_is_raised(self):
        self.assertEqual(rag.clamp_k(0), 1)
        self.assertEqual(rag.clamp_k(-3), 1)

    def test_above_is_cut(self):
        self.assertEqual(rag.clamp_k(1000), 20)

    def test_not_a_number_uses_default(self):
        self.assertEqual(rag.clamp_k(None), 5)
        self.assertEqual(rag.clamp_k("x"), 5)


class FormatSourcesTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(rag.format_sources([]), "(取り込み済みの文書なし)")

    def test_rows(self):
        rows = [{"project": "p", "doc_type": "adr", "files": 2, "chunks": 5,
                 "commit": "abc1234", "model": "bge-m3"}]
        text = rag.format_sources(rows)
        for word in ["p", "adr", "2", "5", "abc1234", "bge-m3"]:
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
