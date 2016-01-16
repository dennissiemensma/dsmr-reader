import json

from django.test import TestCase, Client
from django.core.urlresolvers import reverse

from dsmr_stats.models.consumption import ElectricityConsumption, GasConsumption
from dsmr_stats.models.settings import StatsSettings


class TestRegression(TestCase):
    """ Regression. """
    fixtures = ['dsmr_stats/test_reverse_dashboard_graphs.json']

    def setUp(self):
        self.client = Client()

    def test_energysupplierprice_matching_query_does_not_exist(self):
        """ Test whether default sorting slices consumption as intended. """
        self.assertFalse(StatsSettings().get_solo().reverse_dashboard_graphs)
        self.assertEqual(ElectricityConsumption.objects.count(), 1)
        self.assertEqual(GasConsumption.objects.count(), 100)

        response = self.client.get(
            reverse('stats:dashboard')
        )
        self.assertIn('gas_x', response.context)

        # This will fail when the fix has been reverted.
        self.assertEqual(json.loads(response.context['gas_x'])[0], 'Sun 02:00')
