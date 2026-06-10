# BPMN / Camunda element guide

How to read each element from the parser output and, crucially, **where to find
its implementation in the codebase**. Read this when documenting the activity
catalogue. Targets Camunda Platform 7.

## Implementation bindings → where the code lives

The parser puts these under each node's `implementation` object.

### Service tasks

| Binding (`implementation.*`) | Meaning | Where to find the code |
|---|---|---|
| `type: external` + `topic: X` | External task — handled by an out-of-process worker subscribing to topic `X` | Search the codebase for the topic string `"X"`: Spring `@ExternalTaskSubscription("X")` on a `@Component` implementing `ExternalTaskHandler`; or `externalTaskClient.subscribe("X")`. **Then trace the full call chain** (see below). |
| `class: com.foo.Bar` | JavaDelegate implementation | Open `com/foo/Bar.java`; read `execute(DelegateExecution)`. **Then trace the full call chain** (see below). |
| `delegateExpression: ${beanName}` | Spring bean implementing `JavaDelegate` | Find the bean: `@Component("beanName")` or `@Named` / a `@Bean` method named `beanName`; read its `execute(...)`. **Then trace the full call chain** (see below). |
| `expression: ${bean.method(...)}` | Method expression | Find `bean` and the method. **Then trace the full call chain** (see below). |
| `resultVariable` | Process variable that receives the expression/decision result | Note it in Inputs/Outputs |

#### Deep call-chain tracing (mandatory for every service/external/expression binding)

Delegates, workers, and expression beans are almost never the real logic — they
are thin entry points that delegate to injected services. **You must follow the
entire call chain** from the delegate through every service, repository, API
client, and utility it calls, until you reach the actual business operations:

1. **Read the delegate/worker/bean** — note constructor-injected or `@Autowired`
   dependencies.
2. **Open each called service method** and read what it does.
3. **Keep following** if that method calls further services, repositories, REST
   clients, message producers, or utilities. Stop only when you reach a
   terminal operation:
   - **Database access** (JPA repository, JDBC template, native query) →
     document which entities/tables are read or written, the criteria/filters,
     and the effect (create / update / delete / query).
   - **External HTTP / REST / SOAP call** → document the target system,
     endpoint/operation, request payload, expected response, and error handling.
   - **Message / event production** (Kafka, RabbitMQ, JMS, Camunda message
     correlation) → document the topic/queue, payload structure, and consumer
     if identifiable.
   - **Business logic / calculations** → describe what is computed, which rules
     or formulas apply, and edge cases.
4. **Track every process variable** read (`getVariable`) and written
   (`setVariable`) across the entire chain — not just in the delegate itself.
5. **Document errors**: which exceptions can be thrown, which are mapped to
   `BpmnError` (and with what error code), and which propagate as incidents.

### Business rule tasks (DMN)

| Binding | Meaning | Where to find |
|---|---|---|
| `decisionRef: key` | References a DMN decision by key | Find `key.dmn` (search for `id="key"` or `decisionId`/`<decision id="key"`). Summarise: inputs, output(s), **hit policy** (UNIQUE/FIRST/COLLECT…), and the notable rules in business terms |
| `decisionRefBinding` / `decisionRefVersion` | latest / deployment / version | Note which version is bound |
| `mapDecisionResult` + `resultVariable` | How the DMN result maps to a variable | Document the resulting variable shape |

### User tasks

| Binding | Meaning | Where to find |
|---|---|---|
| `formKey` | Task form / UI | See the detailed UI-location guide below |
| `assignee` / `candidateUsers` / `candidateGroups` | Who works the task | Document the role/group in business terms |
| `dueDate` / `followUpDate` / `priority` | SLA hints | Surface as operational/SLA notes |

**Locating and describing the UI (do this thoroughly for every user task).**
The goal is to describe the screen the user actually sees, field by field.

Resolve the `formKey` to a real artifact:

- `embedded:app:forms/x.html` or `embedded:deployment:x.html` → an embedded
  AngularJS/HTML form. Search for `x.html` under `src/main/webapp`,
  `src/main/resources/static`, or the Tasklist app assets. Read the markup:
  each `<input>/<select>/<textarea>` with `cam-variable-name` binds to a process
  variable; note `cam-variable-type`, `required`, `ng-if`/`ng-show` (conditional
  visibility) and any `<button>`/`cam-...` directives.
- `camunda-forms:` / `camunda-forms:deployment:x.form` → a Camunda Forms JSON
  (`.form`) file. Search for `x.form`. Each component has `key` (the bound
  variable), `label`, `type` (textfield/number/select/checkbox/datetime/…),
  `validate` (required, min/max, pattern), and `values` for selects. Document
  every component as a field.
