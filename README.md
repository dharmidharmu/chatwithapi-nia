# chatwithapi
Chat with API Program

# MSAL is the library used to sign in users and request tokens used to access an API protected by the Microsoft identity Platform. You can add MSAL Python to your application using Pip.
pip install msal 
pip install starlette[sessions]
pip install starlette[full]
pip install python-dotenv
# pip install redis
pip install azure-ai-openai

Error code: 429 - {'error': {'code': '429', 'message': 'Requests to the ChatCompletions_Create Operation under Azure OpenAI API version 2024-02-15-preview have exceeded token rate limit of your current OpenAI S0 pricing tier. Please retry after 86400 seconds. Please go here: https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.'}}

https://kesav-openai.openai.azure.com/openai/deployments/plain_gpt3_5_turbo/chat/completions?api-version=2024-05-01-preview "HTTP/1.1 400 model_error"
2024-10-06 16:05:42,373 - ERROR - azure_openai_utils:140 - Error occurred while fetching model response: Error code: 400 - {'error': {'message': "This model's maximum context length is 8192 tokens. However, your messages resulted in 8231 tokens. Please reduce the length of the messages.", 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}
Traceback (most recent call last):
  File "C:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\azure_openai_utils.py", line 125, in get_completion_from_messages
    response = client.chat.completions.create(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\.venv\Lib\site-packages\openai\_utils\_utils.py", line 274, in wrapper
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "c:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\.venv\Lib\site-packages\openai\resources\chat\completions.py", line 668, in create
    return self._post(
           ^^^^^^^^^^^
  File "c:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\.venv\Lib\site-packages\openai\_base_client.py", line 1260, in post
    return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\.venv\Lib\site-packages\openai\_base_client.py", line 937, in request
    return self._request(
           ^^^^^^^^^^^^^^
  File "c:\Calvin\Learning\Generative AI\Open AI\Workspace\chatwithapi\.venv\Lib\site-packages\openai\_base_client.py", line 1041, in _request
    raise self._make_status_error_from_response(err.response) from None
openai.BadRequestError: Error code: 400 - {'error': {'message': "This model's maximum context length is 8192 tokens. However, your messages resulted in 8231 tokens. Please reduce the length of the messages.", 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}
