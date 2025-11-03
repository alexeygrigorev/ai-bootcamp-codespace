"""
Pytest configuration and fixtures for WikiAgent tests
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add wikiagent to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'wikiagent'))

# Mock environment variables for testing
os.environ['OPENAI_API_KEY'] = 'test-api-key-12345'


@pytest.fixture
def mock_search_results():
    """Mock Wikipedia search results"""
    return [
        {
            "title": "Capybara",
            "snippet": "The capybara is the largest living rodent...",
            "pageid": 12345,
            "size": 50000,
            "wordcount": 5000
        },
        {
            "title": "Rodent",
            "snippet": "Rodents are mammals of the order Rodentia...",
            "pageid": 67890,
            "size": 40000,
            "wordcount": 4000
        }
    ]


@pytest.fixture
def mock_page_content():
    """Mock Wikipedia page content"""
    return """{{Infobox mammal
| name = Capybara
| image = Capybara.jpg
}}
The capybara (''Hydrochoerus hydrochaeris'') is the largest living [[rodent]] in the world. Capybaras are native to [[South America]] and are found in countries such as [[Brazil]], [[Venezuela]], [[Colombia]], and [[Paraguay]]. They inhabit savannas and dense forests, and are always found near bodies of water such as lakes, rivers, swamps, ponds, and marshes.
"""

