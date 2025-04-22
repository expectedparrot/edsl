from edsl.results import Results

def test_sort_by():
    # Create example results
    r = Results.example()
    
    # Get original values
    original_dataset = r.select('how_feeling')
    original_values = original_dataset.to_dict()['data'][0]['answer.how_feeling']
    print("Original values:", original_values)
    
    # Sort by how_feeling in ascending order
    sorted_results = r.sort_by('how_feeling', reverse=False)
    dataset = sorted_results.select('how_feeling')
    values = dataset.to_dict()['data'][0]['answer.how_feeling']
    print("Sorted values:", values)
    
    # Verify that 'Great' comes before 'Terrible' in alphabetical sorting
    great_index = values.index('Great') if 'Great' in values else -1
    terrible_index = values.index('Terrible') if 'Terrible' in values else -1
    
    assert great_index != -1, "'Great' should be in the sorted results"
    assert terrible_index != -1, "'Terrible' should be in the sorted results"
    assert great_index < terrible_index, "'Great' should come before 'Terrible' in alphabetical sorting"
    
    # Try reverse sorting
    reverse_sorted = r.sort_by('how_feeling', reverse=True)
    reverse_dataset = reverse_sorted.select('how_feeling')
    reverse_values = reverse_dataset.to_dict()['data'][0]['answer.how_feeling']
    print("\nReverse sorted values:", reverse_values)
    
    # Verify that 'Terrible' comes before 'Great' in reverse alphabetical sorting
    reverse_great_index = reverse_values.index('Great') if 'Great' in reverse_values else -1
    reverse_terrible_index = reverse_values.index('Terrible') if 'Terrible' in reverse_values else -1
    
    assert reverse_great_index != -1, "'Great' should be in the reverse sorted results"
    assert reverse_terrible_index != -1, "'Terrible' should be in the reverse sorted results"
    assert reverse_terrible_index < reverse_great_index, "'Terrible' should come before 'Great' in reverse sorting"
    
    print("Test passed!")

if __name__ == "__main__":
    test_sort_by()