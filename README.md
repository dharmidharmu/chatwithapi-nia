# ChatWithAPI-Nia

ChatWithAPI-Nia is an application that integrates multiple cloud services and APIs to offer advanced chat and document analysis capabilities. It leverages Azure Cognitive Services, OpenAI, Azure Search, and MongoDB to power its functionalities. This repository contains the source code and configuration needed to run the application in a development environment.

## Overview

- **Chat Interface & API Integration:** Uses OpenAI and other chat APIs to deliver conversation-based interactions.
- **Document Intelligence:** Integrates with Azure Cognitive Services to analyze and extract insights from documents.
- **Search Capabilities:** Leverages Azure Search to index and query data for quick information retrieval.
- **Storage & Database:** Uses MongoDB to maintain application data and Azure Blob Storage for handling images and other media assets.

## Features

- **Azure Integration:** Properly configured to work with multiple Azure services such as OpenAI, Cognitive Services, and Blob Storage.
- **Environment Configuration:** Uses a comprehensive `.env` file to manage API keys, secrets, and connection strings. See [`.env`](./.env) for details.
- **Session Management:** Supports filesystem-based session storage with configurable secret keys.
- **Logging & Monitoring:** Provides integration with various logging services for server and application logs.
- **Customizable Deployment:** Environment variables and configuration settings allow for easy adaptation across different environments (development, staging, production).

## Prerequisites

- **Node.js & npm:** Ensure that Node.js (v14 or later) and npm are installed.
- **MongoDB:** A running MongoDB instance. For development, you can use a local instance.
- **Azure Subscription:** Access to Azure resources such as Cognitive Services and Blob Storage.
- **Azure CLI:** For managing Azure resources if you plan to deploy to Azure.

## Setup

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/<your-username>/chatwithapi-nia.git
   cd chatwithapi-nia
