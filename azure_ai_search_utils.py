from datetime import time
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from azure.core.exceptions import HttpResponseError
from azure.storage.blob.aio import BlobServiceClient, BlobClient, ContainerClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient, SearchIndexerClient
from app_config import blob_service_client
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchFieldDataType,
    SearchField,
    SearchIndexer,
    SearchIndexerDataSourceConnection,
    SemanticConfiguration,
    SemanticField,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,  
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters, 
    SemanticSearch,
    SemanticPrioritizedFields,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset,
    LexicalAnalyzerName
)
from app_config import RAG_DOCUMENTS_FOLDER

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Azure Configuration
BLOB_CONNECTION_STRING = os.getenv("BLOB_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_STORAGE_RAG_CONTAINER_NAME")
SEARCH_SERVICE_ENDPOINT = os.getenv("SEARCH_ENDPOINT_URL")
SEARCH_API_KEY = os.getenv("SEARCH_KEY")
SEARCH_INDEX_NAME = "rag-vector" #os.getenv("SEARCH_INDEX_NAME")

api_version="2024-03-01-preview"
headers={
    "Content-Type": "application/json", 
    "api-key": SEARCH_API_KEY
    }

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_ENDPOINT_URL"]
AZURE_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = "text-embedding-3-large" #os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")
AZURE_OPENAI_MODEL_NAME = "text-embedding-3-large" #os.getenv("EMBEDDING_MODEL_NAME", "gpt-4o")
AZURE_OPENAI_MODEL_DIMENSIONS = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", 1536))

env_instance = os.getenv("ENV_INSTANCE", "dev-001")
index_name = f"{SEARCH_INDEX_NAME}-{env_instance}"

# Initialize Clients
# blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
# blob_service_client = blob_service_client
search_index_client = SearchIndexClient(endpoint=SEARCH_SERVICE_ENDPOINT, credential=AzureKeyCredential(SEARCH_API_KEY))
indexer_client = SearchIndexerClient(endpoint=SEARCH_SERVICE_ENDPOINT, credential=AzureKeyCredential(SEARCH_API_KEY))
search_client = SearchClient(endpoint=SEARCH_SERVICE_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(SEARCH_API_KEY))

# region : Upload PDF File 

# async def upload_file_to_blob(file_path):
#     """Ensures the container exists and uploads a file to Azure Blob Storage."""
#     try:
#         container_client: ContainerClient = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
#         if not container_client.exists():
#             logger.info(f"Container '{BLOB_CONTAINER_NAME}' does not exist. Creating it now...")
#             container_client.create_container()
#             logger.info(f"Container '{BLOB_CONTAINER_NAME}' created.")

#         blob_client: BlobClient = container_client.get_blob_client(blob=os.path.basename(file_path))
        
#         with open(file_path, "rb") as data:
#             blob_client.upload_blob(data, overwrite=True)

#         logger.info(f"Uploaded '{file_path}' to Blob Storage.")
#         return blob_client.url
#     except Exception as e:
#         logger.info(f"Error uploading file to blob: {e}", exc_info=True)
#         return None
    
async def upload_file_to_blob(folder_path):
    """Ensures the container exists and uploads all files in a folder to Azure Blob Storage."""
    try:
        container_client: ContainerClient = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

        # Ensure the container exists
        if not container_client.exists():
            logger.info(f"Container '{BLOB_CONTAINER_NAME}' does not exist. Creating it now...")
            container_client.create_container()
            logger.info(f"Container '{BLOB_CONTAINER_NAME}' created.")

        # Loop through all files in the folder
        logger.info(f"Uploading files from '{folder_path}' to Blob Storage...")
        # logger.info(f"{os.listdir(folder_path)}")
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            logger.info(f"Processing file: {file_path}")

            # Check if it's a file (not a subfolder)
            if os.path.isfile(file_path):
                try:
                    blob_client: BlobClient = container_client.get_blob_client(blob=filename)

                    with open(file_path, "rb") as data:
                        blob_client.upload_blob(data, overwrite=True)

                    logger.info(f"Uploaded '{file_path}' to Blob Storage.")
                except Exception as upload_error:
                    logger.error(f"Error uploading '{file_path}': {upload_error}")

        return True
    except Exception as e:
        logger.error(f"Error accessing folder or container: {e}")
        return None

# endregion

# region : Data Source

#  Data sources name
datasource_name = f"{SEARCH_INDEX_NAME}-blob-{env_instance}"

#  Create Data Source
async def create_data_source():     
    data_source = SearchIndexerDataSourceConnection(
        name=datasource_name,
        type="azureblob",
        connection_string=BLOB_CONNECTION_STRING,
        container={"name": BLOB_CONTAINER_NAME} #, "include": "*.pdf"
    )

    try:
        await indexer_client.create_or_update_data_source_connection(data_source)
        logger.info(f" Successfully created Data Source '{datasource_name}'.")
    except HttpResponseError as e:
        logger.info(f" Failed to create Data Source: {e}")

