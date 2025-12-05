"""
PharmaCheck Web Scraper Module
Handles scraping drug interactions from drugs.com with caching to MySQL
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

from database import (
    Session, Drug, Interaction, DrugInteraction, 
    FoodInteraction, DiseaseInteraction, Condition,
    get_or_create_drug, get_or_create_condition
)
from config import config


class DrugsScraper:
    """Base scraper class for drugs.com"""
    
    BASE_URL = "https://www.drugs.com"
    
    SEVERITY_MAP = {
        "int_3": "Major",
        "int_2": "Moderate", 
        "int_1": "Minor",
        "int_0": "Unknown",
        "status-category-major": "Major",
        "status-category-moderate": "Moderate",
        "status-category-minor": "Minor",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page"""
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return None
            return BeautifulSoup(response.content, "html.parser")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def _extract_severity_from_class(self, element) -> str:
        """Extract severity from element's class list"""
        if element is None:
            return "Unknown"
        
        classes = element.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        
        for cls in classes:
            if cls in self.SEVERITY_MAP:
                return self.SEVERITY_MAP[cls]
            # Check for status-category-* pattern
            if cls.startswith("status-category-"):
                return self.SEVERITY_MAP.get(cls, "Unknown")
        
        return "Unknown"
    
    def _parse_hazard_plausibility(self, text: str) -> Tuple[str, str]:
        """Parse hazard level and plausibility from text"""
        hazard = "Unknown"
        plausibility = "Unknown"
        
        if not text:
            return hazard, plausibility
        
        # Match patterns like "Major Potential Hazard, High plausibility"
        hazard_match = re.search(r'(Major|Moderate|Minor)\s+Potential\s+Hazard', text, re.IGNORECASE)
        if hazard_match:
            hazard = f"{hazard_match.group(1)} Potential Hazard"
        
        plausibility_match = re.search(r'(High|Moderate|Low)\s+plausibility', text, re.IGNORECASE)
        if plausibility_match:
            plausibility = plausibility_match.group(1)
        
        return hazard, plausibility
    
    def _get_generic_name(self, drug_name: str) -> Optional[str]:
        """Get the generic name for a drug by checking its main page"""
        drug_slug = drug_name.lower().replace(' ', '-')
        url = f"{self.BASE_URL}/{drug_slug}.html"
        soup = self._get_page(url)
        
        if not soup:
            return None
        
        # Look for "Generic name:" on the page
        generic_label = soup.find("b", string="Generic name:")
        if generic_label:
            # The generic name is usually in an <a> tag after the label
            a_tag = generic_label.find_next("a")
            if a_tag:
                return a_tag.get_text(strip=True)
        
        # Try meta description or other patterns
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            # Pattern: "Drug Name (generic_name) is..."
            match = re.search(r'\(([a-zA-Z]+)\)', content)
            if match:
                return match.group(1)
        
        return None


