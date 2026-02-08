#!/usr/bin/env python3
"""
NetTune AI Backend - Pod Placement Assistant

This module provides the main backend service for the NetTune AI Pod Placement Assistant.
It handles data processing, query routing, and orchestrates the validation of pod deployments.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set

import pandas as pd

from deployment_validator import DeploymentValidator
from response_generator import ResponseGenerator
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, FeatureFlags, PodType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """Handles data loading and preprocessing from CSV files."""
    
    DIMENSIONING_FIELDS = [
        'Operator', 'Network Function', 'Dimensioning Flavor', 'Package',
        'DPP', 'DIP', 'DMP', 'CMP', 'PMP', 'RMP', 'IPP'
    ]
    
    POD_FLAVOR_FIELDS = [
        'Pod type', 'Pod flavor', 'vCPU Request (vCore)', 'vCPU Limit (vCore)',
        'vMemory (GB)', 'Hugepage (GB)', 'Persistent Volume (GB)'
    ]
    
    def __init__(self):
        self.df_map_list: List[Dict] = []
        self.pf_map_list: List[Dict] = []
    
    def load_csv_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Load and preprocess CSV data from files."""
        try:
            dimensioning_df = pd.read_csv("dimension_flavor_25A_25B_26A.csv")
            pod_flavor_df = pd.read_csv("pod_flavors_25A_25B_EU_US.csv")
        except FileNotFoundError as e:
            logger.error(f"Required CSV files not found: {e}")
            raise FileNotFoundError(f"Required CSV files not found: {e}")

        self.df_map_list = self._process_dataframe(dimensioning_df, self.DIMENSIONING_FIELDS)
        self.pf_map_list = self._process_dataframe(pod_flavor_df, self.POD_FLAVOR_FIELDS)

        logger.info(f"Loaded {len(self.df_map_list)} dimensioning records and {len(self.pf_map_list)} pod flavor records")
        return self.df_map_list, self.pf_map_list
    
    def _process_dataframe(self, df: pd.DataFrame, fields: List[str]) -> List[Dict]:
        """Process dataframe and return list of dictionaries with specified fields."""
        result = []
        for _, row in df.iterrows():
            map_data = {field: row[field] for field in fields if field in row}
            result.append(map_data)
        return result


class TextMatcher:
    """Handles string similarity calculations and fuzzy matching operations."""
    
    SPELLING_VARIATIONS = {
        'flavour': 'flavor',
        'colour': 'color'
    }
    
    @staticmethod
    def normalize_string(text: str) -> str:
        """Normalize string by applying common spelling variations and standardizing format."""
        text = text.lower().strip()
        for variant, standard in TextMatcher.SPELLING_VARIATIONS.items():
            text = text.replace(variant, standard)
        return text
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
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
        """Calculate similarity score between two strings (0.0 to 1.0)."""
        candidate_norm = TextMatcher.normalize_string(candidate)
        target_norm = TextMatcher.normalize_string(target)
        
        if candidate_norm == target_norm:
            return 1.0
        
        distance = TextMatcher.levenshtein_distance(candidate_norm, target_norm)
        max_len = max(len(candidate_norm), len(target_norm))
        
        if max_len == 0:
            return 0.0
        
        edit_similarity = 1.0 - (distance / max_len)
        
        candidate_words = set(candidate_norm.split())
        target_words = set(target_norm.split())
        
        if candidate_words and target_words:
            word_overlap = len(candidate_words.intersection(target_words))
            total_words = len(candidate_words.union(target_words))
            word_similarity = word_overlap / total_words if total_words > 0 else 0
            return 0.6 * edit_similarity + 0.4 * word_similarity
        
        return edit_similarity

    @staticmethod
    def find_best_field_match(candidate_field: str, available_fields: Set[str], min_score: float = 0.5) -> Optional[str]:
        """Find the best matching field from available fields using similarity scoring."""
        best_match = None
        best_score = 0.0
        
        for available_field in available_fields:
            score = TextMatcher.calculate_similarity_score(candidate_field, available_field)
            if score > best_score and score >= min_score:
                best_score = score
                best_match = available_field
        
        return best_match


