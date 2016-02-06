from django.views.generic.base import TemplateView
from django.conf import settings
from django.utils import timezone

from dsmr_datalogger.models.reading import DsmrReading
from dsmr_consumption.models.energysupplier import EnergySupplierPrice


class Statistics(TemplateView):
    template_name = 'dsmr_frontend/statistics.html'

    def get_context_data(self, **kwargs):
        context_data = super(Statistics, self).get_context_data(**kwargs)
        today = timezone.now().astimezone(settings.LOCAL_TIME_ZONE).date()
        context_data['latest_reading'] = DsmrReading.objects.all().order_by('-pk')[0]
        context_data['first_reading'] = DsmrReading.objects.all().order_by('pk')[0]
        context_data['total_reading_count'] = DsmrReading.objects.count()

        try:
            context_data['energy_prices'] = EnergySupplierPrice.objects.by_date(today)
        except EnergySupplierPrice.DoesNotExist:
            pass

        return context_data
