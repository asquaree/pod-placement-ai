#!/usr/bin/env python3
"""
NetTune AI Backend - Pod Placement Assistant

This module provides the backend logic for the NetTune AI application, which assists
with 5G/vDU network pod placement. It handles:
  - Loading dimensioning and pod flavor data from CSV
  - Parsing natural language queries to extract field=value criteria
  - Routing queries to dimensioning DB, pod flavors DB, or LLM (DR rules / general)
  - Calling Samsung Gauss LLM API for conversational and rule-based answers
  - Formatting responses and parsing structured output (dimensioning flavor, pods)

The frontend (nettune_frontend.py) communicates only via get_backend() and
backend.process_query(); no UI dependencies here.
"""

import pandas as pd
import re
import requests
import time
from typing import List, Dict, Any, Optional, Tuple, Set 
from transformers import AutoTokenizer
import logging


# =============================================================================
# LLM INTEGRATION - Samsung Gauss API
# =============================================================================

class GaussLLM():
    """
    Custom LLM client for Samsung Gauss generative AI API.

    Sends chat-style requests (system prompt + contents) to the Gauss OpenAPI
    and returns the model's text response. Used for DR rules answers and
    general conversational queries.
    """
    temperature: float = 0.1
    max_tokens: int = 32000
    top_p: float = 0.8
    top_k: int = 40
    repetition_penalty: float = 1.18
    key: str = "Bearer eyJ4NXQiOiJNV0l5TkRJNVlqRTJaV1kxT0RNd01XSTNOR1ptTVRZeU5UTTJOVFZoWlRnMU5UTTNaVE5oTldKbVpERTFPVEE0TldFMVlUaGxNak5sTldFellqSXlZUSIsImtpZCI6Ik1XSXlOREk1WWpFMlpXWTFPRE13TVdJM05HWm1NVFl5TlRNMk5UVmhaVGcxTlRNM1pUTmhOV0ptWkRFMU9UQTROV0UxWVRobE1qTmxOV0V6WWpJeVlRX1JTMjU2IiwidHlwIjoiYXQrand0IiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJmMTJkMWRiYS1lOWM0LTQ3MzktOGRmNy03Y2IxZjM1MTIxZGEiLCJhdXQiOiJBUFBMSUNBVElPTiIsImF1ZCI6Imk0VmdLTVRFWDNTNWhZd1dpZ3A4TWFYbG1qc2EiLCJuYmYiOjE3NTY4OTAwMDUsImF6cCI6Imk0VmdLTVRFWDNTNWhZd1dpZ3A4TWFYbG1qc2EiLCJzY29wZSI6ImRlZmF1bHQiLCJpc3MiOiJodHRwczpcL1wvaW5ub3ZhdGlvbi13c28yLnNlYy5zYW1zdW5nLm5ldDo0NDNcL29hdXRoMlwvdG9rZW4iLCJleHAiOjQ5MTI2NTAwMDUsImlhdCI6MTc1Njg5MDAwNSwianRpIjoiNDY3M2VhYTEtMDU1YS00ODI2LTlhMzYtM2Y0MWQzODNjMmEwIiwiY2xpZW50X2lkIjoiaTRWZ0tNVEVYM1M1aFl3V2lncDhNYVhsbWpzYSJ9.U3w5m1WkcuQUyPRBvaYYNfB8u5nj-PGSJzYOpyDYL109KY86GD9GWQ3NoK1zptUoIVBVU6KUK170NWMbiOwkFkA0geXnkEw_E8eao1X2i8U9rjtBmTUjcelw9r2Fxf_bEo-W1XnK5MDQOiUhlFw2klweXT4PANdHFo3KsXgqnv0mL-PUyFWTS-gOiB3PyWE9uP_8nkqcftoJI573_zfy9Hl5si5ZzM2HVHcKjyZFpoMSmHMr0rDZqI5-wo1UF93bSkmVKX9fGUTm6MfmtQjZpfIsjXaS43z1r__VBSDao0l3aE3AEBQ2s5xKP55C6KeDW9GjQAPv-L6qnPugtdkFWw"
    api_url: str = "https://genai-openapi.sec.samsung.net/swahq/trial/api-chat/openapi/chat/v1/messages"
    app_id: str = "srOZp3TxPOn="

    def _call(self, contents: List, prompt_template: str = "", stop: Optional[List[str]] = None) -> str:
        """
        Send a single non-streaming request to Gauss API and return the reply text.

        Args:
            contents: List of message content blocks (context, history, question).
            prompt_template: Optional system prompt (injected as system_prompt in body).
            stop: Optional stop sequences (not used by current API).

        Returns:
            Model reply as string, or an error message string if no content in response.
        """
        current_time = str(int(time.time() * 1000))
        headers = {
            "Content-Type": "application/json",
            "x-generative-ai-client": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJjbGllbnRJZCI6IjhhMjZiYWJlLTdmYmUtNDdkYi1iYmQ5LWM3ZjRmNDNiZDkyYi01MTEiLCJjbGllbnRTZWNyZXQiOiJtSXhrMzdZa2ZxbXpGZzZUOUZYRTJlbUFLWUVHY0kwRiIsImV4cCI6MTc2NDY4NzU5OX0.4-vDMYtMlNcZeZ4WJfD6r8I_teYTY6ypxkAe2l6O4Xs",
            "x-openapi-token": f"{self.key}",
            "x-generative-ai-user-email": "aakash.a1@samsung.com"

        }
        body = {
            "modelIds": ["01988e97-abe2-7086-949c-ffd600fdf991"],
            "contents":contents,
            "isStream": False,
            "llmConfig": {
                "max_new_tokens": self.max_tokens,
                "return_full_text": False,
                "seed": None,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "repetition_penalty": self.repetition_penalty,
            },

        }

        if prompt_template:
            body["system_prompt"] = prompt_template

        res = requests.post(self.api_url, headers=headers, json=body, verify=False)
        res.raise_for_status()

        data = res.json()

        if data.get('content'):
            return data.get('content').strip()
        else:
            return "[Error] No valid response received from model."

    @property
    def _llm_type(self) -> str:
        return "gauss-custom-llm"


