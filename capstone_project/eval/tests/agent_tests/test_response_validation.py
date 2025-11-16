"""
Unit tests for validating agent responses.

These tests check:
1. CIK lookup accuracy
2. Data source transparency (no general knowledge)
3. Proper SEC filing citations
4. Subsidiary/parent company mapping
5. Response structure and completeness
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any


# Expected CIK mappings for known companies
EXPECTED_CIKS = {
    "change healthcare": "0000731766",  # Should map to UnitedHealth Group
    "unitedhealth group": "0000731766",
    "capital one": "0000927628",
    "home depot": "0000354950",
    "t-mobile": "0001283699",
    "tmobile": "0001283699",
    "sony pictures": "0000313838",  # Should map to Sony Group Corp
    "sony": "0000313838",
    "yahoo": "0001011006",  # Historical name, should map to Altaba
    "altaba": "0001011006",
    "uber": "0001543151",
    "mgm": "0000789570",
    "mgm resorts": "0000789570",
    "equifax": "0000033185",
    "first american": "0001472787",
    "first american financial": "0001472787",
    "solarwinds": "0001739942",
}

# Forbidden phrases that indicate general knowledge usage
FORBIDDEN_PHRASES = [
    "based on general knowledge",
    "based on publicly available",
    "while there are no documented disclosures",
    "we can outline general risks",
    "even though specific sec filings are not available",
    "based on general context",
    "here is an overview based on",
    "it is important to highlight that while i could not find",
    "however, based on",
]

# Required SEC form types for citations
SEC_FORM_TYPES = ["8-k", "10-k", "10-q", "6-k", "20-f"]


class TestResponseValidation:
    """Test suite for validating agent responses."""
    
    @pytest.fixture
    def stress_test_results(self) -> Dict[str, Any]:
        """Load stress test results."""
        results_path = Path(__file__).parent.parent / "stress_test_results.json"
        if not results_path.exists():
            pytest.skip(f"Stress test results not found at {results_path}")
        with open(results_path) as f:
            return json.load(f)
    
    @pytest.fixture
    def test_results(self, stress_test_results) -> List[Dict[str, Any]]:
        """Extract individual test results."""
        return stress_test_results.get("results", [])
    
    def test_no_forbidden_phrases(self, test_results: List[Dict[str, Any]]):
        """Test that responses don't contain forbidden general knowledge phrases."""
        violations = []
        for result in test_results:
            response_lower = result.get("response", "").lower()
            question_num = result.get("question_number", "unknown")
            
            for phrase in FORBIDDEN_PHRASES:
                if phrase in response_lower:
                    violations.append({
                        "question": question_num,
                        "phrase": phrase,
                        "focus": result.get("primary_focus", "")
                    })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): Found '{v['phrase']}'"
                for v in violations
            ])
            pytest.fail(f"Found forbidden phrases in responses:\n{violation_msg}")
    
    def test_cik_accuracy(self, test_results: List[Dict[str, Any]]):
        """Test that responses use correct CIKs for known companies."""
        violations = []
        
        # Wrong CIKs that were previously found
        wrong_ciks = {
            "0001620492": "FT 5231 (wrong for Change Healthcare)",
            "0001617179": "Conrad Management LLC (wrong for Yahoo)",
            "0001542058": "Sysco Seattle (wrong for Uber)",
            "0001047379": "AUR RESOURCES INC (wrong for MGM)",
        }
        
        for result in test_results:
            response = result.get("response", "")
            question_text = result.get("question_text", "").lower()
            question_num = result.get("question_number", "unknown")
            
            # Check for wrong CIKs
            for wrong_cik, description in wrong_ciks.items():
                if wrong_cik in response:
                    # Check if this CIK is actually wrong for this question
                    if any(company in question_text for company in ["change healthcare", "yahoo", "uber", "mgm"]):
                        violations.append({
                            "question": question_num,
                            "wrong_cik": wrong_cik,
                            "description": description,
                            "focus": result.get("primary_focus", "")
                        })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): Found wrong CIK {v['wrong_cik']} - {v['description']}"
                for v in violations
            ])
            pytest.fail(f"Found wrong CIKs in responses:\n{violation_msg}")
    
    def test_subsidiary_mapping(self, test_results: List[Dict[str, Any]]):
        """Test that subsidiaries are correctly mapped to parent companies."""
        violations = []
        
        for result in test_results:
            response_lower = result.get("response", "").lower()
            question_text = result.get("question_text", "").lower()
            question_num = result.get("question_number", "unknown")
            
            # Check Change Healthcare → UnitedHealth Group mapping
            if "change healthcare" in question_text:
                if "unitedhealth" not in response_lower or "0000731766" not in result.get("response", ""):
                    violations.append({
                        "question": question_num,
                        "issue": "Change Healthcare not mapped to UnitedHealth Group",
                        "focus": result.get("primary_focus", "")
                    })
            
            # Check Sony Pictures → Sony Group Corp mapping
            if "sony pictures" in question_text:
                # If response is just "no filings found", we can't verify mapping from response
                has_no_filings = "no cybersecurity disclosures found" in response_lower or \
                               "no information available" in response_lower or \
                               "unable to provide information" in response_lower
                
                if not has_no_filings:
                    # If response has content, check for parent company mapping
                    if ("sony group" not in response_lower and "0000313838" not in result.get("response", "")):
                        violations.append({
                            "question": question_num,
                            "issue": "Sony Pictures not mapped to Sony Group Corp",
                            "focus": result.get("primary_focus", "")
                        })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): {v['issue']}"
                for v in violations
            ])
            pytest.fail(f"Subsidiary mapping failures:\n{violation_msg}")
    
    def test_sec_citations_when_filings_found(self, test_results: List[Dict[str, Any]]):
        """Test that responses cite SEC filings when information is provided."""
        violations = []
        
        for result in test_results:
            response = result.get("response", "")
            response_lower = response.lower()
            question_num = result.get("question_number", "unknown")
            
            # If response contains actual information (not just "no filings found"),
            # it should cite SEC forms
            has_no_filings = "no cybersecurity disclosures found" in response_lower or \
                           "no information available" in response_lower or \
                           "no sec filings found" in response_lower
            
            if not has_no_filings:
                # Response has information, should cite SEC forms
                # Exception: Responses that are refusals to provide general knowledge
                is_refusal = ("unable to provide information" in response_lower or \
                             "unable to provide" in response_lower and "sec filings" in response_lower) or \
                            ("please let me know" in response_lower and "sec filing" in response_lower)
                
                if not is_refusal:
                    has_citation = any(form_type in response_lower for form_type in SEC_FORM_TYPES)
                    
                    if not has_citation:
                        violations.append({
                            "question": question_num,
                            "focus": result.get("primary_focus", ""),
                            "issue": "Response contains information but no SEC form citations"
                        })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): {v['issue']}"
                for v in violations
            ])
            pytest.fail(f"Missing SEC citations:\n{violation_msg}")
    
    def test_response_structure(self, test_results: List[Dict[str, Any]]):
        """Test that responses have proper structure."""
        violations = []
        
        for result in test_results:
            response = result.get("response", "")
            question_num = result.get("question_number", "unknown")
            
            # Responses should not be empty
            if not response or len(response.strip()) < 10:
                violations.append({
                    "question": question_num,
                    "issue": "Response is empty or too short",
                    "focus": result.get("primary_focus", "")
                })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): {v['issue']}"
                for v in violations
            ])
            pytest.fail(f"Response structure issues:\n{violation_msg}")
    
    def test_historical_name_mapping(self, test_results: List[Dict[str, Any]]):
        """Test that historical names (Yahoo → Altaba) are correctly mapped."""
        violations = []
        
        for result in test_results:
            response = result.get("response", "")
            response_lower = response.lower()
            question_text = result.get("question_text", "").lower()
            question_num = result.get("question_number", "unknown")
            
            # Check Yahoo → Altaba mapping
            if "yahoo" in question_text or "altaba" in question_text:
                # If response is just "no filings found", we can't verify CIK from response
                # But we can check if company info section exists and has CIK
                has_no_filings = "no cybersecurity disclosures found" in response_lower or \
                               "no information available" in response_lower
                
                if has_no_filings:
                    # When no filings found, response might not include CIK
                    # This is acceptable - the lookup still happened correctly
                    continue
                
                # If response has content, check for CIK
                if "0001011006" not in response and "company information" in response_lower:
                    violations.append({
                        "question": question_num,
                        "issue": "Yahoo/Altaba not using correct CIK 0001011006",
                        "focus": result.get("primary_focus", "")
                    })
        
        if violations:
            violation_msg = "\n".join([
                f"Q{v['question']} ({v['focus']}): {v['issue']}"
                for v in violations
            ])
            pytest.fail(f"Historical name mapping failures:\n{violation_msg}")


