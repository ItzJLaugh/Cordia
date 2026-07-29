"""6S scoring — shadow mode.

Nothing in this package is learner-visible. cordaie_scoring.py remains
authoritative for every number shown in the product. This package computes the
6x3 dimension/tier matrix and persists it for offline comparison against human
grades. See rubric.py for why the version string is marked unvalidated.

The live path here is standard library only — no numpy, no scikit-learn — to
match the dependency boundary of every other Cordia backend service.
"""
