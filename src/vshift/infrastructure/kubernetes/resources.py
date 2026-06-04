from __future__ import annotations

from kubernetes import client  # pyright: ignore[reportMissingTypeStubs]

from vshift.application.common.settings import K8sContainerResources


def to_v1_resource_requirements(
    resources: K8sContainerResources,
) -> client.V1ResourceRequirements | None:
    requests = resources.requests.to_dict()
    limits = resources.limits.to_dict()
    if not requests and not limits:
        return None
    return client.V1ResourceRequirements(
        requests=requests or None,
        limits=limits or None,
    )
