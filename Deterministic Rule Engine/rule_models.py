"""
Data models and parser for vDU Deployment Rules (DR)

This module defines the core data structures and enums used throughout the
NetTune AI Pod Placement system, including deployment inputs, server configurations,
and validation results.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class OperatorType(Enum):
    """Supported operator types for vDU deployments."""
    VOS = "VOS"
    VERIZON = "Verizon" 
    BOOST = "Boost"


class PodType(Enum):
    """Supported pod types for vDU deployments."""
    # Mandatory pods
    DPP = "DPP"
    DIP = "DIP"
    RMP = "RMP"
    CMP = "CMP"
    DMP = "DMP"
    PMP = "PMP"
    
    # Optional pods
    IPP = "IPP"
    IIP = "IIP"
    UPP = "UPP"
    CSP = "CSP"
    VCU = "vCU"
    VCSR = "vCSR"


@dataclass
class ServerConfiguration:
    """Server hardware configuration."""
    pcores: int
    vcores: int
    sockets: int
    pcores_per_socket: Optional[int] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Calculate pcores_per_socket if not provided."""
        if self.pcores_per_socket is None and self.sockets > 1:
            self.pcores_per_socket = self.pcores // self.sockets
    
    def validate(self) -> List[str]:
        """Validate server configuration and return list of validation errors."""
        errors = []
        
        if self.pcores <= 0:
            errors.append("pcores must be positive")
        
        if self.vcores <= 0:
            errors.append("vcores must be positive")
        
        if self.sockets <= 0:
            errors.append("sockets must be positive")
        
        if self.pcores_per_socket and self.pcores_per_socket <= 0:
            errors.append("pcores_per_socket must be positive")
        
        if self.pcores_per_socket and self.pcores_per_socket * self.sockets != self.pcores:
            errors.append("pcores_per_socket * sockets must equal pcores")
        
        return errors


@dataclass
class PodRequirement:
    """Pod resource requirement and placement constraints."""
    pod_type: PodType
    vcores: float
    quantity: int = 1
    socket_affinity: Optional[int] = None  # Specific socket requirement
    anti_affinity: bool = False  # Cannot be on same socket as other pods
    co_location_required: List[PodType] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate pod requirement after initialization."""
        if self.vcores < 0:
            raise ValueError("vcores cannot be negative")
        
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
    
    def validate(self) -> List[str]:
        """Validate pod requirement and return list of validation errors."""
        errors = []
        
        if self.vcores < 0:
            errors.append("vcores cannot be negative")
        
        if self.quantity <= 0:
            errors.append("quantity must be positive")
        
        if self.socket_affinity is not None and self.socket_affinity < 0:
            errors.append("socket_affinity must be non-negative")
        
        return errors


@dataclass
class FeatureFlags:
    """Optional feature flags that affect placement rules."""
    ha_enabled: bool = False
    in_service_upgrade: bool = False
    vdu_ru_switch_connection: bool = False
    directx2_required: bool = False
    vcu_deployment_required: bool = False
    vcsr_deployment_required: bool = False
    
    def validate(self) -> List[str]:
        """Validate feature flags and return list of validation errors."""
        # Feature flags are boolean, so no validation needed
        return []


@dataclass
class DeploymentInput:
    """Input parameters for vDU deployment validation."""
    operator_type: OperatorType
    vdu_flavor_name: str
    pod_requirements: List[PodRequirement]
    server_configs: List[ServerConfiguration]
    feature_flags: FeatureFlags
    number_of_servers: int = field(init=False)
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        self.number_of_servers = len(self.server_configs)
    
    def validate(self) -> List[str]:
        """Validate deployment input and return list of validation errors."""
        errors = []
        
        # Validate operator type
        if not isinstance(self.operator_type, OperatorType):
            errors.append("operator_type must be a valid OperatorType enum")
        
        # Validate vDU flavor name
        if not self.vdu_flavor_name or not self.vdu_flavor_name.strip():
            errors.append("vdu_flavor_name cannot be empty")
        
        # Validate server configurations
        if not self.server_configs:
            errors.append("At least one server configuration is required")
        else:
            for i, server_config in enumerate(self.server_configs):
                server_errors = server_config.validate()
                for error in server_errors:
                    errors.append(f"Server {i}: {error}")
        
        # Validate pod requirements
        if not self.pod_requirements:
            errors.append("At least one pod requirement is required")
        else:
            for i, pod_req in enumerate(self.pod_requirements):
                pod_errors = pod_req.validate()
                for error in pod_errors:
                    errors.append(f"Pod {i}: {error}")
        
        # Validate feature flags
        feature_errors = self.feature_flags.validate()
        for error in feature_errors:
            errors.append(f"Feature flags: {error}")
        
        return errors


@dataclass
class ValidationResult:
    """Result of deployment validation."""
    success: bool
    message: str
    violated_rules: List[str] = field(default_factory=list)
    placement_plan: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate validation result after initialization."""
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        
        if not self.message or not self.message.strip():
            raise ValueError("message cannot be empty")
        
        if not isinstance(self.violated_rules, list):
            raise ValueError("violated_rules must be a list")
        
        if self.placement_plan is not None and not isinstance(self.placement_plan, dict):
            raise ValueError("placement_plan must be a dictionary or None")


