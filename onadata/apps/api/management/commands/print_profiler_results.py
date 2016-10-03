from hotshot import stats
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = '<log_file>'

    def handle(self, *args, **options):
        self.stdout.write("Show profiler log file output..", ending='\n')

        _stats = stats.load(args[0])
        _stats.sort_stats('time', 'calls')
        _stats.print_stats(20)
