"""
SEC Filing XML Parser and Chunker

This module provides functionality to parse XML documents from SEC filings
and create intelligent chunks for use in RAG systems.

Based on chunking approaches from week1 docs.py and intelligent-chunking.ipynb
"""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Iterable, Optional, Sequence
from pathlib import Path
import html


class SECXMLParser:
    """Parser for SEC filing XML documents."""
    
    # Common SEC filing document types
    FILING_TYPES = {
        '10-K': 'Annual Report',
        '10-Q': 'Quarterly Report',
        '8-K': 'Current Report',
        'S-1': 'IPO Registration',
        'S-3': 'Registration',
        'DEF 14A': 'Proxy Statement'
    }
    
    def __init__(self, preserve_html: bool = False):
        """
        Initialize the SEC XML parser.
        
        Args:
            preserve_html: If True, keeps HTML tags in text. If False, strips them.
        """
        self.preserve_html = preserve_html
    
    def parse_xml(self, xml_content: str, document_name: str = "filing") -> Dict[str, Any]:
        """
        Parse XML content from an SEC filing.
        
        Args:
            xml_content: Raw XML or HTML content from SEC filing
            document_name: Name/identifier for the document
            
        Returns:
            Dictionary containing parsed document structure
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            # Try parsing as HTML
            return self._parse_html(xml_content, document_name)
        
        # Extract metadata
        metadata = {
            'document_name': document_name,
            'filing_type': self._infer_filing_type(document_name),
            'sections': []
        }
        
        # Parse sections
        sections = self._extract_sections(root)
        metadata['sections'] = sections
        
        return metadata
    
    def _parse_html(self, html_content: str, document_name: str) -> Dict[str, Any]:
        """
        Parse HTML content from SEC filing.
        
        Args:
            html_content: HTML content
            document_name: Name identifier
            
        Returns:
            Dictionary with parsed content
        """
        # Clean and extract text from HTML
        if self.preserve_html:
            cleaned_content = html_content
        else:
            cleaned_content = self._strip_html_tags(html_content)
        
        # Try to find section headers
        sections = self._find_html_sections(cleaned_content)
        
        return {
            'document_name': document_name,
            'filing_type': self._infer_filing_type(document_name),
            'sections': sections if sections else [{'title': 'Content', 'content': cleaned_content}],
            'raw_length': len(html_content)
        }
    
    def _extract_sections(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        Extract logical sections from XML document.
        
        Args:
            root: XML root element
            
        Returns:
            List of section dictionaries
        """
        sections = []
        
        # Look for common SEC filing sections
        # Common section tags we might encounter
        # section_patterns = [
        #     'heading', 'title', 'header', 'section', 
        #     'div[@class]', 'article', 'chapter'
        # ]
        
        current_section = {'title': 'Introduction', 'content': ''}
        
        def process_element(elem, depth=0):
            nonlocal current_section
            
            # Try to identify section headers
            tag = elem.tag.lower()
            if any(keyword in tag for keyword in ['heading', 'title', 'h1', 'h2', 'h3', 'h4']):
                if current_section['content']:
                    sections.append(current_section)
                current_section = {
                    'title': self._get_text(elem),
                    'content': ''
                }
            
            # Collect text content
            text = self._get_text(elem)
            if text and text.strip():
                current_section['content'] += text + ' '
            
            # Process children
            for child in elem:
                process_element(child, depth + 1)
        
        process_element(root)
        
        # Add final section
        if current_section['content']:
            sections.append(current_section)
        
        return sections
    
    def _find_html_sections(self, content: str) -> List[Dict[str, Any]]:
        """Find sections in HTML content using pattern matching."""
        sections = []
        
        # Look for section headers (Item 1, Item 2, etc. in 10-K/10-Q)
        pattern = r'(Item\s+\d+[A-Z]?\.?\s+[^\n]+)'
        matches = re.finditer(pattern, content, re.IGNORECASE)
        
        last_pos = 0
        sections_found: List[str] = []
        
        for match in matches:
            if last_pos > 0:
                section_content = content[last_pos:match.start()].strip()
                if section_content:
                    sections.append({
                        'title': sections_found[-1] if sections_found else 'Introduction',
                        'content': section_content
                    })
            last_pos = match.start()
            sections_found.append(match.group(1))
        
        # Add final section
        if last_pos > 0 and last_pos < len(content):
            section_content = content[last_pos:].strip()
            if section_content:
                sections.append({
                    'title': sections_found[-1] if sections_found else 'Content',
                    'content': section_content
                })
        
        return sections if sections else [{'title': 'Content', 'content': content}]
    
    def _get_text(self, elem: ET.Element) -> str:
        """Extract text from XML element."""
        if self.preserve_html:
            return ET.tostring(elem, method='text', encoding='unicode')
        else:
            return ' '.join(elem.itertext())
    
    def _strip_html_tags(self, html_content: str) -> str:
        """Strip HTML tags from content."""
        # Basic HTML tag removal
        text = re.sub(r'<[^>]+>', '', html_content)
        # Decode HTML entities
        text = html.unescape(text)
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def _infer_filing_type(self, document_name: str) -> str:
        """Infer filing type from document name."""
        name_lower = document_name.lower()
        for filing_code, description in self.FILING_TYPES.items():
            if filing_code.lower() in name_lower:
                return description
        return 'SEC Filing'


