"""
Generated operator-specific validation functions based on DR rules O1-O5
Auto-generated from vdu_dr_rules.json - DO NOT EDIT MANUALLY
"""
from typing import List, Dict, Set, Optional, Tuple
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, PodType, FeatureFlags, DRRulesParser
)


def validate_operator_rule_o1(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule O1: VOS Operator IPsec Pods
    - IPP: Mandatory for VOS operator, exactly 1 per vDU
    - IIP: Required only for multi-server vDU, place exactly 1 IIP on every server that does NOT host IPP
    - Single-server vDU: No IIP needed
    """
    violated_rules = []
    
    # This rule only applies to VOS operator
    if deployment_input.operator_type != OperatorType.VOS:
        return ValidationResult(success=True, message="O1: Not VOS operator - skipping validation")
    
    # Get IPP and IIP requirements
    ipp_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.IPP]
    iip_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.IIP]
    
    total_ipp_pods = sum(req.quantity for req in ipp_requirements)
    total_iip_pods = sum(req.quantity for req in iip_requirements)
    
    # IPP validation: Mandatory for VOS operator, exactly 1 per vDU
    if total_ipp_pods != 1:
        violated_rules.append(
            f"O1: VOS operator requires exactly 1 IPP pod per vDU, found {total_ipp_pods}"
        )
    
    # IIP validation based on server count and special flavor rules
    is_special_flavor = is_special_vdu_flavor(deployment_input.vdu_flavor_name)
    server_count = len(deployment_input.server_configs)
    
    if server_count > 1:
        # Multi-server vDU: IIP required on every server that does NOT host IPP
        
        # Find servers that host IPP
        ipp_servers = set()
        for socket_key, assigned_pods in socket_assignments.items():
            server_idx = socket_key // 1000  # Extract server index from socket key
            if any(pod.pod_type == PodType.IPP for pod in assigned_pods):
                ipp_servers.add(server_idx)
        
        # Expected IIP count: number of servers without IPP
        expected_iip_count = deployment_input.number_of_servers - len(ipp_servers)
        
        # For special flavors, IIP is automatically included, so we expect at least 1
        if is_special_flavor:
            expected_iip_count = max(expected_iip_count, 1)
        
        if total_iip_pods != expected_iip_count:
            violated_rules.append(
                f"O1: Multi-server vDU - Expected {expected_iip_count} IIP pods "
                f"(1 per server without IPP), found {total_iip_pods}"
            )
        
        # Validate IIP placement: should not be on servers with IPP
        for socket_key, assigned_pods in socket_assignments.items():
            server_idx = socket_key // 1000
            has_ipp = any(pod.pod_type == PodType.IPP for pod in assigned_pods)
            has_iip = any(pod.pod_type == PodType.IIP for pod in assigned_pods)
            
            if has_ipp and has_iip:
                violated_rules.append(
                    f"O1: Server {server_idx} has both IPP and IIP - violates placement rule"
                )
    
    else:
        # Single-server vDU: IIP validation
        if is_special_flavor:
            # Special flavor automatically includes IIP - it should be present
            if total_iip_pods == 0:
                violated_rules.append(
                    f"O1: Special flavor {deployment_input.vdu_flavor_name} automatically includes IIP, but none found"
                )
        else:
            # Regular single-server vDU: No IIP needed
            if total_iip_pods > 0:
                violated_rules.append(
                    f"O1: Single-server vDU - No IIP pods needed, found {total_iip_pods}"
                )
    
    success = len(violated_rules) == 0
    message = "VOS IPsec pods validation passed" if success else "VOS IPsec pods validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_operator_rule_o2(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule O2: VOS Operator vCU Deployment
    - vCU deployment is optional. If deployed:
    - medium-regular-spr-t23 flavor: vcu_type = tiny-dran-mini, vcores = 15
    - medium-regular-gnr-t20 flavor: vcu_type = tiny-dran, vcores = 18
    - all_other_flavors: vcu_type = tiny-dran, vcores = 18
    """
    violated_rules = []
    
    # This rule only applies to VOS operator
    if deployment_input.operator_type != OperatorType.VOS:
        return ValidationResult(success=True, message="O2: Not VOS operator - skipping validation")
    
    # Check if vCU deployment is enabled
    if not deployment_input.feature_flags.vcu_deployment_required:
        return ValidationResult(success=True, message="O2: vCU deployment not required - skipping validation")
    
    # Get vCU requirements
    vcu_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.VCU]
    total_vcu_pods = sum(req.quantity for req in vcu_requirements)
    
    if total_vcu_pods == 0:
        violated_rules.append("O2: vCU deployment required but no vCU pods found")
        return ValidationResult(success=False, message="vCU deployment validation failed", violated_rules=violated_rules)
    
    # Determine expected vcores based on flavor (matching LLM logic)
    if deployment_input.vdu_flavor_name == "medium-regular-spr-t23":
        expected_vcores = 15
        expected_type = "tiny-dran-mini"
    elif deployment_input.vdu_flavor_name == "medium-regular-gnr-t20":
        expected_vcores = 18
        expected_type = "tiny-dran"
    else:
        expected_vcores = 18
        expected_type = "tiny-dran"
    
    # Validate vCU vcore requirements
    for vcu_req in vcu_requirements:
        if vcu_req.vcores != expected_vcores:
            violated_rules.append(
                f"O2: vCU deployment validation failed ({expected_type}, {expected_vcores} vcores) for flavor {deployment_input.vdu_flavor_name}"
            )
    
    success = len(violated_rules) == 0
    if success:
        message = f"vCU deployment validation passed ({expected_type}, {expected_vcores} vcores)"
    else:
        message = f"vCU deployment validation failed ({expected_type}, {expected_vcores} vcores)"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_operator_rule_o3(deployment_input: DeploymentInput) -> ValidationResult:
    """
    Rule O3: VOS Operator Special vDU Flavors
    These vDU flavors automatically include IIP:
    - medium-tdd-spr-t20
    - small-tdd-spr-t20
    - medium-tdd-gnr-t20
    """
    violated_rules = []
    
    # This rule only applies to VOS operator
    if deployment_input.operator_type != OperatorType.VOS:
        return ValidationResult(success=True, message="O3: Not VOS operator - skipping validation")
    
    # Check if this is a special vDU flavor
    special_flavors = [
        "medium-tdd-spr-t20",
        "small-tdd-spr-t20", 
        "medium-tdd-gnr-t20"
    ]
    
    is_special_flavor = deployment_input.vdu_flavor_name in special_flavors
    
    # Get IIP requirements
    iip_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.IIP]
    total_iip_pods = sum(req.quantity for req in iip_requirements)
    
    if is_special_flavor:
        # Special flavor: IIP should be automatically included
        if total_iip_pods == 0:
            violated_rules.append(
                f"O3: Special flavor {deployment_input.vdu_flavor_name} automatically includes IIP, but no IIP pods found"
            )
    else:
        # Not a special flavor: IIP follows normal rules (validated in O1)
        pass
    
    success = len(violated_rules) == 0
    message = "Special vDU flavor validation passed" if success else "Special vDU flavor validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_operator_rule_o4(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]]
) -> ValidationResult:
    """
    Rule O4: DirectX2 Co-location
    When DirectX2 function is required, these pods are mandatory and must be co-located on same server/socket:
    - vDU (uADPF) IPP
    - vCU (ACPF) IPP
    - CSP
    - vCU (AUPF) UPP
    Constraint: If co-location cannot be satisfied due to capacity, deployment fails
    """
    violated_rules = []
    
    # This rule only applies to VOS operator
    if deployment_input.operator_type != OperatorType.VOS:
        return ValidationResult(success=True, message="O4: Not VOS operator - skipping validation")
    
    # Check if DirectX2 is required
    if not deployment_input.feature_flags.directx2_required:
        return ValidationResult(success=True, message="O4: DirectX2 not required - skipping validation")
    
    # Mandatory pods for DirectX2
    mandatory_pods = {PodType.IPP, PodType.CSP, PodType.UPP}
    
    # Check if all mandatory pods are present
    provided_pods = set()
    for pod_req in deployment_input.pod_requirements:
        provided_pods.add(pod_req.pod_type)
    
    missing_pods = mandatory_pods - provided_pods
    if missing_pods:
        violated_rules.append(
            f"O4: DirectX2 required - Missing mandatory pods: {', '.join([pod.value for pod in missing_pods])}"
        )
        return ValidationResult(success=False, message="DirectX2 co-location validation failed", violated_rules=violated_rules)
    
    # Check co-location: all mandatory pods must be on same server/socket
    pod_locations = {}  # pod_type -> set of socket_keys where it's placed
    
    for socket_key, assigned_pods in socket_assignments.items():
        for pod in assigned_pods:
            if pod.pod_type in mandatory_pods:
                if pod.pod_type not in pod_locations:
                    pod_locations[pod.pod_type] = set()
                pod_locations[pod.pod_type].add(socket_key)
    
    # Check if all mandatory pods are co-located
    if pod_locations:
        # Find the common socket(s) where all pods are placed
        common_sockets = None
        for pod_type, sockets in pod_locations.items():
            if common_sockets is None:
                common_sockets = sockets.copy()
            else:
                common_sockets.intersection_update(sockets)
            
            if not common_sockets:
                break  # No common sockets found
        
        if not common_sockets or len(common_sockets) == 0:
            violated_rules.append(
                f"O4: DirectX2 co-location failed - Mandatory pods are not on same server/socket. "
                f"Pod locations: {[(pod.value, list(sockets)) for pod, sockets in pod_locations.items()]}"
            )
        elif len(common_sockets) > 1:
            violated_rules.append(
                f"O4: DirectX2 co-location failed - Mandatory pods spread across multiple sockets: {list(common_sockets)}"
            )
    
    success = len(violated_rules) == 0
    message = "DirectX2 co-location validation passed" if success else "DirectX2 co-location validation failed"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_operator_rule_o5(
    deployment_input: DeploymentInput,
    rules_parser: DRRulesParser
) -> ValidationResult:
    """
    Rule O5: vCSR Deployment
    vCSR deployment is optional. If deployed:
    - medium-regular-gnr-t22 flavor: vcores = 4
    - default server config: 64 pcores, 2 sockets
    """
    violated_rules = []
    
    # This rule only applies to VOS operator
    if deployment_input.operator_type != OperatorType.VOS:
        return ValidationResult(success=True, message="O5: Not VOS operator - skipping validation")
    
    # Check if vCSR deployment is enabled
    if not deployment_input.feature_flags.vcsr_deployment_required:
        return ValidationResult(success=True, message="O5: vCSR deployment not required - skipping validation")
    
    # Get vCSR requirements
    vcsr_requirements = [req for req in deployment_input.pod_requirements if req.pod_type == PodType.VCSR]
    total_vcsr_pods = sum(req.quantity for req in vcsr_requirements)
    
    if total_vcsr_pods == 0:
        violated_rules.append("O5: vCSR deployment required but no vCSR pods found")
        return ValidationResult(success=False, message="vCSR deployment validation failed", violated_rules=violated_rules)
    
    # Determine expected vcores based on flavor using the rules parser
    expected_vcores = rules_parser.get_vcsr_vcores(deployment_input.vdu_flavor_name)
    
    # If vCSR is not supported for this flavor (expected_vcores = 0), it's an error
    if expected_vcores == 0:
        violated_rules.append(
            f"O5: vCSR deployment is not supported for flavor {deployment_input.vdu_flavor_name}"
        )
        return ValidationResult(success=False, message="vCSR deployment validation failed", violated_rules=violated_rules)
    
    # Validate vCSR vcore requirements
    for vcsr_req in vcsr_requirements:
        if vcsr_req.vcores != expected_vcores:
            violated_rules.append(
                f"O5: vCSR deployment validation failed ({expected_vcores} vcores) for flavor {deployment_input.vdu_flavor_name}"
            )
    
    # Validate server configuration requirement
    vcsr_default_config = rules_parser.get_vcsr_default_server_config()
    if vcsr_default_config:
        # Check if any server config matches the vCSR default requirements
        config_matches = False
        for server_config in deployment_input.server_configs:
            if (server_config.pcores >= vcsr_default_config["pcores"] and 
                server_config.sockets >= vcsr_default_config["sockets"]):
                config_matches = True
                break
        
        if not config_matches:
            violated_rules.append(
                f"O5: vCSR deployment requires minimum {vcsr_default_config['pcores']} pcores and {vcsr_default_config['sockets']} sockets"
            )
    
    success = len(violated_rules) == 0
    if success:
        message = f"vCSR deployment validation passed ({expected_vcores} vcores)"
    else:
        message = f"vCSR deployment validation failed ({expected_vcores} vcores)"
    
    return ValidationResult(success=success, message=message, violated_rules=violated_rules)


