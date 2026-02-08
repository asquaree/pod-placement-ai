# NetTune AI Pod Placement Assistant

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage](#usage)
6. [API Documentation](#api-documentation)
7. [Data Models](#data-models)
8. [Rules Engine](#rules-engine)
9. [Configuration](#configuration)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)
12. [Contributing](#contributing)
13. [License](#license)

## Overview

NetTune AI Pod Placement Assistant is an intelligent system designed to optimize and validate pod placements for vDU (virtualized Distributed Unit) deployments in telecommunications networks. The system ensures that pod deployments comply with complex deterministic rules while maximizing resource utilization and meeting operator-specific requirements.

The application provides:
- Automated pod placement validation against comprehensive DR (Deployment Rules)
- Multi-operator support (VOS, Verizon, Boost)
- Resource optimization recommendations
- Detailed violation analysis and reporting
- Support for advanced features like HA (High Availability) and in-service upgrades

## Key Features

### Pod Placement Validation
- Validates pod deployments against comprehensive DR rules
- Checks capacity constraints (C1-C4 rules)
- Enforces placement constraints (M1-M4 rules)
- Verifies operator-specific requirements (O1-O4 rules)
- Performs final validation (V1-V3 rules)

### Multi-Operator Support
- **VOS**: Full support with IPP mandatory, vCU deployment, DirectX2 co-location
- **Verizon**: Custom server configurations and constraints
- **Boost**: Specialized placement rules

### Advanced Features
- **High Availability (HA)**: Anti-affinity constraints for CMP pods
- **In-Service Upgrade**: DPP pod separation requirements
- **vDU-RU Switch Connection**: Special RMP placement rules
- **DirectX2 Co-location**: Mandatory pod grouping requirements
- **vCU Deployment**: Automatic vCU pod inclusion with flavor-specific vCores

### Resource Optimization
- Detailed resource utilization metrics
- Capacity violation analysis
- Optimization recommendations
- Socket-level placement planning

### Comprehensive Reporting
- Human-readable validation responses
- Categorized violation reporting
- Detailed placement plans
- Utilization metrics and recommendations

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NetTune AI Backend                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  DataProcessor  │  │  QueryProcessor │  │ ResponseProcessor   │ │
│  │                 │  │                 │  │                     │ │
│  │ - Loads CSVs    │  │ - Parses queries│  │ - Formats responses │ │
│  │ - Preprocessing │  │ - Field matching│  │ - Context creation  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Deployment Validator                         ││
│  │                                                                 ││
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ ││
│  │  │ Capacity Rules  │  │Placement Rules  │  │Operator Rules   │ ││
│  │  │ (C1-C4)         │  │ (M1-M4)         │  │ (O1-O4)         │ ││
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ ││
│  │  ┌─────────────────┐  ┌─────────────────┐                      ││
│  │  │Validation Rules │  │ DR Rules Parser │                      ││
│  │  │ (V1-V3)         │  │                 │                      ││
│  │  └─────────────────┘  └─────────────────┘                      ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Response Generator                           ││
│  │                                                                 ││
│  │  - Human-readable responses                                     ││
│  │  - Violation categorization                                     ││
│  │  - Resource utilization metrics                                 ││
│  │  - Optimization recommendations                                 ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌─────────▼─────────┐   ┌─────▼──────┐
│  CSV Data     │   │  DR Rules JSON    │   │ User Query │
│  Sources      │   │                   │   │            │
│               │   │                   │   │            │
│ - Dimensioning│   │ - Capacity rules  │   │            │
│ - Pod Flavors │   │ - Placement rules │   │            │
│               │   │ - Operator rules  │   │            │
│               │   │ - Validation rules│   │            │
└───────────────┘   │                   │   └────────────┘
                    └───────────────────┘
```

### Core Components

1. **NetTuneBackend**: Main service orchestrator handling data processing, query routing, and validation
2. **DataProcessor**: Loads and preprocesses CSV data for dimensioning and pod flavors
3. **QueryProcessor**: Parses natural language queries and extracts field criteria
4. **DeploymentValidator**: Validates deployments against all DR rules in proper order
5. **ResponseGenerator**: Creates human-readable responses with detailed metrics
6. **DRRulesParser**: Parses and provides access to deterministic rules configuration

### Data Flow

1. User submits query with deployment parameters
2. QueryProcessor parses and extracts relevant fields
3. DataProcessor retrieves matching dimensioning and pod flavor data
4. DeploymentValidator validates deployment against all applicable rules
5. ResponseGenerator creates comprehensive human-readable report
6. Results returned to user with detailed analysis and recommendations

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Git (for cloning repository)

### Dependencies

The application requires the following Python packages:
- pandas
- json
- logging
- typing
- re
- dataclasses
- enum

### Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd PodPlacement
   ```

2. Install required dependencies:
   ```bash
   pip install pandas
   ```

3. Verify data files are present:
   - `dimension_flavor_25A_25B_26A.csv` - Dimensioning data
   - `pod_flavors_25A_25B_EU_US.csv` - Pod flavor specifications
   - `vdu_dr_rules.2.json` - Deterministic rules configuration

4. Run the application:
   ```bash
   python nettune_backend.py
   ```

## Usage

### Basic Usage

The NetTune AI Pod Placement Assistant can be used to validate pod deployments for different operators and configurations.

Example query:
```
Validate pod placement for VOS operator with flavor "medium-regular-spr-t23" on a 1-server configuration with 48 vCores
```

### API Usage

The system provides a programmatic interface through the `NetTuneBackend` class:

```python
from nettune_backend import get_backend

# Initialize backend
backend = get_backend()
backend.initialize()

# Process query
result = backend.process_query(
    question="Validate pod placement for VOS operator with flavor medium-regular-spr-t23",
    qa_history=[]
)

# Access results
if result["status"] == "success":
    print(result["response"])
else:
    print(f"Error: {result['message']}")
```

### Feature Flags

The system supports several feature flags that affect validation:

- `ha_enabled`: Enable High Availability constraints
- `in_service_upgrade`: Enable in-service upgrade constraints
- `vdu_ru_switch_connection`: Enable vDU-RU switch connection mode
- `directx2_required`: Enable DirectX2 co-location requirements
- `vcu_deployment_required`: Require vCU pod deployment

Example with feature flags:
```
Validate pod placement for VOS operator with flavor "medium-regular-spr-t23" and ha_enabled=true
```

### Supported Operators

1. **VOS**
   - Mandatory IPP pod
   - vCU deployment support
   - DirectX2 co-location rules
   - Special flavor handling

2. **Verizon**
   - Custom server configurations
   - Specific placement constraints

3. **Boost**
   - Operator-specific rules
   - Custom resource requirements

### Example Queries

1. **Basic Validation**:
   ```
   Validate pod placement for VOS operator with flavor "medium-regular-spr-t23"
   ```

2. **With Server Configuration**:
   ```
   Validate pod placement for VOS operator with flavor "medium-regular-spr-t23" on 1 server with 48 vCores
   ```

3. **With Feature Flags**:
   ```
   Validate pod placement for VOS operator with flavor "medium-regular-spr-t23" and ha_enabled=true
   ```

4. **Dimensioning Query**:
   ```
   Extract dimensioning information for operator=VOS and Dimensioning Flavor="medium-regular-spr-t23"
   ```

5. **Resource Information**:
   ```
   Give information about all the resources one by one sequentially for all the pod flavors
   ```

## API Documentation

### NetTuneBackend Class

Main entry point for the NetTune AI Pod Placement system.

#### Methods

##### `initialize()`
Initializes the backend service by loading data and setting up processors.

**Returns**: 
```python
{
    "status": "success"|"error",
    "message": str,
    "data_loaded": {
        "dimensioning_records": int,
        "pod_flavor_records": int
    }
}
```

##### `process_query(question: str, qa_history: List[Tuple[str, str]], df_result: Optional[Dict] = None)`
Processes user query and returns validation results.

**Parameters**:
- `question`: User query string
- `qa_history`: List of previous question-answer pairs
- `df_result`: Optional preprocessed dimensioning data

**Returns**:
```python
{
    "status": "success"|"error",
    "response": str,
    "context_source": str,
    "is_direct": bool,
    "preprocess_data": bool,
    "new_df_result": Optional[Dict]
}
```

##### `get_status()`
Returns backend status information.

**Returns**:
```python
{
    "initialized": bool,
    "data_records": {
        "dimensioning": int,
        "pod_flavors": int
    }
}
```

##### `reset_session()`
Resets session data.

**Returns**:
```python
{
    "status": "success",
    "message": "Session reset successfully"
}
```

### DeploymentValidator Class

Validates deployments against all DR rules.

#### Methods

##### `validate_deployment(deployment_input: DeploymentInput, generate_placement_plan: bool = True)`
Validates deployment and optionally generates placement plan.

**Parameters**:
- `deployment_input`: DeploymentInput object with all parameters
- `generate_placement_plan`: Whether to generate socket assignments

**Returns**: ValidationResult object

### ResponseGenerator Class

Generates human-readable responses from validation results.

#### Methods

##### `generate_validation_response(validation_result: ValidationResult, deployment_input: DeploymentInput, include_detailed_metrics: bool = True)`
Generates comprehensive validation response.

**Parameters**:
- `validation_result`: ValidationResult from DeploymentValidator
- `deployment_input`: Original deployment input
- `include_detailed_metrics`: Whether to include resource metrics

**Returns**: Formatted string response

## Data Models

### Core Data Structures

#### OperatorType (Enum)
```python
class OperatorType(Enum):
    VOS = "VOS"
    VERIZON = "Verizon" 
    BOOST = "Boost"
```

#### PodType (Enum)
```python
class PodType(Enum):
    # Mandatory pods
    DPP = "DPP"  # Data Plane Pod
    DIP = "DIP"  # Data Interface Pod
    RMP = "RMP"  # Radio Management Pod
    CMP = "CMP"  # Control Management Pod
    DMP = "DMP"  # Data Management Pod
    PMP = "PMP"  # Platform Management Pod
    
    # Optional pods
    IPP = "IPP"  # Interface Processing Pod
    IIP = "IIP"  # Internal Interface Pod
    UPP = "UPP"  # User Plane Pod
    CSP = "CSP"  # Control Signaling Pod
    VCU = "vCU"  # Virtualized Control Unit
```

#### ServerConfiguration
```python
@dataclass
class ServerConfiguration:
    pcores: int                    # Physical cores
    vcores: int                    # Virtual cores
    sockets: int                   # Number of sockets
    pcores_per_socket: Optional[int]  # Physical cores per socket
    description: Optional[str]     # Optional description
```

#### PodRequirement
```python
@dataclass
class PodRequirement:
    pod_type: PodType              # Type of pod
    vcores: float                  # Required vCores
    quantity: int = 1              # Number of instances
    socket_affinity: Optional[int] # Required socket
    anti_affinity: bool = False    # Cannot be on same socket
    co_location_required: List[PodType] = field(default_factory=list)  # Must be colocated
```

#### FeatureFlags
```python
@dataclass
class FeatureFlags:
    ha_enabled: bool = False              # High Availability
    in_service_upgrade: bool = False      # In-service upgrade
    vdu_ru_switch_connection: bool = False # vDU-RU switch connection
    directx2_required: bool = False       # DirectX2 co-location
    vcu_deployment_required: bool = False # vCU deployment
```

#### DeploymentInput
```python
@dataclass
class DeploymentInput:
    operator_type: OperatorType           # Target operator
    vdu_flavor_name: str                  # vDU flavor
    pod_requirements: List[PodRequirement] # Pod requirements
    server_configs: List[ServerConfiguration] # Server configurations
    feature_flags: FeatureFlags           # Feature flags
    number_of_servers: int = field(init=False) # Derived field
```

#### ValidationResult
```python
@dataclass
class ValidationResult:
    success: bool                         # Validation result
    message: str                          # Summary message
    violated_rules: List[str] = field(default_factory=list)  # Violated rules
    placement_plan: Optional[Dict[str, Any]] = None  # Socket assignments
```

## Rules Engine

The NetTune AI Pod Placement system implements a comprehensive Deterministic Rules (DR) engine that validates deployments against a set of predefined rules.

### Rule Categories

#### Capacity Calculation Rules (C1-C4)
- **C1**: Total pod vCores must not exceed available capacity
- **C2**: Core conversion ratio (1 pCore = 2 vCores)
- **C3**: CaaS (Container-as-a-Service) core allocation per operator
- **C4**: Shared core allocation per operator

#### Placement Rules (M1-M4)
- **M1**: Mandatory pods must be placed (DPP, DIP, RMP, CMP, DMP, PMP)
- **M2**: In-service upgrade requires DPP pods on different sockets
- **M3**: HA requires CMP pods on different sockets
- **M4**: Anti-affinity constraints for specific pod types

#### Operator-Specific Rules (O1-O4)
- **O1**: Operator-specific mandatory pods (e.g., IPP for VOS)
- **O2**: vCU deployment requirements
- **O3**: Special vDU flavors that automatically include IIP
- **O4**: DirectX2 co-location requirements

#### Validation Rules (V1-V3)
- **V1**: Input parameter validation
- **V2**: Server configuration validation
- **V3**: Deployment input validation

### Rule Processing Order

1. **V3**: Input validation
2. **C1-C4**: Capacity validation
3. **M1-M4**: Placement validation
4. **O1-O4**: Operator-specific validation
5. **V1-V2**: Final validation

### Violation Handling

The system categorizes violations and provides detailed explanations:
- **Capacity Violations**: Resource constraints exceeded
- **Placement Violations**: Pod placement constraints violated
- **Operator Violations**: Operator-specific requirements not met
- **Validation Violations**: Input or configuration errors

## Configuration

### Data Sources

#### Dimensioning Data (dimension_flavor_25A_25B_26A.csv)
Contains operator-specific dimensioning information:
- Operator
- Network Function
- Dimensioning Flavor
- Package
- Pod mappings (DPP, DIP, DMP, CMP, PMP, RMP, IPP)

#### Pod Flavors (pod_flavors_25A_25B_EU_US.csv)
Contains detailed pod resource specifications:
- Pod type
- Pod flavor
- vCPU Request (vCore)
- vCPU Limit (vCore)
- vMemory (GB)
- Hugepage (GB)
- Persistent Volume (GB)

#### DR Rules (vdu_dr_rules.2.json)
JSON configuration file containing all deterministic rules:
- Capacity calculation rules
- Placement constraints
- Operator-specific requirements
- Validation criteria
- Server configurations

### Feature Configuration

Feature flags can be enabled through natural language queries:
- `ha_enabled=true`
- `in_service_upgrade=true`
- `directx2_required=true`
- `vcu_deployment_required=true`

### Server Configuration

Supported server configurations vary by operator:
- **VOS**: Flexible server configurations
- **Verizon**: Specific pCore/vCore ratios
- **Boost**: Custom resource allocations

## Testing

### Test Suite

The application includes a comprehensive test suite:

#### Unit Tests
- `test_backend_integration.py`: Backend integration tests
- `test_rule_engine.py`: Rules engine validation
- `test_vcu_addition.py`: vCU deployment tests
- `test_fix_verification.py`: Fix verification tests
- `test_failure_scenarios.py`: Failure scenario tests
- `test_improved_response.py`: Response generation tests

#### Regression Tests
- `regression_test_suite.py`: Comprehensive regression testing
- `verify_ha_tests.py`: High Availability constraint tests

### Running Tests

To run the test suite:
```bash
python -m pytest test_*.py
```

Or run specific test files:
```bash
python test_backend_integration.py
python regression_test_suite.py
```

### Test Coverage

The test suite covers:
- Data processing and parsing
- Rule validation logic
- Edge cases and error conditions
- Feature flag combinations
- Multi-operator scenarios
- Capacity constraint violations
- Placement constraint violations

## Troubleshooting

### Common Issues

#### Initialization Errors
**Problem**: Backend fails to initialize
**Solution**: Verify all CSV files and JSON rules are present in the correct locations

#### Data Loading Failures
**Problem**: CSV files not found or corrupted
**Solution**: Check file paths and ensure files have correct format and required columns

#### Rule Validation Failures
**Problem**: DR rules file missing or invalid
**Solution**: Verify `vdu_dr_rules.2.json` exists and is valid JSON

#### Capacity Violations
**Problem**: Deployment rejected due to insufficient resources
**Solution**: 
- Check server configuration has sufficient vCores
- Consider disabling non-essential feature flags
- Review pod requirements for optimization opportunities

#### Placement Constraint Violations
**Problem**: Anti-affinity or co-location constraints violated
**Solution**:
- Add more servers or sockets
- Review feature flag combinations
- Check mandatory pod requirements

### Debugging Guide

1. **Check Logs**: Enable detailed logging to see processing steps
2. **Validate Inputs**: Ensure all required parameters are provided
3. **Verify Data**: Confirm CSV files contain expected data
4. **Test Rules**: Validate DR rules configuration is correct
5. **Review Violations**: Examine specific rule violations for root causes

### Performance Considerations

- Large CSV files may increase initialization time
- Complex rule combinations may affect validation speed
- Multiple servers/sockets increase placement planning complexity

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Code Style

- Follow PEP 8 Python style guide
- Use descriptive variable and function names
- Include docstrings for all functions and classes
- Write clear, concise comments
- Maintain consistent formatting

### Testing Requirements

- Add unit tests for new features
- Ensure existing tests continue to pass
- Include edge case testing
- Document test scenarios

### Pull Request Process

1. Ensure branch is up to date with main
2. Include clear description of changes
3. Reference any related issues
4. Wait for code review and CI checks
5. Address feedback before merging

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

NetTune AI Pod Placement Assistant is developed and maintained by Samsung Research.

### Contributors
- Development team at Samsung Research
- Telecommunications domain experts
- AI/ML research team

### Acknowledgments
- Thanks to all contributors who have helped shape this project
- Special recognition to the telecommunications engineering community
- Appreciation for open source tools and libraries that made this project possible

### References
- 3GPP specifications for vDU deployments
- Kubernetes resource management documentation
- Telecommunications network architecture guidelines
