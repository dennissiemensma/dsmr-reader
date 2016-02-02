# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def migrate_settings(apps, schema_editor):
    """ NOTE: This migration is executed non-atomic, to reflect datalogger changes instantly. """
    print()
    print(' - Migrating settings...')

    # Create singleton settings record by calling solo().
    consumption_settings = apps.get_model('dsmr_consumption', 'ConsumptionSettings').objects.create()
    frontend_settings = apps.get_model('dsmr_frontend', 'FrontendSettings').objects.create()
    apps.get_model('dsmr_datalogger', 'DataloggerSettings').objects.create()  # No legacy data here.

    # Migrate all old settings among the new ones. If we have any (tests have none).
    StatsSettings = apps.get_model('dsmr_stats', 'StatsSettings')

    if not StatsSettings.objects.exists():
        # New instances above will rely on their model defaults.
        return

    old_stat_settings = StatsSettings.objects.get()

    consumption_settings.compactor_grouping_type = old_stat_settings.compactor_grouping_type
    consumption_settings.save()

    frontend_settings.reverse_dashboard_graphs = old_stat_settings.reverse_dashboard_graphs
    frontend_settings.save()


def halt_datalogger(apps, schema_editor):
    # Now disable tracking to prevent database activity while copying data. The management command
    # job running in the background will skip fetching data on the next run.
    print(' - Temporarily disabling datalogger tracking data...')
    datalogger_settings = apps.get_model('dsmr_datalogger', 'DataloggerSettings').objects.get()
    datalogger_settings.track = False
    datalogger_settings.save()


def migrate_data(apps, schema_editor):
    print()
    print(' - Migrating data...')

    MODEL_MAPPING = {
        # Old model: New model.
        apps.get_model('dsmr_stats', 'DsmrReading'): apps.get_model('dsmr_datalogger', 'DsmrReading'),
        apps.get_model('dsmr_stats', 'ElectricityConsumption'): apps.get_model('dsmr_consumption', 'ElectricityConsumption'),
        apps.get_model('dsmr_stats', 'GasConsumption'): apps.get_model('dsmr_consumption', 'GasConsumption'),
        apps.get_model('dsmr_stats', 'EnergySupplierPrice'): apps.get_model('dsmr_consumption', 'EnergySupplierPrice'),
    }

    COPY_QUERY = 'INSERT INTO %(new_table)s SELECT * FROM %(old_table)s;'

    for OldModel, NewModel in MODEL_MAPPING.items():
        old_model_count = OldModel.objects.count()
        print()
        print(' - Processing {:<32} {:>10} item(s) found in database'.format(
            OldModel.__name__, old_model_count
        ))

        if not old_model_count:
            continue

        print(' --- Copying data... (might take a while)')
        schema_editor.execute(
            COPY_QUERY % {
                "old_table": OldModel._meta.db_table,
                "new_table": NewModel._meta.db_table,
            }
        )

        new_model_count = NewModel.objects.count()
        print(' --- Count check: {} / {}'.format(old_model_count, new_model_count))
        if old_model_count != new_model_count:
            raise AssertionError(
                'Data migration count mismatch: {} != {}'.format(old_model_count, new_model_count)
            )


def resume_datalogger(apps, schema_editor):
    print()
    print(' - Allowing datalogger to resume tracking data...')
    datalogger_settings = apps.get_model('dsmr_datalogger', 'DataloggerSettings').objects.get()
    datalogger_settings.track = True
    datalogger_settings.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dsmr_stats', '0009_reverse_dashboard_graphs_setting'),

        # This will ensure both the new tables exists and we can reference those models.
        ('dsmr_consumption', '0001_initial'),
        ('dsmr_datalogger', '0001_initial'),
        ('dsmr_frontend', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_settings),
        migrations.RunPython(halt_datalogger, atomic=False),
        migrations.RunPython(migrate_data),
        migrations.RunPython(resume_datalogger, atomic=False),
    ]
