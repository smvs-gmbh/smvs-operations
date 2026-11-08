# OpenAI search foundation

Two workflows share the OpenAI Responses transport. Enable them in the portal
environment with an `OPENAI_API_KEY` and the model setting for each workflow.

| Workflow | Model setting | Data sent to OpenAI | Portal action |
| --- | --- | --- | --- |
| Local Exceptions search | `OPENAI_SEARCH_MODEL` | The question entered by the operator | Review allowlisted filters, then open the existing read-only Exceptions results. |
| Public company research | `OPENAI_WEB_MODEL` | Company name and domain | Review a sourced draft in the MAH Company summary editor. Saving uses the existing section update. |

Use a model that supports strict structured outputs for the local workflow and a
model that supports the Responses web search tool for company research. Each
workflow is opt-in through an explicit UI action and requests `store: false`.
The local workflow runs its database query after operator confirmation. Model
output is validated and mapped to existing server-side filters. The browser
shows source links during summary review. The current save flow retains the
summary text and company size. Persisting the draft's sources and generation
date is follow-up work.

The internal role guards continue to protect both workflows. Add further
read-only capabilities as explicit functions with input schemas and bounded
results. An agent can coordinate those functions later for a specific workflow
that genuinely requires several steps. Keep state changes behind explicit
review actions.
