"""
Deployment Validator - Main orchestrator for all DR rules validation

This module coordinates capacity, placement, operator-specific, and validation rules
to provide comprehensive deployment validation for vDU pod placements.
"""

import logging
from typing import List, Dict, Optional, Any

from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, PodType, FeatureFlags, DRRulesParser
)
from generated_capacity_rules import (
    validate_all_capacity_rules, 
    calculate_socket_capacity
)
from generated_placement_rules import (
    validate_all_placement_rules,
    get_mandatory_pod_requirements,
    calculate_required_dpp_count,
    calculate_required_rmp_count,
    calculate_required_cmp_count
)
from generated_operator_rules import (
    validate_all_operator_rules,
    get_operator_specific_mandatory_pods,
    calculate_operator_specific_pod_requirements
)
from generated_validation_rules import (
    validate_all_validation_rules,
    calculate_deployment_metrics
)

# Configure logging
logger = logging.getLogger(__name__)


class DeploymentValidator:
    """
    Main orchestrator for vDU deployment validation.
    Executes all DR rules in proper order and provides comprehensive results.
    """
    
    def __init__(self, rules_file_path: str = "vdu_dr_rules.2.json"):
        self.rules_parser = DRRulesParser(rules_file_path)
        self.validation_results = {}
        self.socket_assignments = {}
        
    def validate_deployment(
        self, 
        deployment_input: DeploymentInput,
        generate_placement_plan: bool = True
    ) -> ValidationResult:
        """
        Complete deployment validation executing all rules in proper order.
        
        Validation Order:
        1. Input validation (V3)
        2. Pre-placement capacity validation (C1-C4) - Check total capacity before attempting placement
        3. Add operator-specific pod requirements
        4. Generate socket assignments
        5. Placement validation (M1-M4)
        6. Operator-specific validation (O1-O4)
        7. Final validation (V1-V2)
        """
        all_violated_rules = []
        all_messages = []
        
        # Step 1: Input validation (V3) - must pass first
        input_result = validate_all_validation_rules(deployment_input, {})
        if not input_result.success:
            logger.error(f"Input validation failed: {input_result.message}")
            return input_result
        
        all_messages.append(input_result.message)
        
        # Step 2: Add operator-specific pod requirements FIRST
        enhanced_deployment_input = self._add_operator_specific_pods(deployment_input)
        
        # Step 3: Enhanced socket-level capacity validation
        from generated_capacity_rules import validate_socket_capacity_constraints, validate_rmp_dpp_co_location_capacity
        socket_capacity_result = validate_socket_capacity_constraints(enhanced_deployment_input)
        if not socket_capacity_result.success:
            all_violated_rules.extend(socket_capacity_result.violated_rules)
            logger.warning(f"Socket capacity validation failed: {socket_capacity_result.message}")
        all_messages.append(socket_capacity_result.message)
        
        # Step 3.5: RMP-DPP co-location capacity validation
        rmp_dpp_co_location_result = validate_rmp_dpp_co_location_capacity(enhanced_deployment_input)
        if not rmp_dpp_co_location_result.success:
            all_violated_rules.extend(rmp_dpp_co_location_result.violated_rules)
            logger.warning(f"RMP-DPP co-location validation failed: {rmp_dpp_co_location_result.message}")
        all_messages.append(rmp_dpp_co_location_result.message)
        
        # Step 3.6: RMP placement feasibility validation
        from generated_placement_rules import validate_rmp_placement_feasibility
        rmp_feasibility_result = validate_rmp_placement_feasibility(enhanced_deployment_input)
        if not rmp_feasibility_result.success:
            all_violated_rules.extend(rmp_feasibility_result.violated_rules)
            logger.warning(f"RMP placement feasibility validation failed: {rmp_feasibility_result.message}")
        all_messages.append(rmp_feasibility_result.message)
        
        # Step 4: Pre-placement capacity validation (C1-C4)
        capacity_result = self._validate_total_capacity_before_placement(enhanced_deployment_input)
        if not capacity_result.success:
            all_violated_rules.extend(capacity_result.violated_rules)
            logger.warning(f"Total capacity validation failed: {capacity_result.message}")
            
            # Only return if we have socket capacity violations, otherwise continue with placement
            if not any("Socket capacity constraint violated" in rule for rule in all_violated_rules):
                return ValidationResult(
                    success=False,
                    message=" | ".join(all_messages),
                    violated_rules=all_violated_rules
                )
        all_messages.append(capacity_result.message)
        
        # Step 5: Generate socket assignments if requested
        if generate_placement_plan:
            placement_result = self._generate_socket_assignments(enhanced_deployment_input)
            if not placement_result.success:
                all_violated_rules.extend(placement_result.violated_rules)
                logger.error(f"Socket assignment generation failed: {placement_result.message}")
                return ValidationResult(
                    success=False,
                    message=" | ".join(all_messages),
                    violated_rules=all_violated_rules
                )
            self.socket_assignments = placement_result.placement_plan or {}
        else:
            self.socket_assignments = deployment_input.placement_plan or {}
        
        # Step 6: Placement validation (M1-M4)
        placement_result = validate_all_placement_rules(enhanced_deployment_input, self.socket_assignments)
        if not placement_result.success:
            all_violated_rules.extend(placement_result.violated_rules)
            logger.warning(f"Placement validation failed: {placement_result.message}")
        all_messages.append(placement_result.message)
        
        # Step 7: Operator-specific validation (O1-O5)
        operator_result = validate_all_operator_rules(enhanced_deployment_input, self.socket_assignments, self.rules_parser)
        if not operator_result.success:
            all_violated_rules.extend(operator_result.violated_rules)
            logger.warning(f"Operator-specific validation failed: {operator_result.message}")
        all_messages.append(operator_result.message)
        
        # Step 8: Final validation (V1-V2)
        final_validation_result = validate_all_validation_rules(enhanced_deployment_input, self.socket_assignments)
        if not final_validation_result.success:
            all_violated_rules.extend(final_validation_result.violated_rules)
            logger.warning(f"Final validation failed: {final_validation_result.message}")
        all_messages.append(final_validation_result.message)
        
        # Determine overall success
        success = len(all_violated_rules) == 0
        combined_message = " | ".join(all_messages)
        
        # Calculate deployment metrics
        deployment_metrics = calculate_deployment_metrics(enhanced_deployment_input, self.socket_assignments)
        
        if success:
            logger.info("Deployment validation completed successfully")
        else:
            logger.warning(f"Deployment validation failed with {len(all_violated_rules)} violations")
        
        return ValidationResult(
            success=success,
            message=combined_message,
            violated_rules=all_violated_rules,
            placement_plan=self.socket_assignments
        )
    
    def _generate_socket_assignments(self, deployment_input: DeploymentInput) -> ValidationResult:
        """
        Generate optimal socket assignments for pods based on all constraints.
        Enhanced algorithm to handle anti-affinity constraints properly.
        """
        socket_assignments = {}
        violated_rules = []
        
        # Check if we have enough sockets for anti-affinity constraints
        anti_affinity_pods = self._identify_anti_affinity_pods(deployment_input)
        required_sockets = self._calculate_required_sockets(anti_affinity_pods, deployment_input)
        available_sockets = sum(server.sockets for server in deployment_input.server_configs)
        
        if required_sockets > available_sockets:
            violated_rules.append(
                f"Insufficient sockets for anti-affinity constraints: "
                f"Need {required_sockets} sockets, have {available_sockets} sockets"
            )
            return ValidationResult(
                success=False,
                message="Anti-affinity constraints cannot be satisfied with available sockets",
                violated_rules=violated_rules
            )
        
        # Initialize socket assignments
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            for socket_idx in range(server_config.sockets):
                socket_key = server_idx * 1000 + socket_idx
                socket_assignments[socket_key] = []
        
        # Handle anti-affinity pods first - distribute them across sockets
        remaining_pods = self._place_anti_affinity_pods(
            deployment_input, socket_assignments, anti_affinity_pods, violated_rules
        )
        
        if violated_rules:
            return ValidationResult(
                success=False,
                message="Failed to place anti-affinity pods",
                violated_rules=violated_rules
            )
        
        # Handle DirectX2 co-location constraints
        remaining_pods = self._handle_directx2_co_location(
            deployment_input, socket_assignments, remaining_pods, violated_rules
        )
        
        if violated_rules:
            return ValidationResult(
                success=False,
                message="Failed to handle DirectX2 co-location constraints",
                violated_rules=violated_rules
            )
        
        # Place remaining pods without anti-affinity constraints
        self._place_remaining_pods(deployment_input, socket_assignments, remaining_pods, violated_rules)
        
        # Check if all pods were placed
        if remaining_pods:
            violated_rules.append(
                f"Could not place all pods: {len(remaining_pods)} pods remaining unassigned"
            )
            for pod_req in remaining_pods:
                violated_rules.append(
                    f"Unassigned pod: {pod_req.pod_type.value} ({pod_req.vcores} vcores, qty: {pod_req.quantity})"
                )
        
        success = len(violated_rules) == 0
        message = "Socket assignment generation completed" if success else "Socket assignment failed"
        
        return ValidationResult(
            success=success,
            message=message,
            violated_rules=violated_rules,
            placement_plan=socket_assignments
        )
    
    def _place_anti_affinity_pods(
        self, 
        deployment_input: DeploymentInput,
        socket_assignments: Dict[int, List[PodRequirement]],
        anti_affinity_pods: Dict[PodType, List[PodRequirement]],
        violated_rules: List[str]
    ) -> List[PodRequirement]:
        """Place anti-affinity pods across different sockets."""
        remaining_pods = deployment_input.pod_requirements.copy()
        available_socket_keys = list(socket_assignments.keys())
        
        for pod_type, pod_list in anti_affinity_pods.items():
            if not pod_list:
                continue
                
            for i, pod_req in enumerate(pod_list):
                socket_idx = i % len(available_socket_keys)
                socket_key = available_socket_keys[socket_idx]
                
                server_idx = socket_key // 1000
                socket_idx_local = socket_key % 1000
                server_config = deployment_input.server_configs[server_idx]
                capacity_info = calculate_socket_capacity(server_config, socket_idx_local, deployment_input.operator_type)
                available_vcores = capacity_info["available_vcores"]
                used_vcores = sum(pod.vcores * pod.quantity for pod in socket_assignments[socket_key])
                
                if used_vcores + pod_req.vcores * pod_req.quantity <= available_vcores:
                    socket_assignments[socket_key].append(pod_req)
                else:
                    violated_rules.append(
                        f"Insufficient capacity on socket {server_idx}.{socket_idx_local} "
                        f"for anti-affinity pod {pod_req.pod_type.value}"
                    )
                    return remaining_pods
            
            # Handle RMP placement for DPP anti-affinity
            if pod_type == PodType.DPP and not deployment_input.feature_flags.vdu_ru_switch_connection:
                original_rmp_req = None
                for rmp_req in remaining_pods:
                    if rmp_req.pod_type == PodType.RMP:
                        original_rmp_req = rmp_req
                        break
                
                if original_rmp_req:
                    for i, pod_req in enumerate(pod_list):
                        rmp_pod = PodRequirement(
                            pod_type=PodType.RMP,
                            vcores=original_rmp_req.vcores,
                            quantity=1
                        )
                        socket_idx = i % len(available_socket_keys)
                        socket_key = available_socket_keys[socket_idx]
                        socket_assignments[socket_key].append(rmp_pod)
                    
                    if original_rmp_req in remaining_pods:
                        remaining_pods.remove(original_rmp_req)
            
            # Remove original anti-affinity pod requirements
            pods_to_remove = []
            for original_pod in remaining_pods:
                if (original_pod.pod_type == pod_type and 
                    ((pod_type == PodType.DPP and deployment_input.feature_flags.in_service_upgrade) or
                     (pod_type == PodType.CMP and deployment_input.feature_flags.ha_enabled))):
                    pods_to_remove.append(original_pod)
            
            for pod_to_remove in pods_to_remove:
                if pod_to_remove in remaining_pods:
                    remaining_pods.remove(pod_to_remove)
        
        return remaining_pods
    
    def _handle_directx2_co_location(
        self,
        deployment_input: DeploymentInput,
        socket_assignments: Dict[int, List[PodRequirement]],
        remaining_pods: List[PodRequirement],
        violated_rules: List[str]
    ) -> List[PodRequirement]:
        """Handle DirectX2 co-location constraints."""
        if not deployment_input.feature_flags.directx2_required:
            return remaining_pods
        
        directx2_pods = {PodType.IPP, PodType.CSP, PodType.UPP}
        directx2_remaining = [pod for pod in remaining_pods if pod.pod_type in directx2_pods]
        
        if not directx2_remaining:
            return remaining_pods
        
        # Find a socket that can accommodate all DirectX2 pods
        directx2_placed = False
        
        for socket_key in socket_assignments.keys():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            server_config = deployment_input.server_configs[server_idx]
            
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            used_vcores = sum(pod.vcores * pod.quantity for pod in socket_assignments[socket_key])
            
            total_directx2_vcores = sum(pod.vcores * pod.quantity for pod in directx2_remaining)
            
            if used_vcores + total_directx2_vcores <= available_vcores:
                socket_assignments[socket_key].extend(directx2_remaining)
                
                for pod in directx2_remaining:
                    if pod in remaining_pods:
                        remaining_pods.remove(pod)
                
                directx2_placed = True
                break
        
        if not directx2_placed:
            violated_rules.append(
                "Could not find a socket with sufficient capacity for DirectX2 co-location constraints"
            )
            return remaining_pods
        
        # Handle IIP placement - IIP must NOT be on the same server as IPP
        remaining_pods = self._handle_iip_placement(
            deployment_input, socket_assignments, remaining_pods, violated_rules
        )
        
        return remaining_pods
    
    def _handle_iip_placement(
        self,
        deployment_input: DeploymentInput,
        socket_assignments: Dict[int, List[PodRequirement]],
        remaining_pods: List[PodRequirement],
        violated_rules: List[str]
    ) -> List[PodRequirement]:
        """Handle IIP placement with IPP separation constraint."""
        iip_pods = [pod for pod in remaining_pods if pod.pod_type == PodType.IIP]
        if not iip_pods:
            return remaining_pods
        
        # Find the server where IPP was placed
        ipp_server_idx = None
        for socket_key, assigned_pods in socket_assignments.items():
            if any(pod.pod_type == PodType.IPP for pod in assigned_pods):
                ipp_server_idx = socket_key // 1000
                break
        
        if ipp_server_idx is None:
            return remaining_pods
        
        # Place IIP pods on servers that do NOT host IPP
        iip_placed = False
        for socket_key in socket_assignments.keys():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            
            if server_idx == ipp_server_idx:
                continue
            
            server_config = deployment_input.server_configs[server_idx]
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            used_vcores = sum(pod.vcores * pod.quantity for pod in socket_assignments[socket_key])
            
            total_iip_vcores = sum(pod.vcores * pod.quantity for pod in iip_pods)
            
            if used_vcores + total_iip_vcores <= available_vcores:
                socket_assignments[socket_key].extend(iip_pods)
                
                for pod in iip_pods:
                    if pod in remaining_pods:
                        remaining_pods.remove(pod)
                
                iip_placed = True
                break
        
        if not iip_placed:
            violated_rules.append(
                "Could not place IIP pods on a server without IPP - violates O1 rule"
            )
        
        return remaining_pods
    
    def _place_remaining_pods(
        self,
        deployment_input: DeploymentInput,
        socket_assignments: Dict[int, List[PodRequirement]],
        remaining_pods: List[PodRequirement],
        violated_rules: List[str]
    ) -> None:
        """Place remaining pods without anti-affinity constraints."""
        # First, place non-RMP pods
        for socket_key, current_pods in socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            server_config = deployment_input.server_configs[server_idx]
            
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            used_vcores = sum(pod.vcores * pod.quantity for pod in current_pods)
            
            pods_to_place = []
            pods_to_remove = []
            
            for pod_req in remaining_pods:
                if pod_req.pod_type == PodType.RMP:
                    continue
                    
                if self._can_place_pod_on_socket(
                    pod_req, socket_assignments, socket_key, 
                    used_vcores, available_vcores, deployment_input
                ):
                    pods_to_place.append(pod_req)
                    pods_to_remove.append(pod_req)
                    used_vcores += pod_req.vcores * pod_req.quantity
            
            for pod_to_remove in pods_to_remove:
                if pod_to_remove in remaining_pods:
                    remaining_pods.remove(pod_to_remove)
            
            socket_assignments[socket_key].extend(pods_to_place)
        
        # Now place RMP pods on sockets that have DPP pods
        for socket_key, current_pods in socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            server_config = deployment_input.server_configs[server_idx]
            
            capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
            available_vcores = capacity_info["available_vcores"]
            used_vcores = sum(pod.vcores * pod.quantity for pod in current_pods)
            
            dpp_on_socket = any(pod.pod_type == PodType.DPP for pod in current_pods)
            
            if dpp_on_socket:
                pods_to_place = []
                pods_to_remove = []
                
                for pod_req in remaining_pods:
                    if pod_req.pod_type != PodType.RMP:
                        continue
                        
                    if self._can_place_pod_on_socket(
                        pod_req, socket_assignments, socket_key, 
                        used_vcores, available_vcores, deployment_input
                    ):
                        pods_to_place.append(pod_req)
                        pods_to_remove.append(pod_req)
                        used_vcores += pod_req.vcores * pod_req.quantity
                
                for pod_to_remove in pods_to_remove:
                    if pod_to_remove in remaining_pods:
                        remaining_pods.remove(pod_to_remove)
                
                socket_assignments[socket_key].extend(pods_to_place)
    
    def _can_place_pod_on_socket(
        self, 
        pod_req: PodRequirement,
        socket_assignments: Dict[int, List[PodRequirement]],
        socket_key: int,
        used_vcores: float,
        available_vcores: float,
        deployment_input: DeploymentInput
    ) -> bool:
        """Check if a pod can be placed on a specific socket considering all constraints."""
        # Check capacity constraint
        if used_vcores + (pod_req.vcores * pod_req.quantity) > available_vcores:
            return False
        
        current_pods = socket_assignments.get(socket_key, [])
        
        # Check anti-affinity constraints
        if pod_req.pod_type == PodType.DPP and deployment_input.feature_flags.in_service_upgrade:
            if any(pod.pod_type == PodType.DPP for pod in current_pods):
                return False
        
        if pod_req.pod_type == PodType.CMP and deployment_input.feature_flags.ha_enabled:
            if any(pod.pod_type == PodType.CMP for pod in current_pods):
                return False
        
        # Check co-location constraints for DirectX2
        if deployment_input.feature_flags.directx2_required:
            directx2_pods = {PodType.IPP, PodType.CSP, PodType.UPP}
            if pod_req.pod_type in directx2_pods:
                for other_socket_key, other_pods in socket_assignments.items():
                    if other_socket_key != socket_key:
                        if any(pod.pod_type in directx2_pods for pod in other_pods):
                            return False
        
        return True
    
    def _identify_anti_affinity_pods(self, deployment_input: DeploymentInput) -> Dict[PodType, List[PodRequirement]]:
        """Identify pods that have anti-affinity constraints."""
        anti_affinity_pods = {}
        
        for pod_req in deployment_input.pod_requirements:
            if pod_req.pod_type == PodType.DPP and deployment_input.feature_flags.in_service_upgrade:
                if pod_req.pod_type not in anti_affinity_pods:
                    anti_affinity_pods[pod_req.pod_type] = []
                for i in range(pod_req.quantity):
                    individual_pod = PodRequirement(
                        pod_type=pod_req.pod_type,
                        vcores=pod_req.vcores,
                        quantity=1
                    )
                    anti_affinity_pods[pod_req.pod_type].append(individual_pod)
            
            elif pod_req.pod_type == PodType.CMP and deployment_input.feature_flags.ha_enabled:
                if pod_req.pod_type not in anti_affinity_pods:
                    anti_affinity_pods[pod_req.pod_type] = []
                for i in range(pod_req.quantity):
                    individual_pod = PodRequirement(
                        pod_type=pod_req.pod_type,
                        vcores=pod_req.vcores,
                        quantity=1
                    )
                    anti_affinity_pods[pod_req.pod_type].append(individual_pod)
        
        return anti_affinity_pods
    
    def _calculate_required_sockets(self, anti_affinity_pods: Dict[PodType, List[PodRequirement]], deployment_input: DeploymentInput) -> int:
        """Calculate minimum number of sockets required for anti-affinity constraints."""
        required_sockets = 1
        
        for pod_type, pod_list in anti_affinity_pods.items():
            pod_count = sum(pod.quantity for pod in pod_list)
            required_sockets = max(required_sockets, pod_count)
        
        return required_sockets
    
    def _add_operator_specific_pods(self, deployment_input: DeploymentInput) -> DeploymentInput:
        """Add operator-specific mandatory pods to the deployment input."""
        operator_mandatory_pods = get_operator_specific_mandatory_pods(deployment_input.operator_type)
        enhanced_pod_requirements = deployment_input.pod_requirements.copy()
        
        # Add operator-specific mandatory pods if they don't already exist
        for mandatory_pod_type in operator_mandatory_pods:
            pod_exists = any(pod.pod_type == mandatory_pod_type for pod in enhanced_pod_requirements)
            
            if not pod_exists:
                if mandatory_pod_type == PodType.VCU:
                    vcu_vcores = self.rules_parser.get_vcu_vcores(deployment_input.vdu_flavor_name)
                    default_vcores = vcu_vcores
                else:
                    default_vcores = {
                        PodType.IPP: 4.0,
                        PodType.IIP: 4.0,
                        PodType.UPP: 2.0,
                        PodType.CSP: 2.0
                    }.get(mandatory_pod_type, 2.0)
                
                enhanced_pod_requirements.append(
                    PodRequirement(
                        pod_type=mandatory_pod_type,
                        vcores=default_vcores,
                        quantity=1
                    )
                )
        
        # Calculate operator-specific additional requirements
        additional_requirements = calculate_operator_specific_pod_requirements(
            deployment_input, self.rules_parser
        )
        
        # Add additional requirements, but avoid duplicates
        for additional_req in additional_requirements:
            pod_exists = any(pod.pod_type == additional_req.pod_type for pod in enhanced_pod_requirements)
            
            if not pod_exists:
                enhanced_pod_requirements.append(additional_req)
        
        return DeploymentInput(
            operator_type=deployment_input.operator_type,
            vdu_flavor_name=deployment_input.vdu_flavor_name,
            pod_requirements=enhanced_pod_requirements,
            server_configs=deployment_input.server_configs,
            feature_flags=deployment_input.feature_flags
        )
    
    def get_detailed_validation_report(self, deployment_input: DeploymentInput) -> Dict[str, Any]:
        """Generate a comprehensive validation report with detailed analysis."""
        validation_result = self.validate_deployment(deployment_input)
        
        report = {
            "summary": {
                "success": validation_result.success,
                "message": validation_result.message,
                "total_violations": len(validation_result.violated_rules)
            },
            "violations": {
                "all_rules": validation_result.violated_rules,
                "categorized": self._categorize_violations(validation_result.violated_rules)
            },
            "deployment_metrics": calculate_deployment_metrics(deployment_input, self.socket_assignments),
            "socket_assignments": self._format_socket_assignments(),
            "recommendations": self._generate_recommendations(validation_result, deployment_input)
        }
        
        return report
    
    def _categorize_violations(self, violated_rules: List[str]) -> Dict[str, List[str]]:
        """Categorize violations by rule type."""
        categories = {
            "capacity": [],
            "placement": [],
            "operator_specific": [],
            "validation": [],
            "anti_affinity": [],
            "co_location": []
        }
        
        for rule in violated_rules:
            if rule.startswith(("C1:", "C2:", "C3:", "C4:")):
                categories["capacity"].append(rule)
            elif rule.startswith(("M1:", "M2:", "M3:", "M4:")):
                categories["placement"].append(rule)
            elif rule.startswith(("O1:", "O2:", "O3:", "O4:")):
                categories["operator_specific"].append(rule)
            elif rule.startswith(("V1:", "V2:", "V3:")):
                categories["validation"].append(rule)
            elif "anti-affinity" in rule.lower():
                categories["anti_affinity"].append(rule)
            elif "co-location" in rule.lower():
                categories["co_location"].append(rule)
        
        return categories
    
    def _format_socket_assignments(self) -> Dict[str, Any]:
        """Format socket assignments for readable output."""
        formatted = {}
        
        for socket_key, pods in self.socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            
            socket_id = f"server_{server_idx}_socket_{socket_idx}"
            formatted[socket_id] = {
                "server_index": server_idx,
                "socket_index": socket_idx,
                "pods": [
                    {
                        "pod_type": pod.pod_type.value,
                        "vcores": pod.vcores,
                        "quantity": pod.quantity
                    }
                    for pod in pods
                ],
                "total_vcores": sum(pod.vcores * pod.quantity for pod in pods),
                "pod_count": len(pods)
            }
        
        return formatted
    
    def _generate_recommendations(
        self, 
        validation_result: ValidationResult, 
        deployment_input: DeploymentInput
    ) -> List[str]:
        """Generate recommendations for fixing validation failures."""
        recommendations = []
        
        if not validation_result.success:
            for violation in validation_result.violated_rules:
                if "capacity" in violation.lower() or "vcores" in violation.lower():
                    recommendations.append(
                        "Consider upgrading server hardware or reducing pod resource requirements"
                    )
                elif "anti-affinity" in violation.lower():
                    recommendations.append(
                        "Add more servers or sockets to satisfy anti-affinity constraints"
                    )
                elif "co-location" in violation.lower():
                    recommendations.append(
                        "Ensure sufficient capacity on a single socket for co-located pods"
                    )
                elif "mandatory" in violation.lower():
                    recommendations.append(
                        "Add all mandatory pods to the deployment requirements"
                    )
                elif "operator" in violation.lower():
                    recommendations.append(
                        "Review operator-specific requirements and constraints"
                    )
        
        # Remove duplicate recommendations
        unique_recommendations = list(dict.fromkeys(recommendations))
        
        return unique_recommendations
    
    def validate_deployment_scenario(
        self,
        operator_type: str,
        vdu_flavor_name: str,
        server_configs: List[Dict[str, Any]],
        pod_requirements: List[Dict[str, Any]],
        feature_flags: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Convenience method to validate deployment from raw parameters."""
        deployment_input = self._create_deployment_input(
            operator_type, vdu_flavor_name, server_configs, pod_requirements, feature_flags
        )
        
        return self.get_detailed_validation_report(deployment_input)
    
    def _create_deployment_input(
        self,
        operator_type: str,
        vdu_flavor_name: str,
        server_configs: List[Dict[str, Any]],
        pod_requirements: List[Dict[str, Any]],
        feature_flags: Dict[str, bool]
    ) -> DeploymentInput:
        """Create DeploymentInput object from raw parameters."""
        servers = []
        for config in server_configs:
            server = ServerConfiguration(
                pcores=config["pcores"],
                vcores=config["vcores"],
                sockets=config["sockets"],
                pcores_per_socket=config.get("pcores_per_socket")
            )
            servers.append(server)
        
        pods = []
        for req in pod_requirements:
            pod = PodRequirement(
                pod_type=PodType(req["pod_type"]),
                vcores=req["vcores"],
                quantity=req.get("quantity", 1)
            )
            pods.append(pod)
        
        flags = FeatureFlags(
            ha_enabled=feature_flags.get("ha_enabled", False),
            in_service_upgrade=feature_flags.get("in_service_upgrade", False),
            vdu_ru_switch_connection=feature_flags.get("vdu_ru_switch_connection", False),
            directx2_required=feature_flags.get("directx2_required", False),
            vcu_deployment_required=feature_flags.get("vcu_deployment_required", False)
        )
        
        return DeploymentInput(
            operator_type=OperatorType(operator_type),
            vdu_flavor_name=vdu_flavor_name,
            pod_requirements=pods,
            server_configs=servers,
            feature_flags=flags
        )
    
    def get_supported_configurations(self, operator_type: str) -> List[Dict[str, Any]]:
        """Get supported server configurations for an operator."""
        operator = OperatorType(operator_type)
        return self.rules_parser.get_server_configurations(operator)
    
    def calculate_minimum_requirements(self, deployment_input: DeploymentInput) -> Dict[str, Any]:
        """Calculate minimum resource requirements for deployment."""
        # First enhance the deployment input with operator-specific pods
        enhanced_deployment_input = self._add_operator_specific_pods(deployment_input)
        
        mandatory_pods = get_mandatory_pod_requirements()
        operator_mandatory = get_operator_specific_mandatory_pods(deployment_input.operator_type)
        all_mandatory = mandatory_pods.union(operator_mandatory)
        
        required_counts = {
            PodType.DPP: calculate_required_dpp_count(enhanced_deployment_input),
            PodType.RMP: calculate_required_rmp_count(enhanced_deployment_input),
            PodType.CMP: calculate_required_cmp_count(enhanced_deployment_input)
        }
        
        minimum_vcores = 0
        for pod_req in enhanced_deployment_input.pod_requirements:
            # For CMP with HA, we need to ensure we account for 2 pods
            if pod_req.pod_type == PodType.CMP and enhanced_deployment_input.feature_flags.ha_enabled:
                minimum_vcores += pod_req.vcores * 2  # HA requires 2 CMP pods
            else:
                minimum_vcores += pod_req.vcores * pod_req.quantity
        
        return {
            "minimum_vcores": minimum_vcores,
            "mandatory_pods": [pod.value for pod in all_mandatory],
            "required_pod_counts": {pod.value: count for pod, count in required_counts.items()},
            "additional_requirements": []  # This is now included in pod_requirements
        }
    
    def _validate_total_capacity_before_placement(self, deployment_input: DeploymentInput) -> ValidationResult:
        """Validate total capacity before attempting placement."""
        violated_rules = []
        
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            total_pod_vcores = sum(pod.vcores * pod.quantity for pod in deployment_input.pod_requirements)
            
            total_vcores = server_config.vcores
            from generated_capacity_rules import get_caas_cores_per_socket, get_shared_cores_per_socket
            
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
        if success:
            message = f"Capacity validation passed (Total available: {available_vcores}, Required: {total_pod_vcores})"
        else:
            message = f"Capacity validation failed (Total available: {available_vcores}, Required: {total_pod_vcores})"
        
        return ValidationResult(success=success, message=message, violated_rules=violated_rules)
