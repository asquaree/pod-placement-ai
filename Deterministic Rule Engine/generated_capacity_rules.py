"""
Generated capacity validation functions based on DR rules C1-C4
Auto-generated from vdu_dr_rules.json - DO NOT EDIT MANUALLY
"""
from typing import List, Dict, Tuple, Optional
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, FeatureFlags, PodType
)


def validate_capacity_rule_c1(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule C1: Server Capacity Formula
    Total server capacity: Sum of pod vcores ≤ (Total vcores) - (CaaS vcores) - (Shared vcores)
    """
    violated_rules = []
    
    for server_idx, server_config in enumerate(deployment_input.server_configs):
        # Calculate total vcore requests for ALL pods (not just placed ones) - same as LLM logic
        total_pod_vcores = sum(pod.vcores * pod.quantity for pod in deployment_input.pod_requirements)
        
        # Calculate available vcores for this server (same as LLM logic)
        total_vcores = server_config.vcores
        caas_vcores = get_caas_cores_per_socket(deployment_input.operator_type) * server_config.sockets
        shared_vcores = get_shared_cores_per_socket(deployment_input.operator_type) * server_config.sockets
        
        available_vcores = total_vcores - caas_vcores - shared_vcores
        
        if total_pod_vcores > available_vcores:
            violated_rules.append(
                f"C1: Server {server_idx} capacity exceeded: "
                f"Total vcores required {total_pod_vcores} > available {available_vcores} "
                f"(Total: {total_vcores} - CaaS: {caas_vcores} - Shared: {shared_vcores} = Available: {available_vcores})"
            )
    
    success = len(violated_rules) == 0
    message = "Capacity validation passed" if success else "Capacity validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_capacity_rule_c2(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule C2: Core Conversion
    Total vcores = Physical cores × 2
    Apply capacity check per socket independently
    """
    violated_rules = []
    
    for server_idx, server_config in enumerate(deployment_input.server_configs):
        # Verify core conversion formula
        expected_vcores = server_config.pcores * 2
        if server_config.vcores != expected_vcores:
            violated_rules.append(
                f"C2: Server {server_idx} core conversion error: "
                f"{server_config.vcores} vcores ≠ {server_config.pcores} pcores × 2"
            )
        
        # Verify multi-socket configuration
        if server_config.sockets > 1:
            if server_config.pcores_per_socket is None:
                violated_rules.append(
                    f"C2: Server {server_idx} missing pcores_per_socket for multi-socket config"
                )
            else:
                expected_pcores_per_socket = server_config.pcores // server_config.sockets
                if server_config.pcores_per_socket != expected_pcores_per_socket:
                    violated_rules.append(
                        f"C2: Server {server_idx} socket core distribution error: "
                        f"{server_config.pcores_per_socket} ≠ {expected_pcores_per_socket} pcores per socket"
                    )
    
    success = len(violated_rules) == 0
    message = "Core conversion validation passed" if success else "Core conversion validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def get_caas_cores_per_socket(operator_type: OperatorType) -> int:
    """
    Rule C3: CaaS Core Allocation per server/socket
    """
    caas_allocations = {
        OperatorType.VOS: 4,
        OperatorType.VERIZON: 4,
        OperatorType.BOOST: 0  # Incomplete rules
    }
    
    return caas_allocations.get(operator_type, 0)


def get_shared_cores_per_socket(operator_type: OperatorType) -> float:
    """
    Rule C4: Shared Core Allocation per server/socket
    """
    # Global minimum
    global_minimum = 1.0
    
    # Operator-specific allocations
    operator_specific = {
        OperatorType.VOS: 2.0,  # PTP(0.3) + PaaS(0.8) + other(0.9) = 2.0 total
        OperatorType.VERIZON: 1.0,  # Global minimum applies
        OperatorType.BOOST: global_minimum  # Incomplete rules, use minimum
    }
    
    return operator_specific.get(operator_type, global_minimum)


def validate_capacity_rule_c3(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule C3: CaaS Core Allocation validation
    Verify CaaS cores are correctly allocated per server/socket
    """
    violated_rules = []
    
    caas_cores = get_caas_cores_per_socket(deployment_input.operator_type)
    
    if deployment_input.operator_type == OperatorType.BOOST:
        violated_rules.append("C3: Boost operator CaaS rules are incomplete")
    
    # This is mostly informational - actual validation happens in C1
    success = len(violated_rules) == 0
    message = f"CaaS allocation: {caas_cores} vcores per socket" if success else "CaaS allocation validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_capacity_rule_c4(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule C4: Shared Core Allocation validation
    Verify shared cores are correctly allocated per server/socket
    """
    violated_rules = []
    
    shared_cores = get_shared_cores_per_socket(deployment_input.operator_type)
    
    # Validate minimum requirement
    if shared_cores < 1.0:
        violated_rules.append(
            f"C4: Shared cores {shared_cores} below global minimum of 1.0"
        )
    
    # VOS specific validation
    if deployment_input.operator_type == OperatorType.VOS:
        if shared_cores != 2.0:
            violated_rules.append(
                f"C4: VOS operator should have 2.0 shared cores, got {shared_cores}"
            )
    
    success = len(violated_rules) == 0
    message = f"Shared core allocation: {shared_cores} vcores per socket" if success else "Shared core allocation validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_all_capacity_rules(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Validate all capacity rules (C1-C4)
    """
    all_violated_rules = []
    all_messages = []
    
    # Rule C2: Core conversion validation
    c2_result = validate_capacity_rule_c2(deployment_input)
    if not c2_result.success:
        all_violated_rules.extend(c2_result.violated_rules)
    all_messages.append(c2_result.message)
    
    # Rule C3: CaaS allocation validation  
    c3_result = validate_capacity_rule_c3(deployment_input)
    if not c3_result.success:
        all_violated_rules.extend(c3_result.violated_rules)
    all_messages.append(c3_result.message)
    
    # Rule C4: Shared core allocation validation
    c4_result = validate_capacity_rule_c4(deployment_input)
    if not c4_result.success:
        all_violated_rules.extend(c4_result.violated_rules)
    all_messages.append(c4_result.message)
    
    # Rule C1: Overall capacity validation (depends on C2, C3, C4)
    c1_result = validate_capacity_rule_c1(deployment_input, socket_assignments)
    if not c1_result.success:
        all_violated_rules.extend(c1_result.violated_rules)
    all_messages.append(c1_result.message)
    
    success = len(all_violated_rules) == 0
    combined_message = " | ".join(all_messages)
    
    return ValidationResult(
        success=success,
        message=combined_message,
        violated_rules=all_violated_rules
    )


def calculate_socket_capacity(
    server_config: ServerConfiguration,
    socket_idx: int,
    operator_type: OperatorType
) -> Dict[str, float]:
    """
    Calculate capacity details for a specific socket
    Returns dict with total, caas, shared, and available vcores
    """
    vcores_per_socket = server_config.vcores // server_config.sockets
    caas_vcores = get_caas_cores_per_socket(operator_type)
    shared_vcores = get_shared_cores_per_socket(operator_type)
    available_vcores = vcores_per_socket - caas_vcores - shared_vcores
    
    return {
        "total_vcores": vcores_per_socket,
        "caas_vcores": caas_vcores,
        "shared_vcores": shared_vcores,
        "available_vcores": available_vcores
    }


def validate_socket_capacity_constraints(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Validate socket-level capacity constraints for all pods
    This pre-validation checks if individual pods can fit on any socket before attempting placement
    """
    violated_rules = []
    
    # For each pod, check if it can fit on ANY socket
    for pod_req in deployment_input.pod_requirements:
        pod_vcores_needed = pod_req.vcores * pod_req.quantity
        can_fit_anywhere = False
        max_socket_capacity = 0
        
        # Check all sockets across all servers
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            for socket_idx in range(server_config.sockets):
                capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
                available_vcores = capacity_info["available_vcores"]
                max_socket_capacity = max(max_socket_capacity, available_vcores)
                
                if pod_vcores_needed <= available_vcores:
                    can_fit_anywhere = True
                    break
            if can_fit_anywhere:
                break
        
        # If pod cannot fit on any socket, report violation
        if not can_fit_anywhere:
            violated_rules.append(
                f"Socket capacity constraint violated: {pod_req.pod_type.value} pod ({pod_vcores_needed} vCores) "
                f"exceeds maximum socket capacity ({max_socket_capacity} vCores) - cannot fit on any socket"
            )
    
    success = len(violated_rules) == 0
    message = "Socket capacity validation passed" if success else "Socket capacity validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_rmp_dpp_co_location_capacity(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Validate RMP-DPP co-location capacity constraints
    Check if there's sufficient socket capacity for both RMP and DPP pods to be co-located
    """
    violated_rules = []
    
    # Skip validation if switch connection is enabled (RMP can be placed anywhere)
    if deployment_input.feature_flags.vdu_ru_switch_connection:
        return ValidationResult(success=True, message="RMP-DPP co-location validation skipped (switch connection enabled)")
    
    # Get RMP and DPP requirements
    rmp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.RMP]
    dpp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.DPP]
    
    if not rmp_requirements or not dpp_requirements:
        return ValidationResult(success=True, message="RMP-DPP co-location validation passed (no RMP or DPP pods)")
    
    total_rmp_vcores = sum(req.vcores * req.quantity for req in rmp_requirements)
    total_dpp_vcores = sum(req.vcores * req.quantity for req in dpp_requirements)
    
    # Check if there's any socket that can accommodate both RMP and DPP together
    can_co_locate = False
    
    for server_idx, server_config in enumerate(deployment_input.server_configs):
        for socket_idx in range(server_config.sockets):
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            
            # Check if both RMP and DPP can fit on this socket together
            combined_vcores = total_rmp_vcores + total_dpp_vcores
            if combined_vcores <= available_vcores:
                can_co_locate = True
                break
        if can_co_locate:
            break
    
    if not can_co_locate:
        violated_rules.append(
            f"RMP-DPP co-location constraint violated: No socket with sufficient capacity for both "
            f"RMP ({total_rmp_vcores} vCores) and DPP ({total_dpp_vcores} vCores) - "
            f"required combined capacity: {total_rmp_vcores + total_dpp_vcores} vCores"
        )
        
        # Add specific socket capacity information for debugging
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            for socket_idx in range(server_config.sockets):
                capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
                available_vcores = capacity_info["available_vcores"]
                violated_rules.append(
                    f"Server {server_idx} Socket {socket_idx} available capacity: {available_vcores} vCores "
                    f"(needed: {total_rmp_vcores + total_dpp_vcores} vCores)"
                )
    
    success = len(violated_rules) == 0
    message = "RMP-DPP co-location validation passed" if success else "RMP-DPP co-location validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)
