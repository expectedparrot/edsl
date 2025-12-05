import edsl
from edsl.reports.charts import BarChartOutput
import webbrowser
import tempfile
import os


def main():
    # Load example results
    results = edsl.Results.load("example_results.json.gz")

    # Find a multiple choice question to visualize
    mc_questions = [
        q
        for q in results.survey.questions
        if q.question_type in ["multiple_choice", "checkbox"]
    ]

    if not mc_questions:
        print("No multiple choice questions found in dataset")
        return

    question = mc_questions[0]
    print(
        f"Creating bar chart for: {question.question_name} - {question.question_text}"
    )

    # Create a bar chart
    chart = BarChartOutput(results, question.question_name)

    # Save and open the chart
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, "test_chart.html")

    # Get the Altair chart and save as HTML
    altair_chart = chart.output()
    altair_chart.save(temp_path)

    print(f"Chart saved to: {temp_path}")
    print("Opening chart in browser...")

    # Open in browser
    webbrowser.open("file://" + os.path.abspath(temp_path))

    print("Done!")


if __name__ == "__main__":
    main()
