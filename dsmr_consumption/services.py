from datetime import time
from decimal import Decimal, ROUND_UP
import pytz

from django.conf import settings
from django.utils import timezone
from django.db import transaction, connection
from django.db.models import Avg, Max

from dsmr_consumption.models.consumption import ElectricityConsumption, GasConsumption
from dsmr_consumption.models.settings import ConsumptionSettings
from dsmr_consumption.models.energysupplier import EnergySupplierPrice
from dsmr_stats.models.note import Note
from dsmr_datalogger.models.reading import DsmrReading
from dsmr_weather.models.reading import TemperatureReading
import dsmr_consumption.signals


def compact_all():
    """ Compacts all unprocessed readings, capped by a max to prevent hanging backend. """
    for current_reading in DsmrReading.objects.unprocessed()[0:128]:
        compact(dsmr_reading=current_reading)


@transaction.atomic
def compact(dsmr_reading):
    """
    Compacts/converts DSMR readings to consumption data. Optionally groups electricity by minute.
    """
    grouping_type = ConsumptionSettings.get_solo().compactor_grouping_type

    # Electricity should be unique, because it's the reading with the lowest interval anyway.
    if grouping_type == ConsumptionSettings.COMPACTOR_GROUPING_BY_READING:
        consumption = ElectricityConsumption.objects.create(
            read_at=dsmr_reading.timestamp,
            delivered_1=dsmr_reading.electricity_delivered_1,
            returned_1=dsmr_reading.electricity_returned_1,
            delivered_2=dsmr_reading.electricity_delivered_2,
            returned_2=dsmr_reading.electricity_returned_2,
            tariff=dsmr_reading.electricity_tariff,
            currently_delivered=dsmr_reading.electricity_currently_delivered,
            currently_returned=dsmr_reading.electricity_currently_returned,
        )
        dsmr_consumption.signals.electricity_consumption_created.send_robust(
            None, instance=consumption
        )
    # Grouping by minute requires some distinction and history checking.
    else:
        minute_start = timezone.datetime.combine(
            dsmr_reading.timestamp.date(),
            time(hour=dsmr_reading.timestamp.hour, minute=dsmr_reading.timestamp.minute),
        ).replace(tzinfo=pytz.UTC)
        minute_end = minute_start + timezone.timedelta(minutes=1)

        # Postpone when current minute hasn't passed yet.
        if timezone.now() <= minute_end:
            return

        # We might have six readings per minute, so there is a chance we already parsed it.
        if not ElectricityConsumption.objects.filter(read_at=minute_end).exists():
            grouped_reading = DsmrReading.objects.filter(
                timestamp__gte=minute_start, timestamp__lt=minute_end
            ).aggregate(
                avg_delivered=Avg('electricity_currently_delivered'),
                avg_returned=Avg('electricity_currently_returned'),
                max_delivered_1=Max('electricity_delivered_1'),
                max_delivered_2=Max('electricity_delivered_2'),
                max_returned_1=Max('electricity_returned_1'),
                max_returned_2=Max('electricity_returned_2')
            )

            # This instance is the average/max and combined result.
            consumption = ElectricityConsumption.objects.create(
                read_at=minute_end,
                delivered_1=grouped_reading['max_delivered_1'],
                returned_1=grouped_reading['max_returned_1'],
                delivered_2=grouped_reading['max_delivered_2'],
                returned_2=grouped_reading['max_returned_2'],
                tariff=dsmr_reading.electricity_tariff,
                currently_delivered=grouped_reading['avg_delivered'],
                currently_returned=grouped_reading['avg_returned'],
            )
            dsmr_consumption.signals.electricity_consumption_created.send_robust(
                None, instance=consumption
            )

    # Gas however only get read every hour, so we should check
    # for any duplicates, as they WILL exist.
    gas_consumption_exists = GasConsumption.objects.filter(
        read_at=dsmr_reading.extra_device_timestamp
    ).exists()

    if not gas_consumption_exists:
        # DSMR does not expose current gas rate, so we have to calculate
        # it ourselves, relative to the previous gas consumption, if any.
        try:
            previous_gas_consumption = GasConsumption.objects.get(
                read_at=dsmr_reading.extra_device_timestamp - timezone.timedelta(hours=1)
            )
        except GasConsumption.DoesNotExist:
            gas_diff = 0
        else:
            gas_diff = dsmr_reading.extra_device_delivered - previous_gas_consumption.delivered

        consumption = GasConsumption.objects.create(
            read_at=dsmr_reading.extra_device_timestamp,
            delivered=dsmr_reading.extra_device_delivered,
            currently_delivered=gas_diff
        )
        dsmr_consumption.signals.gas_consumption_created.send_robust(None, instance=consumption)

    dsmr_reading.processed = True
    dsmr_reading.save(update_fields=['processed'])


