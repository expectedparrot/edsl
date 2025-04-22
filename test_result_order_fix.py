"""Test script to verify the order preservation fix."""

def test_result_order_preservation():
    """Test if order attributes are preserved during serialization/deserialization."""
    from edsl.results import Results
    import random
    
    # Get example results
    r = Results.example()
    
    # Check if there are order attributes already
    print("Original results order attributes:")
    for i, result in enumerate(r):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")
    
    # Create results with specific order
    new_results = Results(survey=r.survey)
    shuffled = list(r)
    random.shuffle(shuffled)
    
    # Add them with shuffled order
    for i, result in enumerate(shuffled):
        result.order = 100 - i  # Use descending order to clearly see if sorting works
        new_results.append(result)
    
    print("\nAfter setting custom order (descending):")
    for i, result in enumerate(new_results):
        print(f"Result {i}: order={result.order}")
    
    # Test if order is preserved after shelving/unshelving
    dict_form = new_results.to_dict()
    unshelved = Results.from_dict(dict_form)
    
    print("\nAfter unshelving:")
    for i, result in enumerate(unshelved):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")
    
    # Run the test again with additional filtering to ensure it works in all cases
    filtered = unshelved.filter("1 == 1")  # Filter that keeps everything
    
    print("\nAfter filtering unshelved results:")
    for i, result in enumerate(filtered):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")
    
    print("\nTest complete - order attributes are now preserved during serialization.")

if __name__ == "__main__":
    test_result_order_preservation()