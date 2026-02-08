"""
Generated placement validation functions based on DR rules M1-M4
Auto-generated from vdu_dr_rules.json - DO NOT EDIT MANUALLY
"""
from typing import List, Dict, Set, Optional, Tuple
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, PodType, FeatureFlags
)


def validate_placement_rule_m1(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule M1: Basic Mandatory Pods
    Every vDU deployment must include: DPP, DIP, RMP, CMP, DMP, PMP
    Flexible placement: DIP, DMP, PMP
    Constrained placement: DPP, RMP, CMP
    """
    violated_rules = []
    
    # Get all pod types from input requirements
    provided_pods = set()
    for pod_req in deployment_input.pod_requirements:
        provided_pods.add(pod_req.pod_type)
    
    # Define mandatory pods
    mandatory_pods = {PodType.DPP, PodType.DIP, PodType.RMP, PodType.CMP, PodType.DMP, PodType.PMP}
    
    # Check for missing mandatory pods
    missing_pods = mandatory_pods - provided_pods
    if missing_pods:
        violated_rules.append(
            f"M1: Missing mandatory pods: {', '.join([pod.value for pod in missing_pods])}"
        )
    
    # Validate flexible vs constrained placement (informational)
    flexible_pods = {PodType.DIP, PodType.DMP, PodType.PMP}
    constrained_pods = {PodType.DPP, PodType.RMP, PodType.CMP}
    
    success = len(violated_rules) == 0
    message = "Mandatory pods validation passed" if success else "Mandatory pods validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_placement_rule_m2(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule M2: DPP Placement Rules
    Scenarios:
    - default: Exactly 1 DPP per socket
    - with_ha_enabled: More than 1 DPP per socket is allowed
    - with_in_service_upgrade: DPP pods must have anti-affinity (not on same socket)
    """
    violated_rules = []
    
    # Get all DPP pod requirements
    dpp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.DPP]
    if not dpp_requirements:
        violated_rules.append("M2: No DPP pods found in deployment requirements")
        return ValidationResult(success=False, message="DPP placement validation failed", violated_rules=violated_rules)
    
    # Count DPP pods per socket
    dpp_per_socket = {}
    for socket_key, assigned_pods in socket_assignments.items():
        dpp_count = sum(1 for pod in assigned_pods if pod.pod_type == PodType.DPP)
        if dpp_count > 0:
            dpp_per_socket[socket_key] = dpp_count
    
    # Apply rules based on feature flags
    if deployment_input.feature_flags.in_service_upgrade:
        # DPP pods must have anti-affinity (not on same socket)
        for socket_key, dpp_count in dpp_per_socket.items():
            if dpp_count > 1:
                violated_rules.append(
                    f"M2: In-service upgrade enabled - DPP anti-affinity violated: "
                    f"{dpp_count} DPP pods on socket {socket_key}"
                )
    
    elif deployment_input.feature_flags.ha_enabled:
        # More than 1 DPP per socket is allowed (no additional constraints)
        pass  # HA allows multiple DPP pods per socket
    
    else:
        # Default scenario: Exactly 1 DPP per socket
        for socket_key, dpp_count in dpp_per_socket.items():
            if dpp_count != 1:
                violated_rules.append(
                    f"M2: Default scenario - Expected exactly 1 DPP per socket, "
                    f"found {dpp_count} DPP pods on socket {socket_key}"
                )
    
    success = len(violated_rules) == 0
    message = "DPP placement validation passed" if success else "DPP placement validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_placement_rule_m3(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule M3: RMP Placement Rules
    Scenarios:
    - normal: Place same number of RMP pods as DPP pods, each RMP on same socket as its corresponding DPP
    - switch: When vDU-RU switch connection = yes, place exactly 1 RMP for entire vDU on any server/socket
    """
    violated_rules = []
    
    # Get all RMP and DPP pod requirements
    rmp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.RMP]
    dpp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.DPP]
    
    if not dpp_requirements:
        violated_rules.append("M3: No DPP pods found - required for RMP placement")
        return ValidationResult(success=False, message="RMP placement validation failed", violated_rules=violated_rules)
    
    total_dpp_pods = sum(req.quantity for req in dpp_requirements)
    total_rmp_pods = sum(req.quantity for req in rmp_requirements)
    
    if deployment_input.feature_flags.vdu_ru_switch_connection:
        # Switch scenario: Place exactly 1 RMP for entire vDU
        if total_rmp_pods != 1:
            violated_rules.append(
                f"M3: Switch connection enabled - Expected exactly 1 RMP pod, found {total_rmp_pods}"
            )
        
        # RMP can be placed on any server/socket with sufficient capacity (no socket constraints)
        
    else:
        # Normal scenario: Place same number of RMP pods as DPP pods
        if total_rmp_pods != total_dpp_pods:
            violated_rules.append(
                f"M3: Normal scenario - Expected {total_dpp_pods} RMP pods to match DPP pods, "
                f"found {total_rmp_pods} RMP pods"
            )
        
        # Each RMP must be on same socket as its corresponding DPP
        # Check socket assignments for co-location
        dpp_socket_map = {}  # Map DPP index to socket
        rmp_socket_map = {}  # Map RMP index to socket
        
        # Build DPP socket map
        dpp_index = 0
        for socket_key, assigned_pods in socket_assignments.items():
            for pod in assigned_pods:
                if pod.pod_type == PodType.DPP:
                    dpp_socket_map[dpp_index] = socket_key
                    dpp_index += 1
        
        # Build RMP socket map
        rmp_index = 0
        for socket_key, assigned_pods in socket_assignments.items():
            for pod in assigned_pods:
                if pod.pod_type == PodType.RMP:
                    rmp_socket_map[rmp_index] = socket_key
                    rmp_index += 1
        
        # In normal scenario, each RMP should be on the same socket as its corresponding DPP
        mismatched_sockets = []
        for i in range(min(len(dpp_socket_map), len(rmp_socket_map))):
            if dpp_socket_map[i] != rmp_socket_map[i]:
                mismatched_sockets.append(f"RMP{i} on socket {rmp_socket_map[i]} != DPP{i} on socket {dpp_socket_map[i]}")
        
        if mismatched_sockets:
            violated_rules.append(
                f"M3: Normal scenario - RMP-DPP socket mismatches: {', '.join(mismatched_sockets)}"
            )
        
        # Also check if we have the right number of RMPs for the DPPs
        if len(rmp_socket_map) != len(dpp_socket_map):
            violated_rules.append(
                f"M3: Normal scenario - RMP count ({len(rmp_socket_map)}) does not match DPP count ({len(dpp_socket_map)})"
            )
            
            # Add detailed information about unplaced RMPs
            unplaced_rmps = total_rmp_pods - len(rmp_socket_map)
            if unplaced_rmps > 0:
                violated_rules.append(
                    f"M3: {unplaced_rmps} RMP pod(s) could not be placed - likely due to insufficient socket capacity "
                    f"for RMP-DPP co-location or DPP placement failure"
                )
                
                # Check if DPPs were placed (if DPPs aren't placed, RMPs can't be placed either)
                if len(dpp_socket_map) == 0:
                    violated_rules.append(
                        f"M3: No DPP pods were placed - RMP pods cannot be placed without corresponding DPP pods "
                        f"on the same socket (co-location constraint)"
                    )
    
    success = len(violated_rules) == 0
    message = "RMP placement validation passed" if success else "RMP placement validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_rmp_placement_feasibility(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Pre-validate RMP placement feasibility before attempting socket assignment
    This helps identify RMP placement issues early and provide clear violation messages
    """
    violated_rules = []
    
    # Skip validation if switch connection is enabled (RMP can be placed anywhere)
    if deployment_input.feature_flags.vdu_ru_switch_connection:
        return ValidationResult(success=True, message="RMP placement feasibility validation passed (switch connection enabled)")
    
    # Get RMP and DPP requirements
    rmp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.RMP]
    dpp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.DPP]
    
    if not rmp_requirements:
        return ValidationResult(success=True, message="RMP placement feasibility validation passed (no RMP pods)")
    
    if not dpp_requirements:
        violated_rules.append("RMP placement feasibility: No DPP pods found - RMP requires DPP for co-location")
        return ValidationResult(success=False, message="RMP placement feasibility validation failed", violated_rules=violated_rules)
    
    total_rmp_vcores = sum(req.vcores * req.quantity for req in rmp_requirements)
    total_dpp_vcores = sum(req.vcores * req.quantity for req in dpp_requirements)
    
    # Check if there's any socket that can accommodate both RMP and DPP together
    from generated_capacity_rules import calculate_socket_capacity
    
    can_co_locate_anywhere = False
    socket_capacity_details = []
    
    for server_idx, server_config in enumerate(deployment_input.server_configs):
        for socket_idx in range(server_config.sockets):
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            
            # Check if both RMP and DPP can fit on this socket together
            combined_vcores = total_rmp_vcores + total_dpp_vcores
            socket_capacity_details.append(
                f"Server {server_idx} Socket {socket_idx}: {available_vcores} vCores available (need {combined_vcores})"
            )
            
            if combined_vcores <= available_vcores:
                can_co_locate_anywhere = True
                break
        if can_co_locate_anywhere:
            break
    
    if not can_co_locate_anywhere:
        violated_rules.append(
            f"RMP placement feasibility violated: Cannot place RMP pods due to co-location constraint with DPP"
        )
        violated_rules.append(
            f"Root cause: No socket has sufficient capacity for both RMP ({total_rmp_vcores} vCores) "
            f"and DPP ({total_dpp_vcores} vCores) together"
        )
        violated_rules.append(
            f"Required combined capacity: {total_rmp_vcores + total_dpp_vcores} vCores"
        )
        
        # Add socket capacity details for debugging
        violated_rules.extend(socket_capacity_details)
        
        # Check if individual pods exceed socket capacity
        for pod_req in deployment_input.pod_requirements:
            pod_vcores = pod_req.vcores * pod_req.quantity
            max_socket_capacity = 0
            
            for server_config in deployment_input.server_configs:
                for socket_idx in range(server_config.sockets):
                    capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
                    max_socket_capacity = max(max_socket_capacity, capacity_info["available_vcores"])
            
            if pod_vcores > max_socket_capacity:
                violated_rules.append(
                    f"Critical: {pod_req.pod_type.value} pod ({pod_vcores} vCores) exceeds maximum socket capacity "
                    f"({max_socket_capacity} vCores) - this pod cannot be placed on any socket"
                )
    
    success = len(violated_rules) == 0
    message = "RMP placement feasibility validation passed" if success else "RMP placement feasibility validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_placement_rule_m4(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule M4: CMP Placement Rules
    Scenarios:
    - with_ha_enabled: Deploy exactly 2 CMP pods with anti-affinity (not on same socket)
    - without_ha: Flexible placement (quantity from input data)
    """
    violated_rules = []
    
    # Get all CMP pod requirements
    cmp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.CMP]
    total_cmp_pods = sum(req.quantity for req in cmp_requirements)
    
    if deployment_input.feature_flags.ha_enabled:
        # HA enabled: Deploy exactly 2 CMP pods with anti-affinity
        if total_cmp_pods != 2:
            violated_rules.append(
                f"M4: HA enabled - Expected exactly 2 CMP pods, found {total_cmp_pods}"
            )
        
        # Check anti-affinity: CMP pods must not be on same socket
        cmp_sockets = set()
        for socket_key, assigned_pods in socket_assignments.items():
            cmp_count = sum(1 for pod in assigned_pods if pod.pod_type == PodType.CMP)
            if cmp_count > 0:
                cmp_sockets.add(socket_key)
                if cmp_count > 1:
                    violated_rules.append(
                        f"M4: HA enabled - CMP anti-affinity violated: "
                        f"{cmp_count} CMP pods on socket {socket_key}"
                    )
        
        if len(cmp_sockets) != 2:
            violated_rules.append(
                f"M4: HA enabled - CMP pods must be on 2 different sockets, "
                f"found {len(cmp_sockets)} sockets"
            )
    
    else:
        # Without HA: Flexible placement (no specific constraints on quantity or placement)
        # Just validate that CMP pods exist if specified in requirements
        if total_cmp_pods == 0 and cmp_requirements:
            violated_rules.append("M4: No CMP pods found despite requirements")
    
    success = len(violated_rules) == 0
    message = "CMP placement validation passed" if success else "CMP placement validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_all_placement_rules(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Validate all placement rules (M1-M4)
    """
    all_violated_rules = []
    all_messages = []
    
    # Rule M1: Basic mandatory pods validation
    m1_result = validate_placement_rule_m1(deployment_input)
    if not m1_result.success:
        all_violated_rules.extend(m1_result.violated_rules)
    all_messages.append(m1_result.message)
    
    # Rules M2-M4 require socket assignments
    if socket_assignments:
        # Rule M2: DPP placement validation
        m2_result = validate_placement_rule_m2(deployment_input, socket_assignments)
        if not m2_result.success:
            all_violated_rules.extend(m2_result.violated_rules)
        all_messages.append(m2_result.message)
        
        # Rule M3: RMP placement validation
        m3_result = validate_placement_rule_m3(deployment_input, socket_assignments)
        if not m3_result.success:
            all_violated_rules.extend(m3_result.violated_rules)
        all_messages.append(m3_result.message)
        
        # Rule M4: CMP placement validation
        m4_result = validate_placement_rule_m4(deployment_input, socket_assignments)
        if not m4_result.success:
            all_violated_rules.extend(m4_result.violated_rules)
        all_messages.append(m4_result.message)
    else:
        all_messages.append("Socket assignments not provided - skipping M2-M4 validation")
    
    success = len(all_violated_rules) == 0
    combined_message = " | ".join(all_messages)
    
    return ValidationResult(
        success=success,
        message=combined_message,
        violated_rules=all_violated_rules
    )