def day_consumption(day):
    consumption = {
        'day': day
    }
    day_start = timezone.datetime(
        year=day.year,
        month=day.month,
        day=day.day,
        tzinfo=settings.LOCAL_TIME_ZONE
    )
    day_end = day_start + timezone.timedelta(days=1)

    # This WILL fail when we either have no prices at all or conflicting ranges.
    try:
        consumption['daily_energy_price'] = EnergySupplierPrice.objects.by_date(
            target_date=day
        )
    except EnergySupplierPrice.DoesNotExist:
        # Default to zero prices.
        consumption['daily_energy_price'] = EnergySupplierPrice()

    electricity_readings = ElectricityConsumption.objects.filter(
        read_at__gte=day_start, read_at__lt=day_end,
    ).order_by('read_at')
    gas_readings = GasConsumption.objects.filter(
        read_at__gte=day_start, read_at__lt=day_end,
    ).order_by('read_at')

    if not electricity_readings.exists() or not gas_readings.exists():
        raise LookupError("No readings found for: {}".format(day))

    electricity_reading_count = electricity_readings.count()
    gas_reading_count = gas_readings.count()

    first_reading = electricity_readings[0]
    last_reading = electricity_readings[electricity_reading_count - 1]
    consumption['electricity1'] = last_reading.delivered_1 - first_reading.delivered_1
    consumption['electricity2'] = last_reading.delivered_2 - first_reading.delivered_2
    consumption['electricity1_start'] = first_reading.delivered_1
    consumption['electricity1_end'] = last_reading.delivered_1
    consumption['electricity2_start'] = first_reading.delivered_2
    consumption['electricity2_end'] = last_reading.delivered_2
    consumption['electricity1_returned'] = last_reading.returned_1 - first_reading.returned_1
    consumption['electricity2_returned'] = last_reading.returned_2 - first_reading.returned_2
    consumption['electricity1_returned_start'] = first_reading.returned_1
    consumption['electricity1_returned_end'] = last_reading.returned_1
    consumption['electricity2_returned_start'] = first_reading.returned_2
    consumption['electricity2_returned_end'] = last_reading.returned_2
    consumption['electricity1_unit_price'] = consumption['daily_energy_price'].electricity_1_price
    consumption['electricity2_unit_price'] = consumption['daily_energy_price'].electricity_2_price
    consumption['electricity1_cost'] = round_price(
        consumption['electricity1'] * consumption['electricity1_unit_price']
    )
    consumption['electricity2_cost'] = round_price(
        consumption['electricity2'] * consumption['electricity2_unit_price']
    )

    first_reading = gas_readings[0]
    last_reading = gas_readings[gas_reading_count - 1]
    consumption['gas'] = last_reading.delivered - first_reading.delivered
    consumption['gas_start'] = first_reading.delivered
    consumption['gas_end'] = last_reading.delivered
    consumption['gas_unit_price'] = consumption['daily_energy_price'].gas_price
    consumption['gas_cost'] = round_price(
        consumption['gas'] * consumption['gas_unit_price']
    )

    consumption['total_cost'] = round_price(
        consumption['electricity1_cost'] + consumption['electricity2_cost'] + consumption['gas_cost']
    )
    consumption['notes'] = Note.objects.filter(day=day).values_list('description', flat=True)

    temperature_readings = TemperatureReading.objects.filter(
        read_at__gte=day_start, read_at__lt=day_end,
    ).order_by('read_at')
    consumption['average_temperature'] = temperature_readings.aggregate(
        avg_temperature=Avg('degrees_celcius'),
    )['avg_temperature'] or 0

    return consumption


def round_price(decimal_price):
    """ Round the price to two decimals. """
    return decimal_price.quantize(Decimal('.01'), rounding=ROUND_UP)


def average_electricity_by_hour():
    """ Calculates the average consumption by hour. Measured over all consumption data. """
    SQL_EXTRA = {
        # Ugly engine check, but still beter than iterating over a hundred thousand items in code.
        'postgresql': "date_part('hour', read_at)",
        'mysql': "extract(hour from read_at)",
    }

    try:
        sql_extra = SQL_EXTRA[connection.vendor]
    except KeyError:
        raise NotImplementedError(connection.vendor)

    return ElectricityConsumption.objects.extra({
        'hour': sql_extra
    }).values('hour').order_by('hour').annotate(
        avg_delivered=Avg('currently_delivered')
    )
