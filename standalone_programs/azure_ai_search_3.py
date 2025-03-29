import os
import re
import time
import base64
import traceback
from typing import List
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import SearchIndex, SearchIndexer, SearchField, SearchFieldDataType, SearchIndexerSkillset
from azure.search.documents.indexes.models import  DocumentExtractionSkill, SplitSkill, AzureOpenAIEmbeddingSkill, OcrSkill, MergeSkill
from azure.search.documents.indexes.models import SimpleField, SemanticConfiguration, SemanticSearch, CorsOptions, ScoringProfile
from azure.search.documents.indexes.models import SemanticPrioritizedFields, SemanticField, OutputFieldMappingEntry, FieldMapping, FieldMappingFunction
from azure.search.documents.indexes.models import InputFieldMappingEntry, SearchIndexerDataSourceConnection
from azure.search.documents.indexes.models import VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration, VectorSearchAlgorithmKind
from azure.search.documents.indexes.models import SearchIndexerIndexProjections, SearchIndexerIndexProjectionSelector, SearchIndexerIndexProjectionsParameters, IndexProjectionMode, CognitiveServicesAccountKey

from azure.search.documents import SearchClient
import glob

from dotenv import load_dotenv


#load environment properties
load_dotenv()

# Azure Credentials
AZURE_STORAGE_CONNECTION_STRING = os.getenv("BLOB_STORAGE_CONNECTION_STRING")
AZURE_SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT_URL")
AZURE_SEARCH_KEY = os.getenv("SEARCH_KEY")
AZURE_AI_EMBEDDING_DEPLOYMENT = os.getenv("EMBEDDING_MODEL_NAME")  # Change based on your deployment
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_ENDPOINT_URL")
AZURE_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_AI_SERVICES_KEY=os.getenv("AZURE_AI_SERVICES_API_KEY")

# Blob Storage Container
BLOB_CONTAINER_NAME = "rag-documents"

# Azure Search Parameters
INDEX_NAME = "rag-index"
SKILLSET_NAME = "rag-processing-skillset"
DATASOURCE_NAME = "rag-datasource"
INDEXER_NAME = "rag-indexer"

blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client: ContainerClient = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
data_source: SearchIndexerDataSourceConnection = SearchIndexerDataSourceConnection(
        name=DATASOURCE_NAME, type="azureblob",
        connection_string=AZURE_STORAGE_CONNECTION_STRING,
        container={"name": BLOB_CONTAINER_NAME}
    )
index_client = SearchIndexClient(AZURE_SEARCH_ENDPOINT, AzureKeyCredential(AZURE_SEARCH_KEY))
indexer_client = SearchIndexerClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
search_client = SearchClient(AZURE_SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(AZURE_SEARCH_KEY))

# Function to generate a valid ID
def generate_valid_id(file_name):
    """Convert filename into a valid ID for Azure AI Search."""
    return re.sub(r'[^A-Za-z0-9_=]', '_', file_name)  # Replace invalid characters

# Function to encode file path (if needed)
def encode_file_path(file_path):
    """Base64 encode file path for unique ID."""
    return base64.urlsafe_b64encode(file_path.encode()).decode()

def sanitize_filename(filename):
    """Sanitize the filename by replacing all dots and special characters with underscores."""
    sanitized_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', filename)  # Replace all non-alphanumeric characters
    return sanitized_filename

# Fetch files from Azure Blob Storage
def get_blob_files():
    """Retrieve list of files in the blob storage."""
    container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
    blob_list = container_client.list_blobs()
    
    documents = []
    for blob in blob_list:
        file_name = blob.name.split("/")[-1]  # Extract filename
        file_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob.name}"

        # Generate a valid ID
        valid_id = generate_valid_id(file_name)  # Option 1
        # valid_id = encode_file_path(file_url)  # Option 2 (Use if file names may conflict)

        # Prepare document for Azure AI Search
        document = {
            "id": valid_id,
            "metadata_storage_name": file_name,
            "metadata_storage_path": file_url
        }
        documents.append(document)

    return documents


