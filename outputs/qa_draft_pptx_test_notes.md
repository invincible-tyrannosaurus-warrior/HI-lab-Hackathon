# QA Draft Notes

Source deck: [outputs/deck_pptx_test.json](/Users/test/Documents/New project/outputs/deck_pptx_test.json)

This draft is intended to be more realistic than the earlier demo-only QA set.

Design choices:

- It avoids pure title recall and instead checks whether the student can explain motivation, mechanism, and evidence.
- It includes comparison questions, because those are useful for revealing shallow understanding.
- It includes one harder theory question on complexity improvement, since that is a likely weak point for undergraduate learners.
- It keeps direct slide references so the resulting errors can still flow into revision and governance logic.

Suggested use:

- Use `q1`, `q2`, and `q10` as baseline comprehension checks.
- Use `q4`, `q5`, and `q6` to probe whether students understand the algorithmic mechanism.
- Use `q8` and `q9` to surface deeper theory or evidence interpretation gaps.
