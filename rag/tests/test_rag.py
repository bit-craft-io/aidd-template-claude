import os
import tempfile
import unittest

import rag


class DocTypeTest(unittest.TestCase):
    def test_shared(self):
        self.assertEqual(rag.doc_type_of("decisions/shared/x.md"), "shared")

    def test_adr(self):
        self.assertEqual(rag.doc_type_of("decisions/adr-0001-x.md"), "adr")

    def test_non_adr_in_decisions_is_other(self):
        self.assertEqual(rag.doc_type_of("decisions/notes.md"), "other")

    def test_design(self):
        self.assertEqual(rag.doc_type_of("design/10-x.md"), "design")

    def test_plan_including_archive(self):
        self.assertEqual(rag.doc_type_of("superpowers/plans/archive/2026-09/x.md"), "plan")

    def test_other(self):
        self.assertEqual(rag.doc_type_of("brainstorming-intake.md"), "other")


class SplitMarkdownTest(unittest.TestCase):
    def test_splits_at_headings(self):
        text = "# 題\n前文\n\n## A\naaa\n\n## B\nbbb\n"
        chunks = rag.split_markdown("design/x.md", text)
        self.assertEqual([c.heading for c in chunks], ["題", "A", "B"])
        self.assertTrue(all(c.path == "design/x.md" for c in chunks))
        self.assertTrue(all(c.text.startswith("[design/x.md]\n") for c in chunks))

    def test_h4_does_not_split(self):
        text = "## 節\nあ\n\n#### 小見出し\nい\n"
        chunks = rag.split_markdown("x.md", text)
        self.assertEqual(len(chunks), 1)
        self.assertIn("小見出し", chunks[0].text)

    def test_hash_in_code_fence_is_not_heading(self):
        text = "## 手順\n```bash\n# コメント\nls\n```\n## 次\nzzz\n"
        chunks = rag.split_markdown("x.md", text)
        self.assertEqual([c.heading for c in chunks], ["手順", "次"])
        self.assertIn("# コメント", chunks[0].text)

    def test_empty_document(self):
        self.assertEqual(rag.split_markdown("x.md", ""), [])
        self.assertEqual(rag.split_markdown("x.md", "\n\n  \n"), [])

    def test_no_heading_document(self):
        chunks = rag.split_markdown("x.md", "ただの文\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "")

    def test_crlf_and_bom(self):
        chunks = rag.split_markdown("x.md", "﻿# 題\r\n本文\r\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "題")
        self.assertIn("本文", chunks[0].text)
        self.assertNotIn("\r", chunks[0].text)
        self.assertNotIn("﻿", chunks[0].text)

    def test_long_section_is_cut_by_paragraph(self):
        para = "あ" * 800
        text = "## 長い\n\n" + "\n\n".join([para, para, para])
        chunks = rag.split_markdown("x.md", text)
        self.assertGreaterEqual(len(chunks), 3)
        for c in chunks:
            body = c.text.split("\n", 1)[1]
            self.assertLessEqual(len(body), rag.MAX_CHUNK)

    def test_single_long_paragraph_is_not_split(self):
        chunks = rag.split_markdown("x.md", "## 長い\n" + "い" * 3000)
        self.assertEqual(len(chunks), 1)


class IterMarkdownTest(unittest.TestCase):
    def test_walks_md_only_and_applies_excludes(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in ["a.md", "sub/b.md", "c.txt", "tmpl/t.md"]:
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write("x")
            got = [rel for rel, _ in rag.iter_markdown(d, excludes=["tmpl/*"])]
            self.assertEqual(got, ["a.md", "sub/b.md"])


class VecLiteralTest(unittest.TestCase):
    def test_literal(self):
        self.assertEqual(rag.vec_literal([1, 0.5]), "[1.0,0.5]")


class EmbedTest(unittest.TestCase):
    def test_empty_input_needs_no_network(self):
        self.assertEqual(rag.embed([]), [])

    def test_unreachable_ollama_has_hint(self):
        with self.assertRaises(RuntimeError) as cm:
            rag.embed(["x"], url="http://127.0.0.1:9")
        self.assertIn("Ollama に繋がらぬ", str(cm.exception))
        self.assertIn("make rag-up", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
