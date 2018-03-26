from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.utils.translation import ugettext as _, ugettext_lazy

from templated_email import send_templated_mail


class Command(BaseCommand):
    help = ugettext_lazy("Send an email to all onadata users")

    def add_arguments(self, parser):
        parser.add_argument("-m", "--message", dest="message", default=False)

    def handle(self, *args, **options):
        message = options.get('message')
        verbosity = options.get('verbosity')
        get_template('templated_email/notice.email')
        if not message:
            raise CommandError(_('message must be included in options'))
        # get all users
        users = User.objects.all()
        for user in users:
            name = user.get_full_name()
            if not name or len(name) == 0:
                name = user.email
            if verbosity:
                self.stdout.write(_(
                    'Emailing name: %(name)s, email: %(email)s')
                    % {'name': name, 'email': user.email})
            # send each email separately so users cannot see eachother
            send_templated_mail(
                template_name='notice',
                from_email='noreply@ona.io',
                recipient_list=[user.email],
                context={
                    'username': user.username,
                    'full_name': name,
                    'message': message
                }, )
