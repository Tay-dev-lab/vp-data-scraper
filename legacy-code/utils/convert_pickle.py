import pickle
import pandas as pd
import pprint

# Load and inspect the pickle file
with open('/Users/andrewtaylor/Documents/GitHub/scrapers/idox_pypostal_mock_data.pkl', 'rb') as f:
    data = pickle.load(f)

# Print the type and structure
print(f"Data type: {type(data)}")
print("Data structure:")
pprint.pprint(data, depth=2)  # Limiting depth to avoid overwhelming output

# If it's a dictionary with uneven lengths, we need to handle differently
if isinstance(data, dict):
    # Option 1: Create DataFrame with compatible data (may drop some data)
    # Check lengths of each value
    lengths = {k: len(v) if hasattr(v, '__len__') else 1 for k, v in data.items()}
    print("Lengths of each item:", lengths)
    
    # Option 2: Normalize the data (better option for irregular data)
    # This will depend on your specific data structure
    # For example, if your values are lists of varying lengths:
    normalized_data = {}
    for key, value in data.items():
        if hasattr(value, '__len__') and not isinstance(value, (str, bytes, bytearray)):
            for i, item in enumerate(value):
                # Create a new row for each item in the list
                row_key = f"{key}_{i}"
                normalized_data[row_key] = item
        else:
            normalized_data[key] = value
    
    # Save the raw data as CSV if possible
    with open('raw_data.csv', 'w') as f:
        for key, value in data.items():
            f.write(f"{key},{value}\n")