from django.test import TestCase


class WriteupMarkdownRenderingTests(TestCase):
    """Ensure Markdown is rendered correctly for writeups."""

    def test_markdownify_renders_headers(self):
        from Blogs.templatetags.markdown_extras import markdownify
        out = markdownify("# Hello\n## World")
        self.assertIn("<h1>", out)
        self.assertIn("Hello", out)
        self.assertIn("<h2>", out)
        self.assertIn("World", out)

    def test_markdownify_renders_bold_and_italic(self):
        from Blogs.templatetags.markdown_extras import markdownify
        out = markdownify("**bold** and *italic*")
        self.assertIn("<strong>", out)
        self.assertIn("bold", out)
        self.assertIn("<em>", out)
        self.assertIn("italic", out)

    def test_markdownify_renders_fenced_code(self):
        from Blogs.templatetags.markdown_extras import markdownify
        out = markdownify("```\nprint('hi')\n```")
        self.assertIn("<pre>", out)
        self.assertIn("<code>", out)
        self.assertIn("print", out)

    def test_markdownify_renders_tables(self):
        from Blogs.templatetags.markdown_extras import markdownify
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        out = markdownify(md)
        self.assertIn("<table>", out)
        self.assertIn("<th>", out)
        self.assertIn("<td>", out)

    def test_markdownify_handles_none_and_empty(self):
        from Blogs.templatetags.markdown_extras import markdownify
        self.assertEqual(markdownify(None), "")
        self.assertEqual(markdownify(""), "")
        self.assertEqual(markdownify("   "), "")

    def test_markdown_to_plain_strips_markdown(self):
        from Blogs.templatetags.markdown_extras import markdown_to_plain
        plain = markdown_to_plain("# Title\n**bold** text")
        self.assertNotIn("#", plain)
        self.assertNotIn("**", plain)
        self.assertIn("Title", plain)
        self.assertIn("bold", plain)
