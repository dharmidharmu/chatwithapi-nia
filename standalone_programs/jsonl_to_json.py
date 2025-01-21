import json

def jsonl_to_json(file_path):
    json_objects = []
    with open(file_path, 'r') as file:
        for line in file:
            json_objects.append(json.loads(line))
    return json_objects

# Example usage
file_path = 'C:\\Users\\rac7cob\\Downloads\\Order_info_data_3.jsonl'
result = jsonl_to_json(file_path)
output_file_path = 'C:\\Projects\\Review Bytes\\NextGenCX\\chatwithapi\\JSON_FILE.json'
with open(output_file_path, 'w') as output_file:
    json.dump(result, output_file)