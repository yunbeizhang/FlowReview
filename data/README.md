# Evaluation data

| Folder | Contents |
| --- | --- |
| `permission/` | Governed objects, policies, and agent graphs for permission decisions |
| `assembly/` | Contributor assignments, object segments, composer inputs, and fallback mappings |
| `policy_updates/` | Policy reversals and agent graphs for recovery evaluation |
| `agentdojo/` | Tool schemas, relay inputs, target contracts, and paired benchmark tasks |

Development and confirmation inputs are provided separately. JSONL files are compressed with gzip and read directly by the evaluation code. The tasks use synthetic records and AgentDojo benchmark fixtures.