def get_mandatory_pod_requirements() -> Set[PodType]:
    """
    Get set of mandatory pod types for vDU deployment
    """
    return {PodType.DPP, PodType.DIP, PodType.RMP, PodType.CMP, PodType.DMP, PodType.PMP}


def get_flexible_placement_pods() -> Set[PodType]:
    """
    Get pods with flexible placement rules
    """
    return {PodType.DIP, PodType.DMP, PodType.PMP}


def get_constrained_placement_pods() -> Set[PodType]:
    """
    Get pods with constrained placement rules
    """
    return {PodType.DPP, PodType.RMP, PodType.CMP}


def calculate_required_dpp_count(deployment_input: DeploymentInput) -> int:
    """
    Calculate required number of DPP pods based on deployment configuration
    """
    # Base requirement: at least 1 DPP pod
    base_count = 1
    
    # HA may allow multiple DPP pods per socket
    if deployment_input.feature_flags.ha_enabled:
        # HA allows multiple DPP pods, but doesn't specify exact count
        # Return base requirement - actual count depends on socket assignments
        return base_count
    
    # In-service upgrade requires anti-affinity, which may require more DPP pods
    if deployment_input.feature_flags.in_service_upgrade:
        # Each socket can have at most 1 DPP pod due to anti-affinity
        # Count total sockets across all servers
        total_sockets = sum(server.sockets for server in deployment_input.server_configs)
        return max(base_count, total_sockets)
    
    return base_count


def calculate_required_rmp_count(deployment_input: DeploymentInput) -> int:
    """
    Calculate required number of RMP pods based on deployment configuration
    """
    if deployment_input.feature_flags.vdu_ru_switch_connection:
        # Switch scenario: exactly 1 RMP for entire vDU
        return 1
    else:
        # Normal scenario: same number as DPP pods
        return calculate_required_dpp_count(deployment_input)


def calculate_required_cmp_count(deployment_input: DeploymentInput) -> int:
    """
    Calculate required number of CMP pods based on deployment configuration
    """
    if deployment_input.feature_flags.ha_enabled:
        # HA enabled: exactly 2 CMP pods with anti-affinity
        return 2
    else:
        # Without HA: flexible placement (determined by input requirements)
        # Return 1 as default if no specific requirement
        return 1
