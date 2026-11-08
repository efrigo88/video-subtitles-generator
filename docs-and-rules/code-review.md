<!-- ABOUTME: Defines review evidence and safe collaboration for this repository. -->
<!-- ABOUTME: Scales review to the diff while avoiding competing edits and heavy inference. -->
# Code review and agent coordination

Review the completed implementation before final delivery. Size the review to the change: a focused change needs one reviewer; a change spanning extraction, timing, translation, and delivery benefits from separate component reviews plus an adversarial pass. Include new untracked files in the review surface rather than relying on `git diff` alone. Generated lockfile churn should be inspected for dependency changes, not mistaken for application logic.

Give reviewers the actual requirements, relevant code, base revision, recorded test results, and any known limitations. Reviews are read-only: no edits, staging, commits, branch moves, or subagents launched by reviewers. They must not run the test suite, download models, or process the movie. Reviewers report concrete file/line evidence, severity, user impact, and a practical fix, and disclose anything they set aside as out of scope.

Confirm important findings against the implementation and apply justified fixes before delivery. Use an independent verifier when a finding is uncertain or changes the design. Fix small clear findings directly. Rerun affected checks after changes; request another review only if a finding requires a substantial redesign.

When the user permits agents, assign disjoint file ownership for concurrent implementation. Run one shared test suite at a time and provide its results to all reviewers. Do not launch competing transcriptions or translation jobs. Keep the parent responsible for integration, validation, output verification, and user communication.

Use providers/models explicitly requested or available under the current task's settings. If a required provider is unavailable, report that fact and obtain a permitted alternative rather than switching silently. Keep personal provider preferences out of the application dependencies.

Use local checks, CI, and the permitted agent review workflow. Do not send messages to other people on the user’s behalf without explicit instructions. Opening an authorized draft PR and responding to its normal CI are part of delivery.