# endregion

# region : Search Index

# Vector Search Profile | Hnsw Algorthim | Vetorizer | Semantic Config Name
hnswProfile = f"{SEARCH_INDEX_NAME}-hnswProfile-{env_instance}"
hnswAlgConfigName = f"{SEARCH_INDEX_NAME}-hnsw-config-{env_instance}"
vectorizerName = f"{SEARCH_INDEX_NAME}-vectorizer-{env_instance}"
semanticConfig = f"{SEARCH_INDEX_NAME}-semantic-config-{env_instance}"

# Function to create the search index
async def create_search_index():
    # async define Search Fields 
    fields = [
    SearchField(name="chunk_id", type=SearchFieldDataType.String, key=True, sortable=True, analyzer_name="keyword"),  #LexicalAnalyzerName.STANDARD_LUCENE
    SearchField(name="parent_id", type=SearchFieldDataType.String, sortable=True, filterable=True),  
    SearchField(name="title", type=SearchFieldDataType.String),      
    SearchField(name="chunk", type=SearchFieldDataType.String, sortable=False),  
    SearchField(name="text_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                hidden=False,
                vector_search_dimensions=AZURE_OPENAI_MODEL_DIMENSIONS, 
                vector_search_profile_name=hnswProfile)
    ]
 
    # Configure the vector search configuration  
    vector_search = VectorSearch(  
        algorithms=[  
            HnswAlgorithmConfiguration(name=hnswAlgConfigName),
        ],  
        profiles=[  
            VectorSearchProfile(  
                name=hnswProfile,  
                algorithm_configuration_name=hnswAlgConfigName,  
                vectorizer_name=vectorizerName
            )
        ],  
        vectorizers=[  
            AzureOpenAIVectorizer(  
                vectorizer_name=vectorizerName,  
                kind="azureOpenAI",  
                parameters=AzureOpenAIVectorizerParameters(  
                    resource_url=AZURE_OPENAI_ENDPOINT,  
                    deployment_name=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                    model_name=AZURE_OPENAI_MODEL_NAME,
                    api_key=AZURE_OPENAI_KEY,
                ),
            ),  
        ]         
    )  
  
    semantic_config = SemanticConfiguration(  
        name=semanticConfig,  
        prioritized_fields=SemanticPrioritizedFields(  
            content_fields=[
                SemanticField(field_name="chunk")
            ],
            title_field=SemanticField(field_name="title"),
            keywords_fields=[
                SemanticField(field_name="title"), 
                SemanticField(field_name="chunk")
            ],
        )
    )
    
    # Create the semantic search with the configuration  
    semantic_search = SemanticSearch(configurations=[semantic_config])    

    index = SearchIndex(
        name=index_name,
        fields=fields,     
        semantic_search=semantic_search,
        vector_search=vector_search 
        )

    try:
        result = await search_index_client.create_or_update_index(index)
        logger.info(f"{result.name} created") 
        return result.name, semantic_config.name
    except HttpResponseError as e:
        logger.info(f" Failed- {index_name} to create index: {e}")
        return False

#endregion

# region : Skillset 

# Skillset name 
skillset_name = f"{SEARCH_INDEX_NAME}-skillset-{env_instance}"

# Create a skillset 
async def create_skillset(): 

    split_skill = SplitSkill(  
        description="Split skill to chunk documents",  
        text_split_mode="pages",  
        context="/document",  
        maximum_page_length=2000,  
        page_overlap_length=500,  
        inputs=[  
            InputFieldMappingEntry(name="text", source="/document/content"),  
        ],  
        outputs=[  
            OutputFieldMappingEntry(name="textItems", target_name="pages")  
        ]
    )
    
    embedding_skill = AzureOpenAIEmbeddingSkill(  
        description="Skill to generate embeddings via Azure OpenAI",  
        context="/document/pages/*",  
        resource_url=AZURE_OPENAI_ENDPOINT,  
        deployment_name=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,  
        model_name=AZURE_OPENAI_MODEL_NAME,
        dimensions=AZURE_OPENAI_MODEL_DIMENSIONS,
        api_key=AZURE_OPENAI_KEY,  
        inputs=[  
            InputFieldMappingEntry(name="text", source="/document/pages/*"),    
        ],  
        outputs=[
            OutputFieldMappingEntry(name="embedding", target_name="text_vector")
        ]
    )

    index_projections = SearchIndexerIndexProjection(  
        selectors=[  
            SearchIndexerIndexProjectionSelector(  
                target_index_name=index_name,  
                parent_key_field_name="parent_id",  
                source_context="/document/pages/*",  
                mappings=[
                    InputFieldMappingEntry(name="chunk", source="/document/pages/*"),  
                    InputFieldMappingEntry(name="text_vector", source="/document/pages/*/text_vector"),
                    InputFieldMappingEntry(name="title", source="/document/metadata_storage_name")
                ]
            )
        ],  
        parameters=SearchIndexerIndexProjectionsParameters(  
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS  
        )  
    )

    skills = [split_skill, embedding_skill]    
    
    indexer =  SearchIndexerSkillset(  
        name=skillset_name,  
        description="Skillset to chunk documents and generating embeddings",  
        skills=skills,  
        index_projection=index_projections
    )

    # Create the skillset
    skillset_enabled_indexer = await indexer_client.create_or_update_skillset(indexer)
    logger.info(f"{skillset_enabled_indexer.name} created")  

