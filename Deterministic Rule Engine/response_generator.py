"""
Response Generator - Creates human-readable responses from validation results

This module converts technical validation results into user-friendly explanations
with detailed metrics, recommendations, and formatted output.
"""

from typing import List, Dict, Any, Optional
import re

from rule_models import ValidationResult, DeploymentInput, OperatorType, PodRequirement, PodType
from generated_validation_rules import categorize_violations
from generated_operator_rules import is_special_vdu_flavor


class ResponseGenerator:
    """Generates human-readable responses from deployment validation results."""
    
    def __init__(self):
        self.emoji_map = {
            "success": "✅",
            "failure": "❌", 
            "warning": "⚠️",
            "info": "ℹ️",
            "resource": "📊",
            "deployment": "🚀",
            "violation": "🚨",
            "recommendation": "💡",
            "server": "🖥️",
            "pod": "📦",
            "rule": "📋"
        }
    
    def generate_validation_response(
        self, 
        validation_result: ValidationResult, 
        deployment_input: DeploymentInput,
        include_detailed_metrics: bool = True
    ) -> str:
        """Generate comprehensive human-readable validation response."""
        if validation_result.success:
            return self._generate_success_response(validation_result, deployment_input, include_detailed_metrics)
        else:
            return self._generate_failure_response(validation_result, deployment_input, include_detailed_metrics)
    
    def _generate_success_response(
        self, 
        validation_result: ValidationResult, 
        deployment_input: DeploymentInput,
        include_detailed_metrics: bool
    ) -> str:
        """Generate success response with deployment details."""
        response_lines = []
        
        response_lines.append(f"{self.emoji_map['success']} Deployment Validation: SUCCESS")
        response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['deployment']} Deployment Summary:")
        response_lines.append(f"  Operator: {deployment_input.operator_type.value}")
        response_lines.append(f"  vDU Flavor: {deployment_input.vdu_flavor_name}")
        response_lines.append(f"  Servers: {len(deployment_input.server_configs)}")
        response_lines.append(f"  Total Sockets: {sum(server.sockets for server in deployment_input.server_configs)}")
        response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['info']} Configuration:")
        flags = deployment_input.feature_flags
        response_lines.append(f"  High Availability: {'Enabled' if flags.ha_enabled else 'Disabled'}")
        response_lines.append(f"  In-Service Upgrade: {'Enabled' if flags.in_service_upgrade else 'Disabled'}")
        response_lines.append(f"  vDU-RU Switch: {'Enabled' if flags.vdu_ru_switch_connection else 'Disabled'}")
        response_lines.append(f"  DirectX2: {'Enabled' if flags.directx2_required else 'Disabled'}")
        response_lines.append(f"  vCU Deployment: {'Enabled' if flags.vcu_deployment_required else 'Disabled'}")
        response_lines.append("")
        
        if include_detailed_metrics and validation_result.placement_plan:
            metrics = self._calculate_utilization_metrics(validation_result.placement_plan, deployment_input)
            response_lines.append(f"{self.emoji_map['resource']} Resource Utilization:")
            response_lines.append(f"  Total vCores Requested: {metrics['total_vcores_requested']}")
            response_lines.append(f"  Total vCores Available: {metrics['total_vcores_available']}")
            response_lines.append(f"  Overall Utilization: {metrics['utilization_percent']:.1f}%")
            response_lines.append("")
        
        if validation_result.placement_plan:
            response_lines.append(f"{self.emoji_map['pod']} Pod Placement Plan:")
            for socket_key, pods in validation_result.placement_plan.items():
                server_idx = socket_key // 1000
                socket_idx = socket_key % 1000
                socket_id = f"Server {server_idx}, Socket {socket_idx}"
                
                total_vcores = sum(pod.vcores * pod.quantity for pod in pods)
                response_lines.append(f"  {socket_id}:")
                response_lines.append(f"    Total vCores: {total_vcores}")
                response_lines.append(f"    Pod Count: {len(pods)}")
                response_lines.append(f"    Pods:")
                for pod in pods:
                    response_lines.append(f"      - {pod.pod_type.value}: {pod.vcores} vcores")
            response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['rule']} Rule Compliance:")
        response_lines.append("  All deployment rules satisfied ✓")
        response_lines.append("  Capacity constraints within limits ✓")
        response_lines.append("  Placement constraints respected ✓")
        response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['deployment']} 🎉 Deployment is ready to proceed!")
        
        return "\n".join(response_lines)
    
    def _generate_failure_response(
        self, 
        validation_result: ValidationResult, 
        deployment_input: DeploymentInput,
        include_detailed_metrics: bool
    ) -> str:
        """Generate failure response with detailed violation information and step-by-step reasoning."""
        from deployment_validator import DeploymentValidator
        from generated_capacity_rules import get_caas_cores_per_socket, get_shared_cores_per_socket
        from generated_operator_rules import get_vcu_vcore_requirements, calculate_operator_specific_pod_requirements
        
        validator = DeploymentValidator()
        enhanced_deployment_input = validator._add_operator_specific_pods(deployment_input)
        
        # Calculate minimum requirements using the proper method
        min_requirements = validator.calculate_minimum_requirements(enhanced_deployment_input)
        total_required_vcores = min_requirements["minimum_vcores"]
        
        response_lines = []
        
        response_lines.append("Objective:")
        response_lines.append(f"  Propose optimal pod placement for {enhanced_deployment_input.operator_type.value} operator with flavor \"{enhanced_deployment_input.vdu_flavor_name}\" on a {len(enhanced_deployment_input.server_configs)}-server configuration, ensuring compliance with rules.")
        if enhanced_deployment_input.feature_flags.vcu_deployment_required:
            response_lines.append("  vCU Deployment is required.")
        response_lines.append("")

        response_lines.append("Input Parameters:")
        response_lines.append(f"  · **Operator**: {enhanced_deployment_input.operator_type.value}")
        response_lines.append(f"  · **Dimensioning Flavor**: {enhanced_deployment_input.vdu_flavor_name}")
        
        server_config_summary = []
        total_pcores = 0
        total_vcores = 0
        total_sockets = 0
        for server in enhanced_deployment_input.server_configs:
            total_pcores += server.pcores
            total_vcores += server.vcores
            total_sockets += server.sockets
            server_config_summary.append(f"{server.sockets} server(s) ({server.vcores} vCores total)")
        
        response_lines.append(f"  · **Server**: {', '.join(server_config_summary)}")
        if enhanced_deployment_input.feature_flags.vcu_deployment_required:
            response_lines.append(f"  · **vCU Deployment Required**: Yes")
        
        pod_vcore_requests_str = []
        for pod_req in enhanced_deployment_input.pod_requirements:
            # For CMP with HA, show the correct quantity
            if pod_req.pod_type == PodType.CMP and enhanced_deployment_input.feature_flags.ha_enabled:
                pod_vcore_requests_str.append(f"o {pod_req.pod_type.value}: {pod_req.vcores} (2 pods × {pod_req.vcores} each - HA enabled)")
            else:
                pod_vcore_requests_str.append(f"o {pod_req.pod_type.value}: {pod_req.vcores}")
            
        response_lines.append("  · **Pod vCore Requests**:")
        for req_str in pod_vcore_requests_str:
            response_lines.append(f"    {req_str}")
        response_lines.append("")

        response_lines.append("**Rules Applied**:")
        response_lines.append("")
        response_lines.append("  · C1 (Capacity Formula): Sum of pod vcores ≤ (Total vcores - CaaS vcores - Shared vcores)")
        response_lines.append("")
        response_lines.append("  · C2 (Core Conversion): 1 pCore = 2 vCores.")
        response_lines.append("")
        
        caas_vcores = get_caas_cores_per_socket(enhanced_deployment_input.operator_type)
        shared_vcores = get_shared_cores_per_socket(enhanced_deployment_input.operator_type)
        response_lines.append(f"  · C3 (CaaS Allocation for {enhanced_deployment_input.operator_type.value}): {caas_vcores} vCores per socket.")
        response_lines.append("")
        response_lines.append(f"  · C4 (Shared Core Allocation for {enhanced_deployment_input.operator_type.value}): {shared_vcores} vCores per socket.")
        response_lines.append("")
        
        if enhanced_deployment_input.operator_type == OperatorType.VOS:
            response_lines.append("  · O1 (IPP Mandatory): 1 IPP per vDU.")
            response_lines.append("")
            if enhanced_deployment_input.feature_flags.vcu_deployment_required:
                 response_lines.append("  · O2 (vCU Deployment for VOS): Requires specific vCores for flavor.")
                 response_lines.append("")
            if is_special_vdu_flavor(enhanced_deployment_input.vdu_flavor_name):
                 response_lines.append("  · O3 (Special vDU Flavors): Automatically includes IIP.")
                 response_lines.append("")
            if enhanced_deployment_input.feature_flags.directx2_required:
                 response_lines.append("  · O4 (DirectX2 Co-location): Mandatory pods must be co-located.")
                 response_lines.append("")
                 
            # Add specific rules for VCU and HA
            if enhanced_deployment_input.feature_flags.vcu_deployment_required:
                vcu_vcores, vcu_type = get_vcu_vcore_requirements(enhanced_deployment_input.vdu_flavor_name)
                response_lines.append(f"  · O2 (vCU Deployment): VCU added ({vcu_vcores} vCores for {vcu_type})")
                response_lines.append("")
            if enhanced_deployment_input.feature_flags.ha_enabled:
                response_lines.append("  · M4 (HA Anti-Affinity): 2 CMP pods required with anti-affinity")
                response_lines.append("")
        elif enhanced_deployment_input.operator_type == OperatorType.VERIZON:
            response_lines.append("  · S1 (Supported Server Configurations for Verizon): Only 32 pCores (64 vCores) is supported (example).")
            response_lines.append("")

        response_lines.append("  · M1 (Mandatory Pods): DPP, DIP, RMP, CMP, DMP, PMP must be placed.")
        response_lines.append("")
        
        # Add HA-related rules if HA is enabled
        if enhanced_deployment_input.feature_flags.ha_enabled:
            response_lines.append("  · M3 (HA Anti-Affinity): CMP pods must be placed on different sockets when HA is enabled.")
            response_lines.append("")
        
        # Add in-service upgrade rule if enabled
        if enhanced_deployment_input.feature_flags.in_service_upgrade:
            response_lines.append("  · M2 (In-Service Upgrade): DPP pods must be placed on different sockets when in-service upgrade is enabled.")
            response_lines.append("")

        response_lines.append("**Calculation**:")
        response_lines.append("")
        response_lines.append(f"  #Calculation:")
        response_lines.append(f"  · Total vCores available: {total_vcores}")
        total_caas_deduction = caas_vcores * total_sockets
        total_shared_deduction = shared_vcores * total_sockets
        response_lines.append(f"  · CaaS deduction (C3): {total_caas_deduction} vCores")
        response_lines.append(f"  · Shared deduction (C4): {total_shared_deduction} vCores")
        net_available_vcores = total_vcores - total_caas_deduction - total_shared_deduction
        response_lines.append(f"  · Net available vCores: {total_vcores} - {total_caas_deduction} - {total_shared_deduction} = {net_available_vcores} vCores")
        response_lines.append("")
        
        response_lines.append(f"  · Total vCores required:")
        response_lines.append(f"    {total_required_vcores} vCores (calculated using minimum requirements function)")
        response_lines.append("")

        response_lines.append("**Result**:")
        if total_required_vcores > net_available_vcores:
            response_lines.append(f"  · Required vCores ({total_required_vcores}) exceed available vCores ({net_available_vcores}).")
            response_lines.append("  · Placement is not possible with the current server configuration.")
        else:
            response_lines.append("  · Capacity is sufficient, but other violations were found.")
        response_lines.append("")

        deduplicated_violations = self._deduplicate_violations(validation_result.violated_rules)
        categorized_violations = categorize_violations(deduplicated_violations)
        
        zero_vcore_pods = self._get_zero_vcore_pods(enhanced_deployment_input.pod_requirements)
        if zero_vcore_pods:
            response_lines.append("ℹ️ **Informational Notes**:")
            response_lines.append("")
            for pod_info in zero_vcore_pods:
                response_lines.append(f"  • Pod {pod_info['pod_type']} has 0.0 vCores - excluded from calculation (pod not available for this deployment)")
            response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['violation']} **Issues Found**:")
        response_lines.append(f"  Total Violations: {len(deduplicated_violations)}")
        response_lines.append("")
        
        for category, violations in categorized_violations.items():
            if violations:
                category_name = category.replace("_", " ").title()
                response_lines.append(f"{self.emoji_map['violation']} **{category_name} Violations**:")
                response_lines.append("")
                for violation in violations:
                    clean_violation = self._clean_violation_message(violation)
                    response_lines.append(f"  • {clean_violation}")
                    response_lines.append("")
                    if "capacity exceeded" in violation.lower():
                        capacity_details = self._extract_capacity_details(violation)
                        if capacity_details:
                            response_lines.append(f"    Calculation: {capacity_details}")
                            response_lines.append("")
                response_lines.append("")

        response_lines.append("Recommendation:")
        if total_required_vcores > net_available_vcores:
            response_lines.append("  Use a higher-capacity server or adjust flavor requirements to meet capacity constraints.")
        else:
            recommendations = self._generate_recommendations(validation_result, enhanced_deployment_input)
            if recommendations:
                for rec in recommendations:
                     response_lines.append(f"  · {rec}")
            else:
                response_lines.append("  Review all deployment parameters and constraints.")
        response_lines.append("")

        response_lines.append(f"{self.emoji_map['warning']} ⚠️  Please address all violations before proceeding with deployment.")
        
        return "\n".join(response_lines)
    
    def _deduplicate_violations(self, violations: List[str]) -> List[str]:
        """Remove duplicate and redundant violations to provide cleaner output."""
        if not violations:
            return []
        
        socket_capacity_issues = []
        server_capacity_issues = []
        rmp_dpp_co_location_issues = []
        rmp_placement_issues = []
        other_violations = []
        
        for violation in violations:
            clean_violation = self._clean_violation_message(violation)
            violation_lower = clean_violation.lower()
            
            if any(skip_phrase in violation_lower for skip_phrase in [
                "unassigned pod", "root cause", "available capacity", "required combined capacity"
            ]):
                continue
            
            if (any(phrase in violation_lower for phrase in [
                "socket capacity constraint violated", "exceeds maximum socket capacity"
            ]) and "dpp pod" in violation_lower):
                socket_capacity_issues.append(clean_violation)
            
            elif ("capacity exceeded" in violation_lower and 
                  "total vcores required" in violation_lower):
                server_capacity_issues.append(clean_violation)
            
            elif "rmp-dpp co-location constraint violated" in violation_lower:
                rmp_dpp_co_location_issues.append(clean_violation)
            
            elif "rmp placement feasibility violated" in violation_lower:
                rmp_placement_issues.append(clean_violation)
            
            else:
                other_violations.append(clean_violation)
        
        deduplicated = []
        
        if socket_capacity_issues:
            socket_capacity_issues.sort(key=len, reverse=True)
            deduplicated.append(socket_capacity_issues[0])
        
        if server_capacity_issues:
            has_socket_issue = any("socket capacity" in v.lower() for v in deduplicated)
            if not has_socket_issue:
                deduplicated.append(server_capacity_issues[0])
        
        if rmp_dpp_co_location_issues:
            deduplicated.append(rmp_dpp_co_location_issues[0])
        
        if rmp_placement_issues:
            deduplicated.append(rmp_placement_issues[0])
        
        for other_violation in other_violations:
            is_duplicate = False
            other_lower = other_violation.lower()
            for existing in deduplicated:
                existing_lower = existing.lower()
                if (any(keyword in other_lower for keyword in ["socket", "capacity", "dpp", "rmp"]) and
                    any(keyword in existing_lower for keyword in ["socket", "capacity", "dpp", "rmp"])):
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduplicated.append(other_violation)
        
        return deduplicated
    
    def _clean_violation_message(self, violation: str) -> str:
        """Clean up violation message for better readability."""
        cleaned = re.sub(r'^[A-Z]\d+:\s*', '', violation)
        cleaned = cleaned.replace("  ", " ").strip()
        return cleaned
    
    def _extract_capacity_details(self, violation: str) -> Optional[str]:
        """Extract detailed capacity calculation from violation message."""
        match = re.search(r'\(Total:\s*(\d+(?:\.\d+)?)\s*-\s*CaaS:\s*(\d+(?:\.\d+)?)\s*-\s*Shared:\s*(\d+(?:\.\d+)?)\s*=\s*Available:\s*(\d+(?:\.\d+)?)\)', violation)
        
        if match:
            total = match.group(1)
            caas = match.group(2)
            shared = match.group(3)
            available = match.group(4)
            
            return f"{total} - {caas} - {shared} = {available}"
        
        return None
    
    def _generate_recommendations(
        self, 
        validation_result: ValidationResult, 
        deployment_input: DeploymentInput
    ) -> List[str]:
        """Generate specific recommendations based on violation types."""
        recommendations = []
        
        violation_categories = categorize_violations(validation_result.violated_rules)
        
        if "capacity" in violation_categories:
            recommendations.append("Consider upgrading server hardware or reducing pod resource requirements")
            recommendations.append("Review CaaS and shared core allocations for optimization")
        
        if "placement" in violation_categories:
            recommendations.append("Check pod placement constraints and anti-affinity requirements")
            recommendations.append("Ensure mandatory pods are included in the deployment")
        
        if "operator_specific" in violation_categories:
            recommendations.append("Review operator-specific requirements and constraints")
            recommendations.append("Verify operator-specific mandatory pods are included")
        
        if "anti_affinity" in violation_categories:
            recommendations.append("Add more servers or sockets to satisfy anti-affinity constraints")
            recommendations.append("Consider disabling HA or in-service upgrade if not required")
        
        if "co_location" in violation_categories:
            recommendations.append("Ensure sufficient capacity on a single socket for co-located pods")
            recommendations.append("Review DirectX2 requirements and pod groupings")
        
        if "validation" in violation_categories:
            recommendations.append("Verify all required input parameters are provided")
            recommendations.append("Check server configuration validity and core conversion ratios")
        
        if len(recommendations) == 0:
            recommendations.append("Review all deployment parameters and constraints")
            recommendations.append("Consult the detailed DR rules documentation for guidance")
        
        return recommendations
    
    def _calculate_utilization_metrics(
        self, 
        socket_assignments: Dict[int, List[Any]], 
        deployment_input: DeploymentInput
    ) -> Dict[str, Any]:
        """Calculate resource utilization metrics."""
        total_vcores_requested = 0
        total_vcores_available = 0
        
        for socket_key, pods in socket_assignments.items():
            server_idx = socket_key // 1000
            server_config = deployment_input.server_configs[server_idx]
            
            for pod in pods:
                total_vcores_requested += pod.vcores * pod.quantity
        
        for server_config in deployment_input.server_configs:
            total_vcores_available += server_config.vcores
        
        utilization_percent = (total_vcores_requested / total_vcores_available * 100) if total_vcores_available > 0 else 0
        
        return {
            "total_vcores_requested": total_vcores_requested,
            "total_vcores_available": total_vcores_available,
            "utilization_percent": utilization_percent
        }
    
    def generate_summary_response(
        self, 
        validation_result: ValidationResult,
        max_violations: int = 5
    ) -> str:
        """Generate a brief summary response."""
        if validation_result.success:
            return f"{self.emoji_map['success']} Deployment validation successful. All rules satisfied."
        else:
            violation_count = len(validation_result.violated_rules)
            if violation_count <= max_violations:
                violations_text = ", ".join(validation_result.violated_rules[:max_violations])
                return f"{self.emoji_map['failure']} Deployment validation failed with {violation_count} violations: {violations_text}"
            else:
                return f"{self.emoji_map['failure']} Deployment validation failed with {violation_count} violations. Too many to list here."
    
    def generate_detailed_report(
        self, 
        validation_result: ValidationResult,
        deployment_input: DeploymentInput
    ) -> Dict[str, Any]:
        """Generate a detailed structured report for programmatic use."""
        report = {
            "validation_summary": {
                "success": validation_result.success,
                "message": validation_result.message,
                "total_violations": len(validation_result.violated_rules)
            },
            "deployment_context": {
                "operator": deployment_input.operator_type.value,
                "vdu_flavor": deployment_input.vdu_flavor_name,
                "server_count": len(deployment_input.server_configs),
                "total_sockets": sum(server.sockets for server in deployment_input.server_configs)
            },
            "feature_flags": {
                "ha_enabled": deployment_input.feature_flags.ha_enabled,
                "in_service_upgrade": deployment_input.feature_flags.in_service_upgrade,
                "vdu_ru_switch_connection": deployment_input.feature_flags.vdu_ru_switch_connection,
                "directx2_required": deployment_input.feature_flags.directx2_required,
                "vcu_deployment_required": deployment_input.feature_flags.vcu_deployment_required
            },
            "violations": {
                "all": validation_result.violated_rules,
                "categorized": categorize_violations(validation_result.violated_rules)
            },
            "recommendations": self._generate_recommendations(validation_result, deployment_input)
        }
        
        if validation_result.success and validation_result.placement_plan:
            report["placement_plan"] = self._format_placement_plan(validation_result.placement_plan)
            report["utilization_metrics"] = self._calculate_utilization_metrics(
                validation_result.placement_plan, deployment_input
            )
        
        return report
    
    def _format_placement_plan(self, socket_assignments: Dict[int, List[Any]]) -> Dict[str, Any]:
        """Format placement plan for structured output."""
        formatted_plan = {}
        
        for socket_key, pods in socket_assignments.items():
            server_idx = socket_key // 1000
            socket_idx = socket_key % 1000
            socket_id = f"server_{server_idx}_socket_{socket_idx}"
            
            formatted_plan[socket_id] = {
                "server_index": server_idx,
                "socket_index": socket_idx,
                "total_vcores": sum(pod.vcores * pod.quantity for pod in pods),
                "pod_count": len(pods),
                "pods": [
                    {
                        "pod_type": pod.pod_type.value,
                        "vcores": pod.vcores,
                        "quantity": pod.quantity
                    }
                    for pod in pods
                ]
            }
        
        return formatted_plan
    
    def _get_zero_vcore_pods(self, pod_requirements: List[PodRequirement]) -> List[Dict[str, Any]]:
        """Get list of pods with 0.0 vCores for informational notes."""
        zero_vcore_pods = []
        
        for pod_req in pod_requirements:
            if pod_req.vcores == 0.0:
                zero_vcore_pods.append({
                    'pod_type': pod_req.pod_type.value,
                    'vcores': pod_req.vcores,
                    'quantity': pod_req.quantity
                })
        
        return zero_vcore_pods

    def generate_comparison_response(
        self,
        original_result: ValidationResult,
        optimized_result: ValidationResult,
        deployment_input: DeploymentInput
    ) -> str:
        """Generate comparison response between original and optimized deployment."""
        response_lines = []
        
        response_lines.append(f"{self.emoji_map['info']} Deployment Optimization Comparison")
        response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['deployment']} Original Deployment:")
        if original_result.success:
            response_lines.append("  Status: ✅ Success")
        else:
            response_lines.append(f"  Status: ❌ Failed ({len(original_result.violated_rules)} violations)")
        response_lines.append("")
        
        response_lines.append(f"{self.emoji_map['deployment']} Optimized Deployment:")
        if optimized_result.success:
            response_lines.append("  Status: ✅ Success")
        else:
            response_lines.append(f"  Status: ❌ Failed ({len(optimized_result.violated_rules)} violations)")
        response_lines.append("")
        
        if not original_result.success and optimized_result.success:
            response_lines.append(f"{self.emoji_map['success']} 🎉 Optimization Successful!")
            response_lines.append("  All violations have been resolved through optimization.")
        elif original_result.success and optimized_result.success:
            response_lines.append(f"{self.emoji_map['info']} Both deployments are valid.")
            if original_result.placement_plan and optimized_result.placement_plan:
                original_metrics = self._calculate_utilization_metrics(original_result.placement_plan, deployment_input)
                optimized_metrics = self._calculate_utilization_metrics(optimized_result.placement_plan, deployment_input)
                
                improvement = optimized_metrics['utilization_percent'] - original_metrics['utilization_percent']
                response_lines.append(f"  Utilization change: {improvement:+.1f}%")
        else:
            response_lines.append(f"{self.emoji_map['warning']} Both deployments have issues.")
            response_lines.append("  Further configuration changes may be needed.")
        
        return "\n".join(response_lines)
