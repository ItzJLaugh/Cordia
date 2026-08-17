import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime_paths import DEFAULT_CORPUS_DIRECTORY, corpus_directory


class TestRuntimePaths(unittest.TestCase):
    def test_corpus_directory_uses_the_production_default(self):
        self.assertEqual(corpus_directory({}), DEFAULT_CORPUS_DIRECTORY)
        self.assertEqual(DEFAULT_CORPUS_DIRECTORY, "/var/lib/cordia/corpus")

    def test_corpus_directory_accepts_only_an_explicit_absolute_override(self):
        absolute = os.path.abspath(os.path.join(os.sep, "tmp", "cordia-review-corpus"))
        self.assertEqual(corpus_directory({"CORDIA_CORPUS_DIR": absolute}), absolute)
        self.assertEqual(corpus_directory({"CORDIA_CORPUS_DIR": "relative/path"}), DEFAULT_CORPUS_DIRECTORY)
        self.assertEqual(corpus_directory({"CORDIA_CORPUS_DIR": ""}), DEFAULT_CORPUS_DIRECTORY)


if __name__ == "__main__":
    unittest.main()