- Generated forms (`formFields` in the parser output) → document each field's
  `id`, `label`, `type` directly from the model.
- External / custom UI (no embedded form, or a custom Tasklist, or a separate
  SPA) → the task is rendered by a frontend app. Search the frontend (e.g. an
  **Angular** project: components, routes, templates) for the form key, the task
  definition key, or the task name. Identify the component/route, then read its
  template to enumerate fields, validators, buttons and the service calls that
  complete the task (e.g. a REST call to `/task/{id}/complete` with variables).

For each user task, fill the template's **User interface** block: the UI file/
route, layout/sections, a table of every field (label, control, bound variable,
required, validation/options, notes), the buttons/actions and their effect
(which variable/outcome they set, whether they complete/claim/save the task),
conditional behaviour, assignment/access, and the in/out variable binding. If
the UI genuinely cannot be located, record it under "Open questions / gaps".

### Call activities (sub-processes)

| Binding | Meaning | Where to find |
|---|---|---|
| `calledElement: key` | Calls another BPMN process by key | Find the `.bpmn` whose process `id="key"`. Link to its doc (or offer to document it). Document the in/out variable mappings |
| `variableMappingClass` / `variableMappingDelegateExpression` | Custom variable mapping | Find that class/bean |

### Script tasks

`implementation.script` + `scriptFormat` — include the script and explain what
it computes and which variables it sets. Inline business logic worth flagging
for review.

## Extension elements (parser keys on the node)

- `ioMapping.inputs/outputs` — local input/output variable mapping. Tells you
  exactly which variables flow into and out of the activity.
- `listeners` — `executionListener` (events: start/end/take) and `taskListener`
  (events: create/assignment/complete). Each has `class`/`expression`/
  `delegateExpression`; find and summarise — listeners often hold side effects
  (notifications, audit, variable prep) that aren't obvious from the task itself.
- `fieldInjections` — configuration passed into a delegate; document the values.
- `formFields` — embedded form fields (id/label/type).

## Events

- **Start event:** none (manually/API started), `messageEventDefinition`
  (correlated by message name — find `runtimeService.correlateMessage("name")`
  or `@EventListener`), `timerEventDefinition` (scheduled — note the cron/ISO),
  `signalEventDefinition`, `conditionalEventDefinition`.
- **Boundary event** (`attachedToRef`, `cancelActivity`): interrupting vs.
  non-interrupting handling attached to an activity. Error boundary → catches a
  thrown `BpmnError`/error code (find where it's thrown); timer boundary →
  timeout/escalation path; message boundary → external interruption.
- **End event:** plain (normal completion) vs. `errorEventDefinition` (ends with
  a business error, often caught by a parent call activity), `terminateEvent`
  (kills the instance), `escalation`, `compensation`.
- The parser resolves `messageRef`/`signalRef`/`errorRef` to their **names** via
  `*RefName` — use those names in the documentation.

## Gateways (routing)

- **exclusiveGateway** — one path taken; document each outgoing `sequenceFlow`
  condition (`${…}`) translated to plain language, plus the `default` flow.
- **parallelGateway** — fork/join; all paths run; note what must complete to join.
- **inclusiveGateway** — one or more paths by condition.
- **eventBasedGateway** — waits for whichever event (message/timer) fires first.

Conditions live on the **sequence flows** (`sequenceFlows[].condition`), not the
gateway — map them back to the gateway by `source`.

## Multi-instance

`multiInstance`: `sequential` vs parallel, `collection` + `elementVariable`
(loops over a collection), `loopCardinality`, `completionCondition`. Document as
"runs once per <item> in <collection>".

## Lanes & pools

- `lanes` map nodes to responsible roles/departments (`nodeRefs`) — use for the
  "who does what" framing.
- `collaboration.participants` are pools (often separate systems/organisations);
  `messageFlows` are cross-pool messages — document as external interactions.

## Async & operations

- `asyncBefore`/`asyncAfter` mark transaction/save points (where the job
  executor takes over) — relevant for retries and incident handling.
- Process `historyTimeToLive`, `versionTag` — operational metadata for section 10.

## Finding implementations efficiently

1. Prefer exact-string search for the binding value (topic, bean name, class
   FQN, decision key, called process key) across the repo.
2. For `${...}` expressions, extract the bean/method name and search for the
   Spring component or `@Bean` definition.
3. If an implementation can't be found, record it under "Open questions / gaps"
   rather than inventing behaviour.