class DrugInteractionScraper(DrugsScraper):
    """Scraper for drug-drug interactions"""
    
    def get_drug_url(self, drug_name: str) -> Optional[str]:
        """Get the URL for a drug's interaction page"""
        # Try to find the drug page first
        search_url = f"{self.BASE_URL}/search.php?searchterm={drug_name}"
        # Direct URL pattern
        return f"{self.BASE_URL}/drug-interactions/{drug_name.lower().replace(' ', '-')}.html"
    
    def get_multi_drug_interactions(self, drug_names: List[str], professional: bool = True) -> Dict:
        """
        Get interactions between multiple drugs using the interaction checker.
        Returns dict with 'drug_interactions', 'food_interactions', 'disease_interactions'
        """
        # First we need to get the drug IDs by searching for each drug
        # For now, we'll use the drug names directly in the URL
        # The actual drugs.com uses IDs like "1115-648" for Prozac
        
        # Build a simple drug list for URL (names)
        drug_list = ",".join([d.lower().replace(' ', '-') for d in drug_names])
        
        # Try the interaction check page
        url = f"{self.BASE_URL}/interactions-check.php?drug_list={drug_list}"
        if professional:
            url += "&professional=1"
        
        soup = self._get_page(url)
        
        result = {
            "drug_interactions": [],
            "food_interactions": [],
            "disease_interactions": []
        }
        
        if not soup:
            return result
        
        # Parse drug-drug interactions
        drug_drug_header = soup.find("h2", string=lambda t: t and "Interactions between your drugs" in t)
        if drug_drug_header:
            wrapper = drug_drug_header.find_next("div", class_="interactions-reference-wrapper")
            if wrapper:
                result["drug_interactions"] = self._parse_interaction_references(wrapper, drug_names)
        
        # Parse food/lifestyle interactions
        food_header = soup.find("h2", string=lambda t: t and "food" in t.lower() and "interaction" in t.lower())
        if food_header:
            wrapper = food_header.find_next("div", class_="interactions-reference-wrapper")
            if wrapper:
                result["food_interactions"] = self._parse_interaction_references(wrapper, drug_names, is_food=True)
        
        # Parse disease interactions
        disease_header = soup.find("h2", string=lambda t: t and "disease" in t.lower() and "interaction" in t.lower())
        if disease_header:
            wrapper = disease_header.find_next("div", class_="interactions-reference-wrapper")
            if wrapper:
                result["disease_interactions"] = self._parse_interaction_references(wrapper, drug_names, is_disease=True)
        
        return result
    
    def _parse_interaction_references(self, wrapper, drug_names: List[str], is_food: bool = False, is_disease: bool = False) -> List[Dict]:
        """Parse interaction reference blocks from a wrapper element"""
        interactions = []
        refs = wrapper.find_all("div", class_="interactions-reference")
        
        for ref in refs:
            interaction = {
                "severity": "Unknown",
                "professional_description": "",
                "patient_description": "",
            }
            
            if is_food:
                interaction["interaction_name"] = "Food/Lifestyle"
            elif is_disease:
                interaction["disease_name"] = ""
            else:
                interaction["name"] = ""
                interaction["drugs_involved"] = []
            
            # Get header
            header = ref.find("div", class_="interactions-reference-header")
            if header:
                # Get severity
                severity_label = header.find("span", class_="ddc-status-label")
                if severity_label:
                    interaction["severity"] = self._extract_severity_from_class(severity_label)
                
                # Get interaction name from h3
                h3 = header.find("h3")
                if h3:
                    text = h3.get_text(strip=True)
                    if is_food:
                        # Extract what's after the drug name
                        for drug in drug_names:
                            if drug.lower() in text.lower():
                                idx = text.lower().find(drug.lower())
                                after = text[idx + len(drug):].strip()
                                if after:
                                    interaction["interaction_name"] = after
                                break
                        if not interaction.get("interaction_name"):
                            interaction["interaction_name"] = text
                    elif is_disease:
                        # Extract disease name
                        for drug in drug_names:
                            if drug.lower() in text.lower():
                                idx = text.lower().find(drug.lower())
                                after = text[idx + len(drug):].strip()
                                if after:
                                    interaction["disease_name"] = after
                                break
                        if not interaction.get("disease_name"):
                            interaction["disease_name"] = text
                    else:
                        # Drug-drug interaction - format is "Drug1 <icon> Drug2"
                        interaction["name"] = text
                        # Try to find which drugs are involved
                        for drug in drug_names:
                            if drug.lower() in text.lower():
                                interaction.setdefault("drugs_involved", []).append(drug)
                
                # Get "applies to" info
                applies_p = header.find("p")
                if applies_p:
                    applies_text = applies_p.get_text(strip=True)
                    if "Applies to:" in applies_text:
                        interaction["applies_to"] = applies_text.replace("Applies to:", "").strip()
            
            # Get description - find p tags that are NOT in header
            all_p = ref.find_all("p")
            for p in all_p:
                if header and p.find_parent("div", class_="interactions-reference-header"):
                    continue
                text = p.get_text(strip=True)
                if len(text) > 50:
                    interaction["professional_description"] = text
                    interaction["patient_description"] = text
                    break
            
            interactions.append(interaction)
        
        return interactions
    
    def get_generic_name(self, drug_url: str) -> Optional[Tuple[str, str]]:
        """Get the generic name and interaction URL from a drug page"""
        soup = self._get_page(drug_url)
        if not soup:
            return None
        
        # Look for "Generic name:" section
        b_tag = soup.find("b", string="Generic name:")
        if b_tag:
            next_elem = b_tag.find_next_sibling()
            while next_elem and next_elem.name != "br":
                if next_elem.name == "a":
                    generic_name = next_elem.text.strip()
                    href = next_elem.get("href", "")
                    if href:
                        interaction_url = f"{self.BASE_URL}/drug-interactions{href}"
                        return generic_name, interaction_url
                next_elem = next_elem.find_next_sibling()
        
        return None
    
    def get_interactions_list(self, drug_name: str) -> List[Dict]:
        """Get list of drug interactions for a given drug"""
        drug_slug = drug_name.lower().replace(' ', '-')
        urls_to_try = [
            f"{self.BASE_URL}/drug-interactions/{drug_slug}.html",
            f"{self.BASE_URL}/drug-interactions/{drug_slug.replace('-', '')}.html",
        ]
        
        soup = None
        for url in urls_to_try:
            soup = self._get_page(url)
            if soup and soup.find("ul", class_="interactions"):
                break
        
        # If still no soup with interactions, try getting generic name
        if not soup or not soup.find("ul", class_="interactions"):
            generic_name = self._get_generic_name(drug_name)
            if generic_name and generic_name.lower() != drug_name.lower():
                url = f"{self.BASE_URL}/drug-interactions/{generic_name.lower().replace(' ', '-')}.html"
                soup = self._get_page(url)
        
        if not soup:
            return []
        
        interactions = []
        
        # Find interactions list - current format uses ul.interactions.ddc-list-unstyled
        interactions_list = soup.find("ul", class_="interactions")
        if not interactions_list:
            interactions_list = soup.find("ul", class_="ddc-list-unstyled")
        
        if not interactions_list:
            return []
        
        for li in interactions_list.find_all("li"):
            interaction = {}
            
            # Get severity from class
            classes = li.get("class", [])
            severity = "Unknown"
            for cls in classes:
                if cls in self.SEVERITY_MAP:
                    severity = self.SEVERITY_MAP[cls]
                    break
            
            interaction["severity"] = severity
            
            # Get interaction name and URL
            a_tag = li.find("a")
            if a_tag:
                interaction["name"] = a_tag.text.strip()
                href = a_tag.get("href", "")
                if href.startswith("/"):
                    interaction["url"] = f"{self.BASE_URL}{href}"
                else:
                    interaction["url"] = href
            
            if interaction.get("name"):
                interactions.append(interaction)
        
        return interactions
    
    def get_interaction_details(self, interaction_url: str, professional: bool = True) -> Dict:
        """Get detailed information about an interaction"""
        url = interaction_url
        if professional:
            url = f"{interaction_url}?professional=1" if "?" not in interaction_url else f"{interaction_url}&professional=1"
        
        soup = self._get_page(url)
        if not soup:
            return {}
        
        result = {
            "professional_description": "",
            "patient_description": "",
            "severity": "Unknown",
            "references": []
        }
        
        # Find the interaction reference wrapper
        wrapper = soup.find("div", class_="interactions-reference-wrapper")
        if not wrapper:
            wrapper = soup.find("div", class_="interactions-reference")
        
        if wrapper:
            # Get severity from status label
            severity_label = wrapper.find("span", class_="ddc-status-label")
            if severity_label:
                result["severity"] = self._extract_severity_from_class(severity_label)
            
            # Get description - it's in the <p> tags
            paragraphs = wrapper.find_all("p")
            if len(paragraphs) >= 2:
                result["professional_description"] = paragraphs[1].get_text(strip=True)
            elif len(paragraphs) == 1:
                result["professional_description"] = paragraphs[0].get_text(strip=True)
            
            # Get references
            refs = wrapper.find("details", class_="ddc-reference-list")
            if refs:
                ref_items = refs.find_all("li")
                result["references"] = [li.get_text(strip=True) for li in ref_items]
        
        # Also get patient description (without professional flag)
        if professional:
            patient_soup = self._get_page(interaction_url)
            if patient_soup:
                patient_wrapper = patient_soup.find("div", class_="interactions-reference-wrapper")
                if not patient_wrapper:
                    patient_wrapper = patient_soup.find("div", class_="interactions-reference")
                if patient_wrapper:
                    paragraphs = patient_wrapper.find_all("p")
                    if len(paragraphs) >= 2:
                        result["patient_description"] = paragraphs[1].get_text(strip=True)
                    elif len(paragraphs) == 1:
                        result["patient_description"] = paragraphs[0].get_text(strip=True)
        
        return result


