import xml.etree.ElementTree as ET

NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI"}


def test_bpmn_files_are_consistent():
    for f in ("bpmn/current_state.bpmn", "bpmn/future_state.bpmn"):
        root = ET.parse(f).getroot()
        proc = root.find("bpmn:process", NS)
        ids = {e.get("id") for e in proc if not e.tag.endswith("sequenceFlow")}
        flows = proc.findall("bpmn:sequenceFlow", NS)
        assert flows and all(fl.get("sourceRef") in ids and fl.get("targetRef") in ids for fl in flows)
        shapes = {s.get("bpmnElement") for s in root.iter(f"{{{NS['bpmndi']}}}BPMNShape")}
        assert ids == shapes                       # every element is drawn
        assert len(proc.findall("bpmn:startEvent", NS)) == 1
