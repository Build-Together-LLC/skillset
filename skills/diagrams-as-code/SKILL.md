---
name: diagrams-as-code
description: Generate professional architecture diagrams (AWS, GCP, Azure, Kubernetes, ERPNext, network, block diagrams) as PNG images using Python code. Use when user asks to create architecture diagrams, AWS diagrams, cloud infrastructure diagrams, system design diagrams, block diagrams, ERPNext implementation diagrams, network diagrams, or any visual representation of a tech/system architecture. Triggers on: "create a diagram", "draw architecture", "make an AWS diagram", "show the system design", "block diagram for X".
---

# Diagrams as Code

Generate architecture diagrams using the Python `diagrams` library. Output is a PNG file with real cloud/tech provider icons.

## Dependencies
- `diagrams` Python package (`pip3 install diagrams --break-system-packages`)
- `graphviz` system package (`brew install graphviz`)

## Workflow

1. Write a Python script using the diagrams library
2. Run it with `python3 script.py`
3. Output PNG is saved to `/home/frappe/.openclaw/workspace/diagrams/`
4. Share the image with the user via the `message` tool

## Quick Reference

```python
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2, Lambda, ECS
from diagrams.aws.database import RDS, Dynamodb, ElastiCache
from diagrams.aws.network import ELB, CloudFront, Route53, VPC, APIGateway
from diagrams.aws.storage import S3
from diagrams.aws.security import IAM, Cognito, WAF
from diagrams.aws.integration import SQS, SNS, Eventbridge
from diagrams.aws.analytics import Kinesis, Glue, Athena
from diagrams.aws.management import Cloudwatch, Cloudformation
from diagrams.aws.devtools import Codepipeline, Codecommit
from diagrams.gcp.compute import GCE, GKE, Functions
from diagrams.gcp.database import SQL, Firestore
from diagrams.gcp.network import LoadBalancing
from diagrams.azure.compute import VM, FunctionApps
from diagrams.azure.database import SQLDatabases
from diagrams.k8s.compute import Pod, Deployment
from diagrams.k8s.network import Service, Ingress
from diagrams.onprem.database import MySQL, PostgreSQL
from diagrams.onprem.queue import Kafka, RabbitMQ
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.network import Nginx
from diagrams.programming.language import Python, Java, NodeJS
from diagrams.generic.compute import Rack
from diagrams.generic.network import Firewall
from diagrams.generic.storage import Storage
from diagrams.generic.database import SQL as GenSQL
from diagrams.saas.chat import Slack
```

## Diagram Template

```python
from diagrams import Diagram, Cluster, Edge
# import required nodes

output_path = "/home/frappe/.openclaw/workspace/diagrams/diagram_name"

with Diagram("Title", filename=output_path, show=False, direction="LR"):
    # direction: LR (left-right), TB (top-bottom), RL, BT
    
    with Cluster("Group Name"):
        node1 = EC2("Web Server")
        node2 = RDS("Database")
    
    node1 >> node2  # arrow from node1 to node2
    node1 - node2   # line (no arrow)
    node1 << node2  # reverse arrow
    
    # Labelled edges:
    node1 >> Edge(label="HTTPS") >> node2
    
    # Colored edges:
    node1 >> Edge(color="red", style="dashed") >> node2
```

## ERPNext / Business Diagrams

For ERPNext or non-cloud diagrams, use generic nodes:

```python
from diagrams.generic.compute import Rack
from diagrams.generic.network import Firewall
from diagrams.generic.storage import Storage
from diagrams.generic.database import SQL
from diagrams.onprem.client import User, Users
from diagrams.onprem.network import Nginx
from diagrams.programming.framework import Django, React
```

## Output

Always save to `/home/frappe/.openclaw/workspace/diagrams/` (create dir if needed).
Always set `show=False` to prevent GUI popup.
After generating, use `message` tool with `media` or `filePath` to send the PNG to the user.

## Common Patterns

### Multi-tier Web App (AWS)
```python
with Diagram("3-Tier Web App", filename=output_path, show=False):
    dns = Route53("DNS")
    cdn = CloudFront("CDN")
    with Cluster("Public Subnet"):
        lb = ELB("Load Balancer")
    with Cluster("Private Subnet"):
        web = [EC2("Web 1"), EC2("Web 2")]
    with Cluster("Data Layer"):
        db = RDS("Primary DB")
        cache = ElastiCache("Cache")
    dns >> cdn >> lb >> web >> db
    web >> cache
```

### ERPNext Implementation Architecture
```python
with Diagram("ERPNext Architecture", filename=output_path, show=False, direction="TB"):
    with Cluster("Client Layer"):
        users = Users("End Users")
        mobile = User("Mobile App")
    with Cluster("Application Layer"):
        nginx = Nginx("Nginx")
        frappe = Django("Frappe/ERPNext")
    with Cluster("Data Layer"):
        db = MySQL("MariaDB")
        cache = Redis("Redis")
        storage = Storage("File Storage")
    users >> nginx >> frappe
    mobile >> nginx
    frappe >> db
    frappe >> cache
    frappe >> storage
```