def validate_all_operator_rules(
    deployment_input: DeploymentInput,
    socket_assignments: Dict[int, List[PodRequirement]],
    rules_parser: DRRulesParser
) -> ValidationResult:
    """
    Validate all operator-specific rules (O1-O5)
    """
    all_violated_rules = []
    all_messages = []
    
    # Rule O1: VOS IPsec pods validation
    o1_result = validate_operator_rule_o1(deployment_input, socket_assignments)
    if not o1_result.success:
        all_violated_rules.extend(o1_result.violated_rules)
    all_messages.append(o1_result.message)
    
    # Rule O2: VOS vCU deployment validation
    o2_result = validate_operator_rule_o2(deployment_input)
    if not o2_result.success:
        all_violated_rules.extend(o2_result.violated_rules)
    all_messages.append(o2_result.message)
    
    # Rule O3: VOS special vDU flavors validation
    o3_result = validate_operator_rule_o3(deployment_input)
    if not o3_result.success:
        all_violated_rules.extend(o3_result.violated_rules)
    all_messages.append(o3_result.message)
    
    # Rule O4: DirectX2 co-location validation (requires socket assignments)
    if socket_assignments:
        o4_result = validate_operator_rule_o4(deployment_input, socket_assignments)
        if not o4_result.success:
            all_violated_rules.extend(o4_result.violated_rules)
        all_messages.append(o4_result.message)
    else:
        all_messages.append("Socket assignments not provided - skipping O4 validation")
    
    # Rule O5: vCSR deployment validation
    o5_result = validate_operator_rule_o5(deployment_input, rules_parser)
    if not o5_result.success:
        all_violated_rules.extend(o5_result.violated_rules)
    all_messages.append(o5_result.message)
    
    success = len(all_violated_rules) == 0
    combined_message = " | ".join(all_messages)
    
    return ValidationResult(
        success=success,
        message=combined_message,
        violated_rules=all_violated_rules
    )


