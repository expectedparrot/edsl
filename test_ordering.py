"""Test script to examine Results ordering issue."""

def test_result_ordering():
    """Test if order attributes are preserved during filtering."""
    from edsl.results import Results
    import random
    
    # Get example results
    r = Results.example()
    
    # Check if there are order attributes already
    print("Original results order attributes:")
    for i, result in enumerate(r):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")
    
    # Add random ordering - check if sorting with insert works
    print("\nCreating new Results with random order:")
    new_results = Results(survey=r.survey)
    
    # Create results in reverse order
    shuffled = list(r)
    random.shuffle(shuffled)
    
    # Add them with shuffled order
    for i, result in enumerate(shuffled):
        result.order = i
        new_results.append(result)
    
    print("After appending with order attribute:")
    for i, result in enumerate(new_results):
        print(f"Result {i}: order={result.order}")
    
    # Test if shelving/unshelving preserves order
    # Mimic the shelving process by converting to dict and back
    print("\nSimulating shelving/unshelving:")
    dict_form = new_results.to_dict()
    unshelved = Results.from_dict(dict_form)
    
    print("After unshelving:")
    for i, result in enumerate(unshelved):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")

if __name__ == "__main__":
    test_result_ordering()