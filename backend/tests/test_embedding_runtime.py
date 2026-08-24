import os
import subprocess
import sys
import unittest
from importlib.util import find_spec


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


OPTIONAL_SHADOW_SCORER_DEPENDENCIES = ('numpy', 'sentence_transformers', 'faiss')
MISSING_OPTIONAL_SHADOW_SCORER_DEPENDENCIES = tuple(
    dependency
    for dependency in OPTIONAL_SHADOW_SCORER_DEPENDENCIES
    if find_spec(dependency) is None
)


class TestEmbeddingRuntime(unittest.TestCase):
    @unittest.skipIf(
        MISSING_OPTIONAL_SHADOW_SCORER_DEPENDENCIES,
        'optional shadow-scorer runtime dependencies unavailable: ' +
        ', '.join(MISSING_OPTIONAL_SHADOW_SCORER_DEPENDENCIES),
    )
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