def sliding_window(
    seq: Sequence[Any],
    size: int,
    step: int
) -> List[Dict[str, Any]]:
    """
    Create overlapping chunks from a sequence using a sliding window approach.

    Args:
        seq: The input sequence (string or list) to be chunked.
        size (int): The size of each chunk/window.
        step (int): The step size between consecutive windows.

    Returns:
        list: A list of dictionaries, each containing:
            - 'start': The starting position of the chunk in the original sequence
            - 'content': The chunk content

    Raises:
        ValueError: If size or step are not positive integers.
    """
    if size <= 0 or step <= 0:
        raise ValueError("size and step must be positive")

    n = len(seq)
    result = []
    for i in range(0, n, step):
        batch = seq[i:i+size]
        result.append({'start': i, 'content': batch})
        if i + size > n:
            break

    return result


def chunk_sec_documents(
    documents: Iterable[Dict[str, Any]],
    size: int = 2000,
    step: int = 1000,
    chunk_by_section: bool = True
) -> List[Dict[str, Any]]:
    """
    Split SEC filing documents into smaller chunks.
    
    This function intelligently chunks SEC filings by:
    1. Preserving section structure when possible
    2. Using sliding windows for large sections
    3. Maintaining document metadata in each chunk
    
    Args:
        documents: Iterable of SEC document dictionaries
        size: Maximum size of each chunk (in characters)
        step: Step size for sliding window overlap
        chunk_by_section: If True, preserves section boundaries
        
    Returns:
        List of chunk dictionaries with all metadata
    """
    results = []
    
    # parser = SECXMLParser()  # Not needed for chunking
    
    for doc in documents:
        doc_copy = doc.copy()
        
        # If document has sections, process each section separately
        if 'sections' in doc and chunk_by_section:
            sections = doc['sections']
            
            for section in sections:
                section_title = section.get('title', 'Untitled')
                section_content = section.get('content', '')
                
                # Chunk the section if it's too large
                if len(section_content) > size:
                    chunks = sliding_window(section_content, size=size, step=step)
                    for chunk in chunks:
                        chunk['section_title'] = section_title
                        chunk.update(doc_copy)
                    results.extend(chunks)
                else:
                    chunk = {
                        'section_title': section_title,
                        'content': section_content,
                        'start': 0
                    }
                    chunk.update(doc_copy)
                    results.append(chunk)
        else:
            # Fall back to simple sliding window chunking
            content = doc.get('content', '')
            if not content:
                continue
                
            chunks = sliding_window(content, size=size, step=step)
            for chunk in chunks:
                chunk.update(doc_copy)
            results.extend(chunks)
    
    return results


def parse_sec_filing(
    file_path: str,
    document_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parse a SEC filing from a file path.
    
    Args:
        file_path: Path to the filing document
        document_name: Optional name for the document
        
    Returns:
        Parsed document dictionary
    """
    parser = SECXMLParser()
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    if document_name is None:
        document_name = Path(file_path).stem
    
    return parser.parse_xml(content, document_name)


if __name__ == "__main__":
    # Example usage
    parser = SECXMLParser()
    
    # Example document
    example_doc = {
        'document_name': 'aapl-10k_2023',
        'sections': [
            {'title': 'Business Overview', 'content': 'Long content here...' * 100},
            {'title': 'Risk Factors', 'content': 'Risk content...' * 50}
        ]
    }
    
    # Chunk the document
    chunks = chunk_sec_documents([example_doc], size=500, step=250)
    
    print(f"Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk.get('section_title', 'N/A')}")
        print(f"  Content length: {len(chunk.get('content', ''))}")
        print(f"  Content preview: {chunk.get('content', '')[:100]}...")

