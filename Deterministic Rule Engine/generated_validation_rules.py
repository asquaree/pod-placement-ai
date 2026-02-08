"""
Generated validation functions based on DR rules V1-V3
Auto-generated from vdu_dr_rules.json - DO NOT EDIT MANUALLY
"""
from typing import List, Dict, Set, Optional, Tuple
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, PodType, FeatureFlags
)


def validate_validation_rule_v1(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule V1: Success Conditions
    Return 'Success' if ALL rules are satisfied
    This is a meta-rule that depends on all other rules passing
    """
    # This rule is implemented in the main validator by checking all other rules
    # For individual validation, we just return a placeholder result
    return ValidationResult(
        success=True,
        message="V1: Success condition depends on all other rules passing",
        violated_rules=[]
    )


def validate_validation_rule_v2(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule V2: Failure Conditions
    Return 'Failure' with specific reason if any rule violation occurs
    Example failures:
    - Insufficient server core capacity
    - Anti-affinity constraint violated
    - Required pod co-location cannot be satisfied
    """
    # This rule collects and categorizes specific failure conditions
    failure_categories = {
        "capacity": [],
        "anti_affinity": [],
        "co_location": [],
        "mandatory_pods": [],
        "operator_specific": [],
        "server_config": []
    }
    
    # Check for common failure patterns based on socket assignments
    if socket_assignments:
        for socket_key, assigned_pods in socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            
            # Check capacity constraints
            server_config = deployment_input.server_configs[server_idx]
            vcores_per_socket = server_config.vcores // server_config.sockets
            
            total_pod_vcores = sum(pod.vcores * pod.quantity for pod in assigned_pods)
            
            # Estimate available vcores (simplified check)
            estimated_available = vcores_per_socket - 6  # Rough estimate of CaaS + shared cores
            
            if total_pod_vcores > estimated_available:
                failure_categories["capacity"].append(
                    f"Socket {server_idx}.{socket_idx}: Insufficient capacity "
                    f"({total_pod_vcores} > ~{estimated_available})"
                )
            
            # Check anti-affinity violations
            pod_counts = {}
            for pod in assigned_pods:
                pod_type = pod.pod_type
                pod_counts[pod_type] = pod_counts.get(pod_type, 0) + pod.quantity
            
            # DPP anti-affinity check
            if (deployment_input.feature_flags.in_service_upgrade and 
                pod_counts.get(PodType.DPP, 0) > 1):
                failure_categories["anti_affinity"].append(
                    f"Socket {server_idx}.{socket_idx}: DPP anti-affinity violated "
                    f"({pod_counts[PodType.DPP]} DPP pods on same socket)"
                )
            
            # CMP anti-affinity check
            if (deployment_input.feature_flags.ha_enabled and 
                pod_counts.get(PodType.CMP, 0) > 1):
                failure_categories["anti_affinity"].append(
                    f"Socket {server_idx}.{socket_idx}: CMP anti-affinity violated "
                    f"({pod_counts[PodType.CMP]} CMP pods on same socket)"
                )
    
    # Check for mandatory pod violations
    mandatory_pods = {PodType.DPP, PodType.DIP, PodType.RMP, PodType.CMP, PodType.DMP, PodType.PMP}
    provided_pods = set()
    for pod_req in deployment_input.pod_requirements:
        provided_pods.add(pod_req.pod_type)
    
    missing_mandatory = mandatory_pods - provided_pods
    if missing_mandatory:
        failure_categories["mandatory_pods"].append(
            f"Missing mandatory pods: {', '.join([pod.value for pod in missing_mandatory])}"
        )
    
    # Check operator-specific violations
    if deployment_input.operator_type == OperatorType.VOS:
        # VOS requires IPP
        if PodType.IPP not in provided_pods:
            failure_categories["operator_specific"].append("VOS operator requires IPP pod")
        
        # DirectX2 co-location check
        if deployment_input.feature_flags.directx2_required:
            directx2_pods = {PodType.IPP, PodType.CSP, PodType.UPP}
            missing_directx2 = directx2_pods - provided_pods
            if missing_directx2:
                failure_categories["co_location"].append(
                    f"DirectX2 missing mandatory pods: {', '.join([pod.value for pod in missing_directx2])}"
                )
    
    # Check server configuration compatibility
    if deployment_input.server_configs:
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            # Validate core conversion
            expected_vcores = server_config.pcores * 2
            if server_config.vcores != expected_vcores:
                failure_categories["server_config"].append(
                    f"Server {server_idx}: Core conversion error "
                    f"({server_config.vcores} vcores ≠ {server_config.pcores} pcores × 2)"
                )
    
    # Convert failure categories to violated rules
    violated_rules = []
    for category, failures in failure_categories.items():
        if failures:
            violated_rules.extend([f"V2:{category.upper()} - {failure}" for failure in failures])
    
    success = len(violated_rules) == 0
    message = "V2: No failure conditions detected" if success else "V2: Failure conditions detected"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_validation_rule_v3(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule V3: Input Validation
    Validate that all required input parameters are provided
    Required parameters:
    - Server configuration details
    - Pod vcore requirements
    - Feature flags (HA, in-service upgrade, switch connection, DirectX2)
    - Operator type
    """
    violated_rules = []
    
    # Validate server configuration details
    if not deployment_input.server_configs:
        violated_rules.append("V3: Server configuration details not provided")
    else:
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            if server_config.pcores <= 0:
                violated_rules.append(f"V3: Server {server_idx} has invalid pcores: {server_config.pcores}")
            if server_config.vcores <= 0:
                violated_rules.append(f"V3: Server {server_idx} has invalid vcores: {server_config.vcores}")
            if server_config.sockets not in [1, 2]:
                violated_rules.append(f"V3: Server {server_idx} has invalid socket count: {server_config.sockets}")
    
    # Validate pod vcore requirements
    if not deployment_input.pod_requirements:
        violated_rules.append("V3: Pod vcore requirements not provided")
    else:
        for pod_idx, pod_req in enumerate(deployment_input.pod_requirements):
            # Skip vcore validation for pods with 0.0 vcores (these are typically excluded pods with "nan" values)
            if pod_req.vcores < 0:
                violated_rules.append(f"V3: Pod {pod_idx} ({pod_req.pod_type.value}) has invalid vcores: {pod_req.vcores}")
            if pod_req.quantity <= 0:
                violated_rules.append(f"V3: Pod {pod_idx} ({pod_req.pod_type.value}) has invalid quantity: {pod_req.quantity}")
    
    # Validate feature flags
    feature_flags = deployment_input.feature_flags
    if not isinstance(feature_flags.ha_enabled, bool):
        violated_rules.append("V3: HA feature flag must be boolean")
    if not isinstance(feature_flags.in_service_upgrade, bool):
        violated_rules.append("V3: In-service upgrade feature flag must be boolean")
    if not isinstance(feature_flags.vdu_ru_switch_connection, bool):
        violated_rules.append("V3: Switch connection feature flag must be boolean")
    if not isinstance(feature_flags.directx2_required, bool):
        violated_rules.append("V3: DirectX2 feature flag must be boolean")
    if not isinstance(feature_flags.vcu_deployment_required, bool):
        violated_rules.append("V3: vCU deployment feature flag must be boolean")
    
    # Validate operator type
    if not isinstance(deployment_input.operator_type, OperatorType):
        violated_rules.append("V3: Invalid operator type provided")
    
    # Validate vDU flavor name
    if not deployment_input.vdu_flavor_name or not isinstance(deployment_input.vdu_flavor_name, str):
        violated_rules.append("V3: vDU flavor name not provided or invalid")
    
    # Validate number of servers
    if deployment_input.number_of_servers is not None:
        if deployment_input.number_of_servers <= 0:
            violated_rules.append(f"V3: Invalid number of servers: {deployment_input.number_of_servers}")
        if deployment_input.number_of_servers != len(deployment_input.server_configs):
            violated_rules.append(
                f"V3: Number of servers ({deployment_input.number_of_servers}) "
                f"does not match server configurations count ({len(deployment_input.server_configs)})"
            )
    
    success = len(violated_rules) == 0
    message = "Input validation passed" if success else "Input validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_all_validation_rules(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Validate all validation rules (V1-V3)
    """
    all_violated_rules = []
    all_messages = []
    
    # Rule V3: Input validation (should be done first)
    v3_result = validate_validation_rule_v3(deployment_input)
    if not v3_result.success:
        all_violated_rules.extend(v3_result.violated_rules)
    all_messages.append(v3_result.message)
    
    # If input validation fails, skip other validations
    if not v3_result.success:
        return ValidationResult(
            success=False,
            message=" | ".join(all_messages),
            violated_rules=all_violated_rules
        )
    
    # Rule V2: Failure condition detection
    v2_result = validate_validation_rule_v2(deployment_input, socket_assignments)
    if not v2_result.success:
        all_violated_rules.extend(v2_result.violated_rules)
    all_messages.append(v2_result.message)
    
    # Rule V1: Success condition (meta-rule)
    v1_result = validate_validation_rule_v1(deployment_input, socket_assignments)
    all_messages.append(v1_result.message)
    
    success = len(all_violated_rules) == 0
    combined_message = " | ".join(all_messages)
    
    return ValidationResult(
        success=success,
        message=combined_message,
        violated_rules=all_violated_rules
    )


def categorize_violations(violated_rules: List[str]) -> Dict[str, List[str]]:
    """
    Categorize violated rules by type for better error reporting
    """
    categories = {
        "capacity": [],
        "placement": [],
        "operator_specific": [],
        "validation": [],
        "anti_affinity": [],
        "co_location": [],
        "other": []
    }
    
    for rule in violated_rules:
        rule_lower = rule.lower()
        if any(keyword in rule_lower for keyword in ["c1:", "c2:", "c3:", "c4:", "capacity", "vcores"]):
            categories["capacity"].append(rule)
        elif any(keyword in rule_lower for keyword in ["m1:", "m2:", "m3:", "m4:", "placement"]):
            categories["placement"].append(rule)
        elif any(keyword in rule_lower for keyword in ["o1:", "o2:", "o3:", "o4:", "operator", "vos", "verizon", "boost"]):
            categories["operator_specific"].append(rule)
        elif any(keyword in rule_lower for keyword in ["v1:", "v2:", "v3:", "validation", "input"]):
            categories["validation"].append(rule)
        elif any(keyword in rule_lower for keyword in ["anti-affinity", "anti_affinity"]):
            categories["anti_affinity"].append(rule)
        elif any(keyword in rule_lower for keyword in ["co-location", "co_location"]):
            categories["co_location"].append(rule)
        else:
            categories["other"].append(rule)
    
    return categories


def generate_failure_summary(violated_rules: List[str]) -> str:
    """
    Generate human-readable summary of validation failures
    """
    if not violated_rules:
        return "All validation rules passed successfully"
    
    categories = categorize_violations(violated_rules)
    summary_lines = ["Deployment validation failed with the following issues:"]
    
    for category, rules in categories.items():
        if rules:
            category_name = category.replace("_", " ").title()
            summary_lines.append(f"\n{category_name}:")
            for rule in rules:
                summary_lines.append(f"  - {rule}")
    
    return "\n".join(summary_lines)


def get_required_input_parameters() -> Dict[str, str]:
    """
    Get description of required input parameters for validation
    """
    return {
        "server_configuration": "List of server hardware configurations (pcores, vcores, sockets)",
        "pod_vcore_requirements": "List of pod resource requirements (pod_type, vcores, quantity)",
        "feature_flags": "Feature flags (HA, in-service upgrade, switch connection, DirectX2, vCU deployment)",
        "operator_type": "Network operator (VOS, Verizon, Boost)",
        "vdu_flavor_name": "vDU flavor identifier (e.g., 'medium-regular-spr-t23')",
        "number_of_servers": "Number of servers in deployment (optional, inferred from server_configs)"
    }


def validate_deployment_feasibility(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> Tuple[bool, List[str], Dict[str, any]]:
    """
    Comprehensive deployment feasibility validation
    Returns tuple of (is_feasible, reasons, deployment_metrics)
    """
    # Run all validation rules
    validation_result = validate_all_validation_rules(deployment_input, socket_assignments)
    
    # Calculate deployment metrics
    metrics = calculate_deployment_metrics(deployment_input, socket_assignments)
    
    # Determine feasibility
    is_feasible = validation_result.success
    
    # Generate detailed reasons
    reasons = validation_result.violated_rules
    
    return is_feasible, reasons, metrics


def calculate_deployment_metrics(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> Dict[str, any]:
    """
    Calculate deployment metrics for analysis and reporting
    """
    metrics = {
        "total_servers": len(deployment_input.server_configs),
        "total_sockets": sum(server.sockets for server in deployment_input.server_configs),
        "total_pods": sum(req.quantity for req in deployment_input.pod_requirements),
        "total_vcores_requested": sum(req.vcores * req.quantity for req in deployment_input.pod_requirements),
        "total_vcores_available": sum(server.vcores for server in deployment_input.server_configs),
        "socket_utilization": {},
        "pod_distribution": {}
    }
    
    # Calculate socket utilization
    if socket_assignments:
        for socket_key, assigned_pods in socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            
            server_config = deployment_input.server_configs[server_idx]
            vcores_per_socket = server_config.vcores // server_config.sockets
            
            used_vcores = sum(pod.vcores * pod.quantity for pod in assigned_pods)
            utilization_percent = (used_vcores / vcores_per_socket) * 100 if vcores_per_socket > 0 else 0
            
            metrics["socket_utilization"][socket_key] = {
                "server_idx": server_idx,
                "socket_idx": socket_idx,
                "total_vcores": vcores_per_socket,
                "used_vcores": used_vcores,
                "utilization_percent": utilization_percent,
                "pod_count": len(assigned_pods)
            }
    
    # Calculate pod distribution
    for pod_req in deployment_input.pod_requirements:
        pod_type = pod_req.pod_type.value
        if pod_type not in metrics["pod_distribution"]:
            metrics["pod_distribution"][pod_type] = {
                "total_vcores": 0,
                "total_quantity": 0,
                "instances": []
            }
        
        metrics["pod_distribution"][pod_type]["total_vcores"] += pod_req.vcores * pod_req.quantity
        metrics["pod_distribution"][pod_type]["total_quantity"] += pod_req.quantity
        metrics["pod_distribution"][pod_type]["instances"].append({
            "vcores_per_pod": pod_req.vcores,
            "quantity": pod_req.quantity
        })
    
    # Calculate overall utilization
    if metrics["total_vcores_available"] > 0:
        metrics["overall_utilization_percent"] = (
            metrics["total_vcores_requested"] / metrics["total_vcores_available"]
        ) * 100
    else:
        metrics["overall_utilization_percent"] = 0
    
    return metrics
