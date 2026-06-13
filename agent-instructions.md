
### Instructions for AI models and Agents

# General Rules:
1. Be sure to use software engineering best practices, including SOLID principles, object orientation (where appropriate), etc...

2. Ensure you consider both functional and non-functional requirements. 

3. Continually refactor code to be best understood by humans. This means small components, functions, objects where possible. This also means code is appropriately structured in the correct directories. If things get messy, please abstract functionality out and create new directories, objects, and helpers where necessary. This is a HARD requirement to ensure the code base is maintainable.

4. Use Context7 MCP for understanding best practices for a given library/technology.

5. Use all tools, plugins, and MCPs available as needed.


# Features:

1. All features must have documents detailing the effort. Feature documents should be named according to convention. The filename must have at least 4 numbers, followed by the feature name. This enables correct ordering in how features will be developed.

2. When creating feature documents, ensure you include a header with the following information:
    - A feature number such as "F0001". This should be in the header of the document.
    - A feature description.
    - A summary of the feature.
    - A summary on the value it will provide
    - the estimated development effort in story points (0.5, 1, 3, 5, or 8). Assume that 8 is reserved ONLY for large features that absolutely cannot be broken up. 8 should be extremely rare.
    - dependencies on other features. (ex: Dependencies: F0002, F0007, F0014)
    - Sample use cases of how the feature will be used.
    - Assumptions being made

3. Be sure when creating development plans, and features that you break each feature down into multiple stages/phases, where each stage is an increment of work. Each stage must be testable, and deliver some value.

4. Ensure every feature, and stage has it's own set of acceptance criteria, dependency callouts, and effort/scope sizing. Stages and overall features CANNOT be considered complete until ALL acceptance criteria are complete.

5. When developing a feature, be sure to create a new branch (in git) for that feature. The branch name should include the feature number and a short title (ex: F0049-add-signal-page). On completion, create commit to the feature branch with a meaningful commit message.

6. All feature documents should also include diagrams when necessary. While this may be further appropriate for architecture plans, be sure to use them when valuable in feature documents.

7. When completing a feature, be sure to callout any corner-cases, misses, or areas that couldn't be complete (if at all).


# UI:

1. Stitch MCP is a HARD REQUIREMENT and MUST be used first for all UI development, redesign, restyling, or UI planning work. Start UI work by creating/updating the relevant Stitch project, design system, or screen concept before making frontend code changes.

2. After Stitch MCP has been used first, leverage other tools, skills, and MCPs to support UI development. Build Web Apps and Uncodexify skills should be used as supplementary structure for frontend design quality, implementation, and validation.

3. Be sure when developing a UI component that it makes sense, and is the most intuitive given the end-users use case. You MUST justify your UI decisions.

4. Please use React, Tailwind CSS, etc... for frontend.

# API:

1. Any API changes must be detailed in the owning service OpenAPI spec under `platform/docs/api/`. Each service/API has its own independent spec, such as `bff.openapi.yaml`, `c2.openapi.yaml`, `beacon-handler.openapi.yaml`, or `scanner.openapi.yaml`.


# Testing:

1. Be sure to use pytest, and behave the primary backend testing engines.

2. Use playwright and other UI testing frameworks.


# On Completion:

1. After completing development, testing, and running validations - be sure we rebuild the project. This may mean rebuilding the docker container and redeploying it on the stack.
