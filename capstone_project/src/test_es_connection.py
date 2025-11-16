#!/usr/bin/env python3
"""Test Elasticsearch connection"""
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://localhost:9200'], request_timeout=5)
try:
    info = es.info()
    print('✓ Connected! Version:', info['version']['number'])
    print('✓ Cluster name:', info['cluster_name'])
except Exception as e:
    print('✗ Connection failed:', e)
    import traceback
    traceback.print_exc()