#endregion 

# region : Indexer

# Indexer Name
indexer_name = f"{SEARCH_INDEX_NAME}-indexer-{env_instance}" 

#   Create Indexer
async def create_indexer():

    indexer_parameters = None
    
    indexer = SearchIndexer(  
        name=indexer_name,  
        description="Indexer to index documents and generate embeddings",  
        skillset_name=skillset_name,  
        target_index_name=index_name,  
        data_source_name=datasource_name,
        parameters=indexer_parameters
    )  

    try:
        await indexer_client.create_or_update_indexer(indexer)
        logger.info(f" Successfully created Indexer '{indexer_name}'.")

        # Run the indexer  
        await indexer_client.run_indexer(indexer_name)  
        logger.info(f' {indexer_name} is created and running. If queries return no results, please wait a bit and try again.')  

        # # Check the indexer status
        # while True:
        #     status = indexer_client.get_indexer_status(indexer_name)
        #     logger.info(f"Indexer Status: {status.status}")
        #     if status.status in ["success", "completed"]:
        #         logger.info("Indexer completed successfully.")
        #         break
        #     elif status.status == "error":
        #         logger.info(f"Indexer failed: {status.last_result.errors}")
        #         break

        #     # call every 5 seconds
        #     time.sleep(5)
    except HttpResponseError as e:
        logger.info(f" Failed to create Indexer: {e}")

#endregion 

# region : Semantic / Vector Search Query

#  Run a Semantic Search Query
async def run_semantic_search(query):
    """Runs a semantic search query.""" 
    
    #vector_query = VectorizableTextQuery(text=query, k_nearest_neighbors=1, fields="vector", exhaustive=True)

    #Query the index
    # results = search_client.search(  
    # search_text=None,  
    # vector_queries= [query,1,"text_vector",True],
    # top=1
    # )  
  
    # for result in results:  
    #     logger.info(f"parent_id: {result['parent_id']}")  
    #     logger.info(f"chunk_id: {result['chunk_id']}")    
    #     logger.info(f"Content: {result['chunk']}") 

async def perform_search(query, search_type="keyword"):
    """ Performs keyword, semantic, or hybrid search """

    # documents = get_blob_files()
    # search_client.upload_documents(documents) # UNDERSTAND MORE ABOUT THIS CODE. It actually reads from the blob storage and adds to the index

    if search_type == "semantic":
        results = await search_client.search(query, query_type="semantic", semantic_configuration_name="semantic-config")
    elif search_type == "vector":
        results = await search_client.search(query, vector_query={"field": "embedding", "query_vector": [0.1] * 1536})
    else:
        results = await search_client.search(query)

    for result in results:
        logger.info(result)

#endregion

#  Main Function
async def store_to_azure_ai_search(collection_name: str, use_semantic_chunking: bool):
    """Main function to execute the workflow."""
    # base_path = "C:/Users/KEO1COB/OneDrive - Bosch Group/Documents/Office/PycharmProjects/NextGenCX/chatwithapi/"
    # Process PDF files
    pdf_folder_path = Path(os.path.join(RAG_DOCUMENTS_FOLDER, "RAG_" + collection_name))
    # pdf_folder_path = Path(base_path) / pdf_folder

    # if the folder doesn't exist create it
    if not pdf_folder_path.exists():
        pdf_folder_path.mkdir(parents=True, exist_ok=True)

    blob_url = await upload_file_to_blob(pdf_folder_path)
    logger.info(f"Blob URL: {blob_url}")
    await create_data_source()    
    index_name, semantic_configuration_name = await create_search_index()
    await create_skillset()
    await create_indexer()

    return index_name, semantic_configuration_name
    
    # input("\n Press Enter to run a Semantic Search Query... ")
    # query = input(" Enter a search query: ")
    # #run_semantic_search(query)
    # logger.info(f"Keyword Search : \n {perform_search(query, search_type="keyword")}") # or "vector" or "keyword"
    # logger.info(f"Semantic Search : \n {perform_search(query, search_type="semantic")}")
    # logger.info(f"Vector Search : \n {perform_search(query, search_type="vector")}")

# Run the script
if __name__ == "__main__":
    store_to_azure_ai_search()


# Azure AI Search - Python SDK
# https://learn.microsoft.com/en-us/python/api/overview/azure/search-documents-readme?view=azure-python
# Async - https://learn.microsoft.com/en-us/python/api/overview/azure/search-documents-readme?view=azure-python#async-apis
# https://learn.microsoft.com/en-us/azure/search/samples-python