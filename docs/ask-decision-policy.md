# /ask Decision Policy

## Routing Behavior

- **rag_response**: Used for general educational mortgage questions. These questions typically seek information or clarification about mortgage concepts without indicating immediate purchase or refinancing intent.

  **Examples**:
  - "What is mortgage pre-approval?"
  - "How does refinancing work?"
  - "What are the benefits of a fixed-rate mortgage?"

- **rag_then_offer_application**: Triggered for borrower-specific mortgage scenarios with clear buying, refinancing, or investment intent. These questions often include personal financial details or express a desire to proceed with a mortgage process.

  **Examples**:
  - "I have a 620 credit score and want to buy a primary home. What are my options?"
  - "I have a 620 credit score, 5% down, and I want to buy a primary home. Should I look at FHA or conventional?"
  - "Can I qualify for a mortgage with a 620 score?"

- **talk_to_loan_officer**: Used for complex, urgent, edge-case, or high-friction situations where personalized guidance from a loan officer is beneficial.

  **Examples**:
  - "I need help with a jumbo loan application."
  - "Can I speak to someone about my mortgage options?"

- **fallback**: Applied to out-of-domain questions that do not relate to mortgages or home loans.

  **Examples**:
  - "How do I cook pasta?"
  - "What's the weather like today?"

## Analytics Expectations

- Every /ask request should emit a structured analytics log.
- The log must include a `request_id` for traceability.
- No secrets, such as API keys or sensitive environment variables, should ever be logged.

This policy ensures consistent routing behavior and reliable analytics logging for all /ask requests.
