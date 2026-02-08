# pod-placement-ai
# Pod Placement AI and Deterministic Rule Engine

## Overview

This repository contains an advanced Pod Placement AI system combined with a Deterministic Rule Engine for optimizing container orchestration and deployment validation. The system leverages artificial intelligence and rule-based decision making to ensure optimal pod placement on Kubernetes clusters while maintaining deployment constraints and resource requirements.

## Features

- **AI-Powered Pod Placement**: Intelligent algorithms for optimal container placement
- **Deterministic Rule Engine**: Consistent rule-based validation and placement decisions
- **Multi-dimensional Pod Flavors**: Support for 25A, 25B, and 26A pod configurations
- **Deployment Validation**: Comprehensive validation suite for deployment safety
- **Capacity Management**: Resource-aware placement strategies
- **Operator Rules**: Support for operational constraints and policies
- **LLM Integration**: Large Language Model response generation and comparison
- **Docker Support**: Containerized deployment with docker-compose

## Project Structure

```
pod-placement-ai/
├── src/
│   ├── core/
│   │   ├── rule_models.py                    # Core rule model definitions
│   │   ├── response_generator.py               # Response generation logic
│   │   ├── calculation_explainer.py           # Explanation of calculations
│   │   ├─│ nettune_backend.py                 # Backend processing logic
│   │   ├─│ nettune_frontend.py                # Frontend UI logic
│   │   └── deployment_validator.py            # Deployment validation
│   ├── rules/
│   │   ├── generated_placement_rules.py       # Generated placement rules
│   │   ├── generated_capacity_rules.py        # Generated capacity rules
│   │   ├── generated_operator_rules.py        # Generated operator rules
│   │   └── generated_validation_rules.py      # Generated validation rules
│   ├── tests/
│   │   └── regression_test_suite.py           # Regression testing
│   └── notebooks/
│       └── podPlacement.ipynb                 # Jupyter notebook for experimentation
├── data/
│   ├── pod_flavors_25A_25B_EU_US.csv     # Pod flavor configurations (US/EU)
│   ├── dimension_flavor_25A_25B_26A.csv # Dimension-based pod configurations
│   ├── dr_rules_rewamped2.txt             # Disaster Recovery rules
│   ├── vdu_rules_questionbank_revamped.txt # VDU rules question bank
│   ├── dr_question_bank2.txt              # Disaster Recovery question bank
│   ├── questions.txt                      # General question bank
│   ├── vdu_dr_rules.json                  # VDU and DR rules in JSON
│   └── LLMResponseComparision.xlsx        # LLM response comparison analysis
├── docs/
│   ├── ARCHITECTURE.md                    # System architecture documentation
│   ├── SYSTEM_IMPLEMENTATION_SUMMARY.md   # Implementation summary
│   └── README.md                          # Additional documentation
├── docker/
│   ├── Dockerfile                         # Container image definition
│   └── docker-compose.yml                 # Multi-container orchestration
├── requirements.txt                    # Python dependencies
├── .gitignore                         # Git ignore rules
└── README.md                          # This file
```

## Components

### Core Modules
- **Rule Models**: Defines the structure and behavior of placement rules
- **Response Generator**: Generates responses based on rule evaluation
- **Calculation Explainer**: Provides transparent explanations for calculations
- **NetTune Backend**: Core processing and orchestration engine
- **NetTune Frontend**: User interface for pod placement management
- **Deployment Validator**: Validates deployments before applying

### Rule Engines
- **Placement Rules**: Determines optimal pod placement locations
- **Capacity Rules**: Manages resource allocation and capacity constraints
- **Operator Rules**: Enforces operational policies and constraints
- **Validation Rules**: Ensures deployment safety and compliance

### Data Files
- Pod flavor specifications for different regions and configurations
- Question banks for disaster recovery and validation
- Disaster recovery and VDU-specific rules
- LLM response comparison data for model evaluation

## Installation

### Prerequisites
- Python 3.8+
- Docker and Docker Compose (optional, for containerized deployment)
- Jupyter Notebook (for notebook exploration)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/asquaree/pod-placement-ai.git
cd pod-placement-ai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Run with Docker:
```bash
docker-compose up
```

## Usage

### Running the System

```python
from src.core import RuleModels, ResponseGenerator
from src.core import DeploymentValidator

# Initialize the system
rule_engine = RuleModels()
validator = DeploymentValidator()

# Process pod placement
placement = rule_engine.compute_placement(pod_specs)
validation_result = validator.validate(placement)
```

### Running Tests

```bash
python -m pytest src/tests/regression_test_suite.py
```

### Using Jupyter Notebook

```bash
jupyter notebook src/notebooks/podPlacement.ipynb
```

## Configuration

The system uses several configuration files:

- **Pod Flavors**: Define available pod configurations in CSV format
- **Rules JSON**: Define rule parameters and constraints
- **Questions**: Question banks for validation and decision-making

## Documentation

Detailed documentation is available in the `docs/` folder:

- **ARCHITECTURE.md**: System architecture and component interactions
- **SYSTEM_IMPLEMENTATION_SUMMARY.md**: Implementation details and technical specifications
- **README.md**: Additional documentation and guides

## Docker Deployment

The system can be deployed using Docker:

```bash
# Build the image
docker build -f docker/Dockerfile -t pod-placement-ai .

# Run with docker-compose
docker-compose -f docker/docker-compose.yml up
```

## Performance

The system includes regression testing to ensure consistent performance:

```bash
python src/tests/regression_test_suite.py
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests as needed
5. Submit a pull request

## License

This project is provided as-is for research and development purposes.

## Support

For questions or issues, please open an issue on the GitHub repository.

## Authors

Original implementation by asquaree

## Changelog

### Version 1.0.0
- Initial release with core Pod Placement AI system
- Deterministic Rule Engine implementation
- Deployment validation framework
- Multi-region pod flavor support
- Docker containerization