class DRRulesParser:
    """Parser for DR rules JSON configuration."""
    
    def __init__(self, rules_file_path: str):
        self.rules_file_path = rules_file_path
        self.rules_data = self._load_rules()
        
    def _load_rules(self) -> Dict[str, Any]:
        """Load rules from JSON file."""
        try:
            with open(self.rules_file_path, 'r', encoding='utf-8') as file:
                rules_data = json.load(file)
                logger.info(f"Successfully loaded DR rules from {self.rules_file_path}")
                return rules_data
        except FileNotFoundError:
            logger.error(f"DR rules file not found: {self.rules_file_path}")
            raise FileNotFoundError(f"DR rules file not found: {self.rules_file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in DR rules file: {e}")
            raise ValueError(f"Invalid JSON in DR rules file: {e}")
        except Exception as e:
            logger.error(f"Error loading DR rules file: {e}")
            raise
    
    def get_server_configurations(self, operator: OperatorType) -> List[ServerConfiguration]:
        """Get supported server configurations for operator."""
        try:
            configs = []
            operator_configs = self.rules_data["server_configuration_rules"]["S1"]["configurations"][operator.value]
            
            for config_data in operator_configs["options"]:
                config = ServerConfiguration(
                    pcores=config_data["pcores"],
                    vcores=config_data["vcores"],
                    sockets=config_data["sockets"],
                    pcores_per_socket=config_data.get("pcores_per_socket"),
                    description=config_data.get("description")
                )
                configs.append(config)
            
            return configs
        except KeyError as e:
            logger.error(f"Server configuration not found for operator {operator.value}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting server configurations: {e}")
            return []
    
    def get_caas_cores(self, operator: OperatorType) -> int:
        """Get CaaS core allocation for operator."""
        try:
            caas_rules = self.rules_data["capacity_calculation_rules"]["C3"]["allocations"]
            return caas_rules.get(operator.value, 0)
        except KeyError as e:
            logger.error(f"CaaS cores not found for operator {operator.value}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error getting CaaS cores: {e}")
            return 0
    
    def get_shared_cores(self, operator: OperatorType) -> float:
        """Get shared core allocation for operator."""
        try:
            shared_rules = self.rules_data["capacity_calculation_rules"]["C4"]
            
            if operator.value in shared_rules["operator_specific"]:
                return shared_rules["operator_specific"][operator.value]["vcores"]
            
            return shared_rules["global_minimum"]
        except KeyError as e:
            logger.error(f"Shared cores not found for operator {operator.value}: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error getting shared cores: {e}")
            return 0.0
    
    def get_mandatory_pods(self) -> List[PodType]:
        """Get list of mandatory pods."""
        try:
            mandatory_pod_names = self.rules_data["core_concepts"]["pod_types"]["mandatory_vdu_pods"]["pods"]
            return [PodType(name) for name in mandatory_pod_names]
        except KeyError as e:
            logger.error(f"Mandatory pods not found in rules: {e}")
            return []
        except ValueError as e:
            logger.error(f"Invalid pod type in mandatory pods: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting mandatory pods: {e}")
            return []
    
    def get_optional_pods(self) -> List[PodType]:
        """Get list of optional pods."""
        try:
            optional_pod_names = self.rules_data["core_concepts"]["pod_types"]["optional_pods"]["pods"]
            return [PodType(name) for name in optional_pod_names]
        except KeyError as e:
            logger.error(f"Optional pods not found in rules: {e}")
            return []
        except ValueError as e:
            logger.error(f"Invalid pod type in optional pods: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting optional pods: {e}")
            return []
    
    def is_special_vdu_flavor(self, operator: OperatorType, flavor_name: str) -> bool:
        """Check if vDU flavor automatically includes IIP."""
        if operator != OperatorType.VOS:
            return False
            
        try:
            special_flavors = self.rules_data["operator_specific_pod_rules"]["O3"]["flavors"]
            return flavor_name in special_flavors
        except KeyError:
            logger.warning(f"Special vDU flavors not found for operator {operator.value}")
            return False
        except Exception as e:
            logger.error(f"Error checking special vDU flavor: {e}")
            return False
    
    def get_vcu_vcores(self, flavor_name: str) -> int:
        """Get vCU vcore requirements based on flavor."""
        try:
            vcu_rules = self.rules_data["operator_specific_pod_rules"]["O2"]["flavor_mapping"]
            
            if flavor_name in vcu_rules:
                return vcu_rules[flavor_name]["vcores"]
            
            return vcu_rules["all_other_flavors"]["vcores"]
        except KeyError:
            logger.warning(f"vCU vcores not found for flavor {flavor_name}, using default")
            return 15  # Default value
        except Exception as e:
            logger.error(f"Error getting vCU vcores: {e}")
            return 15  # Default value
    
    def get_vcsr_vcores(self, flavor_name: str) -> int:
        """Get vCSR vcore requirements based on flavor."""
        try:
            vcsr_rules = self.rules_data["operator_specific_pod_rules"]["O5"]["flavor"]
            
            if flavor_name in vcsr_rules:
                return vcsr_rules[flavor_name]["vcores"]
            
            # If flavor not found in vCSR rules, vCSR is not supported for this flavor
            return 0
        except KeyError:
            logger.warning(f"vCSR vcores not found for flavor {flavor_name}, vCSR not supported")
            return 0  # vCSR not supported for this flavor
        except Exception as e:
            logger.error(f"Error getting vCSR vcores: {e}")
            return 0  # vCSR not supported
    
    def get_vcsr_default_server_config(self) -> Optional[Dict[str, Any]]:
        """Get default server configuration for vCSR deployment."""
        try:
            vcsr_rules = self.rules_data["operator_specific_pod_rules"]["O5"]
            if "default_server_config" in vcsr_rules:
                return vcsr_rules["default_server_config"]
            return None
        except KeyError:
            logger.warning("vCSR default server config not found")
            return None
        except Exception as e:
            logger.error(f"Error getting vCSR default server config: {e}")
            return None
    
    def get_rules_by_category(self, category: str) -> List[str]:
        """Get rule IDs by category."""
        try:
            return self.rules_data["rule_categories"].get(category, [])
        except KeyError:
            logger.warning(f"Rule category {category} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting rules by category: {e}")
            return []
    
    def get_rules_by_operator(self, operator: OperatorType) -> List[str]:
        """Get rule IDs applicable to specific operator."""
        try:
            return self.rules_data["search_keys"]["by_operator"].get(operator.value, [])
        except KeyError:
            logger.warning(f"Rules for operator {operator.value} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting rules by operator: {e}")
            return []
    
    def get_rules_by_feature(self, feature: str) -> List[str]:
        """Get rule IDs applicable to specific feature."""
        try:
            return self.rules_data["search_keys"]["by_feature"].get(feature, [])
        except KeyError:
            logger.warning(f"Rules for feature {feature} not found")
            return []
        except Exception as e:
            logger.error(f"Error getting rules by feature: {e}")
            return []
    
    def validate_rules_data(self) -> List[str]:
        """Validate the loaded rules data and return list of validation errors."""
        errors = []
        
        # Check required top-level sections
        required_sections = [
            "core_concepts",
            "capacity_calculation_rules", 
            "placement_rules",
            "operator_specific_pod_rules",
            "server_configuration_rules",
            "rule_categories",
            "search_keys"
        ]
        
        for section in required_sections:
            if section not in self.rules_data:
                errors.append(f"Missing required section: {section}")
        
        # Validate core concepts
        if "core_concepts" in self.rules_data:
            core_concepts = self.rules_data["core_concepts"]
            if "pod_types" not in core_concepts:
                errors.append("Missing pod_types in core_concepts")
            elif "mandatory_vdu_pods" not in core_concepts["pod_types"]:
                errors.append("Missing mandatory_vdu_pods in pod_types")
            elif "pods" not in core_concepts["pod_types"]["mandatory_vdu_pods"]:
                errors.append("Missing pods list in mandatory_vdu_pods")
        
        # Validate capacity calculation rules
        if "capacity_calculation_rules" in self.rules_data:
            capacity_rules = self.rules_data["capacity_calculation_rules"]
            required_capacity_rules = ["C1", "C2", "C3", "C4"]
            for rule in required_capacity_rules:
                if rule not in capacity_rules:
                    errors.append(f"Missing capacity rule: {rule}")
        
        # Validate server configuration rules
        if "server_configuration_rules" in self.rules_data:
            server_rules = self.rules_data["server_configuration_rules"]
            if "S1" not in server_rules:
                errors.append("Missing server configuration rule S1")
            elif "configurations" not in server_rules["S1"]:
                errors.append("Missing configurations in server configuration rule S1")
            else:
                for operator in OperatorType:
                    if operator.value not in server_rules["S1"]["configurations"]:
                        errors.append(f"Missing server configurations for operator: {operator.value}")
        
        return errors
    
    def get_rule_summary(self) -> Dict[str, Any]:
        """Get a summary of all rules in the configuration."""
        try:
            summary = {
                "total_rules": 0,
                "categories": {},
                "operators": {},
                "features": {},
                "mandatory_pods": [],
                "optional_pods": []
            }
            
            # Count rules by category
            if "rule_categories" in self.rules_data:
                for category, rules in self.rules_data["rule_categories"].items():
                    summary["categories"][category] = len(rules)
                    summary["total_rules"] += len(rules)
            
            # Count rules by operator
            if "search_keys" in self.rules_data and "by_operator" in self.rules_data["search_keys"]:
                for operator, rules in self.rules_data["search_keys"]["by_operator"].items():
                    summary["operators"][operator] = len(rules)
            
            # Count rules by feature
            if "search_keys" in self.rules_data and "by_feature" in self.rules_data["search_keys"]:
                for feature, rules in self.rules_data["search_keys"]["by_feature"].items():
                    summary["features"][feature] = len(rules)
            
            # Get pod lists
            summary["mandatory_pods"] = [pod.value for pod in self.get_mandatory_pods()]
            summary["optional_pods"] = [pod.value for pod in self.get_optional_pods()]
            
            return summary
        except Exception as e:
            logger.error(f"Error generating rule summary: {e}")
            return {}