# =============================================================================
# DATA LOADING - CSV to in-memory records
# =============================================================================

class DataProcessor:
    """
    Loads and normalizes dimensioning and pod flavor data from CSV files.

    Produces two lists of dicts: df_map_list (dimensioning rows: Operator,
    Network Function, Dimensioning Flavor, Package, DPP/DIP/DMP/CMP/PMP/RMP/IPP)
    and pf_map_list (pod flavor rows: Pod type, Pod flavor, vCPU, vMemory, etc.).
    These are used by QueryProcessor for field-based filtering.
    """

    def __init__(self):
        self.df_map_list = []   # Dimensioning flavor records (one dict per row)
        self.pf_map_list = []   # Pod flavor records (one dict per row)

    def load_csv_data(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Load both CSVs and build in-memory lists of record dicts.

        Returns:
            (df_map_list, pf_map_list) for dimensioning and pod flavors.
        Raises:
            Exception if either CSV file is missing.
        """
        try:
            dimensioning_df = pd.read_csv("dimension_flavor_25A_25B_26A.csv")
            pod_flavor_df = pd.read_csv("pod_flavors_25A_25B_EU_US.csv")
        except FileNotFoundError as e:
            raise Exception(f"Required CSV files not found: {e}")

        # --- Dimensioning data: map each row to a dict and keep for query matching ---
        df_docStrList = []
        self.df_map_list = []

        for idx, row in dimensioning_df.iterrows():
            map_data = {
                'Operator': row['Operator'],
                'Network Function': row['Network Function'],
                'Dimensioning Flavor': row['Dimensioning Flavor'],
                'Package': row['Package'],
                'DPP': row['DPP'],
                'DIP': row['DIP'],
                'DMP': row['DMP'],
                'CMP': row['CMP'],
                'PMP': row['PMP'],
                'RMP': row['RMP'],
                'IPP': row['IPP']
            }
            self.df_map_list.append(map_data)
            
            content = self._create_content_string(row, [
                'Operator', 'Network Function', 'Dimensioning Flavor', 'Package',
                'DPP', 'DIP', 'DMP', 'CMP', 'PMP', 'RMP', 'IPP'
            ])
            df_docStrList.append(content.strip())

        # --- Pod flavor data: same idea for pod type/flavor and resource columns ---
        pf_docStrList = []
        self.pf_map_list = []

        for idx, row in pod_flavor_df.iterrows():
            map_data = {
                'Pod type': row['Pod type'],
                'Pod flavor': row['Pod flavor'],
                'vCPU Request (vCore)': row['vCPU Request (vCore)'],
                'vCPU Limit (vCore)': row['vCPU Limit (vCore)'],
                'vMemory (GB)': row['vMemory (GB)'],
                'Hugepage (GB)': row['Hugepage (GB)'],
                'Persistent Volume (GB)': row['Persistent Volume (GB)']
            }
            self.pf_map_list.append(map_data)
            
            content = self._create_content_string(row, [
                'Pod type', 'Pod flavor', 'vCPU Request (vCore)', 'vCPU Limit (vCore)',
                'vMemory (GB)', 'Hugepage (GB)', 'Persistent Volume (GB)'
            ])
            pf_docStrList.append(content.strip())


        return self.df_map_list, self.pf_map_list

    def _create_content_string(self, row, fields):
        """Build a single text line per field (e.g. for display); normalizes 'Flavor' to 'Flavour' in output."""
        content = ""
        for field in fields:
            if field == 'Dimensioning Flavor':
                content += f"Dimensioning Flavour: {row[field]}\n"
            else:
                content += f"{field}: {row[field]}\n"
        return content


# =============================================================================
# TEXT MATCHING - Fuzzy match query field names to CSV column names
# =============================================================================

class TextMatcher:
    """
    String similarity and fuzzy matching so user query terms (e.g. "dimensioning flavour")
    can be matched to actual CSV column names (e.g. "Dimensioning Flavor").
    """

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Edit distance between two strings (insert/delete/substitute)."""
        if len(s1) < len(s2):
            return TextMatcher.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def calculate_similarity_score(candidate: str, target: str) -> float:
        """
        Score in [0, 1]: 1.0 exact match, 0.95 after normalising flavour/colour,
        else combination of character-level (Levenshtein) and word-overlap similarity.
        """
        candidate_lower = candidate.lower().strip()
        target_lower = target.lower().strip()

        if candidate_lower == target_lower:
            return 1.0

        # Treat British vs American spelling as almost identical
        candidate_norm = candidate_lower.replace('flavour', 'flavor').replace('colour', 'color')
        target_norm = target_lower.replace('flavour', 'flavor').replace('colour', 'color')

        if candidate_norm == target_norm:
            return 0.95

        distance = TextMatcher.levenshtein_distance(candidate_lower, target_lower)
        max_len = max(len(candidate_lower), len(target_lower))

        if max_len == 0:
            return 0.0

        similarity = 1.0 - (distance / max_len)

        # Blend with Jaccard-like word overlap for multi-word field names
        candidate_words = set(candidate_lower.split())
        target_words = set(target_lower.split())

        if candidate_words and target_words:
            word_overlap = len(candidate_words.intersection(target_words))
            total_words = len(candidate_words.union(target_words))
            word_similarity = word_overlap / total_words if total_words > 0 else 0
            similarity = 0.6 * similarity + 0.4 * word_similarity

        return similarity

    @staticmethod
    def find_best_field_match(candidate_field: str, available_fields: Set[str], min_score: float = 0.5) -> Optional[str]:
        """Return the available field name that best matches candidate_field, or None if no score >= min_score."""
        best_match = None
        best_score = 0.0

        for available_field in available_fields:
            score = TextMatcher.calculate_similarity_score(candidate_field, available_field)
            if score > best_score and score >= min_score:
                best_score = score
                best_match = available_field

        return best_match


# =============================================================================
# QUERY PROCESSING - Parse natural language into field criteria and filter docs
# =============================================================================

class QueryProcessor:
    """
    Turns natural language queries into structured criteria (field -> list of values)
    and filters document lists (dimensioning or pod flavor records) to matching rows.

    Pipeline: clean_query -> separate_context_from_query -> extract_field_value_pairs
    -> parse_query_for_fields (with TextMatcher) -> find_matching_documents.
    """

    def __init__(self, df_map_list: List[Dict], pf_map_list: List[Dict]):
        self.df_map_list = df_map_list   # Dimensioning records for filtering
        self.pf_map_list = pf_map_list   # Pod flavor records for filtering

    @staticmethod
    def clean_query(query: str) -> str:
        """Normalise query: collapse repeated quotes, remove brackets, collapse whitespace."""
        query = re.sub(r'"{2,}', '"', query)
        query = re.sub(r'[(){}\[\]]', '', query)
        query = re.sub(r'\s+', ' ', query)
        return query.strip()

    @staticmethod
    def separate_context_from_query(query: str) -> str:
        """
        Strip optional 'context' tail (e.g. 'just for the context ...') so we only
        parse the main question part for field=value pairs.
        """
        context_markers = [
            r'just\s+for\s+the\s+context',
            r'these\s+all\s+are',
            r'also\s+called\s+as',
            r'strings\s+like'
        ]

        earliest_pos = len(query)
        for marker in context_markers:
            match = re.search(marker, query, re.IGNORECASE)
            if match and match.start() < earliest_pos:
                earliest_pos = match.start()

        return query[:earliest_pos].strip() if earliest_pos < len(query) else query

    @staticmethod
    def extract_field_value_pairs(query: str) -> List[Tuple[str, str]]:
        """
        Find all field=value or field:value pairs in the query string.
        Handles quoted values and unquoted values (stops at comma, space, or ' and').
        """
        pairs = []

        i = 0
        while i < len(query):
            if query[i] in '=:':
                # Walk backward to find start of field name
                field_start = i - 1
                while field_start >= 0 and query[field_start].isspace():
                    field_start -= 1

                if field_start >= 0:
                    field_end = field_start + 1
                    while field_start >= 0 and (query[field_start].isalnum() or query[field_start] in ' _-'):
                        field_start -= 1
                    field_start += 1

                    field_candidate = query[field_start:field_end].strip()

                    # Walk forward to find value (quoted or unquoted)
                    value_start = i + 1
                    while value_start < len(query) and query[value_start].isspace():
                        value_start += 1

                    if value_start < len(query):
                        if query[value_start] in '"\'':
                            quote_char = query[value_start]
                            value_end = value_start + 1
                            while value_end < len(query) and query[value_end] != quote_char:
                                value_end += 1
                            if value_end < len(query):
                                value = query[value_start + 1:value_end]
                                pairs.append((field_candidate, value))
                                i = value_end + 1
                                continue
                        else:
                            value_end = value_start
                            while (value_end < len(query) and 
                                query[value_end] not in ' ,\n\r\t' and
                                not (value_end < len(query) - 3 and query[value_end:value_end+4].lower() == ' and')):
                                value_end += 1
                            
                            value = query[value_start:value_end].strip()
                            if (len(value) >= 2 and 
                                value.lower() not in {'and', 'or', 'the', 'for', 'with'}):
                                pairs.append((field_candidate, value))
                            
                            i = value_end
                            continue
            i += 1
        
        return QueryProcessor._clean_field_value_pairs(pairs)
    
    @staticmethod
    def _clean_field_value_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Drop noise words from field names and filter out invalid (too short, placeholder, etc.) pairs."""
        cleaned_pairs = []
        for field_candidate, value in pairs:
            words = field_candidate.split()
            filtered_words = [
                word for word in words
                if word.lower() not in {'for', 'the', 'and', 'or', 'extract', 'information', 'following'}
            ]

            if filtered_words:
                clean_field = ' '.join(filtered_words)

                # Keep only reasonable field names (<=3 words) and non-placeholder values
                if (len(clean_field.split()) <= 3 and
                    len(value) >= 2 and
                    not value.startswith('<') and
                    not re.match(r'^[0-9]+\.$', value)):
                    cleaned_pairs.append((clean_field, value))

        return cleaned_pairs

    def parse_query_for_fields(self, query: str, available_fields: Set[str]) -> Dict[str, List[str]]:
        """
        From free-text query, produce a dict: canonical_field_name -> [value1, value2, ...].
        Uses extract_field_value_pairs + TextMatcher to map user field names to CSV columns.
        """
        query_cleaned = self.clean_query(query)
        main_query = self.separate_context_from_query(query_cleaned)
        field_value_pairs = self.extract_field_value_pairs(main_query)

        field_criteria = {}

        for field_candidate, value in field_value_pairs:
            matched_field = TextMatcher.find_best_field_match(field_candidate, available_fields)
            
            if matched_field:
                if matched_field in field_criteria:
                    if value not in field_criteria[matched_field]:
                        field_criteria[matched_field].append(value)
                else:
                    field_criteria[matched_field] = [value]
        
        return field_criteria

    def find_matching_documents(self, documents: List[Dict], field_criteria: Dict[str, List[str]]) -> List[Dict]:
        """Return all documents where every criterion field matches at least one of its allowed values."""
        match_documents = []

        for doc in documents:
            isMatch = True
            for field_name, field_values in field_criteria.items():
                if field_name not in doc:
                    isMatch = False
                    break
                match_found = False
                for value in field_values:
                    if str(doc[field_name]).lower() == str(value).lower():
                        match_found = True
                        break
                if not match_found:
                    isMatch = False
                    break
            if isMatch:
                match_documents.append(doc)

        return match_documents

    def extract_documents_from_query(self, documents: List[Dict], query: str) -> List[Dict]:
        """
        One-shot: parse query into field criteria, then filter documents.
        Returns [] if no field=value pairs found or if documents list is empty.
        """
        if not documents:
            return []

        available_fields = set(documents[0].keys())
        field_criteria = self.parse_query_for_fields(query, available_fields)

        if not field_criteria:
            return []

        return self.find_matching_documents(documents, field_criteria)


# =============================================================================
# RESPONSE PROCESSING - Parse LLM/context output into structured data
# =============================================================================

class ResponseProcessor:
    """
    Parses structured text (e.g. dimensioning context or LLM output) into a standard
    shape: dimensioning_flavor, network_function, pods[ {pod_name, pod_flavor} ].
    Also formats list-of-dicts back into markdown-style context strings for the LLM.
    """

    def __init__(self):
        pass

    def preprocess_df_data(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse dimensioning-style text: 'Dimensioning Flavor: X', 'Network Function: Y',
        and lines like '- DPP: flavor-name' for pods. Pod names must contain 'p' and
        not be 'package' (to avoid matching unrelated list items).
        """
        dimensioning_flavor = "Not Available"
        network_function = "Not Available"
        pods = []

        lines = llm_output.strip().splitlines()

        for line in lines:
            if re.search(r'Dimensioning Flavo[u]?r', line, re.IGNORECASE):
                match = re.search(r'Dimensioning Flavo[u]?r\s*[:\-]\s*(.+)', line, re.IGNORECASE)
                if match:
                    dimensioning_flavor = match.group(1).strip()

            elif re.search(r'Network Function', line, re.IGNORECASE):
                match = re.search(r'Network Function\s*[:\-]\s*(.+)', line, re.IGNORECASE)
                if match:
                    network_function = match.group(1).strip()

            else:
                # Lines like "  - DPP: medium-uni" or "  - IPP: small"
                match = re.match(r'\s*-\s*([A-Za-z]{2,4}):\s*(.+)', line.strip())
                if match:
                    pod_name = match.group(1).strip()
                    pod_flavor = match.group(2).strip()
                    # Accept DPP, DIP, DMP, CMP, PMP, RMP, IPP etc.; skip 'package'
                    if 'p' in pod_name.lower() and pod_name.lower() != 'package':
                        pods.append({
                            'pod_name': pod_name,
                            'pod_flavor': pod_flavor
                        })

        return {
            "dimensioning_flavor": dimensioning_flavor,
            "network_function": network_function,
            "pods": pods
        }

    def dict_to_context(self, data_dict_list: List[Dict], title: str = "Context Information") -> str:
        """Format a list of dicts as markdown (## title, ### Item N, - Key: value) for LLM context."""
        context_lines = [f"## {title}\n"]
        
        for i, data_dict in enumerate(data_dict_list, 1):
            context_lines.append(f"### Item {i}")
            for key, value in data_dict.items():
                formatted_key = key.replace('_', ' ').title()
                context_lines.append(f"- {formatted_key}: {value}")
            context_lines.append("")
        
        return "\n".join(context_lines)


# =============================================================================
# MAIN BACKEND SERVICE - Query routing, orchestration, and API for frontend
# =============================================================================

class NetTuneBackend:
    """
    Single entry point for the Pod Placement Assistant backend.

    - initialize(): Load CSVs, build QueryProcessor (must be called before process_query).
    - process_query(): Route question to dimensioning DB, pod flavors DB, or LLM; return response dict.
    - Session state (e.g. df_result from a previous dimensioning answer) is passed in by the frontend.
    """

    def __init__(self):
        self.data_processor = DataProcessor()
        self.query_processor = None      # Set in initialize() after data is loaded
        self.response_processor = ResponseProcessor()
        self.llm = GaussLLM()
        self.tokenizer = None             # Optional: for token counting if path provided
        self.initialized = False

        # Token budget (for context window); used if implementing truncation later
        self.MAX_CONTEXT_TOKENS = 32000
        self.RESERVED_FOR_RESPONSE = 1024
        self.MAX_TOKENS = 32000
        self.RESERVED_TOKENS = 1024

    def initialize(self, tokenizer_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load CSV data, create QueryProcessor, optionally load tokenizer.
        Must be called once before process_query; frontend typically calls this on startup.
        """
        try:
            if tokenizer_path:
                self._setup_tokenizer(tokenizer_path)

            df_map_list, pf_map_list = self.data_processor.load_csv_data()

            self.query_processor = QueryProcessor(df_map_list, pf_map_list)

            self.initialized = True

            return {
                "status": "success",
                "message": "NetTune AI backend initialized successfully",
                "data_loaded": {
                    "dimensioning_records": len(df_map_list),
                    "pod_flavor_records": len(pf_map_list)
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to initialize backend: {str(e)}"
            }
    
    def _setup_tokenizer(self, tokenizer_path: str) -> bool:
        """Load HuggingFace tokenizer from path for approximate token counting (e.g. Qwen)."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
            return True
        except Exception as e:
            logging.warning(f"Could not load tokenizer from {tokenizer_path}: {e}")
            return False

    def num_tokens(self, text: str) -> int:
        """Return token count for text if tokenizer is loaded; otherwise 0."""
        if self.tokenizer:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        return 0
    
    def route_query(self, query: str) -> str:
        """
        Decide which data source to use: 'dimensioning', 'pod_flavors', or (caller
        may still use LLM for 'pod placement' or fallback). Keyword-based: 'dimensioning'
        -> dimensioning DB; 'resources' -> pod_flavors (expects df_result from prior turn).
        """
        dfdb_keywords = ["dimensioning"]
        pfdb_keywords = ["resources"]

        query_lower = query.lower()

        if any(keyword in query_lower for keyword in dfdb_keywords):
            return "dimensioning"
        elif any(keyword in query_lower for keyword in pfdb_keywords):
            return "pod_flavors"
        else:
            return "dimensioning"

    def process_query(self, question: str, qa_history: List[Tuple[str, str]], df_result: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry: route question, retrieve or generate answer, return standardized dict.

        Args:
            question: User's current question.
            qa_history: List of (user_msg, assistant_msg) for conversation context.
            df_result: Parsed result from a previous dimensioning query (pods list etc.); needed for 'resources' flow.

        Returns:
            Dict with status, response, context_source, token_count, new_df_result (if applicable).
        """
        if not self.initialized:
            return {
                "status": "error",
                "message": "Backend not initialized"
            }

        try:
            retrieved_context = ""
            context_source = ""
            is_direct = False
            preprocess_data = False
            new_df_result = None

            chosendb = self.route_query(question)

            # --- Branch 1: Dimensioning lookup (no prior df_result) ---
            if df_result is None and chosendb == "dimensioning":
                context_source = "📚 Dimensioning Database"
                dimension_flavor_context = self.query_processor.extract_documents_from_query(
                    self.data_processor.df_map_list, question
                )

                retrieved_context = self.response_processor.dict_to_context(dimension_flavor_context) if dimension_flavor_context else ""
                if retrieved_context == "":
                    raise Exception("no such context document with given fields is available")
                preprocess_data = True
                new_df_result = self.response_processor.preprocess_df_data(retrieved_context)
                is_direct = True

            # --- Branch 2: Pod flavor lookup using pods from previous dimensioning result ---
            elif chosendb == "pod_flavors" and df_result:
                context_source = "🔧 Pod Flavors Database"
                retrieved_context = self._extract_pod_flavor_info(df_result)
                if retrieved_context == "":
                    raise Exception("no such context document with given fields is available")
                is_direct = True

            # --- Branch 3: Pod placement -> DR rules file + LLM ---
            elif "pod placement" in question:
                context_source = "⚠️ DR Rules!" + " 🤖 LLM Response"
                retrieved_context = self._load_dr_rules()
                if retrieved_context == "":
                    raise Exception("no such context document with given fields is available")
                retrieved_context = self._generate_llm_response(question, qa_history, retrieved_context)
                if new_df_result:
                    preprocess_data = True

            # --- Branch 4: General question -> LLM only (no structured DB) ---
            else:
                context_source = "🤖 LLM Response"
                retrieved_context = self._generate_llm_response(question, qa_history, retrieved_context)
                if new_df_result:
                    preprocess_data = True

            token_count = self.num_tokens(f"{question} {retrieved_context}")
            
            return {
                "status": "success",
                "response": retrieved_context,
                "context_source": context_source,
                "is_direct": is_direct,
                "preprocess_data": preprocess_data,
                "new_df_result": new_df_result,
                "token_count": token_count
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing query: {str(e)}"
            }
    
    def _extract_pod_flavor_info(self, df_result: Dict) -> str:
        """
        For each pod in df_result['pods'], look up matching row(s) in pod flavors DB
        and return a single formatted context string with all resource details (vCPU, memory, etc.).
        """
        res = []
        for pod in df_result['pods']:
            query = f"Pod type={pod['pod_name']},Pod flavor={pod['pod_flavor']}"
            extracted_documents = self.query_processor.extract_documents_from_query(
                self.data_processor.pf_map_list, query
            )
            res.extend(extracted_documents)

        return self.response_processor.dict_to_context(res) + "\n"

    def _load_dr_rules(self) -> str:
        """Load vDU deployment rules (e.g. capacity, placement) from JSON file for LLM context."""
        try:
            with open("vdu_dr_rules.json", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "DR rules file not found"

    def _generate_llm_response(self, question: str, qa_history: List[Tuple[str, str]], retrieved_context: str) -> str:
        """
        Build system + context + history + question, call Gauss LLM, return reply text.
        Strips any leading </think>... so the user sees only the answer.
        """
        chat_history = "\n".join([f"Q: {q}\nA: {a}" for q, a in qa_history])
        prompt_template_text= """<s>
[INST]
You are a Network pod placement assistant, who can generate the answer for the given Question.
If you don't know the answer, say I don't know.
Don't try to make up an answer.
Make sure to answer in crisp manner.
Please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user.

Do Not hallucinate.
Answer in English language only.
Do not repeat the question. 
If there are multiple answers, give all of them.
Take your time and go through each statement line by line.

You already have everything you need even without internet connection.

If you need more information from user, ask them to be more specific.
Do not give confusing answers.
If you're not sure, say I don't know.
Always assist with care, respect, and truth. Respond with utmost utility yet securely. Avoid harmful, unethical, prejudiced, or negative content. Ensure replies promote fairness and positivity.
[/INST]
[INST]
Give short and crisp answer.
Don't give additional information.
[/INST]
</s>"""
        
        contents = [

            f'''CONTEXT INFORMATION:
            {retrieved_context}
            
            Use this context to inform your responses, but prioritize the conversation history for maintaining consistency.''',
            
            f'''CONVERSATION HISTORY (PRIORITY - Use this to maintain context and consistency):
            {chat_history}
            
            IMPORTANT: Base your responses primarily on this conversation history. Maintain continuity with previous discussions.''',
           
            f'''CURRENT QUESTION:
            {question}
            
            INSTRUCTIONS:
            1. Answer based PRIMARILY on the conversation history above
            2. Use the context information to supplement your knowledge
            # 3. Use examples ONLY for formatting/style reference, NOT for content
            4. Provide a concise, relevant answer
            5. If the question relates to previous conversation, reference that history directly'''
        ]   

        response = self.llm._call(contents, prompt_template_text, stop=None)

        # Remove </think>... wrapper if model returned one
        response = response.split("</think>", 1)[1].strip() if "</think>" in response else response

        return response

    def get_status(self) -> Dict[str, Any]:
        """Return initialization state, tokenizer availability, and record counts for each DB."""
        return {
            "initialized": self.initialized,
            "tokenizer_available": self.tokenizer is not None,
            "data_records": {
                "dimensioning": len(self.data_processor.df_map_list) if self.data_processor.df_map_list else 0,
                "pod_flavors": len(self.data_processor.pf_map_list) if self.data_processor.pf_map_list else 0
            }
        }
    
    def reset_session(self) -> Dict[str, str]:
        """Called when user starts a new chat; backend does not keep conversation state itself."""
        return {
            "status": "success",
            "message": "Session reset successfully"
        }


# -----------------------------------------------------------------------------
# Singleton backend - frontend imports get_backend() and uses one shared instance
# -----------------------------------------------------------------------------

backend_instance = None


def get_backend() -> NetTuneBackend:
    """Return the global NetTuneBackend instance, creating it on first call (singleton)."""
    global backend_instance
    if backend_instance is None:
        backend_instance = NetTuneBackend()
    return backend_instance