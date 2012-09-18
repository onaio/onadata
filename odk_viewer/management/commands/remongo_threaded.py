from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from optparse import make_option
from django.utils.translation import ugettext_lazy, ugettext as _
from odk_viewer.models import ParsedInstance
import time
import threading
import Queue


class Command(BaseCommand):
    help = ugettext_lazy("Insert all existing parsed instances into MongoDB")
    option_list = BaseCommand.option_list + (
        make_option('--batchsize',
            type='int',
            default=100,
            help=ugettext_lazy("Number of records to process per query")),
        make_option('-u', '--username',
            help=ugettext_lazy("Username of the form user")),
        make_option('-i', '--id_string',
            help=ugettext_lazy("id string of the form")),
        make_option('-t', '--threads',
            type='int',
            default=5,
            help=ugettext_lazy("Number of threads"))
    )

    def handle(self, *args, **kwargs):
        ids = None
        # check for username AND id_string - if one exists so must the other
        if (kwargs.get('username') and not kwargs.get('id_string')) or (not\
            kwargs.get('username') and kwargs.get('id_string')):
            raise CommandError("username and idstring must either both be specified or neither")
        elif kwargs.get('username') and kwargs.get('id_string'):
            from odk_logger.models import XForm, Instance
            xform = XForm.objects.get(user__username=kwargs.get('username'),
                id_string=kwargs.get('id_string'))
            ids = [i.pk for i in Instance.objects.filter(xform=xform)]
        # num records per run
        batchsize = kwargs['batchsize']
        num_threads = kwargs['threads']
        start = 0;
        filter_queryset = ParsedInstance.objects.all()
        # instance ids for when we have a username and id_string
        if ids:
            filter_queryset = ParsedInstance.objects.filter(instance__in=ids)
        # total number of records
        record_count = filter_queryset.count()

        # flag to stop queue processing
        queueEmpty = False

        # assign queue lock
        lock = threading.Lock()

        # create work queue
        workQueue = Queue.Queue()

        # put batches in the queue
        lock.acquire()
        while start < record_count:
            workQueue.put(start)
            start = start + batchsize
        lock.release()

        # Create new threads
        threads = []
        for i in range(num_threads):
            threads.append(RemongoThread(batchsize=batchsize,
                filter_queryset=filter_queryset, queue=workQueue))

        # Start new Threads
        for thread in threads:
            thread.start()

        try:
            # Wait for queue to empty
            while not workQueue.empty():
                time.sleep(1)
            # Wait for all threads to complete
            workQueue.join()
        except (KeyboardInterrupt, SystemExit):
            for t in threads:
                t.request_stop()


class RemongoThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.queue = kwargs["queue"]
        self.filter_queryset = kwargs["filter_queryset"]
        self.batchsize = kwargs["batchsize"]
        self._stop_requested = False
        super(RemongoThread, self).__init__()
    def request_stop(self):
      print "Stop requested, waiting for thread %s to exit..." % self.name
      self._stop_requested = True
    def run(self):
        lock = threading.Lock()
        i = 0
        while not self.queue.empty() and not self._stop_requested:
            try:
                start = self.queue.get()
            except Queue.Empty:
                break
            else:
                end = start + self.batchsize
                queryset = self.filter_queryset.order_by('pk')[start:end]
                for pi in queryset.iterator():
                    lock.acquire()
                    pi.update_mongo()
                    i += 1
                    lock.release()
                    if i % 1000 == 0:
                        print 'Updated %d from %s records, flushing MongoDB...' %\
                            (i, self.name)
                        lock.acquire()
                        settings._MONGO_CONNECTION.admin.command({'fsync': 1})
                        lock.release()
                print "Updated %d records from %s" % (i, self.name)
                self.queue.task_done()
                time.sleep(1)
