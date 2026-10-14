"""
lambda_handler.py
=================
AWS Lambda entry point for the Telemedicine Workload Offloader.

This file wraps the existing pure-Python routing pipeline so that it can
be deployed as an AWS Lambda function behind API Gateway — with NO changes
to the core business logic in src/.

AWS Architecture (on migration)
--------------------------------
  IoMT Sensors (MQTT)
        |
  AWS IoT Core
        |
  API Gateway (POST /ingest)
        |
  This Lambda function
    |-- Step 1: predict_latency()       <- SageMaker endpoint (future swap)
    |-- Step 2: route_decision()        <- stays pure Python
    |-- Step 3: edge_handle / cloud_handle
    |       |-- edge:  SNS.publish() + DynamoDB.put_item() + S3.put_object()
    |       |-- cloud: DynamoDB.put_item() + S3.put_object()
    |-- Step 4: CloudWatch log_event()

Usage (local test)
------------------
  python lambda_handler.py

AWS Deployment
--------------
  zip -r lambda_package.zip src/ requirements.txt lambda_handler.py
  aws lambda create-function \
      --function-name TelemedicineOffloader \
      --runtime python3.11 \
      --handler lambda_handler.lambda_handler \
      --zip-file fileb://lambda_package.zip \
      --role arn:aws:iam::<ACCOUNT_ID>:role/<LAMBDA_ROLE>

Environment variables required in Lambda
-----------------------------------------
  (none for the local simulation — add S3_BUCKET, DYNAMODB_TABLE,
   SNS_TOPIC_ARN, SAGEMAKER_ENDPOINT_NAME when migrating each component)
"""

import json
import sys
import os

# Allow Lambda to find the src package when deployed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.prediction.predict_service  import predict_latency
from src.decision.router             import route_decision
from src.execution.edge_node         import handle_event as edge_handle
from src.execution.cloud_node        import handle_event as cloud_handle
from src.execution.logger            import log_event
from src.execution.storage           import init_db

# Initialise DB once during cold start (Lambda re-uses the container)
init_db()


def lambda_handler(event, context):
    """
    AWS Lambda handler for the /ingest pipeline.

    Parameters
    ----------
    event : dict
        API Gateway proxy event.  The request body (JSON string) is at
        event["body"].  Expected body schema:
          {
            "window": [<20 TelemetryRecord dicts>],
            "patient_criticality_score": float,   # 0-10
            "current_cloud_cost_index":  float    # 0-1
          }

    context : LambdaContext
        AWS Lambda context object (runtime info).

    Returns
    -------
    dict
        API Gateway proxy response with statusCode and JSON body.
    """
    # ── Parse request body ───────────────────────────────────────────────────
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            # Direct invocation (e.g., local test or Step Functions)
            body = event
    except (json.JSONDecodeError, KeyError) as e:
        return _error_response(400, f"Invalid JSON body: {e}")

    window     = body.get("window", [])
    criticality = body.get("patient_criticality_score")
    cost_index  = body.get("current_cloud_cost_index")

    # ── Validate required fields ─────────────────────────────────────────────
    if not window or len(window) != 20:
        return _error_response(400, f"'window' must contain exactly 20 records, got {len(window)}")
    if criticality is None or not (0.0 <= criticality <= 10.0):
        return _error_response(400, "'patient_criticality_score' must be a float in [0, 10]")
    if cost_index is None or not (0.0 <= cost_index <= 1.0):
        return _error_response(400, "'current_cloud_cost_index' must be a float in [0, 1]")

    # ── Step 1: Predict latency ──────────────────────────────────────────────
    # TODO AWS MIGRATION: swap predict_latency() call with:
    #   import boto3
    #   sm = boto3.client('sagemaker-runtime')
    #   resp = sm.invoke_endpoint(
    #       EndpointName=os.environ['SAGEMAKER_ENDPOINT_NAME'],
    #       ContentType='application/json',
    #       Body=json.dumps({"window": window})
    #   )
    #   prediction = json.loads(resp['Body'].read())
    try:
        prediction = predict_latency(window)
    except Exception as e:
        log_event("PREDICTION_ERROR", {"error": str(e)})
        return _error_response(500, f"Prediction error: {e}")

    device_id         = prediction["device_id"]
    predicted_latency = prediction["predicted_latency_ms"]

    # ── Step 2: Routing decision ─────────────────────────────────────────────
    try:
        decision = route_decision(
            device_id=device_id,
            patient_criticality_score=criticality,
            predicted_latency_ms=predicted_latency,
            current_cloud_cost_index=cost_index,
        )
    except Exception as e:
        log_event("ROUTING_ERROR", {"error": str(e)})
        return _error_response(500, f"Routing error: {e}")

    # ── Step 3: Build event dict and execute routing ─────────────────────────
    last_reading = window[-1]
    exec_event = {
        "device_id":                 device_id,
        "timestamp":                 last_reading.get("timestamp", ""),
        "routing_decision":          decision["routing_decision"],
        "reason":                    decision["reason"],
        "patient_criticality_score": criticality,
        "predicted_latency_ms":      predicted_latency,
        "raw_payload":               last_reading,
    }

    if decision["routing_decision"] == "EDGE":
        exec_result = edge_handle(exec_event)
    else:
        exec_result = cloud_handle(exec_event)

    # ── Step 4: Audit log ────────────────────────────────────────────────────
    log_event("PIPELINE_COMPLETE", {
        **exec_event,
        "network_degradation_risk": prediction["network_degradation_risk"],
        "cloud_score":              decision.get("cloud_score"),
        "edge_score":               decision.get("edge_score"),
        "execution_status":         exec_result.get("status"),
    })

    # ── Step 5: Return combined response ────────────────────────────────────
    response_body = {
        "device_id":                device_id,
        "predicted_latency_ms":     predicted_latency,
        "network_degradation_risk": prediction["network_degradation_risk"],
        "routing_decision":         decision["routing_decision"],
        "reason":                   decision["reason"],
        "cloud_score":              decision.get("cloud_score"),
        "edge_score":               decision.get("edge_score"),
        "execution_status":         exec_result.get("status", "unknown"),
        "alerted":                  exec_result.get("alerted", False),
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(response_body),
    }


def _error_response(status_code, message):
    """Helper to build a standardised Lambda error response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import random

    dummy_window = [
        {
            "timestamp":           f"2026-09-22T10:00:{i:02d}Z",
            "device_id":           "ECG-101",
            "bandwidth_mbps":      random.uniform(30, 100),
            "packet_loss_pct":     random.uniform(0, 2),
            "jitter_ms":           random.uniform(2, 15),
            "signal_strength_dbm": random.uniform(-80, -50),
            "current_latency_ms":  random.uniform(10, 50),
        }
        for i in range(20)
    ]

    test_event = {
        "body": json.dumps({
            "window":                    dummy_window,
            "patient_criticality_score": 7.5,
            "current_cloud_cost_index":  0.4,
        })
    }

    print("[lambda_handler] Local invocation test:")
    result = lambda_handler(test_event, None)
    print(f"  Status code : {result['statusCode']}")
    body = json.loads(result["body"])
    for k, v in body.items():
        print(f"  {k}: {v}")
