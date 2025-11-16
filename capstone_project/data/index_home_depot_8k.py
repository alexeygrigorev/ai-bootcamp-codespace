#!/usr/bin/env python3
"""
Index Home Depot's November 2014 8-K filing about the data breach.

Accession number: 0000354950-14-000042
Document: hd_8kx110614.htm
"""

from pathlib import Path
import time

from src.sec_edgar_client import SECEdgarClient
from src.sec_xml_parser import parse_sec_filing, chunk_sec_documents
from src.sec_search_tools import index_sec_chunks
from elasticsearch import Elasticsearch

# Home Depot specific information
CIK = "0000354950"
ACCESSION_NUMBER = "0000354950-14-000042"
DOCUMENT_NAME = "hd_8kx110614.htm"

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 1000


def enhance_chunks_with_metadata(chunks, filing_date, form_type):
    """Enhance chunks with filing metadata."""
    enhanced = []
    for i, chunk in enumerate(chunks):
        enhanced_chunk = {
            "id": f"{DOCUMENT_NAME}_chunk_{i}",
            "content": chunk.get("content", ""),
            "metadata": {
                **chunk.get("metadata", {}),
                "cik": CIK,
                "filing_date": filing_date,
                "form": form_type,
                "accession_number": ACCESSION_NUMBER,
                "document_name": DOCUMENT_NAME,
            }
        }
        enhanced.append(enhanced_chunk)
    return enhanced


def main():
    """Download, parse, and index the Home Depot November 2014 8-K."""
    print("="*80)
    print("Indexing Home Depot November 2014 8-K Filing")
    print("="*80)
    print(f"CIK: {CIK}")
    print(f"Accession Number: {ACCESSION_NUMBER}")
    print(f"Document: {DOCUMENT_NAME}")
    print()
    
    # Check Elasticsearch connection
    print("Checking Elasticsearch connection...")
    es = Elasticsearch('http://localhost:9200')
    try:
        if not es.ping():
            print("❌ Cannot connect to Elasticsearch. Make sure it's running on localhost:9200")
            return
        print("✓ Elasticsearch is connected")
        
        # Check current index count
        if es.indices.exists(index="sec_filings"):
            count = es.count(index="sec_filings")['count']
            print(f"✓ Current index has {count:,} documents")
        else:
            print("⚠️  Index 'sec_filings' does not exist - will be created")
    except Exception as e:
        print(f"❌ Error connecting to Elasticsearch: {e}")
        return
    
    # Initialize SEC client
    print("\nInitializing SEC EDGAR client...")
    client = SECEdgarClient()
    print("✓ SEC client initialized")
    
    # Create output directory
    output_dir = Path("sec_downloads") / CIK
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Using cache directory: {output_dir}")
    
    # Download the filing
    print(f"\nDownloading filing...")
    print(f"  Accession: {ACCESSION_NUMBER}")
    print(f"  Document: {DOCUMENT_NAME}")
    
    try:
        downloaded_path = client.download_filing_document(
            accession_number=ACCESSION_NUMBER,
            primary_document=DOCUMENT_NAME,
            cik=CIK,
            output_dir=str(output_dir)
        )
        
        if downloaded_path and Path(downloaded_path).exists():
            print(f"✓ Downloaded to: {downloaded_path}")
            file_path = downloaded_path
        else:
            print("❌ Download failed")
            return
        
        # Parse the filing
        print(f"\nParsing filing...")
        parsed = parse_sec_filing(file_path, document_name=DOCUMENT_NAME)
        print(f"✓ Parsed successfully")
        
        # Chunk the document
        print(f"\nChunking document...")
        chunks = chunk_sec_documents(
            [parsed],
            size=CHUNK_SIZE,
            step=CHUNK_SIZE - CHUNK_OVERLAP
        )
        print(f"✓ Created {len(chunks)} chunks")
        
        # Enhance with metadata
        filing_date = "2014-11-06"  # November 6, 2014 based on document name
        enhanced_chunks = enhance_chunks_with_metadata(chunks, filing_date, "8-K")
        
        # Index the chunks
        print(f"\nIndexing {len(enhanced_chunks)} chunks...")
        indexed_count = index_sec_chunks(
            enhanced_chunks,
            index_name="sec_filings",
            es_client=es,
            create_index=True
        )
        
        print(f"✓ Indexed {indexed_count} chunks")
        
        # Check final index status
        print("\n" + "="*80)
        print("FINAL INDEX STATUS")
        print("="*80)
        try:
            total_count = es.count(index="sec_filings")['count']
            print(f"Total documents in 'sec_filings' index: {total_count:,}")
            
            # Check Home Depot count
            hd_count = es.count(index="sec_filings", body={"query": {"term": {"metadata.cik": CIK}}})['count']
            print(f"Home Depot (CIK {CIK}) chunks: {hd_count:,}")
        except Exception as e:
            print(f"Could not get index count: {e}")
        
        print("\n✅ Successfully indexed Home Depot November 2014 8-K filing!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