class FoodInteractionScraper(DrugsScraper):
    """Scraper for food/lifestyle interactions"""
    
    def get_food_interactions(self, drug_name: str) -> List[Dict]:
        """Get food/lifestyle interactions for a drug"""
        # Track original name for reference
        original_drug_name = drug_name
        
        # Try multiple URL patterns (brand name, generic name variations)
        drug_slug = drug_name.lower().replace(' ', '-')
        urls_to_try = [
            f"{self.BASE_URL}/food-interactions/{drug_slug}.html",
            f"{self.BASE_URL}/food-interactions/{drug_slug.replace('-', '')}.html",
        ]
        
        soup = None
        resolved_drug_name = drug_name  # Track what name was actually used in the URL
        
        for url in urls_to_try:
            soup = self._get_page(url)
            if soup and soup.find("div", class_="interactions-reference"):
                break
        
        # If still no soup, try getting generic name from drug page
        if not soup or not soup.find("div", class_="interactions-reference"):
            generic_name = self._get_generic_name(drug_name)
            if generic_name and generic_name.lower() != drug_name.lower():
                resolved_drug_name = generic_name
                url = f"{self.BASE_URL}/food-interactions/{generic_name.lower().replace(' ', '-')}.html"
                soup = self._get_page(url)
        
        if not soup:
            return []
        
        interactions = []
        
        # Find all interaction reference blocks
        refs = soup.find_all("div", class_="interactions-reference")
        
        for ref in refs:
            interaction = {
                "interaction_name": "",
                "severity": "Unknown",
                "hazard_level": "",
                "plausibility": "Unknown",
                "professional_description": "",
                "patient_description": ""
            }
            
            # Get header
            header = ref.find("div", class_="interactions-reference-header")
            if header:
                # Get severity
                severity_label = header.find("span", class_="ddc-status-label")
                if severity_label:
                    interaction["severity"] = self._extract_severity_from_class(severity_label)
                
                # Get interaction name from h3
                h3 = header.find("h3")
                if h3:
                    # The h3 contains "DrugName <svg icon> InteractionTarget"
                    # When parsed as text, the SVG is stripped, giving "DrugName InteractionTarget"
                    text = h3.get_text(strip=True)
                    
                    # Use the resolved drug name (generic if found) for matching
                    # The HTML will contain the generic name, not the brand name
                    resolved_lower = resolved_drug_name.lower()
                    text_lower = text.lower()
                    
                    if resolved_lower in text_lower:
                        # Find where the resolved drug name ends and extract the rest
                        idx = text_lower.find(resolved_lower)
                        if idx != -1:
                            # Skip past the drug name and any whitespace/SVG content
                            # The pattern is "DrugName <svg>...</svg> InteractionName"
                            # When parsed as text, SVG is stripped, giving "DrugName InteractionName"
                            after_drug_start = idx + len(resolved_drug_name)
                            after_drug = text[after_drug_start:].strip()
                            
                            # Remove any leading non-word characters (like leftover SVG fragments)
                            after_drug = after_drug.lstrip(' <>')
                            
                            if after_drug:
                                interaction["interaction_name"] = after_drug
                            else:
                                # Fallback: try to extract just the interaction part
                                # Pattern might be "DrugName InteractionName"
                                parts = text.split()
                                if len(parts) > 1:
                                    # Skip the first part (drug name) and join the rest
                                    interaction["interaction_name"] = ' '.join(parts[1:])
                                else:
                                    interaction["interaction_name"] = text
                        else:
                            interaction["interaction_name"] = text
                    else:
                        # Drug name not found in text - this shouldn't happen, but handle gracefully
                        # Try to extract interaction name by splitting on common separators
                        parts = text.split()
                        if len(parts) > 1:
                            # Assume first part is drug name, rest is interaction
                            interaction["interaction_name"] = ' '.join(parts[1:])
                        else:
                            interaction["interaction_name"] = text
                
                # Get hazard/plausibility from first p tag in header
                first_p = header.find("p")
                if first_p:
                    hazard_text = first_p.get_text(strip=True)
                    hazard, plausibility = self._parse_hazard_plausibility(hazard_text)
                    interaction["hazard_level"] = hazard
                    if plausibility != "Unknown":
                        interaction["plausibility"] = plausibility
            
            # Get description - look for p tags that are direct children of the reference div
            # OR p tags that come after the header
            description = ""
            all_p = ref.find_all("p")
            for p in all_p:
                # Skip the p tag inside header (hazard info)
                if header and p.find_parent("div", class_="interactions-reference-header"):
                    continue
                text = p.get_text(strip=True)
                # Skip short lines that are likely metadata
                if len(text) > 50 and "Switch to" not in text:
                    description = text
                    break
            
            if description:
                interaction["professional_description"] = description
                interaction["patient_description"] = description
            
            if interaction["interaction_name"] or description:
                if not interaction["interaction_name"]:
                    interaction["interaction_name"] = "Food/Lifestyle Interaction"
                interactions.append(interaction)
        
        return interactions


