import requests
import base64
import logging
import os
from fastapi import UploadFile

logger = logging.getLogger(__name__)

def analyze_image(query: str, system_message: str, uploadedImage: UploadFile):
  # Configuration
  gpt4o_model_name = "gpt-4o"
  gpt4o_endpoint = "end-point"
  api_key = "openapi-key"

  # Read the uploaded image
  imageBytes = uploadedImage.file.read()

  encoded_image = base64.b64encode(imageBytes).decode('ascii')
  headers = {
    "Content-Type": "application/json",
    "api-key": api_key,
  }

  # Payload for the request
  payload = {
    "messages": [
      {
        "role": "system",
        "content": [
          {
            "type": "text",
            "text": system_message
          }
        ]
      },
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "\n"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": f"data:image/jpeg;base64,{encoded_image}"
            }
          },
          {
            "type": "text",
            "text": "\n"
          }
        ]
      },
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": query
          }
        ]
      }
    ],
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 200
    #"encoded_image": encoded_image  # Include the encoded image in the payload
  }

  # Send request
  try:
    response = requests.post(gpt4o_endpoint, headers=headers, json=payload, data=encoded_image)
  except requests.RequestException as e:
    logger.error(f"Failed to make the request. Error: {e}", exc_info=True)

  logger.info("Image Analysis results")
  logger.info(response.json())
  #logger.info(response.choices[0].message.content)

  # Handle the response as needed (e.g., print or process)
  return response.choices[0].message.content