def upload_pdfs_to_blob(pdf_file_path):
    """ Uploads PDFs to Azure Blob Storage """
    # Create container if not exists
    try:
        container_client.create_container()
        print("Created Blob Container.")
    except Exception:
        print("Blob Container already exists.")

    # Get all PDF files in the folder
    pdf_files = glob.glob(os.path.join(pdf_file_path, "*.pdf"))

    for pdf_path in pdf_files:
        # Sanitize file name before using it in blob storage
        original_filename = os.path.basename(pdf_path)
        safe_filename = sanitize_filename(original_filename)
        
        # Check file size (30MB = 30 * 1024 * 1024 bytes)
        if os.path.getsize(pdf_path) <= 30 * 1024 * 1024:
            #blob_client = container_client.get_blob_client(os.path.basename(pdf_path))
            blob_client = container_client.get_blob_client(safe_filename) # Use sanitized name
            with open(pdf_path, "rb") as file:
                print(f"Uploading: {safe_filename} (Original: {original_filename})")
                blob_client.upload_blob(file, overwrite=True, max_concurrency=5)
            print(f"Uploaded {pdf_path} to Azure Blob Storage as {safe_filename}.")
        else:
            print(f"Skipped {pdf_path} as it exceeds 30MB.")

def create_search_index():
    """ Creates an Azure AI Search index with vector and semantic configuration """

    # Define Vector Search Configuration (Fix: Added `kind` field)
    vector_search = VectorSearch(
        algorithms=[
            # VectorSearchAlgorithmConfiguration(
            #     name="vector-config",
            #     kind=VectorSearchAlgorithmKind.HNSW  # Required field specifying the vector search algorithm type
            # ),
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                kind=VectorSearchAlgorithmKind.HNSW
            )
        ],

        profiles=[
            VectorSearchProfile(
                name="hnswVectorSearchProfile",
                algorithm_configuration_name="hnsw-config"
            )
        ]
    )

    cors_options = CorsOptions(allowed_origins=["*"], max_age_in_seconds=60)
    scoring_profiles: List[ScoringProfile] = []
    
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="metadata", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="embedding", 
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single), 
                    searchable=True, 
                    vector_search_dimensions=1536, 
                    vector_search_profile_name="hnswVectorSearchProfile")
    ]

    # semantic_config = SemanticConfiguration(
    #     name="semantic-config",
    #     prioritized_fields=SemanticPrioritizedFields(
    #         title_field=SemanticField(field_name="metadata"),
    #         content_fields=[SemanticField(field_name="content")]
    #     )
    # )

    semantic_config = SemanticConfiguration(
        name="semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="metadata"),
            keywords_fields=[SemanticField(field_name="content")],
            content_fields=[SemanticField(field_name="content")]
        )
    )

    # Create the semantic settings with the configuration
    semantic_search = SemanticSearch(configurations=[semantic_config])

    #index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search, semantic_search=semantic_search)
    index:SearchIndex = SearchIndex(
        name=INDEX_NAME, 
        fields=fields, 
        scoring_profiles=scoring_profiles,
        cors_options=cors_options,
        semantic_search=semantic_search,
        vector_search=vector_search)

    index_client.create_or_update_index(index)
    print("Search Index created successfully.")


