#!/usr/bin/env python3
"""Extract a structured inventory from a BPMN 2.0 / Camunda process file.

Why this exists: reading raw BPMN XML by eye is unreliable — namespaces vary
(bpmn:, bpmn2:, none), implementation bindings hide in Camunda extension
attributes, and conditions/listeners are buried. This script pulls everything
into clean JSON so the documentation step works from facts, not guesses.

Pure stdlib (xml.etree) — no install needed.

Usage:
    python parse_bpmn.py path/to/process.bpmn            # JSON to stdout
    python parse_bpmn.py path/to/process.bpmn --out x.json

The JSON contains, per process: metadata, lanes, every flow node with its
Camunda implementation bindings (class/delegate/expression/external topic/
DMN ref/called element/form/listeners/IO mappings/multi-instance/event
definitions), all sequence flows with conditions, and data objects.
Collaboration pools/message flows and root-level message/signal/error/
escalation definitions are included too.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET

FLOW_NODE_TAGS = {
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
    "boundaryEvent", "task", "userTask", "serviceTask", "scriptTask", "sendTask",
    "receiveTask", "manualTask", "businessRuleTask", "callActivity", "subProcess",
    "transaction", "adHocSubProcess", "exclusiveGateway", "parallelGateway",
    "inclusiveGateway", "eventBasedGateway", "complexGateway",
}

GATEWAY_TAGS = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
}
EVENT_TAGS = {
    "startEvent", "endEvent", "intermediateCatchEvent",
    "intermediateThrowEvent", "boundaryEvent",
}
SUBPROCESS_TAGS = {"subProcess", "transaction", "adHocSubProcess"}

# Camunda binding attributes worth surfacing on a node.
BINDING_ATTRS = (
    "class", "delegateExpression", "expression", "resultVariable", "type",
    "topic", "decisionRef", "decisionRefBinding", "decisionRefVersion",
    "mapDecisionResult", "formKey", "formRef", "assignee", "candidateUsers",
    "candidateGroups", "dueDate", "followUpDate", "priority", "calledElement",
    "calledElementBinding", "calledElementVersion", "variableMappingClass",
    "variableMappingDelegateExpression", "scriptFormat", "modelerTemplate",
)


def local(tag: str) -> str:
    """Strip the XML namespace, leaving the local element/attribute name."""
    return tag.rsplit("}", 1)[-1]


def attr(el: ET.Element, name: str) -> str | None:
    """Get an attribute by local name, ignoring namespace prefix."""
    for k, v in el.attrib.items():
        if local(k) == name:
            return v
    return None


def kids(el: ET.Element, name: str | None = None):
    for c in el:
        if name is None or local(c.tag) == name:
            yield c


def child(el: ET.Element, name: str):
    return next(kids(el, name), None)


def child_text(el: ET.Element, name: str) -> str | None:
    c = child(el, name)
    if c is not None and c.text and c.text.strip():
        return c.text.strip()
    return None


def documentation(el: ET.Element) -> str | None:
    return child_text(el, "documentation")


# --------------------------------------------------------------------------- #
#  Extension elements (Camunda)                                               #
# --------------------------------------------------------------------------- #
def parse_io(ext: ET.Element) -> dict | None:
    io = child(ext, "inputOutput")
    if io is None:
        return None
    out: dict = {"inputs": [], "outputs": []}
    for p in kids(io):
        lt = local(p.tag)
        if lt not in ("inputParameter", "outputParameter"):
            continue
        entry = {"name": attr(p, "name")}
        scr = child(p, "script")
        if scr is not None:
            entry["value"] = f"<script:{attr(scr, 'scriptFormat')}> {(scr.text or '').strip()[:200]}"
        elif list(p):  # nested list/map
            entry["value"] = "<complex>"
        elif p.text and p.text.strip():
            entry["value"] = p.text.strip()
        (out["inputs"] if lt == "inputParameter" else out["outputs"]).append(entry)
    return out


def parse_listeners(ext: ET.Element) -> list[dict]:
    res = []
    for c in kids(ext):
        lt = local(c.tag)
        if lt not in ("executionListener", "taskListener"):
            continue
        res.append({
            "kind": lt,
            "event": attr(c, "event"),
            "class": attr(c, "class"),
            "expression": attr(c, "expression"),
            "delegateExpression": attr(c, "delegateExpression"),
        })
    return res


def parse_fields(ext: ET.Element) -> list[dict]:
    res = []
    for f in kids(ext, "field"):
        res.append({
            "name": attr(f, "name"),
            "value": child_text(f, "string") or attr(f, "stringValue"),
            "expression": child_text(f, "expression"),
        })
    return res


def parse_form_fields(ext: ET.Element) -> list[dict]:
    fd = child(ext, "formData")
    if fd is None:
        return []
    return [{"id": attr(ff, "id"), "label": attr(ff, "label"), "type": attr(ff, "type")}
            for ff in kids(fd, "formField")]


# --------------------------------------------------------------------------- #
#  Event definitions / multi-instance                                         #
# --------------------------------------------------------------------------- #
def parse_event_defs(el: ET.Element, refs: dict) -> list[dict]:
    defs = []
    for c in kids(el):
        lt = local(c.tag)
        if not lt.endswith("EventDefinition"):
            continue
        d: dict = {"kind": lt}
        for ref in ("messageRef", "signalRef", "errorRef", "escalationRef"):
            v = attr(c, ref)
            if v:
                d[ref] = v
                d[ref + "Name"] = refs.get(v)
        if lt == "timerEventDefinition":
            for tk in ("timeDuration", "timeCycle", "timeDate"):
                tv = child_text(c, tk)
                if tv:
                    d["timer"] = {tk: tv}
        if lt == "conditionalEventDefinition":
            d["condition"] = child_text(c, "condition")
        defs.append(d)
    return defs


def parse_multi_instance(el: ET.Element) -> dict | None:
    mi = child(el, "multiInstanceLoopCharacteristics")
    if mi is None:
        return None
    return {
        "sequential": attr(mi, "isSequential") == "true",
        "loopCardinality": child_text(mi, "loopCardinality"),
        "collection": attr(mi, "collection"),
        "elementVariable": attr(mi, "elementVariable"),
        "completionCondition": child_text(mi, "completionCondition"),
    }


# --------------------------------------------------------------------------- #
#  Node parsing                                                               #
# --------------------------------------------------------------------------- #
def parse_node(el: ET.Element, parent_id: str | None, refs: dict) -> dict:
    t = local(el.tag)
    node: dict = {
        "id": attr(el, "id"),
        "type": t,
        "name": attr(el, "name"),
        "parent": parent_id,
        "category": ("gateway" if t in GATEWAY_TAGS else
                     "event" if t in EVENT_TAGS else
                     "subprocess" if t in SUBPROCESS_TAGS else "activity"),
        "documentation": documentation(el),
    }
    for a in ("asyncBefore", "asyncAfter", "jobPriority", "default"):
        v = attr(el, a)
        if v is not None:
            node[a] = v
    if t == "boundaryEvent":
        node["attachedToRef"] = attr(el, "attachedToRef")
        node["cancelActivity"] = attr(el, "cancelActivity") != "false"

    bindings = {a: attr(el, a) for a in BINDING_ATTRS if attr(el, a) is not None}
    scr = child_text(el, "script")
    if scr:
        bindings["script"] = scr
    if bindings:
        node["implementation"] = bindings

    ext = child(el, "extensionElements")
    if ext is not None:
        io = parse_io(ext)
        if io and (io["inputs"] or io["outputs"]):
            node["ioMapping"] = io
        listeners = parse_listeners(ext)
        if listeners:
            node["listeners"] = listeners
        fields = parse_fields(ext)
        if fields:
            node["fieldInjections"] = fields
        ff = parse_form_fields(ext)
        if ff:
            node["formFields"] = ff

    ev = parse_event_defs(el, refs)
    if ev:
        node["eventDefinitions"] = ev
    mi = parse_multi_instance(el)
    if mi:
        node["multiInstance"] = mi
    return node


def collect_nodes(container: ET.Element, refs: dict, parent_id: str | None,
                  nodes: list, flows: list, data: list):
    for el in kids(container):
        lt = local(el.tag)
        if lt in FLOW_NODE_TAGS:
            nodes.append(parse_node(el, parent_id, refs))
            if lt in SUBPROCESS_TAGS:
                collect_nodes(el, refs, attr(el, "id"), nodes, flows, data)
        elif lt == "sequenceFlow":
            flows.append({
                "id": attr(el, "id"),
                "name": attr(el, "name"),
                "source": attr(el, "sourceRef"),
                "target": attr(el, "targetRef"),
                "condition": child_text(el, "conditionExpression"),
            })
        elif lt in ("dataObject", "dataObjectReference", "dataStoreReference"):
            data.append({"id": attr(el, "id"), "name": attr(el, "name"), "type": lt})


# --------------------------------------------------------------------------- #
#  Lanes                                                                      #
# --------------------------------------------------------------------------- #
def parse_lanes(process: ET.Element) -> list[dict]:
    lanes = []
    for laneset in kids(process, "laneSet"):
        for lane in kids(laneset, "lane"):
            lanes.append({
                "id": attr(lane, "id"),
                "name": attr(lane, "name"),
                "nodeRefs": [c.text.strip() for c in kids(lane, "flowNodeRef")
                             if c.text and c.text.strip()],
            })
    return lanes


# --------------------------------------------------------------------------- #
#  Top level                                                                  #
# --------------------------------------------------------------------------- #
def parse_file(path: str) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()

    refs: dict = {}
    for tagname in ("message", "signal", "error", "escalation"):
        for el in root.iter():
            if local(el.tag) == tagname:
                refs[attr(el, "id")] = attr(el, "name")

    result: dict = {"file": path, "processes": [],
                    "definitions": {"messages": [], "signals": [],
                                    "errors": [], "escalations": []}}
    for tagname, key in (("message", "messages"), ("signal", "signals"),
                         ("error", "errors"), ("escalation", "escalations")):
        for el in root.iter():
            if local(el.tag) == tagname:
                result["definitions"][key].append(
                    {"id": attr(el, "id"), "name": attr(el, "name"),
                     "errorCode": attr(el, "errorCode")})

    # Collaboration (pools + message flows)
    for el in root.iter():
        if local(el.tag) == "collaboration":
            result["collaboration"] = {
                "participants": [{"id": attr(p, "id"), "name": attr(p, "name"),
                                  "processRef": attr(p, "processRef")}
                                 for p in kids(el, "participant")],
                "messageFlows": [{"id": attr(m, "id"), "name": attr(m, "name"),
                                  "source": attr(m, "sourceRef"),
                                  "target": attr(m, "targetRef")}
                                 for m in kids(el, "messageFlow")],
            }

    for el in root.iter():
        if local(el.tag) != "process":
            continue
        nodes: list = []
        flows: list = []
        data: list = []
        collect_nodes(el, refs, None, nodes, flows, data)
        proc = {
            "id": attr(el, "id"),
            "name": attr(el, "name"),
            "isExecutable": attr(el, "isExecutable"),
            "versionTag": attr(el, "versionTag"),
            "historyTimeToLive": attr(el, "historyTimeToLive"),
            "documentation": documentation(el),
            "lanes": parse_lanes(el),
            "nodes": nodes,
            "sequenceFlows": flows,
            "dataObjects": data,
        }
        result["processes"].append(proc)

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract a BPMN/Camunda inventory as JSON.")
    ap.add_argument("bpmn", help="Path to the .bpmn file")
    ap.add_argument("--out", help="Write JSON here instead of stdout")
    args = ap.parse_args()

    try:
        data = parse_file(args.bpmn)
    except ET.ParseError as e:
        print(f"ERROR: could not parse XML: {e}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.bpmn}", file=sys.stderr)
        sys.exit(2)

    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