def get_operator_specific_mandatory_pods(operator_type: OperatorType) -> Set[PodType]:
    """
    Get operator-specific mandatory pods in addition to base mandatory pods
    """
    base_mandatory = {PodType.DPP, PodType.DIP, PodType.RMP, PodType.CMP, PodType.DMP, PodType.PMP}
    
    if operator_type == OperatorType.VOS:
        # VOS requires IPP in addition to base mandatory pods
        return base_mandatory | {PodType.IPP}
    
    # Other operators use base mandatory pods only
    return base_mandatory


def get_vcu_vcore_requirements(flavor_name: str) -> Tuple[int, str]:
    """
    Get vCU vcore requirements and type based on flavor
    Returns tuple of (vcores, vcu_type)
    """
    if flavor_name == "medium-regular-spr-t23":
        return (15, "tiny-dran-mini")
    else:
        return (18, "tiny-dran")


def is_special_vdu_flavor(flavor_name: str) -> bool:
    """
    Check if vDU flavor automatically includes IIP
    """
    special_flavors = [
        "medium-tdd-spr-t20",
        "small-tdd-spr-t20",
        "medium-tdd-gnr-t20"
    ]
    return flavor_name in special_flavors


def get_directx2_mandatory_pods() -> Set[PodType]:
    """
    Get set of mandatory pods for DirectX2 deployment
    """
    return {PodType.IPP, PodType.CSP, PodType.UPP}


