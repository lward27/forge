import logging

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

NAMESPACE_PREFIX = "forge-tenant-"


def _get_clients() -> tuple[client.CoreV1Api, client.NetworkingV1Api]:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.NetworkingV1Api()


def create_tenant_namespace(
    name: str,
    resource_limits: dict,
) -> str:
    """Create a tenant namespace with quotas, limits, and network policy."""
    core_v1, networking_v1 = _get_clients()
    namespace = f"{NAMESPACE_PREFIX}{name}"

    # Namespace
    core_v1.create_namespace(
        body=client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace,
                labels={
                    "forge.lucas.engineering/tenant": name,
                    "forge.lucas.engineering/managed-by": "forge-platform",
                },
            )
        )
    )
    logger.info("Created namespace %s", namespace)

    # ResourceQuota
    core_v1.create_namespaced_resource_quota(
        namespace=namespace,
        body=client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name="tenant-quota"),
            spec=client.V1ResourceQuotaSpec(
                hard={
                    "requests.cpu": resource_limits.get("cpu", "2"),
                    "requests.memory": resource_limits.get("memory", "4Gi"),
                    "persistentvolumeclaims": "10",
                    "requests.storage": resource_limits.get("storage", "20Gi"),
                }
            ),
        ),
    )
    logger.info("Created resource quota for %s", namespace)

    # LimitRange
    core_v1.create_namespaced_limit_range(
        namespace=namespace,
        body=client.V1LimitRange(
            metadata=client.V1ObjectMeta(name="tenant-limits"),
            spec=client.V1LimitRangeSpec(
                limits=[
                    client.V1LimitRangeItem(
                        type="Container",
                        default={"cpu": "500m", "memory": "256Mi"},
                        default_request={"cpu": "100m", "memory": "128Mi"},
                    )
                ]
            ),
        ),
    )
    logger.info("Created limit range for %s", namespace)

    # NetworkPolicy — isolate tenants from each other
    networking_v1.create_namespaced_network_policy(
        namespace=namespace,
        body=client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(name="tenant-isolation"),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),
                policy_types=["Ingress", "Egress"],
                ingress=[
                    client.V1NetworkPolicyIngressRule(
                        _from=[
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={
                                        "kubernetes.io/metadata.name": namespace
                                    }
                                )
                            ),
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={
                                        "kubernetes.io/metadata.name": "forge-platform"
                                    }
                                )
                            ),
                        ]
                    )
                ],
                egress=[client.V1NetworkPolicyEgressRule()],
            ),
        ),
    )
    logger.info("Created network policy for %s", namespace)

    return namespace


def delete_tenant_namespace(namespace: str) -> None:
    """Delete a tenant namespace and all its contents."""
    core_v1, _ = _get_clients()
    try:
        core_v1.delete_namespace(name=namespace)
        logger.info("Deleted namespace %s", namespace)
    except ApiException as e:
        if e.status == 404:
            logger.warning("Namespace %s already deleted", namespace)
        else:
            raise


def namespace_exists(namespace: str) -> bool:
    """Check if a namespace exists."""
    core_v1, _ = _get_clients()
    try:
        core_v1.read_namespace(name=namespace)
        return True
    except ApiException as e:
        if e.status == 404:
            return False
        raise


def create_secret(
    namespace: str,
    name: str,
    data: dict[str, str],
    labels: dict[str, str] | None = None,
) -> None:
    """Create a K8s Secret in the given namespace."""
    core_v1, _ = _get_clients()
    core_v1.create_namespaced_secret(
        namespace=namespace,
        body=client.V1Secret(
            metadata=client.V1ObjectMeta(name=name, labels=labels),
            type="Opaque",
            string_data=data,
        ),
    )
    logger.info("Created secret %s in %s", name, namespace)


def delete_secret(namespace: str, name: str) -> None:
    """Delete a K8s Secret from the given namespace."""
    core_v1, _ = _get_clients()
    try:
        core_v1.delete_namespaced_secret(name=name, namespace=namespace)
        logger.info("Deleted secret %s from %s", name, namespace)
    except ApiException as e:
        if e.status == 404:
            logger.warning("Secret %s in %s already deleted", name, namespace)
        else:
            raise
