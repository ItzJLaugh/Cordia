import os
import subprocess
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEmbeddingRuntime(unittest.TestCase):
    def test_declared_runtime_can_import_the_shadow_scorer(self):
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    "import embedding_scoring; "
                    "assert callable(embedding_scoring.score_course); "
                    "print('CORDIA_EMBEDDING_RUNTIME_OK')"
                ),
            ],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [line for line in result.stdout.splitlines() if line][-1],
            'CORDIA_EMBEDDING_RUNTIME_OK',
        )


if __name__ == '__main__':
    unittest.main()
