from unittest import mock

from django.test import TestCase

from dsmr_backend.tests.mixins import CallCommandStdoutMixin
from dsmr_stats.models.settings import StatsSettings
from dsmr_stats.models.statistics import DayStatistics, HourStatistics
import dsmr_stats.services


class TestServices(CallCommandStdoutMixin, TestCase):
    """ Test 'dsmr_backend' management command. """
    fixtures = ['dsmr_stats/electricity-consumption.json', 'dsmr_stats/gas-consumption.json']

    @mock.patch('dsmr_stats.services.analyze')
    def test_analyze_service_signal_trigger(self, analyze_mock):
        """ Test incoming signal communication. """
        self.assertFalse(analyze_mock.called)
        self._call_command_stdout('dsmr_backend')
        self.assertTrue(analyze_mock.called)

    @mock.patch('dsmr_stats.services.create_hourly_statistics')
    @mock.patch('dsmr_stats.services.create_daily_statistics')
    def test_analyze_service_track_setting(self, daily_statistics_mock, hourly_statistics_mock):
        """ Test whether we respect the statistics tracking setting. """
        stats_settings = StatsSettings.get_solo()
        stats_settings.track = False
        stats_settings.save()

        self.assertFalse(daily_statistics_mock.called)
        self.assertFalse(hourly_statistics_mock.called)
        dsmr_stats.services.analyze()
        self.assertFalse(daily_statistics_mock.called)
        self.assertFalse(hourly_statistics_mock.called)

    def test_analyze_service(self):
        self.assertFalse(DayStatistics.objects.exists())
        self.assertFalse(HourStatistics.objects.exists())

        dsmr_stats.services.analyze()
        self.assertEqual(DayStatistics.objects.count(), 1)
        self.assertEqual(HourStatistics.objects.count(), 1)

        # Second run should skip first day.
        dsmr_stats.services.analyze()
        self.assertEqual(DayStatistics.objects.count(), 2)
        self.assertEqual(HourStatistics.objects.count(), 4)

        # Third run should have no effect, as our fixtures are limited to two days.
        dsmr_stats.services.analyze()
        self.assertEqual(DayStatistics.objects.count(), 2)
        self.assertEqual(HourStatistics.objects.count(), 4)

    @mock.patch('django.core.cache.cache.clear')
    def test_analyze_service_clear_cache(self, clear_cache_mock):
        dsmr_stats.services.analyze()
        self.assertTrue(clear_cache_mock.called)

    def test_flush(self):
        dsmr_stats.services.analyze()
        self.assertTrue(DayStatistics.objects.exists())
        self.assertTrue(HourStatistics.objects.exists())

        dsmr_stats.services.flush()
        self.assertFalse(DayStatistics.objects.exists())
        self.assertFalse(HourStatistics.objects.exists())

    @mock.patch('django.core.cache.cache.clear')
    def test_flush_clear_cache(self, clear_cache_mock):
        dsmr_stats.services.flush()
        self.assertTrue(clear_cache_mock.called)
