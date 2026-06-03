# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from kubernetes import client, config

from vshift.application.common.settings import KubernetesSettings
from vshift.exception import VShiftException


def create_batch_api(settings: KubernetesSettings) -> client.BatchV1Api:
    _load_config(settings)
    return client.BatchV1Api()


def _load_config(settings: KubernetesSettings) -> None:
    try:
        if settings.in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config()
    except config.ConfigException as error:
        msg = f"failed to load kubernetes config: {error}"
        raise VShiftException(msg) from error
