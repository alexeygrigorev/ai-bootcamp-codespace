#!/usr/bin/env python3
"""Check indexing status"""
import json

with open('indexing_results.json') as f:
    data = json.load(f)

print("=" * 60)
print("INDEXING SUMMARY")
print("=" * 60)
print(f"Companies processed: {len(data)}")
print(f"Successful: {sum(1 for r in data if r.get('chunks_indexed', 0) > 0)}")
print(f"Total chunks: {sum(r.get('chunks_indexed', 0) for r in data):,}")
print()
print("Top companies by chunks:")
for r in sorted(data, key=lambda x: x.get('chunks_indexed', 0), reverse=True)[:10]:
    if r.get('chunks_indexed', 0) > 0:
        print(f"  {r['company']}: {r.get('chunks_indexed', 0):,} chunks ({r.get('filings_indexed', 0)} filings)")

