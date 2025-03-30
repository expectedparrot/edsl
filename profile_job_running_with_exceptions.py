from edsl import Model, QuestionFreeText, ScenarioList, Cache 
from memory_profiler import profile

@profile
def run_model_with_exceptions(n, throw_exception = True):
    print(f"Running model with {n} scenarios")
    
    # Use the context manager pattern for proper resource cleanup
    with Cache() as cache:
        m = Model("test", canned_response="Hello", throw_exception=throw_exception, exception_probability=0.5)
        
        q = QuestionFreeText(question_text="Do you like {{ number}}", question_name="cool_question")
        
        s = ScenarioList.from_list("number", list(range(n)))
        
        results = q.by(s).by(m).run(disable_remote_inference=True, cache=cache)
        
        # Explicitly clean up to release resources
        del results
    
    # Force garbage collection to release any lingering references
    import gc
    gc.collect()
    
    return None

if __name__ == "__main__":
    run_model_with_exceptions(10, throw_exception = False)
    run_model_with_exceptions(20, throw_exception = False)
    run_model_with_exceptions(100, throw_exception = False)
 