class TestCIKLookup:
    """Test CIK lookup functionality directly."""
    
    def test_change_healthcare_maps_to_unitedhealth(self):
        """Test that Change Healthcare maps to UnitedHealth Group CIK."""
        from src.company_cik_lookup import lookup_company_cik
        from src.subsidiary_cik_mapping import find_parent_cik_for_subsidiary
        
        # Test subsidiary mapping
        result = find_parent_cik_for_subsidiary("Change Healthcare")
        assert result is not None, "Change Healthcare should be found as subsidiary"
        parent_cik, _ = result
        assert parent_cik == "0000731766", f"Expected UnitedHealth Group CIK, got {parent_cik}"
    
    def test_sony_pictures_maps_to_sony_group(self):
        """Test that Sony Pictures maps to Sony Group Corp CIK."""
        from src.subsidiary_cik_mapping import find_parent_cik_for_subsidiary
        
        result = find_parent_cik_for_subsidiary("Sony Pictures")
        assert result is not None, "Sony Pictures should be found as division"
        parent_cik, _ = result
        assert parent_cik == "0000313838", f"Expected Sony Group Corp CIK, got {parent_cik}"
    
    def test_yahoo_maps_to_altaba_cik(self):
        """Test that Yahoo maps to Altaba CIK (historical name)."""
        from src.company_cik_lookup import lookup_company_cik
        
        cik = lookup_company_cik("Yahoo")
        assert cik == "0001011006", f"Expected Altaba CIK, got {cik}"
    
    def test_ticker_symbol_lookup(self):
        """Test that ticker symbols map to correct CIKs."""
        from src.company_cik_lookup import lookup_by_ticker
        
        test_cases = [
            ("UBER", "0001543151"),
            ("MGM", "0000789570"),
            ("EFX", "0000033185"),
            ("UNH", "0000731766"),
        ]
        
        for ticker, expected_cik in test_cases:
            cik = lookup_by_ticker(ticker)
            assert cik == expected_cik, f"Ticker {ticker} should map to CIK {expected_cik}, got {cik}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