def create_skillset():
    """ Creates a skillset for text extraction, chunking, and embedding """
    # DocumentExtractionSkill is used to extract text from various document types (e.g., PDFs, Word documents). 
    # It ensures that the content is accurately extracted from different formats.
    # Using DocumentExtractionSkill can enhance the quality of content extraction, especially when dealing with diverse document formats. 
    # It ensures that the text is correctly extracted before any further processing.
    document_extraction_skill: DocumentExtractionSkill = DocumentExtractionSkill(
        name="Document Extraction",
        description="Extract text from different types of documents",
        context="/document",
        parsing_mode="default",
        data_to_extract="contentAndMetadata",
        inputs=[InputFieldMappingEntry(name="file_data", source="/document/file_data")],
        outputs=[OutputFieldMappingEntry(name="content", target_name="/document/content")]
    )

    ocr_skill: OcrSkill = OcrSkill(
        description="OCR skill to scan PDFs and other images with text",
        context="/document/normalized_images/*",
        line_ending="Space",
        default_language_code="en",
        should_detect_orientation=True,
        inputs=[
            InputFieldMappingEntry(name="image", source="/document/normalized_images/*")
        ],
        outputs=[
            OutputFieldMappingEntry(name="text", target_name="text"),
            OutputFieldMappingEntry(name="layoutText", target_name="layoutText")
        ]
    )

    merge_skill: MergeSkill = MergeSkill(
        description="Merge skill for combining OCR'd and regular text",
        context="/document",
        inputs=[
            InputFieldMappingEntry(name="text", source="/document/content"),
            InputFieldMappingEntry(name="itemsToInsert", source="/document/normalized_images/*/text"),
            InputFieldMappingEntry(name="offsets", source="/document/normalized_images/*/contentOffset")
        ],
        outputs=[
            OutputFieldMappingEntry(name="mergedText", target_name="merged_content")
        ]
    )

    use_ocr: bool = False

    split_skill_text_source = "/document/content" if not use_ocr else "/document/merged_content"
    split_skill = SplitSkill(
        description="Split skill to chunk documents",
        context="/document",
        text_split_mode="pages", #"sentences",
        maximum_page_length=2000,
        page_overlap_length=500,
        inputs=[
            InputFieldMappingEntry(name="text", source=split_skill_text_source),
        ],
        outputs=[
            OutputFieldMappingEntry(name="textItems", target_name="pages")
        ],
    )

    # Split Skill is used to break down the extracted text into smaller chunks, which is useful for processing and embedding.
    # If your documents are already in a text-friendly format (e.g., plain text), you might not need DocumentExtractionSkill. 
    # However, for PDFs, scanned images, or complex formats, it is beneficial.
    # text_split_skill: SplitSkill = SplitSkill(
    #     name="Text Split",
    #     description="Splits text into chunks",
    #     context="/document",
    #     text_split_mode="pages", #"sentences",
    #     maximum_page_length=2000, 
    #     page_overlap_length=500,
    #     inputs=[InputFieldMappingEntry(name="text", source="/document/extracted_text")],
    #     outputs=[OutputFieldMappingEntry(name="textItems", target_name="chunks")]
    # )

    embedding_skill = AzureOpenAIEmbeddingSkill(
        description="Skill to generate embeddings via Azure OpenAI",
        context="/document/pages/*",
        resource_uri=AZURE_OPENAI_ENDPOINT,
        deployment_id=AZURE_AI_EMBEDDING_DEPLOYMENT,
        #model_name=azure_openai_model_name,
        #dimensions=azure_openai_model_dimensions,
        api_key=AZURE_OPENAI_API_KEY,
        inputs=[
            InputFieldMappingEntry(name="text", source="/document/pages/*"),
        ],
        outputs=[
            OutputFieldMappingEntry(name="embedding", target_name="vector")
        ],
    )


    # embedding_skill: AzureOpenAIEmbeddingSkill = AzureOpenAIEmbeddingSkill(
    #     name="Embedding Generation",
    #     description="Generates embeddings",
    #     context="/document/chunks/*",
    #     inputs=[InputFieldMappingEntry(name="text", source="/document/chunks/*")],
    #     outputs=[OutputFieldMappingEntry(name="embedding", target_name="embedding")],
    #     deployment_id=AZURE_AI_EMBEDDING_DEPLOYMENT,
    #     resource_uri=AZURE_OPENAI_ENDPOINT,
    #     api_key=AZURE_OPENAI_API_KEY
    # )

    # index_projections = SearchIndexerIndexProjections(
    #     selectors=[
    #         SearchIndexerIndexProjectionSelector(
    #             target_index_name=INDEX_NAME,
    #             parent_key_field_name="title",
    #             source_context="/document/pages/*",
    #             mappings=[
    #                 InputFieldMappingEntry(name="chunk", source="/document/pages/*"),
    #                 InputFieldMappingEntry(name="vector", source="/document/pages/*/vector"),
    #                 InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),
    #             ],
    #         ),
    #     ],
    #     parameters=SearchIndexerIndexProjectionsParameters(
    #         projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
    #     ),
    # )

    cognitive_services_account = CognitiveServicesAccountKey(key=AZURE_AI_SERVICES_KEY) if use_ocr else None
    skills = [document_extraction_skill, split_skill, embedding_skill]
    if use_ocr:
        skills.extend([ocr_skill, merge_skill])

    skillset: SearchIndexerSkillset = SearchIndexerSkillset(
        name=SKILLSET_NAME, 
        description="PDF processing skillset",
        skills=skills,
        #index_projections=index_projections,
        cognitive_services_account=cognitive_services_account
    )

    indexer_client.create_or_update_skillset(skillset)
    print("Skillset created successfully.")

def create_datasource():
    """ Creates a data source connection to Azure Blob Storage """
    indexer_client.create_or_update_data_source_connection(data_source)
    print("Data Source created successfully.")


