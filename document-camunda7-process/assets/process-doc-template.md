<!--
  camunda-process-docs output template.
  Fill EVERY section thoroughly. Delete bracketed guidance. Keep headings stable
  so re-runs produce clean diffs. Write for business readers first; put
  technical detail in the clearly-marked technical fields. Be thorough, not
  terse — this document should let a reader fully understand the process without
  opening the model or the code.
-->
# Process: [Process Name]

> **Process key:** `[process id]` · **File:** `[relative/path.bpmn]` · **Executable:** [yes/no] · **Version tag:** [if any]
> _Last documented: [YYYY-MM-DD] · Generated with the camunda-process-docs skill._

## 1. Summary

[Write an EXTENSIVE summary — several paragraphs, not a couple of sentences:]

- **What the process does:** the business outcome it produces and for whom.
- **Why it exists:** the problem it solves and the business capability it serves.
- **End-to-end narrative:** walk the happy path in plain language from trigger to
  outcome, naming each major step and the decisions along the way, so a reader
  grasps the whole flow before the detailed catalogue.
- **Main variants / alternative outcomes:** the significant branches (e.g.
  approved vs. declined, manual review, error/timeout paths) and when each occurs.
- **Actors involved:** the people, roles, systems and external parties that
  participate.
- **Key systems & decisions:** the important integrations, DMN decisions and
  sub-processes the flow relies on.

## 2. Intention & business context

[The deeper context: the business goal, constraints and rules that shaped the
design, relevant SLAs/deadlines/compliance requirements (timers, due dates), and
how this process fits into the wider landscape (upstream triggers, downstream
consumers).]

## 3. Trigger & start conditions

[How instances begin: start event type (none/message/timer/signal), the message
name or schedule, who or what initiates it, and the data expected at start
(initial process variables and their meaning).]

## 4. Activity catalogue

[One subsection per activity, in process order. Describe EACH activity in depth —
do not abbreviate. Use the structure below for every item.]

### 4.x [Activity name] — `[id]`

- **Type:** [user task / service task (external|class|delegate|expression) / business rule task / call activity / script task / send/receive / sub-process …]
- **Purpose (business):** [a full paragraph: what this step accomplishes for the
  business and why it is here.]
- **Detailed description:** [a thorough, step-by-step account of what happens in
  this activity: preconditions (what must be true to reach it), what it does
  while running, the data it consumes and produces, postconditions, and how it
  hands off to the next step. Several sentences minimum.]
- **Implementation:** [the exact binding — external topic `x`, class `com.…`,
  bean `${…}`, DMN key, called process key, script, form key.]
- **Implementation analysis:** [WHAT THE CODE ACTUALLY DOES — summarise the
  worker / delegate / bean method / DMN table / called process found in the
  codebase in detail: key steps, branching, external calls, side effects,
  retries, and the errors it can throw. Reference the real file(s).]
- **Inputs / outputs:** [process variables read and written, from IO mapping AND
  the implementation, with their meaning.]
- **Async / listeners / multi-instance:** [asyncBefore/After save points;
  execution & task listeners and exactly what they do; multi-instance
  collection/cardinality and what one iteration represents.]
- **Source:** `[path(s) to the implementation file(s)]`

#### User interface  *(include this block for USER TASKS only — describe the UI precisely)*

- **Form / UI located at:** `[exact file or route found in the codebase]`
  [embedded form HTML, Camunda Forms `.form` JSON, or an external SPA route/
  component — e.g. an Angular component. State how you found it from the form key
  or task, and note if it could not be located.]
- **UI type & layout:** [embedded form / Camunda Form / custom SPA screen;
  sections, tabs, grouping, overall structure of the screen.]
- **Fields:** describe every field in a table.

  | Field (label) | UI control | Bound variable | Required | Validation / options | Notes |
  |---|---|---|---|---|---|
  | [label] | [text/select/date/checkbox/…] | [process var] | [yes/no] | [rules, allowed values] | [read-only, prefilled, conditional] |

- **Actions / buttons:** [each button and what it does — which outcome/variable
  it sets, whether it completes/claims/saves the task, navigation.]
- **Conditional behaviour:** [fields or sections shown/hidden/required based on
  data or role; dynamic options.]
- **Assignment & access:** [candidate groups/users, assignee, due/follow-up date,
  priority — who sees and works this screen.]
- **Data binding:** [how form fields map to process variables in and out.]

## 5. Routing & decisions

[Each gateway: type, the question it answers, and EVERY outgoing path with its
condition expression translated into plain language; note the default flow. For
business rule tasks, summarise the DMN decision: inputs, outputs, hit policy and
the notable rules in business terms.]

## 6. Events & exception handling

[Boundary events (error/timer/message/signal) and what they catch, the
end-event outcomes (normal vs. error end), escalations, compensation. Explain in
detail what happens to an instance on each failure or timeout path.]

## 7. Data & variables

| Variable | Type/shape | Written by | Read by | Meaning |
|----------|------------|-----------|---------|---------|
| [name]   | [type]     | [activity] | [activity] | [business meaning] |

## 8. Integrations & dependencies

[External systems, services, queues/topics, DMN decisions, called sub-processes
(link to their docs), forms/UIs, and message flows to other pools. One bullet per
dependency with direction (in/out) and purpose.]

## 9. Operational notes

[History TTL, job priorities, async save points, retries/incidents to expect,
idempotency considerations, and anything an operator should know to support this
process.]

## 10. Open questions / gaps

[Anything the model references but whose implementation could not be located,
ambiguous conditions, or TODOs for a human to confirm. Preserve human-added notes
here across re-runs.]
