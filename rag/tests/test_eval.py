import importlib
import os
import tempfile
import unittest

evalmod = importlib.import_module("eval")

SAMPLE = """\
| 軸 | 札 | 意味 |
|---|---|---|
| 内容 | 仕様 | 何を |

| # | 内容 | 難所 | 質問 | 期待する答えの要点 | 出典 |
|---|---|---|---|---|---|
| 1 | 理由 | 基本 | なぜか | 理由 | `docs/decisions/adr-0001-x.md` |
| 2 | 仕様 | 基本 | 型は | 型 | 同上 |
| 3 | 仕様 | 答えが無い | 配布は | 無い | — |
| 4 | 理由 | 横断 | 食い違いは | 差 | `docs/decisions/adr-0005-y.md`、`docs/design/09-z.md` |
"""


class LoadQuestionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        self.tmp.write(SAMPLE)
        self.tmp.close()
        self.qs = evalmod.load_questions(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_reads_only_question_rows(self):
        self.assertEqual([q["n"] for q in self.qs], [1, 2, 3, 4])

    def test_fields(self):
        q = self.qs[0]
        self.assertEqual((q["content"], q["hard"], q["q"]), ("理由", "基本", "なぜか"))

    def test_sources_strip_docs_prefix(self):
        self.assertEqual(self.qs[0]["sources"], ["decisions/adr-0001-x.md"])

    def test_same_as_above_inherits(self):
        self.assertEqual(self.qs[1]["sources"], ["decisions/adr-0001-x.md"])

    def test_no_source(self):
        self.assertEqual(self.qs[2]["sources"], [])

    def test_multiple_sources(self):
        self.assertEqual(self.qs[3]["sources"], ["decisions/adr-0005-y.md", "design/09-z.md"])


class RankTest(unittest.TestCase):
    def test_rank_is_one_based(self):
        self.assertEqual(evalmod.rank_of(["a.md"], ["b.md", "a.md"]), 2)

    def test_rank_none_when_absent(self):
        self.assertIsNone(evalmod.rank_of(["a.md"], ["b.md"]))

    def test_any_of_sources_counts(self):
        self.assertEqual(evalmod.rank_of(["a.md", "c.md"], ["c.md"]), 1)


class SummarizeTest(unittest.TestCase):
    def test_counts(self):
        rows = [
            ({"hard": "基本"}, 1),
            ({"hard": "基本"}, None),
            ({"hard": "横断"}, 3),
        ]
        s = evalmod.summarize(rows, k=5)
        self.assertEqual((s["total"], s["top1"], s["top3"], s["topk"]), (3, 1, 2, 2))
        self.assertEqual(s["by_hard"], {"基本": (1, 2), "横断": (1, 1)})


if __name__ == "__main__":
    unittest.main()
