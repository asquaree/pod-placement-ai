"""
Calculation Explainer - Provides detailed breakdown of deployment calculations
Extracts and centralizes calculation logic for use in predictions and responses
"""
from typing import List, Dict, Any, Optional, Tuple
from rule_models import (
    DeploymentInput, ServerConfiguration, PodRequirement, 
    OperatorType, ValidationResult, FeatureFlags, PodType
)
from generated_capacity_rules import (
    get_caas_cores_per_socket, get_shared_cores_per_socket,
    calculate_socket_capacity
)
from generated_operator_rules import get_vcu_vcore_requirements, get_operator_specific_mandatory_pods


class CalculationExplainer:
    """
    Provides detailed explanations of deployment calculations and predictions
    Shows step-by-step breakdown of how required and available vCores are calculated
    """
    
    def __init__(self):
        self.emoji_map = {
            "calculation": "🧮",
            "available": "✅",
            "required": "📋", 
            "result": "🎯",
            "rule": "📋",
            "pod": "📦",
            "server": "🖥️",
            "socket": "🔌",
            "caas": "☁️",
            "shared": "🔄",
            "vcu": "🎛️"
        }
    
    def generate_calculation_explanation(
        self, 
        deployment_input: DeploymentInput,
        prediction_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate comprehensive calculation explanation for deployment prediction
        """
        explanation_lines = []
        
        # Header
        explanation_lines.append(f"{self.emoji_map['calculation']} CALCULATION BREAKDOWN:")
        explanation_lines.append("")
        
        # Server capacity calculation
        server_explanation = self._explain_server_capacity(deployment_input)
        explanation_lines.extend(server_explanation)
        explanation_lines.append("")
        
        # Pod requirements calculation
        pod_explanation = self._explain_pod_requirements(deployment_input)
        explanation_lines.extend(pod_explanation)
        explanation_lines.append("")
        
        # Operator-specific additions
        operator_explanation = self._explain_operator_specific_requirements(deployment_input)
        explanation_lines.extend(operator_explanation)
        explanation_lines.append("")
        
        # Final comparison and result
        result_explanation = self._explain_final_result(deployment_input, prediction_details)
        explanation_lines.extend(result_explanation)
        
        return "\n".join(explanation_lines)
    
    def _explain_server_capacity(self, deployment_input: DeploymentInput) -> List[str]:
        """Explain server capacity calculations"""
        lines = []
        
        # Calculate totals across all servers
        total_pcores = sum(server.pcores for server in deployment_input.server_configs)
        total_vcores = sum(server.vcores for server in deployment_input.server_configs)
        total_sockets = sum(server.sockets for server in deployment_input.server_configs)
        
        lines.append(f"{self.emoji_map['server']} Server Capacity:")
        lines.append(f"   Total pCores: {total_pcores}")
        lines.append(f"   Total vCores: {total_vcores} (pCores × 2)")
        lines.append(f"   Total sockets: {total_sockets}")
        lines.append("")
        
        # Deductions calculation
        caas_per_socket = get_caas_cores_per_socket(deployment_input.operator_type)
        shared_per_socket = get_shared_cores_per_socket(deployment_input.operator_type)
        
        total_caas_deduction = caas_per_socket * total_sockets
        total_shared_deduction = shared_per_socket * total_sockets
        
        lines.append(f"{self.emoji_map['caas']} CaaS Deduction (C3 rule):")
        lines.append(f"   {caas_per_socket} vCores per socket × {total_sockets} sockets = {total_caas_deduction} vCores")
        lines.append("")
        
        lines.append(f"{self.emoji_map['shared']} Shared Core Deduction (C4 rule):")
        lines.append(f"   {shared_per_socket} vCores per socket × {total_sockets} sockets = {total_shared_deduction} vCores")
        lines.append("")
        
        # Net available calculation
        net_available = total_vcores - total_caas_deduction - total_shared_deduction
        
        lines.append(f"{self.emoji_map['available']} Net Available vCores (C1 rule):")
        lines.append(f"   {total_vcores} - {total_caas_deduction} - {total_shared_deduction} = {net_available} vCores")
        
        return lines
    
    def _explain_pod_requirements(self, deployment_input: DeploymentInput) -> List[str]:
        """Explain pod vCore requirements"""
        lines = []
        
        lines.append(f"{self.emoji_map['pod']} Pod vCore Requirements:")
        
        total_base_vcores = 0.0
        
        for pod_req in deployment_input.pod_requirements:
            pod_vcores = pod_req.vcores * pod_req.quantity
            total_base_vcores += pod_vcores
            lines.append(f"   • {pod_req.pod_type.value}: {pod_vcores} vCores")
        
        lines.append(f"   Base pod total: {total_base_vcores} vCores")
        
        return lines
    
    def _explain_operator_specific_requirements(self, deployment_input: DeploymentInput) -> List[str]:
        """Explain operator-specific additions like vCU"""
        lines = []
        
        additions = []
        total_additions = 0.0
        
        # vCU requirements
        if deployment_input.feature_flags.vcu_deployment_required:
            vcu_vcores, vcu_type = get_vcu_vcore_requirements(deployment_input.vdu_flavor_name)
            additions.append(("vCU (O2 rule)", vcu_vcores))
            total_additions += vcu_vcores
        
        # HA requirements (IIP pods)
        if deployment_input.feature_flags.ha_enabled and deployment_input.operator_type == OperatorType.VOS:
            iip_vcores = 4.0  # Standard IIP vCore requirement
            additions.append(("IIP (HA requirement)", iip_vcores))
            total_additions += iip_vcores
        
        if additions:
            lines.append(f"{self.emoji_map['rule']} Operator-Specific Additions:")
            for addition_name, addition_vcores in additions:
                lines.append(f"   • {addition_name}: {addition_vcores} vCores")
            lines.append(f"   Additions total: {total_additions} vCores")
        
        return lines
    
    def _explain_final_result(
        self, 
        deployment_input: DeploymentInput,
        prediction_details: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Explain final comparison result"""
        lines = []
        
        # Calculate totals
        total_base_vcores = sum(pod.vcores * pod.quantity for pod in deployment_input.pod_requirements)
        total_additions = 0.0
        
        if deployment_input.feature_flags.vcu_deployment_required:
            vcu_vcores, _ = get_vcu_vcore_requirements(deployment_input.vdu_flavor_name)
            total_additions += vcu_vcores
        
        if deployment_input.feature_flags.ha_enabled and deployment_input.operator_type == OperatorType.VOS:
            total_additions += 4.0  # IIP vCores
        
        total_required = total_base_vcores + total_additions
        
        # Calculate available
        total_vcores = sum(server.vcores for server in deployment_input.server_configs)
        total_sockets = sum(server.sockets for server in deployment_input.server_configs)
        caas_per_socket = get_caas_cores_per_socket(deployment_input.operator_type)
        shared_per_socket = get_shared_cores_per_socket(deployment_input.operator_type)
        
        total_caas_deduction = caas_per_socket * total_sockets
        total_shared_deduction = shared_per_socket * total_sockets
        total_available = total_vcores - total_caas_deduction - total_shared_deduction
        
        lines.append(f"{self.emoji_map['result']} Final Result:")
        lines.append(f"   Total required vCores: {total_required}")
        lines.append(f"   Total available vCores: {total_available}")
        
        if total_required <= total_available:
            lines.append(f"   Result: {total_required} vCores required ≤ {total_available} vCores available ✓")
        else:
            lines.append(f"   Result: {total_required} vCores required > {total_available} vCores available ✗")
            lines.append(f"   Shortfall: {total_required - total_available} vCores")
        
        return lines
    
    def generate_socket_level_explanation(
        self, 
        deployment_input: DeploymentInput,
        socket_assignments: Optional[Dict[int, List[PodRequirement]]] = None
    ) -> str:
        """
        Generate socket-level capacity explanation for detailed debugging
        """
        lines = []
        lines.append(f"{self.emoji_map['socket']} Socket-Level Capacity Details:")
        lines.append("")
        
        for server_idx, server_config in enumerate(deployment_input.server_configs):
            lines.append(f"   Server {server_idx} ({server_config.pcores} pCores, {server_config.vcores} vCores):")
            
            for socket_idx in range(server_config.sockets):
                capacity_info = calculate_socket_capacity(server_config, socket_idx, deployment_input.operator_type)
                
                lines.append(f"     Socket {socket_idx}:")
                lines.append(f"       Total vCores: {capacity_info['total_vcores']}")
                lines.append(f"       CaaS deduction: {capacity_info['caas_vcores']}")
                lines.append(f"       Shared deduction: {capacity_info['shared_vcores']}")
                lines.append(f"       Available vCores: {capacity_info['available_vcores']}")
                
                if socket_assignments:
                    socket_key = server_idx * 1000 + socket_idx
                    assigned_pods = socket_assignments.get(socket_key, [])
                    if assigned_pods:
                        used_vcores = sum(pod.vcores * pod.quantity for pod in assigned_pods)
                        lines.append(f"       Used vCores: {used_vcores}")
                        lines.append(f"       Remaining vCores: {capacity_info['available_vcores'] - used_vcores}")
                        
                        lines.append(f"       Assigned pods:")
                        for pod in assigned_pods:
                            lines.append(f"         • {pod.pod_type.value}: {pod.vcores} vCores")
                
                lines.append("")
        
        return "\n".join(lines)
    
    def explain_rule_violations(
        self, 
        violated_rules: List[str],
        deployment_input: DeploymentInput
    ) -> str:
        """
        Generate explanations for rule violations with calculation context
        """
        lines = []
        lines.append(f"{self.emoji_map['rule']} Rule Violation Explanations:")
        lines.append("")
        
        for violation in violated_rules:
            lines.append(f"   • {violation}")
            
            # Add specific explanations for common violation types
            if "capacity exceeded" in violation.lower():
                lines.append(f"     Explanation: Total pod requirements exceed available server capacity after deductions")
            elif "socket capacity" in violation.lower():
                lines.append(f"     Explanation: Individual pod too large to fit on any single socket")
            elif "rmp-dpp co-location" in violation.lower():
                lines.append(f"     Explanation: No socket has sufficient capacity for both RMP and DPP pods together")
            elif "mandatory" in violation.lower():
                lines.append(f"     Explanation: Required pod missing from deployment specification")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_prediction_summary(
        self,
        deployment_input: DeploymentInput,
        prediction_success: bool,
        prediction_details: Dict[str, Any]
    ) -> str:
        """
        Generate a comprehensive prediction summary with calculation details
        """
        lines = []
        
        # Basic prediction info
        lines.append(f"📋 PREDICTION: {'SUCCESS' if prediction_success else 'FAILURE'}")
        lines.append(f"   Predicted Required: {prediction_details['total_required_vcores']:.1f} vCores")
        lines.append(f"   Predicted Available: {prediction_details['total_available_vcores']:.1f} vCores")
        lines.append("")
        
        # Add detailed calculation explanation
        calculation_explanation = self.generate_calculation_explanation(deployment_input, prediction_details)
        lines.append(calculation_explanation)
        
        # Add socket-level details if available
        if 'socket_capacity_ok' in prediction_details:
            lines.append("")
            if not prediction_details['socket_capacity_ok']:
                lines.append(f"{self.emoji_map['socket']} Socket Capacity Issues:")
                lines.append("   One or more pods exceed maximum socket capacity")
                lines.append("")
        
        # Add constraint violations if any
        if not prediction_success:
            violations = []
            
            if not prediction_details.get('socket_capacity_ok', True):
                violations.append("Socket capacity constraints")
            if not prediction_details.get('rmp_dpp_co_location_ok', True):
                violations.append("RMP-DPP co-location constraints")
            if not prediction_details.get('total_capacity_check', True):
                violations.append("Total capacity constraints")
            
            if violations:
                lines.append(f"{self.emoji_map['rule']} Constraint Violations:")
                for violation in violations:
                    lines.append(f"   • {violation}")
                lines.append("")
        
        return "\n".join(lines)
