import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import profile_calibration


VALID = {
    "schema_version": "cordia-profile-v1",
    "survey_version": "research-2026-08",
    "profile_id": "profile_018f0f4d",
    "communication": {
        "explicit_implicit": 7.3,
        "detail_big_picture": 2.0,
        "indirect_direct": 3.5,
        "reasoning_before_conclusion": True,
        "infer_unstated_context": True,
    },
    "domains": [{"id": "technology_software", "self_rating": 5,
                 "calibration": "consistent"}],
    "personality": {},
    "natural_requests": ["Show me how the dependencies fit together."],
    "completed_at": "2026-08-20T12:00:00Z",
}


class TestProfileCalibrationContract(unittest.TestCase):
    def test_validate_result_returns_a_copy_of_the_exact_v1_contract(self):
        result = profile_calibration.validate_result(VALID)

        self.assertEqual(result, VALID)
        self.assertIsNot(result, VALID)

    def test_validate_result_rejects_unknown_fields_and_out_of_range_scores(self):
        for bad in (
            {**VALID, "unexpected": "model prompt injection"},
            {**VALID, "communication": {**VALID["communication"],
                                     "explicit_implicit": 10.1}},
        ):
            with self.assertRaises(ValueError):
                profile_calibration.validate_result(bad)


if __name__ == "__main__":
    unittest.main()
