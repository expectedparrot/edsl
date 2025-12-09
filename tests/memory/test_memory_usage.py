import pytest
from memory_profiler import memory_usage
from edsl import FileStore, Scenario, Survey, Model
from edsl import QuestionFreeText, QuestionList
import os 
@pytest.fixture
def sample_image():
    """Fixture to provide a sample image for testing."""
    current_dir = os.path.dirname(__file__)
    img_path = os.path.join(current_dir, "test_img.png")
    return FileStore(img_path)


@pytest.fixture
def scenario_with_images(sample_image):
    """Create a scenario with multiple copies of the same image."""
    return Scenario({f"image_{i}": sample_image for i in range(1, 10)})


def create_image_survey(num_questions=10):
    """Create a survey with questions about images."""
    questions = []
    for i in range(1, num_questions + 1):
        q0 = QuestionFreeText(
            question_name=f"topic_{i}",
            question_text="Describe what is happening in this print: {{ scenario.image_" + f"{i}" + " }}"
        )

        q1 = QuestionFreeText(
            question_name=f"colors_{i}",
            question_text="List the prominent colors in this print: {{ scenario.image_" + f"{i}" + " }}",
        )

        q2 = QuestionFreeText(
            question_name=f"year_{i}",
            question_text="Estimate the year that this print was created: {{ scenario.image_" + f"{i}" + " }}",
        )
        questions.extend([q0, q1, q2])
    return Survey(questions=questions)


def test_memory_usage_basic(scenario_with_images):
    """Test basic memory usage of survey processing."""
    survey = create_image_survey(5)  # Use fewer questions for basic test
    model = Model("test", rpm=10000, tpm=10000000)
    
    # Measure memory usage during execution
    mem_usage = memory_usage(
        (lambda: survey.by(scenario_with_images).by(model).run(disable_remote_inference=True,cache=False)), 
        interval=0.1, 
        timeout=30
    )
    
    # Basic assertions about memory usage
    assert len(mem_usage) > 0
    print(f"Peak memory usage: {max(mem_usage)} MB")
    
    # Optional: Set a reasonable memory limit based on expected usage
    # This value should be adjusted based on baseline measurements
    assert max(mem_usage) < 1000  # Example: 1000 MB limit


def test_memory_scaling(scenario_with_images):
    """Test how memory usage scales with increasing number of questions."""
    model = Model("test", rpm=10000, tpm=10000000)
    results = {}
    
    for num_questions in [2, 4]:  # Use small values for testing
        survey = create_image_survey(num_questions)
        
        # Measure memory usage
        mem_usage = memory_usage(
            (lambda: survey.by(scenario_with_images).by(model).run(disable_remote_inference=True,cache=False)),
            interval=0.1,
            timeout=30
        )
        
        results[num_questions] = max(mem_usage)
    
    # Check that memory usage scales somewhat linearly
    # (This is a simplistic check and may need adjustment)
    print(f"Memory usage scaling: {results}")
    assert results[4] < results[2] * 3  # Should not scale worse than O(n)


def test_memory_with_faulty_question_type(scenario_with_images):
    """Test memory usage when one question is of a wrong type (QuestionList instead of QuestionFreeText)."""
    questions = []
    for i in range(1, 10):  # Smaller set to trigger issue without overload
        # Injecting a faulty question to simulate a misconfiguration
        q0 = QuestionList(
            question_name=f"topic_{i}",
            question_text="Choose what's happening in this print: {{ scenario.image_" + f"{i}" + " }}",
        )

        q1 = QuestionFreeText(
            question_name=f"colors_{i}",
            question_text="List the prominent colors in this print: {{ scenario.image_" + f"{i}" + " }}",
        )

        q2 = QuestionFreeText(
            question_name=f"year_{i}",
            question_text="Estimate the year that this print was created: {{ scenario.image_" + f"{i}" + " }}",
        )
        questions.extend([q0, q1, q2])
    
    faulty_survey = Survey(questions=questions)
    model = Model("test", rpm=10000, tpm=10000000)

    try:
        mem_usage = memory_usage(
            (lambda: faulty_survey.by(scenario_with_images).by(model).run(disable_remote_inference=True,cache=False)),
            interval=0.1,
            timeout=30
        )
        print(f"Memory usage with faulty question: {max(mem_usage)} MB")
    except Exception as e:
        print(f"Expected error triggered: {e}")


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
