#!/usr/bin/env python3
"""
Quick script to check Elasticsearch status and connection.
Run this to verify Elasticsearch is ready before using the agent.
"""

import sys
import subprocess
from pathlib import Path

def check_docker():
    """Check if Docker is running"""
    try:
        result = subprocess.run(['docker', 'info'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def check_elasticsearch_container():
    """Check if Elasticsearch container exists and is running"""
    try:
        # Check running containers
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=elasticsearch', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=5
        )
        running = [c for c in result.stdout.strip().split('\n') if c]
        
        # Check all containers (including stopped)
        result_all = subprocess.run(
            ['docker', 'ps', '-a', '--filter', 'name=elasticsearch', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=5
        )
        all_containers = [c for c in result_all.stdout.strip().split('\n') if c]
        
        return running, all_containers
    except:
        return [], []

def check_elasticsearch_connection():
    """Check if Elasticsearch is responding on port 9200"""
    try:
        import requests
        response = requests.get('http://localhost:9200', timeout=2)
        if response.status_code == 200:
            data = response.json()
            return True, data.get('version', {}).get('number', 'unknown')
        return False, None
    except ImportError:
        return None, "requests package not installed"
    except Exception as e:
        return False, str(e)

def check_index():
    """Check if sec_filings index exists"""
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch('http://localhost:9200', request_timeout=2)
        if es.ping():
            if es.indices.exists(index="sec_filings"):
                count = es.count(index="sec_filings")['count']
                return True, count
            return True, 0  # Connected but no index
        return False, "Cannot ping Elasticsearch"
    except ImportError:
        return None, "elasticsearch package not installed"
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 60)
    print("Elasticsearch Status Check")
    print("=" * 60)
    print()
    
    # Check Docker
    print("1. Checking Docker...")
    docker_running = check_docker()
    if not docker_running:
        print("   ❌ Docker is not running")
        print()
        print("   📋 To fix:")
        print("      - Start Docker Desktop from Applications")
        print("      - Wait for Docker to fully start")
        print("      - Run: ./setup_elasticsearch.sh")
        print()
        return 1
    print("   ✓ Docker is running")
    print()
    
    # Check container
    print("2. Checking Elasticsearch container...")
    running, all_containers = check_elasticsearch_container()
    if not all_containers:
        print("   ⚠️  No Elasticsearch container found")
        print()
        print("   📋 To create one:")
        print("      - Run: ./setup_elasticsearch.sh")
        print("      - Or manually: docker run -d -p 9200:9200 -e 'discovery.type=single-node' --name elasticsearch elasticsearch:8.11.0")
        print()
        return 1
    elif not running:
        print(f"   ⚠️  Container exists but is not running: {all_containers[0]}")
        print()
        print("   📋 To start it:")
        print(f"      Run: docker start {all_containers[0]}")
        print("      Or: ./setup_elasticsearch.sh")
        print()
        return 1
    else:
        print(f"   ✓ Container is running: {running[0]}")
    print()
    
    # Check connection
    print("3. Checking Elasticsearch connection...")
    conn_status, conn_info = check_elasticsearch_connection()
    if conn_status is None:
        print(f"   ⚠️  {conn_info}")
        print("      Install with: pip install requests")
    elif not conn_status:
        print(f"   ❌ Cannot connect: {conn_info}")
        print("      Container may still be starting. Wait a few seconds and try again.")
    else:
        print(f"   ✓ Connected! Version: {conn_info}")
    print()
    
    # Check index
    print("4. Checking sec_filings index...")
    index_status, index_info = check_index()
    if index_status is None:
        print(f"   ⚠️  {index_info}")
        print("      Install with: pip install elasticsearch")
    elif index_status:
        if isinstance(index_info, int):
            if index_info > 0:
                print(f"   ✓ Index exists with {index_info:,} documents")
            else:
                print("   ⚠️  Index exists but is empty")
                print("      You need to index SEC filing chunks first")
        else:
            print(f"   ⚠️  {index_info}")
    else:
        print("   ⚠️  Index 'sec_filings' does not exist")
        print("      It will be created automatically when you index documents")
    print()
    
    # Summary
    print("=" * 60)
    if docker_running and running and conn_status:
        print("✅ Elasticsearch is ready!")
        if index_status and isinstance(index_info, int) and index_info > 0:
            print("✅ Index exists with data - you can use the agent!")
        else:
            print("⚠️  Index is empty - you need to index SEC filings first")
    else:
        print("❌ Elasticsearch is not ready. Fix the issues above.")
        return 1
    
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())


