# One assigned stimulus per respondent

Suppose students in beginner and advanced classes each rate one of two lesson descriptions. For exact balance, shuffle the students within each class with a seeded random generator and split each class equally between lessons. Save a table with one row per student, including student ID, class and assigned lesson. Reuse those assignments when rebuilding the study.

Two ways to show the assigned lesson in an EDSL question:

- Join the assigned lesson text onto each student row, create a ScenarioList from the joined rows, and interpolate `{{ lesson_text }}`.
- Store the lesson texts and assignment on each scenario. Use `{% if lesson == 'A' %}{{ text_a }}{% else %}{{ text_b }}{% endif %}` in the question. Validate the saved lesson values before rendering.

If the student should answer from their level of experience, give the model that detail in its persona or question, e.g. `You are in the {{ level }} class.` A level used only for balancing can stay in the assignment table. Building one scenario per assigned student keeps the number of interviews equal to the number of students when using one agent and one model.

Alternatively, keep student traits in an AgentList and assigned lessons in a ScenarioList. Put the two lists in the same student ID order. With 24 students and one model, the following command saves a job only if it plans 24 interviews. Without pairing, 24 agents crossed with 24 scenarios would produce 576.

```bash
ep jobs build --survey lessons-survey.ep --agents students.ep --scenarios assigned-lessons.ep --pair-agents-scenarios --expect-interviews 24 --output lessons.ep
```

After saving the job, render the question for a row from each class and lesson. For example, if interview 3 is an advanced student assigned the geometry lesson, check that the student sees their level and the assigned description, and that the other description is absent.

```bash
ep jobs preview-prompt lessons.ep clarity --interview-index 3 --expect-text "advanced class" --expect-text "Explore triangles" --forbid-text "Practice fractions"
```

The JSON includes the system and user prompts, and the indices of the selected agent, scenario and model. A text mismatch exits with code 5 and includes the missing or unexpected text. Use distinctive phrases from the study materials for those checks.
