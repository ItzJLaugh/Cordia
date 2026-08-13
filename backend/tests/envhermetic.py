#!/usr/bin/env python3
"""Shared test base: hermetic against the personalization kill switch.

Any suite whose fixtures call framework/adaptation code live must run with
PERSONALIZATION_MODE unset — the kill switch is read at call time, so a
developer (or CI) exporting ``off`` would collapse every personalized
fixture to the generic shape and fail tests for the wrong reason. The
developer's own environment is restored after each test.
"""
import os
import unittest


class EnvHermeticCase(unittest.TestCase):
    def setUp(self):
        prior = os.environ.pop("PERSONALIZATION_MODE", None)
        if prior is not None:
            self.addCleanup(os.environ.__setitem__, "PERSONALIZATION_MODE", prior)
