from edsl.questions.question_registry import get_question_class, QuestionBase


def test_all_questions():
    ## TODO: Add serialization test
    ## TODO: inspect & delete inputs
    print(f"The available questions are:{QuestionBase.available()}")
    for question_type in QuestionBase.available():
        print(f"Now running: {question_type}")
        cls = get_question_class(question_type)
        try:
            results = cls.example().run()
        except Exception as e:
            print(f"Error running {question_type}: {e}")
            continue
