# MachineEar — Session 2: tool selection tests

Model: openai/gpt-oss-20b

These tests check tool selection and argument schemas only.
No audio analysis, document search or ticket creation is executed.
Ticket approval is simulated in the test request.

## Test 1

Request: Analyze /content/pump_id_00.wav. It is a pump recording for machine ID 00. Tell me whether an audio anomaly is detected.

Expected tool: `analyze_machine_audio`

Selected tool: `analyze_machine_audio`

Arguments:
```json
{
  "audio_path": "/content/pump_id_00.wav",
  "machine_id": "00",
  "machine_type": "pump"
}
```

Result: **PASS**

## Test 2

Request: Search the fan manuals for bearing inspection instructions and return up to 5 relevant passages.

Expected tool: `search_manuals`

Selected tool: `search_manuals`

Arguments:
```json
{
  "machine_type": "fan",
  "query": "bearing inspection instructions",
  "top_k": 5
}
```

Result: **PASS**

## Test 3

Request: I have reviewed and explicitly approve this exact ticket. Create it for machine ID 00, linked to analysis A-001. Title: Pump audio anomaly to investigate. Description: An audio anomaly was detected. Request a technician review; no specific fault is confirmed.

Expected tool: `create_maintenance_ticket`

Selected tool: `create_maintenance_ticket`

Arguments:
```json
{
  "analysis_id": "A-001",
  "description": "An audio anomaly was detected. Request a technician review; no specific fault is confirmed.",
  "machine_id": "00",
  "title": "Pump audio anomaly to investigate"
}
```

Result: **PASS**

## Summary

3/3 tests passed.

A passing test demonstrates tool selection and structurally valid
arguments, not successful execution or verified factual values.