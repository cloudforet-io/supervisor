CACHES = {}

CONNECTORS = {
    "SpaceConnector": {
        "backend": "spaceone.core.connector.space_connector:SpaceConnector",
        "endpoints": {
            "plugin": "grpc://plugin:50051",
            "repository": "grpc://repository:50051",
        },
    },
    "PluginConnector": {
        # 'endpoint': {
        #    'v1': 'grpc://plugin:50051'
        # }
    },
    "RepositoryConnector": {
        # 'endpoint': {
        #    'v1': 'grpc://repository:50051'
        # }
    },
    "DockerConnector": {
        # "start_port": 50060,
        # "end_port": 50090
    },
    "KubernetesConnector": {
        # "start_port": 50060,
        # "end_port": 50090,
        # "namespace": "supervisor",
        # "service_account": "service_account_name",
        # "env": [
        #     {"name": "HTTP_PROXY", "value": "http://***"},
        #     {...}
        # ],
        # "resources": {
        #     "requests": {
        #         "memory": "64Mi",
        #         "cpu": "250m"
        #     },
        #     "limits": {
        #         "memory": "128Mi",
        #         "cpu": "500m"
        #     }
        # },
        # "volumes": [
        # ],
        # "volume_mounts": [
        # ],
        # "headless": True,
        # "replica": {
        #    "inventory.collector": 4
        # },
        # "nodeSelector": {
        #     "Category": "supervisor"
        # }
    },
}

HANDLERS = {
    # # TODO: add system key authentication handler
    # 'authentication': [{
    #     'backend': 'spaceone.core.handler.authentication_handler.AuthenticationGRPCHandler',
    #     'uri': 'grpc://identity:50051/v1/Domain/get_public_key'
    # }],
    # 'authorization': [{
    #    'backend': 'spaceone.core.handler.authorization_handler.AuthorizationGRPCHandler',
    #    'uri': 'grpc://identity:50051/v1/Authorization/verify'
    # }],
    # 'event': []
}

# Define Queue options
QUEUES = {
    # 'default_q': {
    #     'backend': 'spaceone.core.queue.redis_queue.RedisQueue',
    #     'host': 'redis',
    #     'port': 6379,
    #     'channel': 'supervisor_queue'
    # }
}

# Define scheduler options
SCHEDULERS = {
    # 'publish': {
    #     'backend': 'spaceone.supervisor.scheduler.publish_scheduler.PublishScheduler',
    #     'queue': 'default_q',
    #     'interval': 30
    # },
    # 'sync': {
    #     'backend': 'spaceone.supervisor.scheduler.sync_scheduler.SyncScheduler',
    #     'queue': 'default_q',
    #     'interval': 120
    # }
}

# This value should be global unique
# Update at config.yml
NAME = ""
HOSTNAME = ""
BACKEND = "DockerConnector"
# PLUGIN = {
#     "backend": "DockerConnector",
#     "start_port": 50060,
#     "end_port": 50090
# }

TAGS = {}
LABELS = {}

# This is admin user token for this domain
# If you want remote TOKEN for security, use TOKEN_INFO instead of TOKEN
TOKEN = ""
TOKEN_INFO = {}

# This is for unittest
ENDPOINTS = {}
LOG = {}
