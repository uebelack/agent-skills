---
name: document-camunda7-process
description: "Generate or update detailed, business-readable documentation for a BPMN / Camunda 7 process from its .bpmn file. Use this skill whenever the user wants to document a BPMN process, asks to 'document this process', mentions a .bpmn file, a Camunda 7 process, a process definition, a workflow model, or asks what a process does or how a process works — even if they don't say the word 'documentation'. The skill parses the BPMN, analyses each activity's actual implementation in the codebase (delegates, external-task workers, DMN decisions, called processes, forms), and writes a Markdown file under doc/processes/ named after the process. Always use this skill for BPMN/Camunda 7 process documentation instead of reading the XML by hand."
---

# Camunda Process Documentation

Produce a complete, business-readable document for a single BPMN/Camunda
process, grounded in both the model **and** the real implementation behind each
activity. The reader should understand what the process achieves and how each
step actually behaves, without reading code or XML.

## Input

The user provides the **filename of the process to document** (a `.bpmn` file).
If they give only a process name or partial filename, search the repository for
the matching `.bpmn` (look for a `process` element whose `id` or `name` matches).
If several match, list them and ask which one.

## Output

A single Markdown file at **`doc/processes/<BpmnFilename>.md`**, where
`<BpmnFilename>` is the exact name of the source `.bpmn` file with its
extension replaced by `.md` (e.g. `loan-application.bpmn` →
`loan-application.md`).

- **Create** the file (and the `doc/processes/` directory) if absent.
- **Update** it in place if it exists: regenerate the content but preserve the
  stable section headings so the diff is clean, and carry over any human-written
  notes you find under "Open questions / gaps". Mention to the user that you
  updated an existing file.

Use `assets/process-doc-template.md` as the exact skeleton. Keep its headings.

## Workflow

### 1. Locate and parse the BPMN

Run the parser (deterministic — do **not** hand-read the XML):

```bash
python3 scripts/parse_bpmn.py <path-to.bpmn> --out /tmp/bpmn.json
```

Read `/tmp/bpmn.json`. It contains, per process: metadata, lanes, every flow
node with its Camunda `implementation` bindings, IO mappings, listeners, event
definitions, multi-instance, all sequence flows with conditions, data objects,
plus collaboration pools/message flows and resolved message/signal/error names.
If the file defines several processes, document the one the user asked for (or
the executable one); offer to document the others.

### 2. Understand the process as a whole and write an extensive summary

From the structure (start trigger, the path of activities, gateways, end
events) and the process `documentation`, work out the business intent. Write a
**thorough, multi-paragraph Summary** (section 1 of the template) and the
Intention section **before** drilling into activities, so the detail has a
frame. The summary must cover: what the process does and for whom, why it
exists, an end-to-end narrative of the happy path in plain language, the main
alternative outcomes/branches, the actors involved, and the key systems and
decisions it relies on. Aim for depth — a reader should grasp the whole process
from the summary alone.

### 3. Analyse and describe each activity in depth — the core step

Document **every** activity thoroughly using the activity template — do not
abbreviate. For each one, write a full "Purpose" paragraph and a detailed
"Detailed description" (preconditions, what happens while it runs, the data it
consumes and produces, postconditions, hand-off to the next step). The model
only says _what_ binding an activity uses; you must find and read _what that code
does_. Consult `references/element-guide.md` for the exact mapping from each
binding/element type to where its implementation lives and what to extract. In
short:

**CRITICAL: deep call-chain tracing.** Delegates, workers and expression beans
are almost never the real logic — they are thin wrappers that call injected
services, which in turn call other services, repositories, REST/SOAP clients,
message producers, etc. You **must** follow the entire call chain until you
reach the actual business logic, data access, or external system interaction.
Do not stop at the delegate. Concretely:

1. Read the delegate / worker / bean.
2. Identify every injected dependency (constructor args, `@Autowired` fields).
3. For each service method called, open that service class and read the method.
4. If that method calls further services, repositories, API clients, or utility
   classes — follow those too. Keep going until you reach:
   - **Database access** (JPA repositories, JDBC templates, native queries) →
     document which entities/tables are read or written, what criteria/filters
     are used, and the effect (create/update/delete).
   - **External HTTP / REST / SOAP calls** → document the target system, the
     endpoint/operation, request payload, expected response, and error handling.
   - **Message / event production** (Kafka, RabbitMQ, JMS, Camunda messages) →
     document the topic/queue, the payload structure, and the consumer if known.
   - **Calculations / transformations / business rules** implemented in code →
     describe the logic in business terms (what is computed, which rules or
     formulas apply, edge cases).
   - **Variable reads/writes** (`execution.getVariable` / `setVariable`,
     `runtimeService`, `taskService`) → track every process variable consumed
     and produced.
5. Document the complete picture: not "calls FooService" but what FooService
   actually *does* — the data it reads, the decisions it makes, the systems it
   talks to, the data it writes back, and the errors it can throw.

Apply this deep tracing to every activity type:

- **External task** (`type: external`, `topic: X`) → find the worker subscribing
  to topic `X`. Then trace its full call chain as described above.
- **`class` / `delegateExpression` / `expression`** → find the JavaDelegate /
  Spring bean / method. Then trace its full call chain as described above.
- **Business rule task** (`decisionRef`) → find the `.dmn`, summarise inputs,
  outputs, hit policy, and the key rules in business language.
- **Call activity** (`calledElement`) → find the called `.bpmn`; link to its doc
  and document the variable in/out mapping. Offer to document it too.
- **User task** → **locate the actual UI and describe it precisely.** Find the
  form or screen behind the task (embedded form HTML, a Camunda Forms `.form`
  JSON, or an external SPA route/component such as an Angular component) by
  searching for the form key or the task id/name. Then fill the "User interface"
  block of the template in full: where the UI lives (file/route), its type and
  layout, **every field** (label, control type, bound process variable,
  required, validation/allowed values), the buttons/actions and what each does,
  conditional show/hide logic, assignment (candidate groups/users, due dates),
  and how fields bind to process variables in and out. If the UI cannot be
  found, say so explicitly under gaps rather than guessing.
- **Script task** → include the script and explain what it computes.
- **Listeners / field injections** → find their classes and trace their full
  call chain — listeners often hold critical side effects (audit logging,
  notifications, variable preparation, external calls) that are invisible from
  the process model alone.

Search the repo by the **exact binding value** (topic / FQN / bean name /
decision key / called process key). If an implementation genuinely can't be
found, record it under "Open questions / gaps" — never invent behaviour.

### 4. Document routing, events, data, integrations

- **Gateways:** translate each outgoing sequence-flow condition into plain
  language; note the default flow. (Conditions are on the flows, matched to the
  gateway by `source`.)
- **Events & exceptions:** start triggers, boundary events (what they catch and
  the resulting path), error/terminate end events, escalation, compensation.
- **Data & variables:** build the variables table from IO mappings + what the
  implementations read/write.
- **Integrations:** external systems, queues/topics, DMN decisions, called
  processes, forms, cross-pool message flows — each with direction and purpose.
- **Operational notes:** history TTL, async save points, retries/incidents.

### 5. Assemble the document

Fill `assets/process-doc-template.md` end to end. Write for a business reader;
keep code-level detail inside the clearly-marked technical fields. Then write the
file to `doc/processes/<BpmnFilename>.md` and tell the user the path and a
one-line summary of what you documented (and list any gaps).

## Quality bar

- The Summary is extensive and lets someone who has never seen the code
  understand the whole process on its own.
- Every activity has a full "Purpose" and "Detailed description", plus an
  "Implementation analysis" that traces the **complete call chain** — not just
  the delegate but every service, repository, API client, and utility it calls —
  grounded in code that actually exists in the repo, or an explicit gap note.
- Every user task documents its actual UI: where it lives, its fields, actions
  and data bindings — or an explicit gap note if the UI could not be found.
- Every gateway path's condition is explained in plain language.
- Re-running on an unchanged repo produces a near-identical file (stable
  headings, ordered by process flow).

## Resources

- `scripts/parse_bpmn.py` — BPMN/Camunda inventory extractor (stdlib only).
- `references/element-guide.md` — element/binding → implementation lookup. Read
  it during step 3.
- `assets/process-doc-template.md` — the output skeleton. Follow it exactly.
