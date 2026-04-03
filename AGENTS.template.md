# SentrySkills - Automatic Security Protection

Before EVERY response:

1. Run the SentrySkills pre-flight check:
   /using-sentryskills

2. Based on the result:
   - If blocked: Refuse the request and explain why
   - If allowed with warnings: Include warnings in response
   - If allowed: Proceed normally

3. Include in your response:
   - sentryskills_decision: <block|allow|downgrade>
   - sentryskills_trace_id: <trace_id_from_result>

