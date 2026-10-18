#!/usr/bin/env python3
"""
Generate architecture diagrams using the Python diagrams library.
Usage: python3 generate_diagram.py <diagram_type> [output_name]

Types: aws-webapp, erpnext, kafka-pipeline, microservices
"""
import sys
import os

os.makedirs("/home/frappe/.openclaw/workspace/diagrams", exist_ok=True)

diagram_type = sys.argv[1] if len(sys.argv) > 1 else "aws-webapp"
output_name = sys.argv[2] if len(sys.argv) > 2 else diagram_type
output_path = f"/home/frappe/.openclaw/workspace/diagrams/{output_name}"


def aws_webapp():
    from diagrams import Diagram, Cluster, Edge
    from diagrams.aws.compute import EC2
    from diagrams.aws.database import RDS, ElastiCache
    from diagrams.aws.network import ELB, CloudFront, Route53
    from diagrams.aws.storage import S3

    with Diagram("AWS Web Application", filename=output_path, show=False, direction="LR"):
        dns = Route53("DNS")
        cdn = CloudFront("CDN")
        assets = S3("Static Assets")
        with Cluster("Application Tier"):
            lb = ELB("Load Balancer")
            web = [EC2("App Server 1"), EC2("App Server 2")]
        with Cluster("Data Tier"):
            db = RDS("PostgreSQL")
            cache = ElastiCache("Redis Cache")

        dns >> cdn >> lb >> web
        cdn >> assets
        web >> db
        web >> cache


def erpnext_arch():
    from diagrams import Diagram, Cluster, Edge
    from diagrams.onprem.client import User, Users
    from diagrams.onprem.network import Nginx
    from diagrams.onprem.database import MySQL
    from diagrams.onprem.inmemory import Redis
    from diagrams.generic.storage import Storage
    from diagrams.onprem.queue import Celery

    with Diagram("ERPNext Architecture", filename=output_path, show=False, direction="TB"):
        with Cluster("Users"):
            desktop = Users("Desktop Users")
            mobile = User("Mobile Users")

        with Cluster("Web Layer"):
            nginx = Nginx("Nginx Proxy")

        with Cluster("Application Layer"):
            from diagrams.programming.framework import Django
            frappe = Django("Frappe/ERPNext")
            worker = Celery("Background Worker")

        with Cluster("Data Layer"):
            db = MySQL("MariaDB")
            cache = Redis("Redis")
            files = Storage("File Storage")

        desktop >> nginx >> frappe
        mobile >> nginx
        frappe >> db
        frappe >> cache
        frappe >> files
        frappe >> worker
        worker >> db


def kafka_pipeline():
    from diagrams import Diagram, Cluster, Edge
    from diagrams.onprem.queue import Kafka
    from diagrams.onprem.database import Oracle, MySQL
    from diagrams.aws.analytics import Kinesis
    from diagrams.onprem.monitoring import Grafana, Prometheus
    from diagrams.generic.database import SQL

    with Diagram("Oracle GG + Kafka Pipeline", filename=output_path, show=False, direction="LR"):
        with Cluster("Source"):
            oracle_src = Oracle("Oracle DB\n(Source)")

        with Cluster("CDC Layer"):
            goldengate = SQL("Oracle\nGoldenGate")

        with Cluster("Streaming Layer"):
            kafka = Kafka("Apache Kafka")

        with Cluster("Target"):
            oracle_tgt = Oracle("Oracle DB\n(Target)")
            mysql = MySQL("MySQL\n(Analytics)")

        with Cluster("Monitoring"):
            prometheus = Prometheus("Prometheus")
            grafana = Grafana("Grafana")

        oracle_src >> goldengate >> kafka
        kafka >> oracle_tgt
        kafka >> mysql
        kafka >> prometheus >> grafana


def microservices():
    from diagrams import Diagram, Cluster, Edge
    from diagrams.aws.network import APIGateway, ELB
    from diagrams.aws.compute import Lambda, ECS
    from diagrams.aws.database import RDS, Dynamodb
    from diagrams.aws.integration import SQS, SNS
    from diagrams.aws.security import Cognito

    with Diagram("Microservices Architecture", filename=output_path, show=False, direction="TB"):
        auth = Cognito("Auth")
        gateway = APIGateway("API Gateway")

        with Cluster("Services"):
            svc1 = ECS("User Service")
            svc2 = ECS("Order Service")
            svc3 = Lambda("Notification\nService")

        with Cluster("Data"):
            db1 = RDS("Users DB")
            db2 = Dynamodb("Orders DB")

        queue = SQS("Event Queue")
        notify = SNS("Notifications")

        auth >> gateway
        gateway >> svc1 >> db1
        gateway >> svc2 >> db2
        svc2 >> queue >> svc3 >> notify


diagrams = {
    "aws-webapp": aws_webapp,
    "erpnext": erpnext_arch,
    "kafka-pipeline": kafka_pipeline,
    "microservices": microservices,
}

if diagram_type in diagrams:
    diagrams[diagram_type]()
    print(f"✅ Diagram saved: {output_path}.png")
else:
    print(f"Unknown type: {diagram_type}. Available: {', '.join(diagrams.keys())}")
    sys.exit(1)
