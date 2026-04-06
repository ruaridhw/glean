from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="glean")
tracer = Tracer(service="glean")
