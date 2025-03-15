from edsl import QuestionCheckBox
import time
from concurrent.futures import ThreadPoolExecutor
from edsl import Survey
from edsl import Cache
import matplotlib.pyplot as plt


running_time = {}
def test_1(disable_remote_inference=False,th_id=0):

    start = time.time()
    try:
        q = QuestionCheckBox.example()
        cache = Cache()

        res = Survey(questions=[q]).run(disable_remote_inference=disable_remote_inference,disable_remote_cache=True,cache=cache)

    except Exception as e:
        print(e)    
    end = time.time()
    print("Time taken to run the survey: ", end-start)
    running_time[th_id] = end-start

def run_tests_in_parallel(disable_remote_inference=False,nr_jobs=2):
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_1,disable_remote_inference=disable_remote_inference,th_id=i) for i in range(nr_jobs)]
        for future in futures:
            future.result()
def plot_times(disable_remote_inference=False):
    fig = plt.figure()

    values = [running_time[k] for k in range(len(running_time))]
    max_value = max(values)
    plt.plot(values)
    plt.ylim(0, max(max_value, 12))
    plt.xlabel('Job Number')
    plt.ylabel('Execution Time (s)')
    plt.title('Execution Time per Job')
    plt.xticks(range(len(running_time)))  # Set x-axis to display only integer positions
    if disable_remote_inference:
        plt.savefig(f'plot_{len(running_time)}_no_remote.png')
    else:
        plt.savefig(f'plot_{len(running_time)}.png')
    plt.show()

####################
# Main
disable_remote_inference=True
nr_jobs=20
run_tests_in_parallel(disable_remote_inference=disable_remote_inference, nr_jobs=nr_jobs)

plot_times(disable_remote_inference=disable_remote_inference)
