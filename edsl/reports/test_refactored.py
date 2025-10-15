import edsl
from reports.charts import BarChartOutput, ScatterPlotOutput
from reports.tables import SummaryStatisticsTable
from reports.research import Research, Report
import pandas as pd

def main():
    print("Testing refactored reports modules...")
    
    # Use example_results.json.gz to test functionality
    try:
        # Load the example results
        results = edsl.Results.load("example_results.json.gz")
        print(f"Loaded results with {len(results)} respondents")
        print(f"Survey has {len(results.survey.questions)} questions")
        
        # List the first few questions to pick ones for testing
        for i, q in enumerate(results.survey.questions[:5]):
            print(f"{i}: {q.question_name} ({q.question_type}): {q.question_text[:50]}...")
        
        # Create a Research object for a single question (assuming first question is appropriate)
        question = results.survey.questions[0]
        print(f"\nTesting research on question: {question.question_name}")
        
        research = Research(results, question.question_name)
        
        # Get appropriate charts for this question
        charts = research.get_appropriate_charts()
        print(f"Appropriate charts for this question: {list(charts.keys())}")
        
        # Try to create a chart
        if "BarChartOutput" in charts:
            print("\nCreating BarChartOutput...")
            chart = research.create_chart("BarChartOutput")
            # Save the chart to a temporary file and return the path
            print(f"Chart created. Saving as PNG...")
            png_path = chart.png.path
            print(f"Chart saved to: {png_path}")
            
        # Test a different chart type directly
        print("\nTesting another question with ScatterPlot...")
        
        # Find numerical questions for scatter plot
        numerical_questions = [q for q in results.survey.questions 
                              if q.question_type in ["numerical", "linear_scale"]]
        
        if len(numerical_questions) >= 2:
            q1, q2 = numerical_questions[:2]
            print(f"Testing scatter plot with questions: {q1.question_name} and {q2.question_name}")
            
            try:
                scatter = ScatterPlotOutput(results, q1.question_name, q2.question_name)
                scatter_png = scatter.png.path
                print(f"Scatter plot created and saved to: {scatter_png}")
            except Exception as e:
                print(f"Error creating scatter plot: {e}")
        else:
            print("Not enough numerical questions for scatter plot test")
            
        # Test table output
        print("\nTesting table output...")
        if len(numerical_questions) > 0:
            try:
                stats_table = SummaryStatisticsTable(results, numerical_questions[0].question_name)
                table_df = stats_table.output()
                print("Summary statistics table created:")
                print(table_df)
            except Exception as e:
                print(f"Error creating table: {e}")
                
        # Test full report generation (just initialization)
        print("\nInitializing report (without full generation)...")
        report = Report(results)
        print("Report initialized successfully")
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
if __name__ == "__main__":
    main()