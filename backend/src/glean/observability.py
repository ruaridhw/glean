from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(service="glean")
tracer = Tracer(service="glean")
# CloudWatch metrics for the async stack (sessions started, completed and failed, and wall time).
# Queue consumers call `metrics.flush_metrics()` in a finally block; the API Lambda only adds none.
metrics = Metrics(service="glean", namespace="Glean")