class DiseaseInteractionScraper(DrugsScraper):
    """Scraper for disease interactions"""
    
    def get_disease_interactions(self, drug_name: str) -> List[Dict]:
        """Get disease interactions for a drug"""
        # Try multiple URL patterns (brand name, generic name variations)
        drug_slug = drug_name.lower().replace(' ', '-')
        urls_to_try = [
            f"{self.BASE_URL}/disease-interactions/{drug_slug}.html",
            f"{self.BASE_URL}/disease-interactions/{drug_slug.replace('-', '')}.html",
        ]
        
        soup = None
        resolved_drug_name = drug_name  # Track what name was actually used in the URL
        
        for url in urls_to_try:
            soup = self._get_page(url)
            if soup and soup.find("div", class_="interactions-reference"):
                break
        
        # If still no soup, try getting generic name from drug page
        if not soup or not soup.find("div", class_="interactions-reference"):
            generic_name = self._get_generic_name(drug_name)
            if generic_name and generic_name.lower() != drug_name.lower():
                resolved_drug_name = generic_name
                url = f"{self.BASE_URL}/disease-interactions/{generic_name.lower().replace(' ', '-')}.html"
                soup = self._get_page(url)
        
        if not soup:
            return []
        
        interactions = []
        
        # Find all interaction reference blocks
        refs = soup.find_all("div", class_="interactions-reference")
        
        for ref in refs:
            interaction = {
                "disease_name": "",
                "severity": "Unknown",
                "hazard_level": "",
                "plausibility": "Unknown",
                "applicable_conditions": "",
                "professional_description": "",
                "patient_description": ""
            }
            
            # Get header
            header = ref.find("div", class_="interactions-reference-header")
            if not header:
                header = ref.find("div", class_="ddc-anchor-offset")
            
            if header:
                # Get severity
                severity_label = header.find("span", class_="ddc-status-label")
                if severity_label:
                    interaction["severity"] = self._extract_severity_from_class(severity_label)
                
                # Get disease name from h3
                h3 = header.find("h3")
                if h3:
                    text = h3.get_text(strip=True)
                    # The h3 contains "DrugName <svg icon> DiseaseName"
                    # When parsed as text, SVG is stripped, giving something like "Diazepam Acute Alcohol Intoxication"
                    
                    # Use the resolved drug name (generic if found) for matching
                    resolved_lower = resolved_drug_name.lower()
                    text_lower = text.lower()
                    
                    # Try to find resolved drug name and extract what's after it
                    if resolved_lower in text_lower:
                        idx = text_lower.find(resolved_lower)
                        if idx != -1:
                            # Skip past the drug name and any whitespace/SVG content
                            after_drug_start = idx + len(resolved_drug_name)
                            after_drug = text[after_drug_start:].strip()
                            
                            # Remove any leading non-word characters (like leftover SVG fragments)
                            after_drug = after_drug.lstrip(' <>')
                            
                            if after_drug:
                                interaction["disease_name"] = after_drug
                            else:
                                # Fallback: try to extract just the disease part
                                parts = text.split()
                                if len(parts) > 1:
                                    interaction["disease_name"] = ' '.join(parts[1:])
                                else:
                                    interaction["disease_name"] = text
                        else:
                            interaction["disease_name"] = text
                    else:
                        # Drug class name might be used (e.g., "Benzodiazepines (applies to diazepam)")
                        # Try to find "(applies to" pattern
                        applies_match = re.search(r'\(applies to [^)]+\)\s*(.+)$', text)
                        if applies_match:
                            interaction["disease_name"] = applies_match.group(1).strip()
                        else:
                            interaction["disease_name"] = text
                
                # Get hazard/plausibility from first p tag in header
                first_p = header.find("p")
                if first_p:
                    hazard_text = first_p.get_text(strip=True)
                    hazard, plausibility = self._parse_hazard_plausibility(hazard_text)
                    interaction["hazard_level"] = hazard
                    if plausibility != "Unknown":
                        interaction["plausibility"] = plausibility
                    
                    # Extract applicable conditions
                    conditions_match = re.search(r'Applicable conditions?:\s*(.+?)(?:\.|$)', hazard_text, re.IGNORECASE)
                    if conditions_match:
                        interaction["applicable_conditions"] = conditions_match.group(1).strip()
            
            # Get description - look for p tags that are NOT in the header
            description = ""
            all_p = ref.find_all("p")
            for p in all_p:
                # Skip p tags inside header
                if header and p.find_parent("div", class_="interactions-reference-header"):
                    continue
                text = p.get_text(strip=True)
                # Skip short lines, metadata, and switch links
                if len(text) > 50 and "Switch to" not in text and "Potential Hazard" not in text:
                    description = text
                    break
            
            if description:
                interaction["professional_description"] = description
                interaction["patient_description"] = description
            
            if interaction["disease_name"] or description:
                if not interaction["disease_name"]:
                    interaction["disease_name"] = "Disease Interaction"
                interactions.append(interaction)
        
        return interactions


