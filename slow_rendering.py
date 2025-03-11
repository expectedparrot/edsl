from edsl import QuestionFreeText, Survey, Model
import time
import pandas as pd
import matplotlib.pyplot as plt

questions = []
m = Model("gpt-4o")
timing_data = []  # List to store timing data

def render_survey(num_questions):
    questions = []
    for i in range(num_questions):
        q = QuestionFreeText(
            question_name=f"test{i}",
            question_text=f"You are a man of . What do you think about the current state of the world? {i}"
        )
        questions.append(q)    
    s = Survey(questions)
    job = s.by(m)
    start = time.time()
    prompts = job.prompts()
    elapsed_time = time.time() - start
    return elapsed_time

#render_survey(100)

#print(render_survey(150))

for i in range(500):
    elapsed_time = render_survey(i+1)
    timing_data.append({'iteration': i, 'num_questions': i+1, 'time': elapsed_time})
    print(f"Prompts took {elapsed_time} seconds for iteration {i}")

# Create DataFrame from timing data
df = pd.DataFrame(timing_data)

# Plot the results
plt.figure(figsize=(10, 6))
plt.plot(df['num_questions'], df['time'])
plt.xlabel('Number of Questions')
plt.ylabel('Time (seconds)')
plt.title('Time to Generate Prompts vs Number of Questions')
plt.grid(True)
plt.savefig('prompt_generation_timing.png')  # Save the plot to a file
plt.show()  # Display the plot

# Print summary statistics
print("\nSummary Statistics:")
print(df.describe())