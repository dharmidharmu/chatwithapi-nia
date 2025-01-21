import os
import json
from openai import AzureOpenAI
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Initialize the Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint = os.getenv("AZURE_ENDPOINT_URL"), 
    api_key=os.getenv("OPEN_API_KEY"),  
    api_version=os.getenv("API_VERSION")

    # azure_endpoint = os.getenv("GPT4O_ENDPOINT_URL"), 
    # api_key=os.getenv("GPT4O_API_KEY"),  
    # api_version=os.getenv("GPT4O_API_VERSION")
)

# Define the deployment you want to use for your chat completions API calls

deployment_name = os.getenv("DEFAULT_MODEL_NAME")
#deployment_name = os.getenv("GPT4O_MODEL_NAME")

# Simplified timezone data
TIMEZONE_DATA = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris"
}

def get_current_time(location):
    """Get the current time for a given location"""
    print(f"get_current_time called with location: {location}")  
    location_lower = location.lower()
    
    for key, timezone in TIMEZONE_DATA.items():
        if key in location_lower:
            print(f"Timezone found for {key}")  
            current_time = datetime.now(ZoneInfo(timezone)).strftime("%I:%M %p")
            return json.dumps({
                "location": location,
                "current_time": current_time
            })
    
    print(f"No timezone data found for {location_lower}")  
    return json.dumps({"location": location, "current_time": "unknown"})

def run_conversation():
    messages = []
    
    system_message = """You're an AI assistant designed to help users search for current time across different locations. 
     When a user asks for finding current time in a location, you should call the get_current_time function. 
     Always return valid, formatted json compatible with json.loads function for the identified function arguments. Do not add anything extra to the json.
     Don't make assumptions about what values to use with functions. Ask for clarification if a user request is ambiguous.
     Only use the functions you have been provided with."""

    # Initial user message
    messages.append({"role": "system", "content": system_message}) # Single function call
    messages.append({"role": "user", "content": "What's the current time in San Francisco"}) # Single function call
    #messages = [{"role": "user", "content": "What's the current time in San Francisco, Tokyo, and Paris?"}] # Parallel function call with a single tool/function defined

    # Define the function for the model
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "The function takes a given location and provides the current time for that location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The name of the city, e.g. San Francisco, Tokyo, Paris",
                        },
                    },
                    "required": ["location"],
                },
            }
        }
    ]

    # First API call: Ask the model to use the function
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=tools,
        #tool_choice="none",
        #tool_choice="auto"
        tool_choice={"type": "function", "function" : {"name"  : "get_current_time"}}
    )

    # Process the model's response
    response_message = response.choices[0].message
    messages.append(response_message)

    print("Model's response:")  
    print(response_message)  

    # Handle function calls
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "get_current_time":
                function_args = json.loads(tool_call.function.arguments)
                print(f"Function arguments: {function_args}")  
                time_response = get_current_time(
                    location=function_args.get("location")
                )
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "get_current_time",
                    "content": time_response,
                })
    else:
        print("No tool calls were made by the model.")  

    # Second API call: Get the final response from the model
    final_response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
    )

    return final_response.choices[0].message.content

# Run the conversation and print the result
print(run_conversation())