class QueryProcessor:
    """Processes natural language queries to filter and extract documents."""
    
    CONTEXT_MARKERS = [
        r'just\s+for\s+the\s+context',
        r'these\s+all\s+are',
        r'also\s+called\s+as',
        r'strings\s+like'
    ]
    
    STOP_WORDS = {'for', 'the', 'and', 'or', 'extract', 'information', 'following'}
    INVALID_VALUE_PATTERNS = {'and', 'or', 'the', 'for', 'with'}
    
    def __init__(self, df_map_list: List[Dict], pf_map_list: List[Dict]):
        self.df_map_list = df_map_list
        self.pf_map_list = pf_map_list
    
    @staticmethod
    def clean_query(query: str) -> str:
        """Clean and normalize query text by removing extra characters and whitespace."""
        query = re.sub(r'"{2,}', '"', query)
        query = re.sub(r'[(){}\[\]]', '', query)
        query = re.sub(r'\s+', ' ', query)
        return query.strip()

    @staticmethod
    def separate_context_from_query(query: str) -> str:
        """Separate main query from context information using context markers."""
        earliest_pos = len(query)
        for marker in QueryProcessor.CONTEXT_MARKERS:
            match = re.search(marker, query, re.IGNORECASE)
            if match and match.start() < earliest_pos:
                earliest_pos = match.start()
        
        return query[:earliest_pos].strip() if earliest_pos < len(query) else query

    @staticmethod
    def extract_field_value_pairs(query: str) -> List[Tuple[str, str]]:
        """Extract field-value pairs from query using regex parsing."""
        pairs = []
        i = 0
        
        while i < len(query):
            if query[i] in '=:':
                field_candidate, value, new_i = QueryProcessor._parse_field_value_at_position(query, i)
                if field_candidate and value:
                    pairs.append((field_candidate, value))
                    i = new_i
                    continue
            i += 1
        
        return QueryProcessor._clean_field_value_pairs(pairs)
    
    @staticmethod
    def _parse_field_value_at_position(query: str, pos: int) -> Tuple[Optional[str], Optional[str], int]:
        """Parse field-value pair at given position in query."""
        field_start = pos - 1
        while field_start >= 0 and query[field_start].isspace():
            field_start -= 1
        
        if field_start < 0:
            return None, None, pos
        
        field_end = field_start + 1
        while field_start >= 0 and (query[field_start].isalnum() or query[field_start] in ' _-'):
            field_start -= 1
        field_start += 1
        
        field_candidate = query[field_start:field_end].strip()
        
        value_start = pos + 1
        while value_start < len(query) and query[value_start].isspace():
            value_start += 1
        
        if value_start >= len(query):
            return None, None, pos
        
        if query[value_start] in '"\'':
            quote_char = query[value_start]
            value_end = value_start + 1
            while value_end < len(query) and query[value_end] != quote_char:
                value_end += 1
            if value_end < len(query):
                value = query[value_start + 1:value_end]
                return field_candidate, value, value_end + 1
        
        value_end = value_start
        while (value_end < len(query) and 
               query[value_end] not in ' ,\n\r\t' and
               not (value_end < len(query) - 3 and query[value_end:value_end+4].lower() == ' and')):
            value_end += 1
        
        value = query[value_start:value_end].strip()
        return field_candidate, value, value_end

    @staticmethod
    def _clean_field_value_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Clean and filter field-value pairs by removing stop words and invalid patterns."""
        cleaned_pairs = []
        
        for field_candidate, value in pairs:
            words = field_candidate.split()
            filtered_words = [word for word in words if word.lower() not in QueryProcessor.STOP_WORDS]
            
            if not filtered_words:
                continue
            
            clean_field = ' '.join(filtered_words)
            
            if (len(clean_field.split()) <= 3 and
                len(value) >= 2 and
                not value.startswith('<') and
                not re.match(r'^[0-9]+\.$', value) and
                value.lower() not in QueryProcessor.INVALID_VALUE_PATTERNS):
                cleaned_pairs.append((clean_field, value))
        
        return cleaned_pairs

    def parse_query_for_fields(self, query: str, available_fields: Set[str]) -> Dict[str, List[str]]:
        """Parse query and extract field criteria using fuzzy matching."""
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
        """Find documents that match all field criteria"""
        if not documents or not field_criteria:
            return []

        match_documents = []
        
        for doc in documents:
            if self._document_matches_criteria(doc, field_criteria):
                match_documents.append(doc)
        
        return match_documents
    
    @staticmethod
    def _document_matches_criteria(doc: Dict, field_criteria: Dict[str, List[str]]) -> bool:
        """Check if document matches all field criteria."""
        for field_name, field_values in field_criteria.items():
            if field_name not in doc:
                return False
            
            doc_value = str(doc[field_name]).lower()
            if not any(doc_value == str(value).lower() for value in field_values):
                return False
        
        return True

    def extract_documents_from_query(self, documents: List[Dict], query: str) -> List[Dict]:
        """Extract documents matching query criteria."""
        if not documents:
            return []
            
        available_fields = set(documents[0].keys())
        field_criteria = self.parse_query_for_fields(query, available_fields)
        
        if not field_criteria:
            return []
        
        return self.find_matching_documents(documents, field_criteria)


class ResponseProcessor:
    """Handles response processing and data parsing from LLM outputs."""
    
    DIMENSIONING_FLAVOR_PATTERN = re.compile(r'-?\s*Dimensioning Flavo[u]?r\s*[:\-]\s*(.+)', re.IGNORECASE)
    NETWORK_FUNCTION_PATTERN = re.compile(r'-?\s*Network Function\s*[:\-]\s*(.+)', re.IGNORECASE)
    POD_PATTERN = re.compile(r'-?\s*([A-Za-z]{2,4}):\s*(.+)', re.IGNORECASE)
    
    def preprocess_df_data(self, llm_output: str) -> Dict[str, Any]:
        """Parse LLM output to extract dimensioning data."""
        dimensioning_flavor = "Not Available"
        network_function = "Not Available"
        pods = []

        for line in llm_output.strip().splitlines():
            dimensioning_flavor, network_function, pods = self._process_line_for_dimensioning(
                line, dimensioning_flavor, network_function, pods
            )

        return {
            "dimensioning_flavor": dimensioning_flavor,
            "network_function": network_function,
            "pods": pods
        }
    
    def _process_line_for_dimensioning(self, line: str, dimensioning_flavor: str, network_function: str, pods: List[Dict]) -> Tuple[str, str, List[Dict]]:
        """Process a single line for dimensioning data extraction"""
        flavor_match = self.DIMENSIONING_FLAVOR_PATTERN.match(line)
        if flavor_match:
            dimensioning_flavor = flavor_match.group(1).strip()
            return dimensioning_flavor, network_function, pods
        
        function_match = self.NETWORK_FUNCTION_PATTERN.match(line)
        if function_match:
            network_function = function_match.group(1).strip()
            return dimensioning_flavor, network_function, pods
        
        pod_match = self.POD_PATTERN.match(line)
        if pod_match:
            pod_name = pod_match.group(1).strip()
            pod_flavor = pod_match.group(2).strip()
            
            if 'p' in pod_name.lower() and pod_name.lower() != 'package':
                pods.append({
                    'pod_name': pod_name,
                    'pod_flavor': pod_flavor
                })
        
        return dimensioning_flavor, network_function, pods
    
    def dict_to_context(self, data_dict_list: List[Dict], title: str = "Context Information") -> str:
        """Convert dictionary list to formatted context string."""
        if not data_dict_list:
            return f"## {title}\n\nNo data available."
        
        context_lines = [f"## {title}\n"]
        
        for i, data_dict in enumerate(data_dict_list, 1):
            context_lines.extend(self._format_dict_item(i, data_dict))
        
        return "\n".join(context_lines)
    
    @staticmethod
    def _format_dict_item(index: int, data_dict: Dict) -> List[str]:
        """Format a single dictionary item for context display."""
        lines = [f"### Item {index}"]
        for key, value in data_dict.items():
            formatted_key = key.replace('_', ' ').title()
            lines.append(f"- {formatted_key}: {value}")
        lines.append("")
        return lines


class NetTuneBackend:
    """Main backend service for NetTune AI Pod Placement Assistant."""
    
    POD_TYPE_MAP = {
        'DPP': PodType.DPP, 'DIP': PodType.DIP, 'RMP': PodType.RMP,
        'CMP': PodType.CMP, 'DMP': PodType.DMP, 'PMP': PodType.PMP,
        'IPP': PodType.IPP, 'IIP': PodType.IIP, 'UPP': PodType.UPP,
        'CSP': PodType.CSP, 'VCSR': PodType.VCSR
    }
    
    DEFAULT_VCORES = {
        PodType.DPP: 4.0, PodType.DIP: 2.0, PodType.RMP: 4.0,
        PodType.CMP: 3.0, PodType.DMP: 2.0, PodType.PMP: 2.0,
        PodType.IPP: 3.0
    }
    
    def __init__(self):
        self.data_processor = DataProcessor()
        self.query_processor: Optional[QueryProcessor] = None
        self.response_processor = ResponseProcessor()
        self.initialized = False
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize the backend service by loading data and setting up processors."""
        try:
            df_map_list, pf_map_list = self.data_processor.load_csv_data()
            self.query_processor = QueryProcessor(df_map_list, pf_map_list)
            self.initialized = True
            
            logger.info("NetTune AI backend initialized successfully")
            return {
                "status": "success",
                "message": "NetTune AI backend initialized successfully",
                "data_loaded": {
                    "dimensioning_records": len(df_map_list),
                    "pod_flavor_records": len(pf_map_list)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize backend: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to initialize backend: {str(e)}"
            }
    
    def route_query(self, query: str) -> str:
        """Route query to appropriate database based on keywords."""
        dfdb_keywords = {"dimensioning"}
        pfdb_keywords = {"resources"}
        
        query_words = set(query.lower().split())
        
        if query_words & dfdb_keywords:
            return "dimensioning"
        elif query_words & pfdb_keywords:
            return "pod_flavors"
        else:
            return "dimensioning"
    
    def process_query(self, question: str, qa_history: List[Tuple[str, str]], df_result: Optional[Dict] = None) -> Dict[str, Any]:
        """Process user query and return response."""
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
            
            if df_result is None and chosendb == "dimensioning":
                context_source = "📚 Dimensioning Database"
                dimension_flavor_context = self.query_processor.extract_documents_from_query(
                    self.data_processor.df_map_list, question
                )

                retrieved_context = self.response_processor.dict_to_context(dimension_flavor_context) if dimension_flavor_context else ""
                if not retrieved_context:
                    raise ValueError("No context document found with given fields")
                
                preprocess_data = True
                new_df_result = self.response_processor.preprocess_df_data(retrieved_context)
                is_direct = True
                
            elif chosendb == "pod_flavors" and df_result:
                context_source = "🔧 Pod Flavors Database"
                retrieved_context = self._extract_pod_flavor_info(df_result)
                if not retrieved_context:
                    raise ValueError("No context document found with given fields")
                is_direct = True
                
            elif "pod placement" in question:
                context_source = "⚠️ DR Rules! 🤖 Deterministic Rule Engine"
                print("question:")
                print(question)
                print("qa_history:")
                print(qa_history)
                print("df_result:")
                print(df_result)
                retrieved_context = self._process_pod_placement_query(question, qa_history, df_result)
                
                if not retrieved_context:
                    raise ValueError("No context document found with given fields")
                preprocess_data = False
                
            else:
                retrieved_context = "I can help with dimensioning queries, pod flavor information, and pod placement validation. Please try rephrasing your question."
                context_source = "ℹ️ Help Message"
            
            return {
                "status": "success",
                "response": retrieved_context,
                "context_source": context_source,
                "is_direct": is_direct,
                "preprocess_data": preprocess_data,
                "new_df_result": new_df_result
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "status": "error",
                "message": f"Error processing query: {str(e)}"
            }
    
    def _extract_pod_flavor_info(self, df_result: Dict) -> str:
        """Extract pod flavor information from df_result."""
        res = []
        for pod in df_result['pods']:
            query = f"Pod type={pod['pod_name']},Pod flavor={pod['pod_flavor']}"
            extracted_documents = self.query_processor.extract_documents_from_query(
                self.data_processor.pf_map_list, query
            )
            res.extend(extracted_documents)
        
        return self.response_processor.dict_to_context(res) + "\n"
    
    def _load_dr_rules(self) -> str:
        """Load DR rules from file."""
        try:
            with open("vdu_dr_rules.2.json", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("DR rules file not found")
            return "DR rules file not found"
    
    def _process_pod_placement_query(self, question: str, qa_history: List[Tuple[str, str]], df_result: Optional[Dict] = None) -> str:
        """Process pod placement queries using deterministic rule engine."""
        try:
            deployment_validator = DeploymentValidator()
            response_generator = ResponseGenerator()
            
            deployment_input = self._parse_deployment_query(question, df_result, qa_history)
            if deployment_input is None:
                return "I could not parse the deployment parameters from your query. Please provide operator type, vDU flavor, and server configuration."
            
            validation_result = deployment_validator.validate_deployment(deployment_input, generate_placement_plan=True)
            response = response_generator.generate_validation_response(
                validation_result,
                deployment_input,
                include_detailed_metrics=True
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in deterministic rule engine: {str(e)}")
            return f"Error: Unable to process pod placement query. Please check your input parameters. Details: {str(e)}"
    
    def _parse_deployment_query(self, question: str, df_result: Optional[Dict] = None, qa_history: Optional[List[Tuple[str, str]]] = None) -> Optional[DeploymentInput]:
        """Parse natural language query to extract deployment parameters."""
        try:
            operator_type = self._extract_operator_type(question, qa_history)
            vdu_flavor_name = self._extract_vdu_flavor(question, df_result)
            server_configs = self._extract_server_config(question)
            
            # If no server config provided, check if vCSR deployment is required and use its default config
            if not server_configs:
                feature_flags = self._extract_feature_flags(question)
                if feature_flags.vcsr_deployment_required:
                    # Try to get vCSR default server config from rules
                    try:
                        from rule_models import DRRulesParser
                        rules_parser = DRRulesParser("vdu_dr_rules.2.json")
                        vcsr_config = rules_parser.get_vcsr_default_server_config()
                        if vcsr_config:
                            server_configs = [ServerConfiguration(
                                pcores=vcsr_config["pcores"],
                                vcores=vcsr_config["pcores"] * 2,  # Auto-convert pcores to vcores
                                sockets=vcsr_config["sockets"],
                                pcores_per_socket=vcsr_config.get("pcores_per_socket"),
                                description=vcsr_config.get("description")
                            )]
                    except Exception as e:
                        logger.warning(f"Could not load vCSR default server config: {e}")
                
                # If still no server config, use default
                if not server_configs:
                    server_configs = [ServerConfiguration(pcores=32, vcores=64, sockets=1)]
            
            feature_flags = self._extract_feature_flags(question)
            pod_requirements = self._extract_pod_requirements(df_result, vdu_flavor_name, operator_type, qa_history or [])
            
            return DeploymentInput(
                operator_type=operator_type,
                vdu_flavor_name=vdu_flavor_name,
                pod_requirements=pod_requirements,
                server_configs=server_configs,
                feature_flags=feature_flags
            )
            
        except Exception as e:
            logger.error(f"Error parsing deployment query: {str(e)}")
            return None
    
    def _extract_operator_type(self, question: str, qa_history: Optional[List[Tuple[str, str]]] = None) -> OperatorType:
        """Extract operator type from query, with fallback to qa_history."""
        operator_match = re.search(r'operator\s*[:=]\s*([A-Za-z]+)', question, re.IGNORECASE)
        
        if operator_match:
            operator_str = operator_match.group(1).upper()
            operator_mapping = {
                "VOS": "VOS",
                "VERIZON": "Verizon", 
                "BOOST": "Boost"
            }
            
            if operator_str in operator_mapping:
                try:
                    return OperatorType(operator_mapping[operator_str])
                except ValueError:
                    logger.warning(f"Invalid operator type: {operator_str}")
        
        if qa_history:
            for q, _ in qa_history:
                qa_operator_match = re.search(r'operator\s*[:=]\s*([A-Za-z]+)', q, re.IGNORECASE)
                if qa_operator_match:
                    qa_operator_str = qa_operator_match.group(1).upper()
                    operator_mapping = {
                        "VOS": "VOS",
                        "VERIZON": "Verizon", 
                        "BOOST": "Boost"
                    }
                    
                    if qa_operator_str in operator_mapping:
                        try:
                            return OperatorType(operator_mapping[qa_operator_str])
                        except ValueError:
                            logger.warning(f"Invalid operator type in qa_history: {qa_operator_str}")
        
        return OperatorType.VOS
    
    def _extract_vdu_flavor(self, question: str, df_result: Optional[Dict]) -> str:
        """Extract vDU flavor from query or df_result."""
        if df_result and df_result.get('dimensioning_flavor'):
            return df_result['dimensioning_flavor']
        
        flavor_match = re.search(r'(?:flavor|flavour)\s*[:=]\s*([A-Za-z0-9\-]+)', question, re.IGNORECASE)
        return flavor_match.group(1) if flavor_match else "medium-regular-spr-t23"
    
    def _extract_feature_flags(self, question: str) -> FeatureFlags:
        """Extract feature flags from query."""
        flag_patterns = {
            'ha_enabled': (r'ha_enabled\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled']),
            'in_service_upgrade': (r'(?:in.service|upgrade)\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled']),
            'vdu_ru_switch_connection': (r'switch\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled']),
            'directx2_required': (r'DirectX2?\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled']),
            'vcu_deployment_required': (r'vcu_deployment_required\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled']),
            'vcsr_deployment_required': (r'vcsr_deployment_required\s*[:=]\s*(true|false|yes|no|enabled|disabled)', ['true', 'yes', 'enabled'])
        }
        
        flags = {}
        for flag_name, (pattern, true_values) in flag_patterns.items():
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                flags[flag_name] = match.group(1).lower() in true_values
            else:
                # Try alternative patterns for the specific format in the user's query
                if flag_name == 'ha_enabled' and '"ha_enabled"=true' in question:
                    flags[flag_name] = True
                if flag_name == 'vcu_deployment_required' and '"vcu_deployment_required"=true' in question:
                    flags[flag_name] = True
                if flag_name == 'vcsr_deployment_required' and '"vcsr_deployment_required"=true' in question:
                    flags[flag_name] = True
                if flag_name not in flags:
                    flags[flag_name] = False
        
        return FeatureFlags(**flags)
    
    def _extract_server_config(self, question: str) -> List[ServerConfiguration]:
        """Extract server configuration from query."""
        patterns = [
            (r'server\s*[:=]\s*pcores\s*[:=]\s*(\d+),\s*vcores\s*[:=]\s*(\d+),\s*sockets\s*[:=]\s*(\d+)', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)), vcores=int(m.group(2)), sockets=int(m.group(3)))]),
            (r'(\d+)\s*server\(s\)\s*\(\s*(\d+)\s*vCores\s*total\)', 
             lambda m: self._create_multi_server_config(int(m.group(1)), int(m.group(2)))),
            (r'number of pCore\s*[:=]\s*(\d+)', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)), vcores=int(m.group(1)) * 2, sockets=1)]),
            (r'server with (\d+)\s*pCores?', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)), vcores=int(m.group(1)) * 2, sockets=1)]),
            (r'server with (\d+)\s*vCores?', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)) // 2, vcores=int(m.group(1)), sockets=1)]),
            (r'number of vCore\s*[:=]\s*(\d+)', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)) // 2, vcores=int(m.group(1)), sockets=1)]),
            (r'vcores\s*[:=]\s*(\d+)', 
             lambda m: [ServerConfiguration(pcores=int(m.group(1)) // 2, vcores=int(m.group(1)), sockets=1)])
        ]
        
        for pattern, config_func in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return config_func(match)
        
        return []
    
    def _create_multi_server_config(self, num_servers: int, total_vcores: int) -> List[ServerConfiguration]:
        """Create configuration for multiple servers with total vCores distributed."""
        vcores_per_server = total_vcores // num_servers
        pcores_per_server = vcores_per_server // 2
        sockets_per_server = 2
        
        return [
            ServerConfiguration(
                pcores=pcores_per_server,
                vcores=vcores_per_server,
                sockets=sockets_per_server,
                pcores_per_socket=pcores_per_server // sockets_per_server
            )
            for _ in range(num_servers)
        ]
    
    def _extract_pod_requirements(self, df_result: Optional[Dict], vdu_flavor_name: str, operator_type: OperatorType, qa_history: List[Tuple[str, str]]) -> List[PodRequirement]:
        """Extract pod requirements from df_result and qa_history using real pod vCore data."""
        pod_requirements = []
        actual_vcore_map = self._parse_vcores_from_qa_history(qa_history)

        if df_result and 'pods' in df_result:
            for pod_info in df_result['pods']:
                pod_name_upper = pod_info.get('pod_name', '').upper()
                
                pod_type = self.POD_TYPE_MAP.get(pod_name_upper)
                if pod_type:
                    vcores = actual_vcore_map.get(pod_name_upper)
                    if vcores is not None:
                        # Special handling for CMP with HA - we'll handle quantity in the validator
                        pod_requirements.append(PodRequirement(pod_type=pod_type, vcores=vcores, quantity=1))
                    else:
                        logger.info(f"Pod {pod_name_upper} has 'nan' vCore value - excluding from calculation")
                        pod_requirements.append(PodRequirement(pod_type=pod_type, vcores=0.0, quantity=1))
        else:
            pod_requirements = self._get_default_pod_requirements(operator_type, vdu_flavor_name)
        
        return pod_requirements
    
    def _parse_vcores_from_qa_history(self, qa_history: List[Tuple[str, str]]) -> Dict[str, float]:
        """Parse qa_history to extract actual vCore requests for each pod type."""
        vcore_map = {}
        
        if not qa_history:
            logger.warning("qa_history is empty, cannot parse vcores")
            return vcore_map
            
        _, context_text = qa_history[-1]

        pod_section_pattern = re.compile(
            r"### Item \d+\s*- Pod Type:\s*([A-Z]{2,4})\s*(?:.*?)- Vcpu Request \(Vcore\):\s*([\d\.]+)",
            re.IGNORECASE | re.DOTALL
        )
        
        matches = pod_section_pattern.findall(context_text)
        
        for pod_name, vcore_str in matches:
            try:
                vcore_value = float(vcore_str)
                if not (vcore_value != vcore_value):  # NaN check
                    vcore_map[pod_name.upper()] = vcore_value
                else:
                    logger.info(f"Pod {pod_name} has 'nan' vCore value - excluding from calculation")
            except ValueError:
                logger.warning(f"Could not parse vcore value '{vcore_str}' for pod '{pod_name}'.")
        
        return vcore_map

    def _get_default_pod_requirements(self, operator_type: OperatorType, vdu_flavor_name: str) -> List[PodRequirement]:
        """Get default pod requirements based on flavor and operator."""
        pod_requirements = []
        
        mandatory_pods = [
            (PodType.DPP, 38.0),
            (PodType.DIP, 2.0),
            (PodType.RMP, 0.5),
            (PodType.CMP, 0.2),
            (PodType.DMP, 0.2),
            (PodType.PMP, 0.1)
        ]
        
        for pod_type, vcores in mandatory_pods:
            pod_requirements.append(PodRequirement(pod_type=pod_type, vcores=vcores, quantity=1))
        
        if operator_type == OperatorType.VOS:
            pod_requirements.append(PodRequirement(pod_type=PodType.IPP, vcores=4.0, quantity=1))
        
        return pod_requirements
    
    def get_status(self) -> Dict[str, Any]:
        """Get backend status information."""
        return {
            "initialized": self.initialized,
            "data_records": {
                "dimensioning": len(self.data_processor.df_map_list) if self.data_processor.df_map_list else 0,
                "pod_flavors": len(self.data_processor.pf_map_list) if self.data_processor.pf_map_list else 0
            }
        }
    
    def reset_session(self) -> Dict[str, str]:
        """Reset session data."""
        logger.info("Session reset successfully")
        return {
            "status": "success",
            "message": "Session reset successfully"
        }


# Global backend instance
_backend_instance: Optional[NetTuneBackend] = None


def get_backend() -> NetTuneBackend:
    """Get or create backend instance (singleton pattern)."""
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = NetTuneBackend()
    return _backend_instance
