Supervisor Service

Supervisor is plugin deployment system like aws-ec2, aws-cloud-service.

For example,
If the inventory asks endpoint of aws-ec2-plugin collector, plugin service returns the real endpoint of aws-ec2-plugin collector.
In this process, supervisor deploy aws-ec2-plugin collector, if it does not exist.

# Deployment

Supervisor should be deployed as standalone mode, since supervisor have to deploy plugins like aws-ec2, google-oauth2.

## Docker mode

Supervisor deploys plugins as docker.
In this mode, supervisor communicates with docker API.

## Kubernetes mode

Supervisor deploys plugins as K8S Pod.
In this mode, supervisor communicates with K8S API.