def create_indexer():
    """ Creates an indexer to process and store documents in the search index """
    # Define the field mapping function to replace '.' with '_'
    # field_mapping_function: FieldMappingFunction = FieldMappingFunction(
    #     name="replace",  # Built-in Azure function for string replacement
    #     parameters={"find": ".", "replace": "_"}  # Replace '.' with '_'
    # )

    # # Define a field mapping function to replace '.' with '_'
    # field_mapping_function = FieldMappingFunction(
    #     name="replace",
    #     parameters={"pattern": "\\.", "replacement": "_"}  # Replace '.' with '_'
    # )

    # Use base64Encode mapping function to encode the metadata_storage_path
    field_mapping_function = FieldMappingFunction(
        name="base64Encode"  # Supported Azure AI Search function
    )

    # Define the field mapping with the transformation function
    field_mapping_id = FieldMapping(
        source_field_name="metadata_storage_path",  # Source field in the data source
        target_field_name="id",  # Target field in the index
        mapping_function=field_mapping_function  # Apply the transformation
    )
    
    # Define the field mapping with the transformation function
    # field_mapping_id: FieldMapping = FieldMapping(
    #     source_field_name="metadata_storage_name",  # Source field in the data source
    #     target_field_name="id",  # Target field in the index
    #     mapping_function=field_mapping_function  # Apply the transformation function
    # )

    indexer: SearchIndexer = SearchIndexer(
        name=INDEXER_NAME, 
        data_source_name=DATASOURCE_NAME, 
        target_index_name=INDEX_NAME, 
        skillset_name=SKILLSET_NAME,
        field_mappings=[
                            field_mapping_id, # Use the field mapping with transformation
                            #FieldMapping(source_field_name="metadata_storage_path", target_field_name="id"),
                            FieldMapping(source_field_name="content", target_field_name="content"),
                            FieldMapping(source_field_name="metadata_storage_name", target_field_name="metadata")
                       ],  
        # field_mappings=[
        #     {
        #         "source_field_name": "metadata_storage_path", 
        #         "target_field_name": "id",
        #         "inputValueTransformation": "base64Encode" #"replace('.', '_')"
        #     },
        #     {
        #         "source_field_name": "content", 
        #         "target_field_name": "content"
        #     },
        #     {
        #         "source_field_name": "metadata_storage_name", 
        #         "target_field_name": "metadata"
        #     }
        # ],
        output_field_mappings=[
            {"source_field_name": "/document/chunks/*/embedding", "target_field_name": "embedding"}
        ]
    )

    indexer_client.create_or_update_indexer(indexer)
    print("Indexer created successfully.")


def monitor_indexer():
    """Monitors the status of the indexer"""
    while True:
        status = indexer_client.get_indexer_status(INDEXER_NAME)
        print(f"Indexer Status: {status.status}")
        if status.status in ["success", "completed"]:
            print("Indexer completed successfully.")
            break
        elif status.status == "error":
            print(f"Indexer failed: {status.last_result.errors}")
            break
        time.sleep(10)


def perform_search(query, search_type="keyword"):
    """ Performs keyword, semantic, or hybrid search """

    # documents = get_blob_files()
    # search_client.upload_documents(documents) # UNDERSTAND MORE ABOUT THIS CODE. It actually reads from the blob storage and adds to the index

    if search_type == "semantic":
        results = search_client.search(query, query_type="semantic", semantic_configuration="semantic-config")
    elif search_type == "vector":
        results = search_client.search(query, vector_query={"field": "embedding", "query_vector": [0.1] * 1536})
    else:
        results = search_client.search(query)

    for result in results:
        print(result)


if __name__ == "__main__":
    pdf_file_path = "C:\Projects\ABB Robotics\ABB Robotics\Azure AI Service Documentation"

    try:
        upload_pdfs_to_blob(pdf_file_path)
        create_search_index()
        create_skillset()
        create_datasource()
        create_indexer()
        monitor_indexer()
        perform_search("Azure AI Search", search_type="semantic")
    except Exception as e:
        print(f"Exception occurered {e}")
        traceback.print_exc()


    # Tutorial: Design an index for RAG in Azure AI Search : https://learn.microsoft.com/en-us/azure/search/tutorial-rag-build-solution-index-schema

    # Python examples for Azure AI Search - https://learn.microsoft.com/en-us/azure/search/samples-python
    # https://learn.microsoft.com/en-us/azure/search/search-get-started-semantic?tabs=python
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-extraction
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-textsplit
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-defining-skillset
    # A skillset executes after text and images are extracted from an external data source, and after field mappings are processed.
    # Indexers drive skillset execution. You need an indexer, data source, and index before you can test your skillset.

    # Enable enrichment caching to reuse the content you've already processed and lower the cost of development.
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-incremental-indexing-conceptual

    # https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization
    # https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-configure-vectorizer

    # https://dev.to/willvelida/improving-azure-ai-search-results-with-semantic-search-1mpk

    
# Limitations
#Semantic search is applied to results returned from the BM25 ranking function. It can re-rank results provided by the BM25 ranking function, it won't provide any additional documents that weren't returned by the BM25 ranking function.
#Also, remember that the BM25 ranking only works for the first 50 results. If more than 50 results are returned, only the top 50 results are considered.