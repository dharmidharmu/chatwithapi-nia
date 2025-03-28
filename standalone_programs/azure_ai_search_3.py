import os
import time
import traceback
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import SearchIndex, SearchField, SearchFieldDataType, VectorSearch, VectorSearchAlgorithmConfiguration, SearchIndexerSkillset
from azure.search.documents.indexes.models import  DocumentExtractionSkill, SplitSkill, AzureOpenAIEmbeddingSkill, SearchIndexer
from azure.search.documents.indexes.models import SimpleField, SemanticConfiguration, SemanticSearch
from azure.search.documents.indexes.models import SemanticPrioritizedFields, SemanticField, OutputFieldMappingEntry
from azure.search.documents.indexes.models import InputFieldMappingEntry, SearchIndexerDataSourceConnection

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

# Blob Storage Container
BLOB_CONTAINER_NAME = "rag-documents"

# Azure Search Parameters
INDEX_NAME = "rag-index"
SKILLSET_NAME = "pdf-processing-skillset"
DATASOURCE_NAME = "pdfs-datasource"
INDEXER_NAME = "pdf-indexer"

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
        # Check file size (30MB = 30 * 1024 * 1024 bytes)
        if os.path.getsize(pdf_path) <= 30 * 1024 * 1024:
            blob_client = container_client.get_blob_client(os.path.basename(pdf_path))
            with open(pdf_path, "rb") as file:
                print(f"Current file path : {file.name}")
                blob_client.upload_blob(file, overwrite=True, max_concurrency=5)
            print(f"Uploaded {pdf_path} to Azure Blob Storage.")
        else:
            print(f"Skipped {pdf_path} as it exceeds 30MB.")


def create_search_index():
    """ Creates an Azure AI Search index with vector and semantic configuration """
    
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="metadata", type=SearchFieldDataType.String, searchable=True),
        #SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions=1536, vector_search_profile_name="vector-config")
    ]

    # Define Vector Search Configuration (Fix: Added `kind` field)
    vector_search = VectorSearch(
        algorithms=[
            VectorSearchAlgorithmConfiguration(
                name="vector-config",
                kind="hnsw"  # Required field specifying the vector search algorithm type
            )
        ]
    )

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
    index = SearchIndex(name=INDEX_NAME, fields=fields, semantic_search=semantic_search)

    index_client.create_or_update_index(index)
    print("Search Index created successfully.")


def create_skillset():
    """ Creates a skillset for text extraction, chunking, and embedding """
    
    document_extraction_skill: DocumentExtractionSkill = DocumentExtractionSkill(
        name="Document Extraction",
        description="Extracts text from PDFs",
        context="/document",
        parsing_mode="default",
        data_to_extract="contentAndMetadata",
        inputs=[InputFieldMappingEntry(name="content", source="/document/content")],
        outputs=[OutputFieldMappingEntry(name="text", target_name="text")]
    )

    text_split_skill: SplitSkill = SplitSkill(
        name="Text Split",
        description="Splits text into chunks",
        maximum_page_length=2000, 
        page_overlap_length=10,
        context="/document",
        inputs=[InputFieldMappingEntry(name="text", source="/document/text")],
        outputs=[OutputFieldMappingEntry(name="chunks", target_name="chunks")],
        text_split_mode="pages"
    )

    embedding_skill: AzureOpenAIEmbeddingSkill = AzureOpenAIEmbeddingSkill(
        name="Embedding Generation",
        description="Generates embeddings",
        context="/document/chunks/*",
        inputs=[InputFieldMappingEntry(name="text", source="/document/chunks/*")],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="embedding")],
        deployment_name=AZURE_AI_EMBEDDING_DEPLOYMENT
    )

    skillset: SearchIndexerSkillset = SearchIndexerSkillset(
        name=SKILLSET_NAME, description="PDF processing skillset",
        #skills=[document_extraction_skill, text_split_skill, embedding_skill]
        skills=[document_extraction_skill, text_split_skill]
    )

    indexer_client.create_or_update_skillset(skillset)
    print("Skillset created successfully.")

def create_datasource():
    """ Creates a data source connection to Azure Blob Storage """
    indexer_client.create_or_update_data_source_connection(data_source)
    print("Data Source created successfully.")


def create_indexer():
    """ Creates an indexer to process and store documents in the search index """
    indexer: SearchIndexer = SearchIndexer(
        name=INDEXER_NAME, data_source_name=DATASOURCE_NAME, target_index_name=INDEX_NAME, skillset_name=SKILLSET_NAME,
        field_mappings=[
            {"source_field_name": "metadata_storage_path", "target_field_name": "id"},
            {"source_field_name": "content", "target_field_name": "content"},
            {"source_field_name": "metadata_storage_name", "target_field_name": "metadata"}
        ],
        output_field_mappings=[
            {"source_field_name": "/document/chunks/*/embedding", "target_field_name": "embedding"}
        ]
    )

    indexer_client.create_or_update_indexer(indexer)
    print("Indexer created successfully.")


def monitor_indexer():
    """ Monitors the status of the indexer """
    while True:
        status = indexer_client.get_indexer_status(INDEXER_NAME)
        print(f"Indexer Status: {status.status}")
        if status.status == "completed":
            break
        time.sleep(10)


def perform_search(query, search_type="keyword"):
    """ Performs keyword, semantic, or hybrid search """

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

    # https://learn.microsoft.com/en-us/azure/search/search-get-started-semantic?tabs=python
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-document-extraction
    # https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-textsplit

    