class DrugInteractionChecker:
    """
    Main class for checking drug interactions with database caching
    Updated for current drugs.com HTML format
    """
    
    def __init__(self, active_ingredient: str):
        self.active_ingredient = active_ingredient
        self.drug_scraper = DrugInteractionScraper()
        self.food_scraper = FoodInteractionScraper()
        self.disease_scraper = DiseaseInteractionScraper()
        
        self.interactions = []
        self.food_interactions = []
        self.disease_interactions = []
        
        self.knowns = []
        self.unknowns = []
    
    def get_drug_interactions(self, use_cache: bool = True) -> List[Dict]:
        """Get drug-drug interactions, checking cache first"""
        db_session = Session()
        
        try:
            # Check if drug exists in database with cached interactions
            if use_cache:
                drug = db_session.query(Drug).filter(
                    Drug.name.ilike(self.active_ingredient)
                ).first()
                
                if drug and drug.drug_interactions:
                    # Return cached interactions
                    cached = []
                    for di in drug.drug_interactions:
                        interaction = di.interaction
                        cached.append({
                            "name": di.interacting_drug_name,
                            "severity": interaction.severity,
                            "professional_description": interaction.professional_description,
                            "patient_description": interaction.patient_description,
                            "ai_description": interaction.ai_description,
                            "url": interaction.url
                        })
                    if cached:
                        self.interactions = cached
                        self._categorize_interactions()
                        return cached
            
            # Scrape from drugs.com
            interactions_list = self.drug_scraper.get_interactions_list(self.active_ingredient)
            
            # Get details for each interaction
            for interaction in interactions_list:
                if interaction.get("url"):
                    details = self.drug_scraper.get_interaction_details(interaction["url"])
                    interaction.update(details)
            
            self.interactions = interactions_list
            self._categorize_interactions()
            
            # Cache to database
            self._cache_drug_interactions(db_session, interactions_list)
            
            return interactions_list
            
        finally:
            db_session.close()
    
    def _categorize_interactions(self):
        """Separate known and unknown severity interactions"""
        self.unknowns = [i for i in self.interactions if i.get("severity") == "Unknown"]
        self.knowns = [i for i in self.interactions if i.get("severity") != "Unknown"]
    
    def _cache_drug_interactions(self, session, interactions: List[Dict]):
        """Cache drug interactions to database"""
        try:
            # Get or create the drug
            drug = get_or_create_drug(session, self.active_ingredient)
            
            for interaction_data in interactions:
                # Create interaction record
                interaction = Interaction(
                    severity=interaction_data.get("severity", "Unknown"),
                    professional_description=interaction_data.get("professional_description", ""),
                    patient_description=interaction_data.get("patient_description", ""),
                    url=interaction_data.get("url", "")
                )
                session.add(interaction)
                session.flush()
                
                # Create junction record
                drug_interaction = DrugInteraction(
                    drug_id=drug.drug_id,
                    interaction_id=interaction.interaction_id,
                    interacting_drug_name=interaction_data.get("name", "")
                )
                session.add(drug_interaction)
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error caching interactions: {e}")
    
    def get_food_interactions(self, use_cache: bool = True) -> List[Dict]:
        """Get food/lifestyle interactions"""
        db_session = Session()
        
        try:
            if use_cache:
                drug = db_session.query(Drug).filter(
                    Drug.name.ilike(self.active_ingredient)
                ).first()
                
                if drug and drug.food_interactions:
                    cached = [fi.to_dict() for fi in drug.food_interactions]
                    if cached:
                        self.food_interactions = cached
                        return cached
            
            # Scrape from drugs.com
            self.food_interactions = self.food_scraper.get_food_interactions(self.active_ingredient)
            
            # Cache to database
            self._cache_food_interactions(db_session, self.food_interactions)
            
            return self.food_interactions
            
        finally:
            db_session.close()
    
    def _cache_food_interactions(self, session, interactions: List[Dict]):
        """Cache food interactions to database"""
        try:
            drug = get_or_create_drug(session, self.active_ingredient)
            
            for interaction_data in interactions:
                food_interaction = FoodInteraction(
                    drug_id=drug.drug_id,
                    interaction_name=interaction_data.get("interaction_name", ""),
                    severity=interaction_data.get("severity", "Unknown"),
                    hazard_level=interaction_data.get("hazard_level", ""),
                    plausibility=interaction_data.get("plausibility", "Unknown"),
                    professional_description=interaction_data.get("professional_description", ""),
                    patient_description=interaction_data.get("patient_description", "")
                )
                session.add(food_interaction)
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error caching food interactions: {e}")
    
    def get_disease_interactions(self, use_cache: bool = True) -> List[Dict]:
        """Get disease interactions"""
        db_session = Session()
        
        try:
            if use_cache:
                drug = db_session.query(Drug).filter(
                    Drug.name.ilike(self.active_ingredient)
                ).first()
                
                if drug and drug.disease_interactions:
                    cached = [di.to_dict() for di in drug.disease_interactions]
                    if cached:
                        self.disease_interactions = cached
                        return cached
            
            # Scrape from drugs.com
            self.disease_interactions = self.disease_scraper.get_disease_interactions(self.active_ingredient)
            
            # Cache to database
            self._cache_disease_interactions(db_session, self.disease_interactions)
            
            return self.disease_interactions
            
        finally:
            db_session.close()
    
    def _cache_disease_interactions(self, session, interactions: List[Dict]):
        """Cache disease interactions to database"""
        try:
            drug = get_or_create_drug(session, self.active_ingredient)
            
            for interaction_data in interactions:
                disease_interaction = DiseaseInteraction(
                    drug_id=drug.drug_id,
                    disease_name=interaction_data.get("disease_name", ""),
                    severity=interaction_data.get("severity", "Unknown"),
                    hazard_level=interaction_data.get("hazard_level", ""),
                    plausibility=interaction_data.get("plausibility", "Unknown"),
                    applicable_conditions=interaction_data.get("applicable_conditions", ""),
                    professional_description=interaction_data.get("professional_description", ""),
                    patient_description=interaction_data.get("patient_description", "")
                )
                session.add(disease_interaction)
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error caching disease interactions: {e}")
    
    def build_all_interactions(self):
        """Build all types of interactions"""
        self.get_drug_interactions()
        self.get_food_interactions()
        self.get_disease_interactions()


# Utility functions for similarity matching (Levenshtein)
def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def is_similar(drug1: str, drug2: str, threshold: float = 0.35) -> bool:
    """Check if two drug names are similar using Levenshtein distance"""
    distance = levenshtein_distance(drug1.lower(), drug2.lower())
    max_length = max(len(drug1), len(drug2))
    normalized_distance = distance / max_length
    return normalized_distance <= threshold


def check_interaction(drug: str, interaction_name: str, threshold: float = 0.2) -> bool:
    """Check if a drug matches an interaction name"""
    if interaction_name.lower() in drug.lower():
        return True
    return is_similar(drug, interaction_name, threshold)

