from edsl import Results 

def test_multiline_filter():
    r = Results.example()
    # Test the original failing case with multi-line strings and template syntax
    filtered_results = r.filter(""" 
    {{ answer.how_feeling}} == 'OK' 
             or {{ answer.how_feeling}} == 'Good'
    """)
    
    # Verify that only results with "OK" or "Good" feelings are returned
    for result in filtered_results:
        assert result["answer"]["how_feeling"] == "OK" or result["answer"]["how_feeling"] == "Good"
    
    # Test with multi-line strings but without template syntax
    filtered_results2 = r.filter("""
    how_feeling == 'OK'
    or how_feeling == 'Good'
    """)
    
    # Verify that both filters produce the same result
    assert len(filtered_results) == len(filtered_results2)
    assert set(hash(result) for result in filtered_results) == set(hash(result) for result in filtered_results2)
    
    print("All tests passed!")
    return filtered_results

# Run the tests and print the result
result = test_multiline_filter()
print(result)