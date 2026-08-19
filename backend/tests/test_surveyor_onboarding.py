import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import freeform, pipeline, question_strategy, scenarios, types


def stage_attempt(stage, key, answer):
    return [
        {
            "role": "assistant",
            "content": f"question-{key}",
            "meta": {
                "stage": stage,
                "key": key,
                "signal": key if stage == "preferences" else None,
            },
        },
        {"role": "user", "content": answer, "meta": {}},
    ]


def preference_history(count):
    history = []
    for index, key in enumerate(types.SIGNAL_PRIORITY[:count]):
        history.extend(stage_attempt("preferences", key, f"answer-{index}"))
    return history


class TestBoundedOnboarding(unittest.TestCase):
    def test_sequence_uses_six_preferences_three_scenarios_three_freeform_turns(self):
        profile = types.empty_profile()
        history = []
        stages = []

        for turn in range(types.ONBOARDING_TURN_LIMIT):
            step = question_strategy.next_step(profile, history)
            stages.append(step["stage"])
            history.extend(stage_attempt(step["stage"], step["key"], f"answer-{turn}"))
            profile["questions_answered"] = turn + 1

        self.assertEqual(
            stages,
            ["preferences"] * 6 + ["scenarios"] * 3 + ["freeform"] * 3,
        )
        self.assertEqual(question_strategy.next_step(profile, history)["stage"], "done")

    def test_invalid_typed_scenario_attempt_moves_forward_without_inventing_a_choice(self):
        profile = types.empty_profile()
        history = preference_history(6) + stage_attempt(
            "scenarios", scenarios.IDS[0], "typed answer"
        )

        step = question_strategy.next_step(profile, history)

        self.assertEqual(step["stage"], "scenarios")
        self.assertEqual(step["key"], scenarios.IDS[1])
        self.assertEqual(profile["scenarios"], {})

    def test_public_status_is_complete_at_the_cap_and_contains_no_numeric_score(self):
        profile = types.empty_profile()
        profile["questions_answered"] = 12

        status = pipeline.onboarding_status(profile)

        self.assertEqual(
            status,
            {
                "turn_limit": 12,
                "turns_used": 12,
                "turns_remaining": 0,
                "complete": True,
            },
        )
        self.assertNotIn("score", repr(status).lower())

    def test_status_clamps_legacy_counts_and_malformed_profiles(self):
        self.assertEqual(pipeline.onboarding_status(None)["turns_used"], 0)
        self.assertEqual(
            pipeline.onboarding_status({"questions_answered": "bad"})["turns_used"], 0
        )
        self.assertEqual(
            pipeline.onboarding_status({"questions_answered": 99})["turns_used"], 12
        )
        self.assertEqual(
            pipeline.onboarding_status({"questions_answered": 99})["turns_remaining"], 0
        )

    def test_legacy_preference_question_text_still_counts_as_attempted(self):
        first = types.SIGNAL_PRIORITY[0]
        second = types.SIGNAL_PRIORITY[1]
        history = [
            {
                "role": "assistant",
                "content": question_strategy.QUESTIONS[first],
                "meta": {},
            }
        ]

        self.assertEqual(
            question_strategy.attempted_keys(history, "preferences"), [first]
        )
        self.assertEqual(question_strategy.next_step({}, history)["key"], second)

    def test_three_stage_evidence_can_complete_before_cap_without_requiring_all_items(self):
        profile = types.empty_profile()
        profile["signals"] = {
            key: (
                f"answer-{key}"
                if types.SIGNAL_SCHEMA[key] is None
                else next(
                    value
                    for value in types.SIGNAL_SCHEMA[key]
                    if value != "unknown"
                )
            )
            for key in types.SIGNAL_PRIORITY[:6]
        }
        profile["scenarios"] = {
            item["id"]: item["options"][0][0] for item in scenarios.SCENARIOS[:3]
        }
        profile["freeform"] = {
            key: "known answer" for key in freeform.KEYS[:3]
        }

        self.assertTrue(types.onboarding_complete(profile))


if __name__ == "__main__":
    unittest.main()
