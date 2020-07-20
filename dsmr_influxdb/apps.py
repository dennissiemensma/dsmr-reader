import logging

from django.apps import AppConfig
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from influxdb import InfluxDBClient

from dsmr_backend.signals import initialize_persistent_client, run_persistent_client, terminate_persistent_client
from dsmr_datalogger.signals import dsmr_reading_created


logger = logging.getLogger('dsmrreader')


class DsmrInfluxdbConfig(AppConfig):
    name = 'dsmr_influxdb'
    verbose_name = _('InfluxDB')


@receiver(dsmr_reading_created)
def _on_dsmrreading_created_signal(instance, **kwargs):
    import dsmr_influxdb.services

    try:
        dsmr_influxdb.services.publish_dsmr_reading(instance=instance)
    except Exception as error:
        logger.error('publish_dsmr_reading() failed: %s', error)


@receiver(initialize_persistent_client)
def on_initialize_persistent_client(**kwargs):
    import dsmr_influxdb.services
    return dsmr_influxdb.services.initialize_client()


@receiver(run_persistent_client)
def on_run_persistent_client(client, **kwargs):
    if not isinstance(client, InfluxDBClient):
        return

    import dsmr_influxdb.services
    dsmr_influxdb.services.run(client)


@receiver(terminate_persistent_client)
def on_terminate_persistent_client(client, **kwargs):
    if not isinstance(client, InfluxDBClient):
        return

    client.close()
