"""Test script to check serialization of order attribute."""

def test_order_serialization():
    """Test if Result order attributes are preserved during serialization."""
    from edsl.results import Results
    
    # Get example results
    r = Results.example()
    
    # Add order attribute to results
    for i, result in enumerate(r):
        result.order = i
    
    # Serialize and deserialize
    dict_form = r.to_dict()
    unshelved = Results.from_dict(dict_form)
    
    # Check if order is preserved
    print("Order attribute values after serialization/deserialization:")
    all_preserved = True
    for i, result in enumerate(unshelved):
        order_val = getattr(result, 'order', 'No order attribute')
        print(f"Result {i}: {order_val}")
        if order_val != i:
            all_preserved = False
    
    print(f"All order attributes preserved correctly: {all_preserved}")

if __name__ == "__main__":
    test_order_serialization()