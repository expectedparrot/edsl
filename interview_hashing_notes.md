# Interview Hashing and Result Ordering in EDSL

## Interview Hashing System

1. **Interview Hash Creation**
   - In `Interview` class (line 171), an `initial_hash` is created during initialization with `self.initial_hash = hash(self)`
   - The hash function (line 343-353) uses `dict_hash(self.to_dict(include_exceptions=False, add_edsl_version=False))` to create a unique identifier based on the interview configuration

2. **Hash Preservation in Results**
   - When creating a `Result` from an interview in `Result.from_interview()` (line 577-688), the interview hash is stored:
   ```python
   result.interview_hash = interview.initial_hash
   ```

3. **Result Ordering Mechanism**
   - In `Results.insert()` (line 420-437), there's logic that respects an `order` property when inserting results
   - The `order` attribute is set in `AsyncInterviewRunner._process_single_interview()` (line 165) during execution
   
4. **Interview Order Tracking**
   - In `AsyncInterviewRunner.run()`, interviews are processed in chunks but maintain their original ordering index
   - Each result is assigned its original position using `result.order = idx` (line 165)

5. **Results Collection in Ordered Manner**
   - In `JobsRunnerAsyncio.run()`, results are collected via `results.append(result)` (line 218)
   - The `append` method in `Results` class calls `insert` which maintains order
   - The `Results.insert()` method uses `bisect_left` to maintain ordering based on the `order` attribute

## How It All Works Together

1. When interviews are created, each gets a unique hash based on its configuration (agent, survey, scenario, model)
2. During execution, AsyncInterviewRunner tracks the original position index of each interview
3. As results come in (potentially out of order due to async execution), they maintain both:
   - Their interview hash (for identification)
   - Their original position (for ordering)
4. The Results class uses a custom insert method that maintains order when collecting results
5. When results are deserialized or reloaded, the ordering information is preserved

This system ensures that even though interviews are executed concurrently, the results are still presented in a consistent, deterministic order matching how the interviews were originally generated.