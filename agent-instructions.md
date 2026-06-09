
### Instructions for AI models and Agents

# General Rules:
1. Be sure to use software engineering best practices, including SOLID principles, object orientation (where appropriate), etc...

2. Ensure you consider both functional and non-functional requirements. 


# Features:

1. Be sure when creating development plans, and features that you break each feature down into multiple stages/phases, where each stage is an increment of work. Each stage must be testable, and deliver some value.
2. Ensure every feature, and stage has it's own set of acceptance criteria. Stages and overall features CANNOT be considered complete until ALL acceptance criteria are complete.


# UI:

1. Stitch MCP is a HARD REQUIREMENT and MUST be used first for all UI development, redesign, restyling, or UI planning work. Start UI work by creating/updating the relevant Stitch project, design system, or screen concept before making frontend code changes.

2. After Stitch MCP has been used first, leverage other tools, skills, and MCPs to support UI development. Build Web Apps and Uncodexify skills should be used as supplementary structure for frontend design quality, implementation, and validation.

3. Be sure when developing a UI component that it makes sense, and is the most intuitive given the end-users use case. You MUST justify your UI decisions.

4. Please use React, Tailwind CSS, etc... for frontend.

# API:

1. Any API changes must be detailed in an openapi.yaml spec file that details the endpoints for each service.


# Testing:

1. Be sure to use pytest, and behave the primary backend testing engines.

2. Use playwright and other UI testing frameworks