def calculate_operator_specific_pod_requirements(
    deployment_input: DeploymentInput,
    rules_parser: DRRulesParser
) -> List[PodRequirement]:
    """
    Calculate operator-specific pod requirements based on deployment configuration
    """
    additional_requirements = []
    
    if deployment_input.operator_type == OperatorType.VOS:
        # VOS operator specific requirements
        
        # Rule O1: IPP is mandatory for VOS
        ipp_requirement = PodRequirement(
            pod_type=PodType.IPP,
            vcores=4.0,  # Typical IPP vcore requirement
            quantity=1
        )
        additional_requirements.append(ipp_requirement)
        
        # Rule O3: Special flavors automatically include IIP (check before multi-server logic)
        if is_special_vdu_flavor(deployment_input.vdu_flavor_name):
            # Special flavor always gets IIP, regardless of server count
            iip_requirement = PodRequirement(
                pod_type=PodType.IIP,
                vcores=4.0,
                quantity=1
            )
            additional_requirements.append(iip_requirement)
        else:
            # Rule O1: IIP for multi-server deployments (only for non-special flavors)
            if deployment_input.number_of_servers > 1:
                # For multi-server deployments, add IIP pods
                # The exact quantity will be determined during placement based on IPP location
                # Start with assumption that IPP is on one server, so we need number_of_servers - 1 IIP pods
                iip_requirement = PodRequirement(
                    pod_type=PodType.IIP,
                    vcores=4.0,  # Typical IIP vcore requirement
                    quantity=deployment_input.number_of_servers - 1  # One less than server count
                )
                additional_requirements.append(iip_requirement)
        
        # Rule O2: vCU deployment if enabled
        if deployment_input.feature_flags.vcu_deployment_required:
            vcu_vcores = rules_parser.get_vcu_vcores(deployment_input.vdu_flavor_name)
            vcu_requirement = PodRequirement(
                pod_type=PodType.VCU,
                vcores=float(vcu_vcores),
                quantity=1
            )
            additional_requirements.append(vcu_requirement)
        
        # Rule O4: DirectX2 mandatory pods
        if deployment_input.feature_flags.directx2_required:
            # Add CSP and UPP if not already present
            csp_requirement = PodRequirement(
                pod_type=PodType.CSP,
                vcores=2.0,  # Typical CSP vcore requirement
                quantity=1
            )
            additional_requirements.append(csp_requirement)
            
            upp_requirement = PodRequirement(
                pod_type=PodType.UPP,
                vcores=2.0,  # Typical UPP vcore requirement
                quantity=1
            )
            additional_requirements.append(upp_requirement)
        
        # Rule O5: vCSR deployment if enabled
        if deployment_input.feature_flags.vcsr_deployment_required:
            vcsr_vcores = rules_parser.get_vcsr_vcores(deployment_input.vdu_flavor_name)
            # Only add vCSR requirement if it's supported for this flavor (vcores > 0)
            if vcsr_vcores > 0:
                vcsr_requirement = PodRequirement(
                    pod_type=PodType.VCSR,
                    vcores=float(vcsr_vcores),
                    quantity=1
                )
                additional_requirements.append(vcsr_requirement)
    
    return additional_requirements
