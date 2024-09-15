from edsl import Question
import pytest


def test_all_question():
    questions = Question.available()
    for question in questions:
        print(question)
        if question != "functional":
            q = Question.example(question)
            r = q.example_results()
            _ = hash(r)
            _ = r._repr_html_()
